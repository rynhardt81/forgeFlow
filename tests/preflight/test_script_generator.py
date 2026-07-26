"""Unit tests for script_generator._rewrite_actions_templates.

Covers both the simple (`${{ vars.X }}`) and the GHA fallback
(`${{ vars.X || 'default' }}`) forms. Run with:

    python3 -m unittest tests.preflight.test_script_generator

or directly:

    python3 tests/preflight/test_script_generator.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "preflight"))

from script_generator import (  # noqa: E402
    _job_db_host_port,
    _job_needs_postgres,
    _rewrite_actions_templates,
    generate_scripts,
    render_script,
)
from workflow_parser import Job, Step  # noqa: E402

FIXTURE_COMPOSE = (
    REPO_ROOT / "tests" / "preflight" / "fixtures" / "docker-compose.yml"
)


class TestSimpleForm(unittest.TestCase):
    """The original `${{ context.X }}` form, no fallback."""

    def test_vars_simple(self):
        self.assertEqual(
            _rewrite_actions_templates("${{ vars.COVERAGE_MIN_UNIT }}"),
            "${COVERAGE_MIN_UNIT:-}",
        )

    def test_secrets_simple(self):
        self.assertEqual(
            _rewrite_actions_templates("${{ secrets.API_KEY }}"),
            "${API_KEY:-}",
        )

    def test_env_simple(self):
        self.assertEqual(
            _rewrite_actions_templates("${{ env.NODE_ENV }}"),
            "${NODE_ENV:-}",
        )

    def test_inputs_simple(self):
        self.assertEqual(
            _rewrite_actions_templates("${{ inputs.MODE }}"),
            "${MODE:-}",
        )


class TestFallbackForm(unittest.TestCase):
    """GHA `||` fallback: ${{ context.X || 'default' }}."""

    def test_single_quoted_default(self):
        self.assertEqual(
            _rewrite_actions_templates("${{ vars.COVERAGE_MIN_UNIT || '60' }}"),
            "${COVERAGE_MIN_UNIT:-60}",
        )

    def test_double_quoted_default(self):
        self.assertEqual(
            _rewrite_actions_templates('${{ secrets.API_URL || "https://example.com" }}'),
            "${API_URL:-https://example.com}",
        )

    def test_bare_default(self):
        self.assertEqual(
            _rewrite_actions_templates("${{ env.LEVEL || debug }}"),
            "${LEVEL:-debug}",
        )

    def test_single_quoted_default_with_spaces(self):
        self.assertEqual(
            _rewrite_actions_templates("${{ vars.MSG || 'hello world' }}"),
            "${MSG:-hello world}",
        )

    def test_default_with_url_special_chars(self):
        self.assertEqual(
            _rewrite_actions_templates(
                "${{ secrets.APISIX_ADMIN_URL || 'http://apisix:9180' }}"
            ),
            "${APISIX_ADMIN_URL:-http://apisix:9180}",
        )

    def test_default_with_underscores(self):
        self.assertEqual(
            _rewrite_actions_templates(
                "${{ secrets.CI_POSTGRES_PASSWORD || 'ci_ephemeral_pw' }}"
            ),
            "${CI_POSTGRES_PASSWORD:-ci_ephemeral_pw}",
        )

    def test_secrets_all_fallback_form_examples(self):
        """Six representative GHA `||` fallback forms — vars, secrets, env."""
        cases = [
            (
                "${{ vars.COVERAGE_MIN_UNIT || '60' }}",
                "${COVERAGE_MIN_UNIT:-60}",
            ),
            (
                "${{ vars.COVERAGE_MIN_INT  || '40' }}",
                "${COVERAGE_MIN_INT:-40}",
            ),
            (
                "${{ vars.VITEST_COVERAGE_MIN || '60' }}",
                "${VITEST_COVERAGE_MIN:-60}",
            ),
            (
                "${{ secrets.CI_POSTGRES_PASSWORD || 'ci_ephemeral_pw' }}",
                "${CI_POSTGRES_PASSWORD:-ci_ephemeral_pw}",
            ),
            (
                "${{ secrets.APISIX_ADMIN_URL || 'http://apisix:9180' }}",
                "${APISIX_ADMIN_URL:-http://apisix:9180}",
            ),
            (
                "${{ secrets.APISIX_ADMIN_KEY || 'default-admin-key' }}",
                "${APISIX_ADMIN_KEY:-default-admin-key}",
            ),
        ]
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(_rewrite_actions_templates(source), expected)


class TestDefaultEscaping(unittest.TestCase):
    """Bash-special chars in the default must be escaped so they're literal."""

    def test_dollar_sign_escaped(self):
        # GHA default 'foo$bar' is literal; bash without escaping would treat
        # $bar as a variable expansion.
        self.assertEqual(
            _rewrite_actions_templates("${{ vars.PASS || 'foo$bar' }}"),
            "${PASS:-foo\\$bar}",
        )

    def test_backtick_escaped(self):
        self.assertEqual(
            _rewrite_actions_templates("${{ vars.CMD || 'echo `pwd`' }}"),
            "${CMD:-echo \\`pwd\\`}",
        )

    def test_backslash_escaped(self):
        self.assertEqual(
            _rewrite_actions_templates("${{ vars.PATH || 'a\\b' }}"),
            "${PATH:-a\\\\b}",
        )


class TestMultiTemplate(unittest.TestCase):
    """Multiple templates in one string all rewrite in one pass."""

    def test_concatenated_simple_and_fallback(self):
        self.assertEqual(
            _rewrite_actions_templates(
                "prefix-${{ vars.X }}-${{ vars.Y || '0' }}-suffix"
            ),
            "prefix-${X:-}-${Y:-0}-suffix",
        )

    def test_three_templates(self):
        self.assertEqual(
            _rewrite_actions_templates(
                "${{ secrets.A || 'a' }} ${{ env.B }} ${{ vars.C || 'c' }}"
            ),
            "${A:-a} ${B:-} ${C:-c}",
        )


class TestPassthrough(unittest.TestCase):
    """Out-of-scope GHA contexts must pass through unchanged.

    Per the comment in script_generator.py, `github.*`, `steps.*`, `matrix.*`,
    and function calls are CI-only and can't map to a local env var.
    """

    def test_github_context_passthrough(self):
        self.assertEqual(
            _rewrite_actions_templates("${{ github.event_name }}"),
            "${{ github.event_name }}",
        )

    def test_steps_outputs_passthrough(self):
        self.assertEqual(
            _rewrite_actions_templates("${{ steps.foo.outputs.bar }}"),
            "${{ steps.foo.outputs.bar }}",
        )

    def test_matrix_passthrough(self):
        self.assertEqual(
            _rewrite_actions_templates("${{ matrix.python-version }}"),
            "${{ matrix.python-version }}",
        )

    def test_no_template_passthrough(self):
        self.assertEqual(
            _rewrite_actions_templates("just a plain string"),
            "just a plain string",
        )

    def test_empty_string(self):
        self.assertEqual(_rewrite_actions_templates(""), "")


class TestGenerateScriptsComposeRewrite(unittest.TestCase):
    """T496: generate_scripts(project_root=...) rewrites localhost ports.

    Wire-through test — verifies the introspector is actually invoked from
    the public generator entry point, not just unit-testable in isolation.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        # Drop the fixture Compose at the canonical location.
        compose_dir = self.tmp / "infrastructure" / "compose"
        compose_dir.mkdir(parents=True)
        shutil.copy(FIXTURE_COMPOSE, compose_dir / "docker-compose.yml")
        self.out = self.tmp / ".forge" / "preflight"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_job(self, env: dict[str, str]) -> Job:
        return Job(
            name="test",
            file=str(self.tmp / ".github" / "workflows" / "ci.yml"),
            runs_on="ubuntu-latest",
            env=env,
            steps=[],
        )

    def test_rewrites_database_url_in_generated_script(self):
        import contextlib
        import io
        job = self._make_job(
            {
                "DATABASE_URL": "postgresql://app:pw@localhost:5432/app_test",
                "REDIS_HOST": "localhost",
                "REDIS_PASSWORD": "",
            }
        )
        # REDIS_PASSWORD="" triggers the T496 rewrite → env-ref emitted →
        # T499 warning fires because no .env in self.tmp. Not asserted here;
        # suppress the noise.
        with contextlib.redirect_stderr(io.StringIO()):
            generate_scripts([job], self.out, project_root=self.tmp)
        body = (self.out / "test.sh").read_text()
        # Port rewritten to the Compose host port (5440)
        self.assertIn("localhost:5440", body)
        self.assertNotIn("localhost:5432", body)
        # Empty REDIS_PASSWORD → env-ref form. The introspector emits the
        # GHA template `${{ env.REDIS_PASSWORD }}` which the existing
        # `_rewrite_actions_templates` pass turns into bash
        # `${REDIS_PASSWORD:-}` AND keeps `$` unescaped so it expands.
        self.assertIn('export REDIS_PASSWORD="${REDIS_PASSWORD:-}"', body)

    def test_no_project_root_skips_rewrite(self):
        # Backwards-compat: callers that don't pass project_root get the
        # current behaviour — workflow values transcribed verbatim.
        job = self._make_job(
            {"DATABASE_URL": "postgresql://x:y@localhost:5432/z"}
        )
        generate_scripts([job], self.out)
        body = (self.out / "test.sh").read_text()
        self.assertIn("localhost:5432", body)

    def test_no_compose_file_skips_rewrite(self):
        # Project without a Compose file: rewrite is a no-op, generator
        # falls through to current behaviour.
        bare = Path(tempfile.mkdtemp())
        try:
            job = self._make_job(
                {"DATABASE_URL": "postgresql://x:y@localhost:5432/z"}
            )
            generate_scripts([job], bare / "out", project_root=bare)
            body = (bare / "out" / "test.sh").read_text()
            self.assertIn("localhost:5432", body)
        finally:
            shutil.rmtree(bare, ignore_errors=True)

    # Sentinel string used to find the env-source block in the generated
    # script. Mirrors the literal that render_script emits; if that
    # comment ever changes, update here.
    ENV_BLOCK_SENTINEL = "T497/T498: layered .env merge"

    def test_env_source_block_emitted_when_env_present(self):
        # Project with .env at root → generated script sources it before
        # any export, so password env-refs resolve to real values.
        (self.tmp / ".env").write_text("POSTGRES_PASSWORD=devpw\n")
        job = self._make_job(
            {"DATABASE_URL": "postgresql://x:${POSTGRES_PASSWORD:-}@localhost:5432/y"}
        )
        generate_scripts([job], self.out, project_root=self.tmp)
        body = (self.out / "test.sh").read_text()
        # Sentinel + key tokens of the source block
        self.assertIn(self.ENV_BLOCK_SENTINEL, body)
        self.assertIn("set +eu", body)
        self.assertIn("set -a", body)
        self.assertIn('. "$_env_layer"', body)
        self.assertIn("set +a", body)
        self.assertIn("set -eu", body)
        self.assertIn(".env", body)

    def test_env_source_block_has_no_break(self):
        # T498: layered-merge requires every existing layer to be sourced,
        # so the for-loop must NOT contain `break`. T497 used break for
        # first-found-wins; that silently let a stale root .env shadow
        # the installer-managed Compose .env. Regression test.
        (self.tmp / ".env").write_text("X=1\n")
        (self.tmp / "infrastructure" / "compose" / ".env").write_text("Y=2\n")
        job = self._make_job({"X": "${X:-}"})
        generate_scripts([job], self.out, project_root=self.tmp)
        body = (self.out / "test.sh").read_text()
        # Scope to the executable lines of the env-source block, not the
        # comment header (which legitimately contains the word "break").
        # Anchor on `set +eu` (first executable line) → `set -eu` (last).
        block_start = body.index(self.ENV_BLOCK_SENTINEL)
        exec_start = body.index("set +eu", block_start)
        exec_end = body.index("set -eu", exec_start) + len("set -eu")
        exec_block = body[exec_start:exec_end]
        self.assertNotIn("break", exec_block)

    def test_env_source_block_before_shim_source(self):
        # Shims may want env vars, so the .env source must run BEFORE the
        # shim source. Position-test: sentinel appears before the
        # _shim_path assignment.
        (self.tmp / ".env").write_text("X=1\n")
        job = self._make_job({"X": "${X:-}"})
        generate_scripts([job], self.out, project_root=self.tmp)
        body = (self.out / "test.sh").read_text()
        env_idx = body.index(self.ENV_BLOCK_SENTINEL)
        shim_idx = body.index("_shim_path=")
        self.assertLess(
            env_idx, shim_idx, "env source must run before shim source"
        )

    def test_no_env_source_block_when_no_env_present(self):
        # Bare project — no .env, no source block. Backwards-compat: the
        # generator's output for an env-less project is unchanged. Note:
        # self.tmp has the fixture Compose file (postgres + redis with
        # password) from setUp, so the password rewrite fires; without
        # an .env, T499's silent-fail warning is correctly emitted. The
        # other tests assert on that warning; here we only care about
        # the rendered body shape — suppress stderr to keep test output
        # clean.
        import contextlib
        import io
        job = self._make_job({"X": "y"})
        with contextlib.redirect_stderr(io.StringIO()):
            generate_scripts([job], self.out, project_root=self.tmp)
        body = (self.out / "test.sh").read_text()
        self.assertNotIn(self.ENV_BLOCK_SENTINEL, body)
        self.assertNotIn("set +eu", body)

    def test_env_source_block_compose_first_root_last(self):
        # T498: when BOTH layers exist, the generator emits them in
        # base-first / override-last order so root .env wins per-key
        # over Compose values via bash last-export semantics.
        (self.tmp / ".env").write_text("X=1\n")
        (self.tmp / "infrastructure" / "compose" / ".env").write_text("Y=2\n")
        job = self._make_job({"X": "x"})
        generate_scripts([job], self.out, project_root=self.tmp)
        body = (self.out / "test.sh").read_text()
        # Both candidates appear, Compose subdir BEFORE root .env in the
        # for-loop's text order.
        compose_idx = body.index("infrastructure/compose/.env")
        # Root .env is the bare token ".env" on its own line in the loop.
        # Anchor on the newline+whitespace+.env pattern to avoid matching
        # the longer "infrastructure/compose/.env" path.
        root_match = body.index("\n    .env", compose_idx)
        self.assertLess(
            compose_idx, root_match,
            "Compose .env must appear before root .env in the source loop",
        )

    def test_compose_relative_env_discovered_for_non_canonical_layout(self):
        # T499: a project whose Compose file isn't at any canonical path
        # (here, deploy/compose/dev.yml — a non-canonical layout). The
        # .env next to that compose file should still be discovered and
        # land in the source-block, without requiring pyproject.toml.
        non_canon_root = Path(tempfile.mkdtemp())
        try:
            (non_canon_root / "deploy" / "compose").mkdir(parents=True)
            # Override the canonical-fixture compose with a non-canonical one
            shutil.copy(
                FIXTURE_COMPOSE,
                non_canon_root / "deploy" / "compose" / "dev.yml",
            )
            (non_canon_root / "deploy" / "compose" / ".env").write_text(
                "POSTGRES_PASSWORD=devpw\n"
            )
            # Opt the consumer in via pyproject.toml so discover_compose_file
            # finds the non-canonical compose path; that's the existing T496
            # mechanism. T499's piece is the env-side: once the compose file
            # is found, its sibling .env is also discovered automatically.
            (non_canon_root / "pyproject.toml").write_text(
                '[tool.forge.preflight]\n'
                'compose_file = "deploy/compose/dev.yml"\n'
            )
            job = Job(
                name="test",
                file=str(non_canon_root / ".github" / "workflows" / "ci.yml"),
                runs_on="ubuntu-latest",
                env={},
                steps=[],
            )
            out = non_canon_root / ".forge" / "preflight"
            generate_scripts([job], out, project_root=non_canon_root)
            body = (out / "test.sh").read_text()
            # The compose-relative .env shows up in the source-loop.
            self.assertIn("deploy/compose/.env", body)
        finally:
            shutil.rmtree(non_canon_root, ignore_errors=True)

    def test_warning_when_password_refs_emitted_but_no_env_found(self):
        # T499: regression guard against the silent-fail case — a project
        # with a Compose file whose services declare passwords (so the
        # rewrite emits env-refs), but no .env file anywhere. Generator
        # must print a stderr hint pointing at the pyproject override
        # so the consumer can opt their non-canonical .env in.
        import contextlib
        import io
        # self.tmp already has the canonical Compose fixture from setUp
        # (postgres + redis with password). No .env exists in self.tmp.
        job = self._make_job(
            {
                "DATABASE_URL": "postgresql://u:pw@localhost:5432/db",
                "REDIS_PASSWORD": "",  # triggers the password env-ref rewrite
            }
        )
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            generate_scripts([job], self.out, project_root=self.tmp)
        warning = stderr.getvalue()
        self.assertIn("no .env was found", warning)
        self.assertIn("pyproject.toml", warning)
        self.assertIn("[tool.forge.preflight]", warning)
        self.assertIn("env_files", warning)

    def test_no_warning_when_env_file_present(self):
        # The warning is conditional — when .env IS discovered, no hint.
        import contextlib
        import io
        (self.tmp / ".env").write_text("POSTGRES_PASSWORD=x\n")
        job = self._make_job(
            {"DATABASE_URL": "postgresql://u:pw@localhost:5432/db",
             "REDIS_PASSWORD": ""}
        )
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            generate_scripts([job], self.out, project_root=self.tmp)
        self.assertEqual(stderr.getvalue(), "")

    def test_no_warning_when_no_password_refs(self):
        # Projects without password rewrites (no Compose-declared password
        # env, or no empty workflow defaults) don't depend on .env sourcing;
        # warning stays silent even if no .env exists.
        import contextlib
        import io
        bare_root = Path(tempfile.mkdtemp())
        try:
            # No Compose file → no rewrite → no env-refs → no warning.
            job = Job(
                name="test",
                file=str(bare_root / ".github" / "workflows" / "ci.yml"),
                runs_on="ubuntu-latest",
                env={"NODE_ENV": "test"},
                steps=[],
            )
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                generate_scripts(
                    [job], bare_root / "out", project_root=bare_root
                )
            self.assertEqual(stderr.getvalue(), "")
        finally:
            shutil.rmtree(bare_root, ignore_errors=True)

    def test_env_layered_merge_root_overrides_compose(self):
        # T498 acceptance criterion #6: two-file fixture (one key in
        # both, one key in compose-only, one key in root-only) — exercise
        # the full layered semantic in a real bash subshell.
        #
        # Compose .env (base) defines BASE_KEY + SHARED_KEY=from-compose.
        # Root .env (override) defines SHARED_KEY=from-root + ROOT_KEY.
        # Expected after source-block runs:
        #   BASE_KEY=from-compose    (compose-only carries through)
        #   SHARED_KEY=from-root     (root overrides compose, last wins)
        #   ROOT_KEY=from-root       (root-only present)
        compose_env = self.tmp / "infrastructure" / "compose" / ".env"
        compose_env.write_text(
            "BASE_KEY=from-compose\nSHARED_KEY=from-compose\n"
        )
        (self.tmp / ".env").write_text(
            "SHARED_KEY=from-root\nROOT_KEY=from-root\n"
        )
        job = self._make_job({})
        generate_scripts([job], self.out, project_root=self.tmp)
        # Extract just the executable lines of the env-source block
        # (skip the comment header so bash doesn't try to parse it),
        # run them in a probe script, then echo the three keys.
        body = (self.out / "test.sh").read_text()
        block_start = body.index(self.ENV_BLOCK_SENTINEL)
        exec_start = body.index("set +eu", block_start)
        exec_end = body.index("set -eu", exec_start) + len("set -eu")
        exec_block = body[exec_start:exec_end]
        probe = self.tmp / "_probe.sh"
        probe.write_text(
            "#!/usr/bin/env bash\nset -euo pipefail\n"
            + exec_block
            + '\necho "BASE=$BASE_KEY"\necho "SHARED=$SHARED_KEY"\necho "ROOT=$ROOT_KEY"\n'
        )
        probe.chmod(0o755)
        import subprocess
        result = subprocess.run(
            ["bash", str(probe)],
            cwd=self.tmp,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(
            result.returncode, 0,
            f"probe failed: stderr={result.stderr}",
        )
        out = result.stdout
        self.assertIn("BASE=from-compose", out)
        self.assertIn("SHARED=from-root", out)
        self.assertIn("ROOT=from-root", out)

    def test_env_file_outside_project_root_uses_absolute_path(self):
        # T502: a symlinked .env (or absolute pyproject.toml override) may
        # resolve outside project_root. The pre-fix code called
        # Path.relative_to(project_root) which raises ValueError, aborting
        # script generation entirely. Verify: generation succeeds, script
        # sources via absolute path, warning logged.
        import contextlib
        import io
        # Secrets dir lives OUTSIDE self.tmp (separately-managed) but the
        # in-repo .env is a symlink pointing into it. Common pattern for
        # production-shape creds available locally without committing.
        outside = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, outside, True)
        outside_env = outside / ".env"
        outside_env.write_text("REDIS_PASSWORD=from-outside\n")
        # Symlink the canonical root .env to the outside file.
        (self.tmp / ".env").symlink_to(outside_env)

        job = self._make_job(
            {"DATABASE_URL": "postgresql://u:pw@localhost:5432/db",
             "REDIS_PASSWORD": ""}
        )
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            # Must not raise — the pre-fix code aborted with ValueError here.
            generate_scripts([job], self.out, project_root=self.tmp)

        body = (self.out / "test.sh").read_text()
        # Script embeds the resolved absolute path of the symlink target.
        self.assertIn(str(outside_env.resolve()), body)
        # Warning surfaced so the operator knows the path is machine-specific.
        warning = stderr.getvalue()
        self.assertIn("resolve outside project", warning)
        self.assertIn(str(outside_env.resolve()), warning)

    def test_env_file_with_whitespace_path_does_not_split(self):
        # T503: an env file whose resolved absolute path contains whitespace
        # (macOS `~/Library/Application Support/...`, any user-created dir
        # with spaces) — the pre-fix renderer emitted the path unquoted into
        # the for-loop, so bash word-split the path into fragments and the
        # `[ -f "$_env_layer" ]` check silently failed on each fragment.
        # Glob metachars (`*`, `?`, `[`) would have the same failure mode
        # via pathname expansion. shlex.quote on each token blocks both.
        import contextlib
        import io
        import subprocess
        outside = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, outside, True)
        spaced = outside / "Application Support"
        spaced.mkdir()
        outside_env = spaced / ".env"
        outside_env.write_text("WHITESPACE_KEY=resolved\n")
        (self.tmp / ".env").symlink_to(outside_env)

        job = self._make_job({"X": "y"})
        with contextlib.redirect_stderr(io.StringIO()):
            generate_scripts([job], self.out, project_root=self.tmp)

        body = (self.out / "test.sh").read_text()
        # Extract the env-source block and run it under real bash. If the
        # path were unquoted, bash would split on whitespace and the
        # `[ -f ]` check would fail on every fragment — WHITESPACE_KEY
        # would be undefined after the loop. With shlex.quote, the single-
        # quoted form survives word-splitting and the .env actually sources.
        block_start = body.index(self.ENV_BLOCK_SENTINEL)
        exec_start = body.index("set +eu", block_start)
        exec_end = body.index("set -eu", exec_start) + len("set -eu")
        exec_block = body[exec_start:exec_end]
        probe = self.tmp / "_probe.sh"
        probe.write_text(
            "#!/usr/bin/env bash\nset -euo pipefail\n"
            + exec_block
            + '\necho "WS=${WHITESPACE_KEY:-MISSING}"\n'
        )
        probe.chmod(0o755)
        result = subprocess.run(
            ["bash", str(probe)],
            cwd=self.tmp,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(
            result.returncode, 0,
            f"probe failed: stderr={result.stderr}",
        )
        self.assertIn("WS=resolved", result.stdout)

    def test_rewrites_step_level_env(self):
        # Workflows that declare DATABASE_URL / REDIS_PASSWORD at the *step*
        # env rather than the job env are a common shape (per-step CI
        # matrices). The rewrite must reach both — half a fix is no fix.
        import contextlib
        import io
        step = Step(
            name="Test Control Plane",
            run="pytest tests/unit",
            env={
                "DATABASE_URL": "postgresql://app:pw@localhost:5432/app_test",
                "REDIS_PASSWORD": "",
            },
        )
        job = Job(
            name="test",
            file=str(self.tmp / ".github" / "workflows" / "ci.yml"),
            runs_on="ubuntu-latest",
            env={},  # job-level env is empty — value lives on the step
            steps=[step],
        )
        # T499 warning suppressed — see test_rewrites_database_url note.
        with contextlib.redirect_stderr(io.StringIO()):
            generate_scripts([job], self.out, project_root=self.tmp)
        body = (self.out / "test.sh").read_text()
        self.assertIn("localhost:5440", body)
        self.assertNotIn("localhost:5432", body)
        self.assertIn('REDIS_PASSWORD="${REDIS_PASSWORD:-}"', body)


if __name__ == "__main__":
    unittest.main()


class TestPostgresGuard(unittest.TestCase):
    """T600: the pg-reachability guard is emitted ONLY for DB-dependent jobs."""

    def _wf(self) -> Path:
        return Path("/tmp/x/.github/workflows/ci.yml")

    def _job(self, *, name="test", env=None, steps=None) -> Job:
        return Job(
            name=name,
            file=str(self._wf()),
            runs_on="ubuntu-latest",
            env=env or {},
            steps=steps or [],
        )

    def test_needs_postgres_true_when_job_env_has_database_url(self):
        job = self._job(env={"DATABASE_URL": "postgresql://a:b@localhost:5440/t"})
        self.assertTrue(_job_needs_postgres(job))

    def test_needs_postgres_true_when_step_env_has_database_url(self):
        step = Step(name="t", run="pytest", env={"DATABASE_URL": "x"})
        job = self._job(steps=[step])
        self.assertTrue(_job_needs_postgres(job))

    def test_needs_postgres_true_when_step_run_references_database_url(self):
        step = Step(name="t", run='export DATABASE_URL=x; pytest', env={})
        job = self._job(steps=[step])
        self.assertTrue(_job_needs_postgres(job))

    def test_needs_postgres_false_for_frontend_only_job(self):
        step = Step(name="vitest", run="cd frontend/portal && npm test", env={})
        job = self._job(name="lint", steps=[step])
        self.assertFalse(_job_needs_postgres(job))

    def test_guard_emitted_for_db_job(self):
        job = self._job(env={"DATABASE_URL": "postgresql://a:b@localhost:5440/t"})
        body = render_script(job, self._wf())
        self.assertIn("_forge_pg_reachable", body)
        self.assertIn("SKIP: postgres not reachable", body)
        # The guard must sit AFTER the shim source (which defines the helper)
        # and BEFORE any step subshell.
        self.assertLess(
            body.index('source "$_shim_path"'), body.index("_forge_pg_reachable")
        )
        self.assertIn("exit 0", body)

    def test_guard_exports_pg_host_port_before_probe(self):
        # PR #509 review (P2): the probe must be told the host:port the DB
        # steps use, because DATABASE_URL is exported per-step (in subshells,
        # after the guard) and is NOT in scope at guard time. The generator
        # extracts it from the (Compose-rewritten) URL and exports FORGE_PG_*
        # right before the probe call.
        job = self._job(
            env={"DATABASE_URL": "postgresql://a:b@localhost:5440/t"}
        )
        body = render_script(job, self._wf())
        self.assertIn('export FORGE_PG_HOST="localhost" FORGE_PG_PORT="5440"', body)
        # ...and it must come BEFORE the probe call so the probe reads it.
        self.assertLess(
            body.index("FORGE_PG_PORT"), body.index("declare -F _forge_pg_reachable")
        )

    def test_guard_uses_step_level_db_url_port(self):
        # DATABASE_URL commonly lives on the step, not the job. The extractor
        # must still find the port (e.g. a non-5440 mapping) from step env.
        step = Step(
            name="test",
            run="pytest",
            env={"DATABASE_URL": "postgresql://a:b@localhost:6543/t"},
        )
        job = self._job(steps=[step])
        body = render_script(job, self._wf())
        self.assertIn('FORGE_PG_PORT="6543"', body)

    def test_guard_absent_for_non_db_job(self):
        step = Step(name="lint", run="ruff check .", env={})
        job = self._job(name="lint", steps=[step])
        body = render_script(job, self._wf())
        self.assertNotIn("_forge_pg_reachable", body)
        self.assertNotIn("SKIP: postgres not reachable", body)
        self.assertNotIn("FORGE_PG_HOST", body)


class TestJobDbHostPort(unittest.TestCase):
    """PR #509 review: extract the DB host:port the probe should target."""

    def _job(self, *, env=None, steps=None) -> Job:
        return Job(
            name="test",
            file="/tmp/x/.github/workflows/ci.yml",
            runs_on="ubuntu-latest",
            env=env or {},
            steps=steps or [],
        )

    def test_extracts_host_and_port_from_job_env(self):
        job = self._job(env={"DATABASE_URL": "postgresql://u:p@db.host:5440/t"})
        self.assertEqual(_job_db_host_port(job), ("db.host", "5440"))

    def test_extracts_from_step_env_when_not_on_job(self):
        step = Step(name="t", run="pytest",
                    env={"DATABASE_URL": "postgresql://u:p@localhost:6543/t"})
        job = self._job(steps=[step])
        self.assertEqual(_job_db_host_port(job), ("localhost", "6543"))

    def test_extracts_from_step_run_body(self):
        # PR #509 review (2nd P2): a step may inline the URL in `run:`, which
        # _job_needs_postgres() treats as DB-dependent — so the extractor MUST
        # cover run bodies too, or the guard emits no FORGE_PG_* and the probe
        # falls back to its hardcoded default.
        step = Step(
            name="test",
            run="export DATABASE_URL=postgresql://a:b@localhost:6543/t\npytest",
            env={},
        )
        job = self._job(steps=[step])
        self.assertEqual(_job_db_host_port(job), ("localhost", "6543"))

    def test_run_body_extraction_wires_into_generated_guard(self):
        # End-to-end: the run-body case emits FORGE_PG_* into the script.
        step = Step(
            name="test",
            run="export DATABASE_URL=postgresql://a:b@db.host:6543/t\npytest",
            env={},
        )
        job = self._job(steps=[step])
        body = render_script(job, Path("/tmp/x/.github/workflows/ci.yml"))
        self.assertIn('export FORGE_PG_HOST="db.host" FORGE_PG_PORT="6543"', body)

    def test_run_body_without_database_url_is_ignored(self):
        # An unrelated postgresql:// URL in a run body that does NOT mention
        # DATABASE_URL must not be mistaken for the DB target.
        step = Step(
            name="t",
            run="psql postgresql://a:b@other:9999/x -c 'SELECT 1'",
            env={},
        )
        job = self._job(steps=[step])
        self.assertIsNone(_job_db_host_port(job))

    def test_port_defaults_to_5432_when_url_omits_it(self):
        job = self._job(env={"DATABASE_URL": "postgresql://u:p@localhost/t"})
        self.assertEqual(_job_db_host_port(job), ("localhost", "5432"))

    def test_none_when_no_literal_host(self):
        # A pure env-ref URL with no literal host → None (helper keeps default).
        job = self._job(env={"DATABASE_URL": "${DATABASE_URL:-}"})
        self.assertIsNone(_job_db_host_port(job))

    def test_none_when_no_database_url_at_all(self):
        job = self._job(env={"REDIS_HOST": "localhost"})
        self.assertIsNone(_job_db_host_port(job))



class TestPostgresGuardDegradesSafely(unittest.TestCase):
    """The guard must never skip a job just because the helper is absent.

    `_local_shims.sh` is seeded only-if-missing, so an install predating
    `_forge_pg_reachable` still has a shim without it. An unguarded
    `if ! _forge_pg_reachable` would exit 127 -> `!` -> true -> silently SKIP
    every DB job. Absent helper must mean "run".
    """

    def _db_job(self) -> Job:
        return Job(
            name="test",
            file="/tmp/x/.github/workflows/ci.yml",
            runs_on="ubuntu-latest",
            env={"DATABASE_URL": "postgresql://a:b@localhost:5432/t"},
            steps=[],
        )

    def _guard_snippet(self) -> str:
        body = render_script(self._db_job(), Path("/tmp/x/.github/workflows/ci.yml"))
        start = body.index("if declare -F _forge_pg_reachable")
        return body[start:body.index("fi", start) + 2]

    def test_guard_checks_declare_before_calling(self):
        snippet = self._guard_snippet()
        self.assertLess(
            snippet.index("declare -F _forge_pg_reachable"),
            snippet.index("! _forge_pg_reachable"),
        )

    def test_absent_helper_runs_job_instead_of_skipping(self):
        # Behavioural: execute the guard in a shell with NO helper defined.
        # It must fall through (no SKIP, exit 0 from the trailing marker).
        import subprocess
        script = self._guard_snippet() + '\necho REACHED_STEPS\n'
        out = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
        self.assertIn("REACHED_STEPS", out.stdout)
        self.assertNotIn("SKIP: postgres not reachable", out.stderr)

    def test_present_helper_returning_false_does_skip(self):
        # Falsifier: with the helper defined and reporting unreachable, the
        # guard MUST skip — otherwise the test above would pass vacuously.
        import subprocess
        script = (
            "_forge_pg_reachable() { return 1; }\n"
            + self._guard_snippet()
            + '\necho REACHED_STEPS\n'
        )
        out = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
        self.assertNotIn("REACHED_STEPS", out.stdout)
        self.assertIn("SKIP: postgres not reachable", out.stderr)


