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
from hook_installer import SENTINEL, refresh_if_stale  # noqa: E402
from script_generator import (  # noqa: E402
    GENERATOR_CONTRACT,
    compute_drift,
    dropped_gating_steps,
    render_script,
    write_lockfile,
)
from script_generator import JOB_SKIP_MARKER as EMITTER_MARKER  # noqa: E402
from workflow_parser import Job  # noqa: E402

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
