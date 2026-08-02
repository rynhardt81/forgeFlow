"""Unit tests for self-skip reporting in the preflight runner.

A generated job can self-skip (exit 0) when an infra dependency is absent —
the pg-reachability guard does exactly this when the compose stack is down.
Exit 0 is deliberate so an absent local stack never blocks a push, but it makes
a skip indistinguishable from a pass unless the runner surfaces it. These tests
pin that: a skipped job must never render as a plain green.

Run with:

    python3 -m unittest tests.preflight.test_preflight_skip_reporting

or directly:

    python3 tests/preflight/test_preflight_skip_reporting.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "preflight"))

from preflight import (  # noqa: E402
    JOB_SKIP_MARKER,
    JobResult,
    PreflightReport,
    _extract_skip_reason,
    exit_code_for,
    format_human,
    run_one_script,
)
from hook_installer import SENTINEL, _hooks_dir, refresh_if_stale  # noqa: E402
from script_generator import (  # noqa: E402
    GENERATOR_CONTRACT,
    STEP_ALWAYS,
    STEP_NEVER,
    STEP_NORMAL,
    STEP_ON_FAILURE,
    STEP_OVER_RUN,
    classify_condition,
    compute_drift,
    destructive_commands,
    dropped_gating_steps,
    render_script,
    write_lockfile,
)
from script_generator import JOB_SKIP_MARKER as EMITTER_MARKER  # noqa: E402
from workflow_parser import Job, Step  # noqa: E402

# The exact line the generated pg guard writes before `exit 0`.
PG_SKIP = (
    f"{JOB_SKIP_MARKER}postgres not reachable (compose stack down) — skipping "
    "test.sh (DB-dependent job). Bring the stack up (docker compose up -d) to "
    "run it."
)


def _job(name: str, exit_code: int = 0, stderr: str = "") -> JobResult:
    """Build a JobResult the way run_one_script does — same derivation path."""
    return JobResult(
        name=name,
        exit_code=exit_code,
        duration_seconds=0.1,
        stdout_tail="",
        stderr_tail=stderr,
        skip_reason=_extract_skip_reason(stderr) if exit_code == 0 else None,
    )


def _report(*jobs: JobResult) -> PreflightReport:
    return PreflightReport(
        project_root="/tmp/x",
        workflows_dir="/tmp/x/.github/workflows",
        out_dir="/tmp/x/.forge/preflight",
        drift_detected=False,
        drift_changed=[],
        drift_new=[],
        drift_removed=[],
        jobs_run=list(jobs),
    )


class TestSkipDetection(unittest.TestCase):
    def test_skip_reason_extracted_from_stderr(self):
        job = _job("test", stderr=PG_SKIP)
        self.assertIsNotNone(job.skip_reason)
        self.assertIn("postgres not reachable", job.skip_reason)

    def test_marker_prefix_is_stripped(self):
        self.assertFalse(_job("test", stderr=PG_SKIP).skip_reason.startswith("SKIP:"))

    def test_ran_job_has_no_skip_reason(self):
        self.assertIsNone(_job("test", stderr="some warning\n").skip_reason)

    def test_skip_found_among_other_stderr_lines(self):
        stderr = f"[notice] pip is out of date\n{PG_SKIP}\ntrailing noise\n"
        self.assertIsNotNone(_job("test", stderr=stderr).skip_reason)

    def test_failing_job_is_never_reported_as_skipped(self):
        # A red job mentioning SKIP must still read as a failure, not a skip.
        self.assertIsNone(_job("test", exit_code=1, stderr=PG_SKIP).skip_reason)

    def test_empty_stderr_is_not_a_skip(self):
        self.assertIsNone(_job("test").skip_reason)


class TestSkipReporting(unittest.TestCase):
    def test_skipped_job_does_not_render_as_passed(self):
        body = format_human(_report(_job("test", stderr=PG_SKIP)))
        self.assertNotIn("✅ test", body)
        self.assertIn("SKIPPED", body)

    def test_skip_reason_is_shown(self):
        body = format_human(_report(_job("test", stderr=PG_SKIP)))
        self.assertIn("postgres not reachable", body)

    def test_safe_to_push_is_withheld_when_a_job_skipped(self):
        # The regression this guards: a skipped DB job reporting a clean green.
        body = format_human(_report(_job("lint"), _job("test", stderr=PG_SKIP)))
        self.assertNotIn("all gating jobs passed — safe to push", body)
        self.assertIn("did NOT run", body)

    def test_clean_run_still_says_safe_to_push(self):
        body = format_human(_report(_job("lint"), _job("test")))
        self.assertIn("all gating jobs passed — safe to push", body)
        self.assertNotIn("SKIPPED", body)

    def test_skip_keeps_the_run_green(self):
        # Skips must stay non-blocking — exit 0 semantics are the whole point.
        report = _report(_job("lint"), _job("test", stderr=PG_SKIP))
        self.assertTrue(report.all_green)
        self.assertEqual([j.name for j in report.jobs_skipped], ["test"])

    def test_json_payload_carries_skips(self):
        payload = _report(_job("test", stderr=PG_SKIP)).to_dict()
        self.assertEqual(payload["jobs_skipped"], ["test"])
        self.assertIn("postgres not reachable", payload["jobs_run"][0]["skip_reason"])


class TestExitCode(unittest.TestCase):
    """The machine contract. Consumers read this, never the printed summary."""

    def test_skip_is_five_not_zero(self):
        # 0 would leave /create-pr --preflight and the pre-push hook seeing the
        # same plain green this whole feature exists to remove.
        self.assertEqual(exit_code_for(_report(_job("lint"), _job("test", stderr=PG_SKIP))), 5)

    def test_clean_run_is_zero(self):
        self.assertEqual(exit_code_for(_report(_job("lint"), _job("test"))), 0)

    def test_failure_outranks_skip(self):
        report = _report(_job("lint", exit_code=1), _job("test", stderr=PG_SKIP))
        self.assertEqual(exit_code_for(report), 3)

    def test_drift_outranks_skip(self):
        report = _report(_job("test", stderr=PG_SKIP))
        report.drift_detected = True
        self.assertEqual(exit_code_for(report), 2)


class TestTailTruncation(unittest.TestCase):
    def test_marker_survives_a_noisy_job(self):
        # skip_reason is derived from FULL stderr; deriving it from stderr_tail
        # (last 40 lines) would lose the marker here and silently report green.
        noisy = PG_SKIP + "\n" + "\n".join(f"line {i}" for i in range(45))
        self.assertIsNotNone(_extract_skip_reason(noisy))


class TestEmitterRunnerContract(unittest.TestCase):
    """The generator emits the marker; the runner sniffs for it. One literal.

    These two live in different modules, and nothing but this test links them.
    A reworded echo (`SKIP:` without the space, `[SKIP]`, an emoji) would break
    detection silently and restore the exact bug this feature fixes: a job that
    never ran reported as a plain green.
    """

    def test_runner_and_emitter_share_one_literal(self):
        self.assertIs(JOB_SKIP_MARKER, EMITTER_MARKER)

    def test_generated_guard_emits_the_marker_the_runner_detects(self):
        job = Job(
            name="test",
            file="ci.yml",
            runs_on="ubuntu-latest",
            env={"DATABASE_URL": "postgresql://a:b@localhost:5440/t"},
        )
        body = render_script(job, Path("/tmp/x/.github/workflows/ci.yml"))

        skip_echo = next(
            line for line in body.splitlines() if JOB_SKIP_MARKER in line
        )
        # The guard must announce on stderr — the runner reads stderr only, so a
        # guard echoing to stdout is undetected and renders as a plain green.
        self.assertIn(">&2", skip_echo)

        # End-to-end: feed the emitted line back through the runner's detector.
        emitted = skip_echo.split('echo "', 1)[1].rsplit('"', 1)[0]
        self.assertIsNotNone(_job("test", stderr=emitted).skip_reason)

    def test_guard_exits_zero_so_a_skip_never_blocks_a_push(self):
        job = Job(
            name="test",
            file="ci.yml",
            runs_on="ubuntu-latest",
            env={"DATABASE_URL": "postgresql://a:b@localhost:5440/t"},
        )
        body = render_script(job, Path("/tmp/x/.github/workflows/ci.yml"))
        guard = body[body.index(JOB_SKIP_MARKER):]
        self.assertIn("exit 0", guard.split("fi", 1)[0])


class TestNonUtf8JobOutput(unittest.TestCase):
    """A job emitting invalid UTF-8 must be reported red, not crash the runner.

    Real case: gitleaks truncates a finding mid-character and writes a lone
    0xFA to stdout. Before `errors="replace"`, the decode raised inside
    subprocess.run and the entire preflight run died with a traceback.
    """

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.root = Path(self._tmp)
        self.addCleanup(shutil.rmtree, self._tmp, True)

    def test_invalid_utf8_on_stdout_does_not_raise(self):
        script = self.root / "noisy.sh"
        script.write_text("#!/usr/bin/env bash\nprintf 'be\\xfagin\\n'\nexit 1\n")
        result = run_one_script(script, cwd=self.root)
        self.assertEqual(result.exit_code, 1)
        self.assertIn("gin", result.stdout_tail)

    def test_invalid_utf8_does_not_break_skip_detection(self):
        script = self.root / "skippy.sh"
        script.write_text(
            "#!/usr/bin/env bash\n"
            "printf 'junk\\xfa\\n'\n"
            f'echo "{JOB_SKIP_MARKER}dependency absent" >&2\n'
            "exit 0\n"
        )
        result = run_one_script(script, cwd=self.root)
        self.assertEqual(result.skip_reason, "dependency absent")


class TestMigrationOfExistingInstalls(unittest.TestCase):
    """Both halves of the upgrade path, each of which silently re-broke the fix.

    Generated scripts and the installed hook are BOTH snapshots taken at some
    earlier version, and neither is refreshed by pulling new framework code.
    """

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.root = Path(self._tmp)
        self.addCleanup(shutil.rmtree, self._tmp, True)

    def test_lockfile_records_the_contract(self):
        wf = self.root / ".github" / "workflows"
        wf.mkdir(parents=True)
        (wf / "ci.yml").write_text("name: ci\n")
        lock = self.root / "drift.lock"
        write_lockfile(wf, lock)
        self.assertEqual(
            json.loads(lock.read_text())["generator_contract"], GENERATOR_CONTRACT
        )

    def test_old_contract_is_detected_as_stale(self):
        wf = self.root / ".github" / "workflows"
        wf.mkdir(parents=True)
        (wf / "ci.yml").write_text("name: ci\n")
        lock = self.root / "drift.lock"
        write_lockfile(wf, lock)
        data = json.loads(lock.read_text())
        data["generator_contract"] = GENERATOR_CONTRACT - 1
        lock.write_text(json.dumps(data))
        drift = compute_drift(wf, lock)
        self.assertTrue(drift.contract_stale)
        # Must NOT masquerade as workflow drift — that path blocks the run and
        # tells the user to fix something they did not break.
        self.assertFalse(drift.has_drift)

    def test_prehistoric_lockfile_without_the_key_is_stale(self):
        wf = self.root / ".github" / "workflows"
        wf.mkdir(parents=True)
        (wf / "ci.yml").write_text("name: ci\n")
        lock = self.root / "drift.lock"
        lock.write_text(json.dumps({"workflow_hashes": {}}))
        self.assertTrue(compute_drift(wf, lock).contract_stale)

    def _install_hook(self, body: str) -> Path:
        hooks = self.root / ".git" / "hooks"
        hooks.mkdir(parents=True)
        hook = hooks / "pre-push"
        hook.write_text(body)
        return hook

    def test_stale_forge_hook_is_refreshed(self):
        hook = self._install_hook("#!/bin/sh\n# Sentinel: FORGE_PREFLIGHT_HOOK_V1\nexit 0\n")
        self.assertTrue(refresh_if_stale(self.root))
        self.assertIn(SENTINEL, hook.read_text())

    def test_current_forge_hook_is_left_alone(self):
        self._install_hook(f"#!/bin/sh\n# Sentinel: {SENTINEL}\nexit 0\n")
        self.assertFalse(refresh_if_stale(self.root))

    def test_hand_written_hook_is_never_touched(self):
        body = "#!/bin/sh\n# my own hook\nexit 0\n"
        hook = self._install_hook(body)
        self.assertFalse(refresh_if_stale(self.root))
        self.assertEqual(hook.read_text(), body)

    def test_absent_hook_is_not_an_error(self):
        (self.root / ".git" / "hooks").mkdir(parents=True)
        self.assertFalse(refresh_if_stale(self.root))


class TestHooksDirResolution(unittest.TestCase):
    """Where the hook actually lives, asked of git rather than assumed.

    In a linked worktree `<root>/.git` is a FILE pointing at
    `<common>/.git/worktrees/<name>`, so `<root>/.git/hooks` never exists. The
    naive join reports "no hook installed", a V1 hook survives the migration,
    and its catch-all failure branch blocks the push on the new exit code 5 —
    the opposite of the non-blocking guarantee.
    """

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.root = Path(self._tmp)
        self.addCleanup(shutil.rmtree, self._tmp, True)

    def _git(self, *args, cwd=None):
        subprocess.run(["git", *args], cwd=cwd or self.root, check=True,
                       capture_output=True, text=True)

    def _repo(self) -> Path:
        main = self.root / "main"
        main.mkdir()
        self._git("init", "-q", cwd=main)
        self._git("config", "user.email", "t@example.com", cwd=main)
        self._git("config", "user.name", "t", cwd=main)
        (main / "a.txt").write_text("x")
        self._git("add", "-A", cwd=main)
        self._git("commit", "-qm", "init", cwd=main)
        return main

    def test_plain_checkout_is_unchanged(self):
        main = self._repo()
        self.assertEqual(_hooks_dir(main), main / ".git" / "hooks")

    def test_linked_worktree_resolves_to_the_shared_hooks_dir(self):
        main = self._repo()
        linked = self.root / "linked"
        self._git("worktree", "add", "-q", str(linked), "-b", "feature", cwd=main)
        # The premise: the naive join finds nothing here.
        self.assertFalse((linked / ".git").is_dir())
        # resolve() both sides: on macOS the temp dir is /var, a symlink to
        # /private/var, and git answers with the resolved form.
        self.assertEqual(
            _hooks_dir(linked).resolve(), (main / ".git" / "hooks").resolve()
        )

    def test_stale_hook_in_a_worktree_is_actually_refreshed(self):
        # The consequence that matters: without resolution the V1 hook survives.
        main = self._repo()
        linked = self.root / "linked"
        self._git("worktree", "add", "-q", str(linked), "-b", "feature", cwd=main)
        hook = main / ".git" / "hooks" / "pre-push"
        hook.parent.mkdir(parents=True, exist_ok=True)
        hook.write_text("#!/bin/sh\n# Sentinel: FORGE_PREFLIGHT_HOOK_V1\nexit 0\n")
        self.assertTrue(refresh_if_stale(linked))
        self.assertIn(SENTINEL, hook.read_text())

    def test_core_hookspath_is_honoured(self):
        main = self._repo()
        custom = main / "myhooks"
        custom.mkdir()
        self._git("config", "core.hooksPath", "myhooks", cwd=main)
        self.assertEqual(_hooks_dir(main).resolve(), custom.resolve())

    def test_non_git_directory_falls_back_to_the_naive_join(self):
        plain = self.root / "not-a-repo"
        plain.mkdir()
        self.assertEqual(_hooks_dir(plain), plain / ".git" / "hooks")


if __name__ == "__main__":
    unittest.main()


# --- T626: hollowed jobs -----------------------------------------------------
# A `uses:` step cannot run locally, so it is emitted as an inert comment. When
# the job's actual gating work IS that step, the job still runs its `run:`
# steps, exits 0, and reports a clean green having proved nothing. image-scan
# built two Docker images and scanned neither.

def _script(*skipped: str) -> str:
    body = ["#!/usr/bin/env bash", "set -euo pipefail"]
    for s in skipped:
        body.append(f"# Skipped step: {s}")
    body.append("echo work")
    return "\n".join(body) + "\n"


class TestDroppedStepClassification(unittest.TestCase):
    def test_real_scanner_counts_as_dropped(self):
        text = _script(
            "Scan Control Plane image (uses: aquasecurity/trivy-action@master, "
            "no local mirror)"
        )
        self.assertEqual(
            dropped_gating_steps(text),
            ["Scan Control Plane image (aquasecurity/trivy-action)"],
        )

    def test_environment_setup_is_not_dropped_work(self):
        # The anti-inflation case: if this warns, 45 of 46 scripts warn and the
        # real signal drowns.
        text = _script(
            "actions/checkout@v5 (uses: actions/checkout@v5, no local mirror)",
            "Setup Python (uses: actions/setup-python@v6, no local mirror)",
            "Setup Node.js (uses: actions/setup-node@v5, no local mirror)",
            "Cache deps (uses: actions/cache@v4, no local mirror)",
        )
        self.assertEqual(dropped_gating_steps(text), [])

    def test_uploading_results_out_of_ci_is_not_dropped_work(self):
        text = _script(
            "Upload coverage (uses: actions/upload-artifact@v4, no local mirror)",
            "Codecov (uses: codecov/codecov-action@v4, no local mirror)",
        )
        self.assertEqual(dropped_gating_steps(text), [])

    def test_unknown_action_counts_as_dropped(self):
        # Denylist, not allowlist: an action nobody classified must warn.
        text = _script("Do a thing (uses: some-vendor/mystery@v1, no local mirror)")
        self.assertEqual(dropped_gating_steps(text), ["Do a thing (some-vendor/mystery)"])

    def test_data_producing_actions_count_as_dropped(self):
        # paths-filter sets outputs later steps branch on; download-artifact
        # brings in data the job consumes. Dropping either changes the logic.
        text = _script(
            "Detect changes (uses: dorny/paths-filter@v3, no local mirror)",
            "Get results (uses: actions/download-artifact@v4, no local mirror)",
        )
        self.assertEqual(len(dropped_gating_steps(text)), 2)

    def test_script_with_no_skipped_steps_is_clean(self):
        self.assertEqual(dropped_gating_steps(_script()), [])


class TestIncompleteReporting(unittest.TestCase):
    def _job_inc(self, name="image-scan", exit_code=0, dropped=("Scan (x/y)",)):
        return JobResult(
            name=name, exit_code=exit_code, duration_seconds=2.1,
            stdout_tail="", stderr_tail="", dropped_steps=list(dropped),
        )

    def test_incomplete_job_is_not_rendered_as_passed(self):
        body = format_human(_report(self._job_inc()))
        self.assertNotIn("✅ image-scan", body)
        self.assertIn("INCOMPLETE", body)

    def test_dropped_step_names_are_shown(self):
        body = format_human(_report(self._job_inc(dropped=("Scan CP (trivy)",))))
        self.assertIn("Scan CP (trivy)", body)

    def test_safe_to_push_withheld_when_a_job_is_incomplete(self):
        body = format_human(_report(_job("lint"), self._job_inc()))
        self.assertNotIn("safe to push", body)

    def test_incomplete_yields_exit_5_not_0(self):
        self.assertEqual(exit_code_for(_report(_job("lint"), self._job_inc())), 5)

    def test_failing_job_is_not_downgraded_to_incomplete(self):
        # A red job stays red — failure is the loudest signal, and exit 3 must
        # outrank 5 or a real failure would stop blocking the PR gate.
        red = self._job_inc(exit_code=1)
        self.assertFalse(red.incomplete)
        self.assertEqual(exit_code_for(_report(red)), 3)

    def test_skip_takes_precedence_over_incomplete(self):
        # A job that never ran is not "incomplete", it is skipped; reporting
        # both would double-count it in the summary.
        j = JobResult(
            name="test", exit_code=0, duration_seconds=0.1, stdout_tail="",
            stderr_tail=PG_SKIP, skip_reason="postgres not reachable",
            dropped_steps=["Scan (x/y)"],
        )
        self.assertFalse(j.incomplete)

    def test_json_lists_incomplete_jobs(self):
        payload = _report(self._job_inc()).to_dict()
        self.assertEqual(payload["jobs_incomplete"], ["image-scan"])


# --- T625: step-level `if:` --------------------------------------------------
# The mirror dropped `if:` entirely, which was wrong in three directions at
# once: always()/failure() cleanup was killed by `set -e` at the moment it
# exists for, failure() steps ran on the success path, and steps gated on a
# prior step's output ran with no such output — including a git commit/push
# step gated on `github.event_name == 'push'`.

class TestConditionClassification(unittest.TestCase):
    def test_absent_condition_is_normal(self):
        self.assertEqual(classify_condition(None), STEP_NORMAL)

    def test_always_and_not_cancelled_both_mean_run_regardless(self):
        for c in ("always()", "!cancelled()", "! cancelled()"):
            self.assertEqual(classify_condition(c), STEP_ALWAYS, c)

    def test_wrapped_expression_form_is_equivalent(self):
        # `if: ${{ !cancelled() }}` and `if: '!cancelled()'` are the same thing.
        self.assertEqual(classify_condition("${{ !cancelled() }}"), STEP_ALWAYS)
        self.assertEqual(classify_condition("${{ always() }}"), STEP_ALWAYS)

    def test_failure_is_its_own_mode(self):
        self.assertEqual(classify_condition("failure()"), STEP_ON_FAILURE)

    def test_success_is_the_default_mode(self):
        self.assertEqual(classify_condition("success()"), STEP_NORMAL)

    def test_change_detection_conditions_are_over_run_not_dropped(self):
        # These gate on "did anything relevant change". CI skips the work as an
        # optimisation; running it anyway locally is a superset, never wrong.
        # Dropping them would remove working local coverage — the CHANGELOG and
        # CORS drift checks live behind exactly these.
        for c in (
            "steps.filter.outputs.cors == 'true'",
            "steps.filter.outputs.changelog == 'true'",
            "hashFiles('docs/api/openapi.yaml') != ''",
            "steps.npm-cache-tests.outputs.cache-hit != 'true'",
        ):
            self.assertEqual(classify_condition(c), STEP_OVER_RUN, c)

    def test_github_context_conditions_are_dropped(self):
        # These select an execution context rather than more work. Running them
        # anyway does work meant for another context.
        for c in (
            "github.event_name == 'push'",
            "startsWith(github.ref, 'refs/heads/x')",
            "steps.a.outputs.b == 'true' && github.event_name == 'push'",
        ):
            self.assertIsNone(classify_condition(c), c)

    def test_github_half_of_a_compound_wins(self):
        # The git-push step is `steps.x.outputs.y == 'true' && github.event_name
        # == 'push'`. The change-detection half must not rescue it.
        self.assertIsNone(
            classify_condition("steps.x.outputs.y == 'true' && github.event_name == 'push'")
        )

    def test_disabled_steps_are_their_own_mode(self):
        # `if: false` is a step switched off on purpose rather than deleted.
        # It must NOT reach the over-run default: over-running is only safe for
        # change DETECTION, where running anyway is a superset. A disabled step
        # is the opposite — CI suppresses it deliberately.
        for c in ("false", "${{ false }}"):
            self.assertEqual(classify_condition(c), STEP_NEVER, c)

    def test_compound_containing_false_is_not_treated_as_disabled(self):
        # Only a bare `false` is a deliberate off-switch. Anything compound is
        # an expression the mirror cannot evaluate and must not silently drop.
        self.assertEqual(
            classify_condition("steps.a.outputs.b == 'false'"), STEP_OVER_RUN
        )

    def test_compound_containing_always_is_not_treated_as_always(self):
        # `github.event_name == 'pull_request' && always()` is NOT always():
        # matching loosely here would run PR-only work on every local run.
        self.assertIsNone(
            classify_condition("github.event_name == 'pull_request' && always()")
        )


class TestConditionalStepEmission(unittest.TestCase):
    """End-to-end: generate a job, run it, observe which steps executed."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.root = Path(self._tmp)
        self.addCleanup(shutil.rmtree, self._tmp, True)
        (self.root / "_local_shims.sh").write_text(":\n")

    def _run(self, first_fails: bool):
        job = Job(name="demo", file="ci.yml", runs_on="ubuntu-latest", steps=[
            Step(name="work", run="echo STEP1; false" if first_fails else "echo STEP1"),
            Step(name="normal2", run="echo STEP2"),
            Step(name="diag", run="echo DIAG", if_condition="failure()"),
            Step(name="teardown", run="echo TEARDOWN", if_condition="always()"),
        ])
        body = render_script(job, Path("/tmp/x/.github/workflows/ci.yml"))
        script = self.root / "demo.sh"
        script.write_text(body)
        proc = subprocess.run(["bash", str(script)], capture_output=True, text=True)
        return proc.returncode, proc.stdout.split()

    def test_success_path_matches_github(self):
        rc, ran = self._run(first_fails=False)
        self.assertEqual(rc, 0)
        self.assertEqual(ran, ["STEP1", "STEP2", "TEARDOWN"])

    def test_failure_path_matches_github(self):
        rc, ran = self._run(first_fails=True)
        # Normal step skipped after the failure; conditional steps still run;
        # the job is still red.
        self.assertEqual(rc, 1)
        self.assertEqual(ran, ["STEP1", "DIAG", "TEARDOWN"])

    def test_failure_is_not_swallowed(self):
        # The `|| true` inversion: a broken gate that reports success is worse
        # than the bug being fixed.
        rc, _ = self._run(first_fails=True)
        self.assertNotEqual(rc, 0)

    def test_failure_inside_a_step_body_is_not_masked(self):
        # The step body's FIRST command fails and its LAST succeeds. GHA runs
        # each `run:` under `bash -e`, so the step dies at the first command.
        # A compound command on the LHS of `||` has errexit suppressed inside
        # its body too, so the old `( … ) || _forge_failed=1` shape ran the body
        # to the end, exited 0, and reported the job green — a false green on a
        # real CI failure, which is the bug this whole mechanism exists to stop.
        job = Job(name="demo", file="ci.yml", runs_on="ubuntu-latest", steps=[
            Step(name="work", run="false\necho STEP1"),
            Step(name="teardown", run="echo TEARDOWN", if_condition="always()"),
        ])
        body = render_script(job, Path("/tmp/x/.github/workflows/ci.yml"))
        script = self.root / "midstep.sh"
        script.write_text(body)
        proc = subprocess.run(["bash", str(script)], capture_output=True, text=True)
        ran = proc.stdout.split()
        self.assertNotIn("STEP1", ran)   # errexit killed the body, as on GHA
        self.assertIn("TEARDOWN", ran)   # always() cleanup still runs
        self.assertEqual(proc.returncode, 1)

    def test_job_without_conditional_steps_keeps_the_simple_shape(self):
        job = Job(name="plain", file="ci.yml", runs_on="ubuntu-latest",
                  steps=[Step(name="a", run="echo A")])
        body = render_script(job, Path("/tmp/x/.github/workflows/ci.yml"))
        self.assertNotIn("_forge_failed", body)


class TestUntranslatableStepsAreOmitted(unittest.TestCase):
    def _body(self, condition):
        job = Job(name="j", file="ci.yml", runs_on="ubuntu-latest", steps=[
            Step(name="Commit generated configs", run="git push", if_condition=condition),
        ])
        return render_script(job, Path("/tmp/x/.github/workflows/ci.yml"))

    def test_untranslatable_step_body_is_not_emitted(self):
        # The real hazard: this step commits and pushes in CI only on `push`.
        body = self._body("steps.x.outputs.y == 'true' && github.event_name == 'push'")
        self.assertNotIn("git push", body)

    def test_omission_names_the_condition(self):
        body = self._body("github.event_name == 'push'")
        self.assertIn("condition not evaluable locally", body)
        self.assertIn("github.event_name == 'push'", body)

    def test_omitted_step_surfaces_as_dropped_work(self):
        # Must reach the runner's INCOMPLETE channel, not vanish silently.
        body = self._body("github.event_name == 'push'")
        dropped = dropped_gating_steps(body)
        self.assertEqual(len(dropped), 1)
        self.assertIn("Commit generated configs", dropped[0])


class TestDisabledStepsAreOmitted(unittest.TestCase):
    """`if: false` — switched off on purpose, so the mirror declines it too."""

    def _body(self, condition="false", **step_kwargs):
        step_kwargs.setdefault("run", "echo SHOULD-NOT-RUN")
        job = Job(name="j", file="ci.yml", runs_on="ubuntu-latest", steps=[
            Step(name="Old migration", if_condition=condition, **step_kwargs),
        ])
        return render_script(job, Path("/tmp/x/.github/workflows/ci.yml"))

    def test_disabled_step_body_is_not_emitted(self):
        body = self._body()
        self.assertNotIn("SHOULD-NOT-RUN", body)
        self.assertIn("# Disabled step: Old migration (if: false)", body)

    def test_yaml_boolean_and_wrapped_forms_are_both_disabled(self):
        # `if: false` deserializes to a bool; the parser normalizes it to the
        # string. `${{ false }}` is the wrapped spelling of the same thing.
        for c in ("false", "${{ false }}"):
            self.assertNotIn("SHOULD-NOT-RUN", self._body(c), c)

    def test_disabled_step_is_not_reported_as_dropped_work(self):
        # The whole point of a separate marker: CI does not run this step
        # either, so omitting it locally is faithful, not lost coverage. A
        # false INCOMPLETE here would exit 5 and block /create-pr forever.
        self.assertEqual(dropped_gating_steps(self._body()), [])

    def test_disabled_uses_step_takes_the_disabled_branch(self):
        # A `uses:` step disabled with `if: false` is still disabled. Routing it
        # to the `# Skipped step:` branch would mark an otherwise clean job
        # INCOMPLETE over coverage CI never ran either.
        body = self._body(run=None, uses="some/costly-action@v1")
        self.assertIn("# Disabled step: Old migration (if: false)", body)
        self.assertNotIn("# Skipped step:", body)
        self.assertEqual(dropped_gating_steps(body), [])


class TestDestructiveCommandsAreRefused(unittest.TestCase):
    """Commands that are free on a runner and expensive on a workstation.

    `run:` bodies are transcribed verbatim into scripts the developer executes
    against their real daemon. The generator is the one physical chokepoint
    where "never mirror this locally" can be enforced — an in-workflow
    `if [ "$CI" = true ]` guard is armed by the `env:` block the generator
    itself exports above every step body.
    """

    _CLEANUP = (
        'if [ "${CI:-}" = "true" ]; then\n'
        "  docker compose -f x.yml down -v --remove-orphans || true\n"
        "  docker volume prune -f || true\n"
        "fi\n"
    )

    def _body(self, run, **job_kwargs):
        job = Job(name="e2e", file="ci.yml", runs_on="ubuntu-latest",
                  steps=[Step(name="Clean", run=run),
                         Step(name="Keep", run="echo KEPT")],
                  **job_kwargs)
        return render_script(job, Path("/tmp/x/.github/workflows/ci.yml"))

    def _executable(self, run, **job_kwargs):
        """The script minus its refusal notices.

        The notice NAMES the command it refused, so a naive substring check
        against the whole script matches its own explanation and passes for the
        wrong reason. What must not survive is an executable line.
        """
        return "\n".join(
            ln for ln in self._body(run, **job_kwargs).splitlines()
            if not ln.startswith("# Refused step:")
        )

    def test_destructive_body_never_reaches_the_mirror(self):
        self.assertNotIn("volume prune", self._executable(self._CLEANUP))
        self.assertNotIn("down -v", self._executable(self._CLEANUP))
        self.assertIn("# Refused step: Clean (destructive:", self._body(self._CLEANUP))

    def test_env_cannot_re_arm_a_refused_command(self):
        # The bypass the in-workflow guard cannot survive: two lines in an
        # `env:` block, the kind of PR titled "force CI mode so compose stops
        # prompting". The generator exports these ABOVE every step body.
        env = {"CI": "true", "GITHUB_ACTIONS": "true"}
        self.assertIn('export CI="true"', self._body(self._CLEANUP, env=env))
        self.assertNotIn("volume prune", self._executable(self._CLEANUP, env=env))

    def test_sibling_steps_are_still_mirrored(self):
        self.assertIn("echo KEPT", self._body(self._CLEANUP))

    def test_refusal_is_not_reported_as_dropped_work(self):
        # Not the `# Skipped step:` form: that would mark the job INCOMPLETE on
        # every run, for an omission that is correct and permanent.
        self.assertEqual(dropped_gating_steps(self._body(self._CLEANUP)), [])

    def test_recoverable_compose_down_is_still_mirrored(self):
        # `down` without a volume flag stops containers and keeps volumes. This
        # is the false-positive guard that matters — refusing it would remove
        # real local coverage from every project that tears a stack down.
        body = self._body("docker compose -f x.yml down")
        self.assertIn("docker compose -f x.yml down", body)
        self.assertNotIn("# Refused step:", body)

    def test_destructive_body_is_refused_even_with_unresolved_templates(self):
        # Refusal must come BEFORE the `${{` check, or a body carrying both
        # takes the Skipped branch and the command stays in the file.
        run = "docker volume prune -f ${{ steps.x.outputs.y }}"
        self.assertNotIn("volume prune", self._executable(run))
        self.assertIn("# Refused step:", self._body(run))

    def test_variants_the_narrow_form_missed(self):
        # Probed 2026-08-02: each of these was NOT caught by the first draft of
        # the denylist while being exactly as destructive as a form that was.
        for run in (
            "docker-compose -f x.yml down -v",       # hyphenated v1 binary
            "docker-compose down --volumes",
            "docker compose down -fv",               # clustered flags
            "rm -rf /*",                             # glob form of the root
            "rm -rfv /",                             # three-letter cluster
            "rm --recursive --force /",              # long flags
        ):
            self.assertTrue(destructive_commands(run), f"not caught: {run}")

    def test_ordinary_commands_are_not_refused(self):
        for run in (
            "docker compose down",
            "docker compose up -d",
            "rm -rf ./node_modules",
            "rm -rf /tmp/build-cache",               # scoped path, not the root
            "rm -rf dist",
            "docker image prune -f",                 # rebuild cost, not data loss
            "echo 'docker volume'",
        ):
            self.assertEqual(destructive_commands(run), [], f"false positive: {run}")


class TestUnresolvableBodyTemplates(unittest.TestCase):
    """A step whose body needs a context the mirror lacks cannot run at all.

    `_rewrite_actions_templates` maps secrets/env/vars/inputs onto shell
    variables. `${{ steps.* }}` and `${{ github.* }}` have no local equivalent
    and pass through verbatim, where bash rejects them as "bad substitution" —
    so emitting the step makes the job permanently red for a reason the
    developer cannot fix. Real case: build.sh line 59.
    """

    def _body(self, run):
        job = Job(name="build", file="ci.yml", runs_on="ubuntu-latest",
                  steps=[Step(name="Archive Artifacts", run=run)])
        return render_script(job, Path("/tmp/x/.github/workflows/ci.yml"))

    def test_step_output_reference_is_not_emitted(self):
        body = self._body('VERSION="${{ steps.version.outputs.version_number }}"')
        self.assertNotIn("bad", body)
        self.assertNotIn("${{", body)

    def test_omission_names_the_unresolved_context(self):
        body = self._body('VERSION="${{ steps.version.outputs.version_number }}"')
        self.assertIn("steps.version.outputs.version_number", body)
        self.assertIn("condition not evaluable locally", body)

    def test_it_surfaces_as_dropped_work(self):
        body = self._body('VERSION="${{ steps.version.outputs.version_number }}"')
        self.assertEqual(len(dropped_gating_steps(body)), 1)

    def test_rewritable_contexts_still_emit_normally(self):
        # secrets/env/vars/inputs DO have a local mapping — must not regress.
        body = self._body('TOKEN="${{ secrets.MY_TOKEN }}"')
        self.assertIn("${MY_TOKEN:-}", body)
        self.assertNotIn("Skipped step", body)
