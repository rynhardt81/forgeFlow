"""Regression tests for workflow_parser trigger + working-directory handling.

Both cases were found in the field as local patches in consumer projects and
upstreamed on 2026-07-25. Run with:

    python3 -m unittest tests.preflight.test_workflow_parser
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "preflight"))

from script_generator import render_script  # noqa: E402
from workflow_parser import _trigger_targets_branch, derive_gating_jobs  # noqa: E402


def _workflows(yaml_text: str):
    """Write one workflow file into a temp dir and return its gating jobs."""
    tmp = tempfile.mkdtemp()
    (Path(tmp) / "ci.yml").write_text(yaml_text)
    return derive_gating_jobs(Path(tmp), "main")


class TestPullRequestTrigger(unittest.TestCase):
    """`on: pull_request:` with no value is the most common gating form."""

    def test_bare_pull_request_is_gating(self):
        # Regression: this deserializes to {"pull_request": None} and used to
        # return False, so preflight mirrored nothing and reported clean.
        self.assertTrue(_trigger_targets_branch({"pull_request": None}, "main"))

    def test_bare_pull_request_end_to_end(self):
        jobs = _workflows(
            "name: CI\non:\n  pull_request:\njobs:\n"
            "  lint:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo hi\n"
        )
        self.assertEqual(len(jobs), 1)

    def test_absent_pull_request_is_not_gating(self):
        self.assertFalse(_trigger_targets_branch({"push": None}, "main"))

    def test_empty_dict_trigger_is_not_gating(self):
        self.assertFalse(_trigger_targets_branch({}, "main"))

    def test_explicit_branches_still_filter(self):
        trigger = {"pull_request": {"branches": ["release"]}}
        self.assertFalse(_trigger_targets_branch(trigger, "main"))


class TestWorkingDirectory(unittest.TestCase):
    """GHA `defaults.run.working-directory` inherits workflow -> job -> step."""

    def test_workflow_level_default(self):
        jobs = _workflows(
            "on:\n  pull_request:\ndefaults:\n  run:\n    working-directory: backend\n"
            "jobs:\n  lint:\n    runs-on: ubuntu-latest\n"
            "    steps:\n      - run: ruff check app/\n"
        )
        self.assertEqual(jobs[0].working_directory, "backend")
        self.assertIn("cd backend", render_script(jobs[0], "ci.yml"))

    def test_job_level_overrides_workflow(self):
        jobs = _workflows(
            "on:\n  pull_request:\ndefaults:\n  run:\n    working-directory: backend\n"
            "jobs:\n  web:\n    runs-on: ubuntu-latest\n"
            "    defaults:\n      run:\n        working-directory: frontend\n"
            "    steps:\n      - run: npm test\n"
        )
        self.assertEqual(jobs[0].working_directory, "frontend")

    def test_step_level_wins_over_job(self):
        jobs = _workflows(
            "on:\n  pull_request:\ndefaults:\n  run:\n    working-directory: backend\n"
            "jobs:\n  lint:\n    runs-on: ubuntu-latest\n    steps:\n"
            "      - run: npm test\n        working-directory: frontend\n"
        )
        script = render_script(jobs[0], "ci.yml")
        self.assertIn("cd frontend", script)
        self.assertNotIn("cd backend", script)

    def test_no_defaults_emits_no_cd(self):
        jobs = _workflows(
            "on:\n  pull_request:\njobs:\n  lint:\n    runs-on: ubuntu-latest\n"
            "    steps:\n      - run: echo hi\n"
        )
        self.assertIsNone(jobs[0].working_directory)
        self.assertNotIn("  cd ", render_script(jobs[0], "ci.yml"))

    def test_malformed_defaults_ignored(self):
        # Anti-case: `defaults: backend` (a string, not a mapping) must not crash.
        jobs = _workflows(
            "on:\n  pull_request:\ndefaults: backend\n"
            "jobs:\n  lint:\n    runs-on: ubuntu-latest\n"
            "    steps:\n      - run: echo hi\n"
        )
        self.assertIsNone(jobs[0].working_directory)

    def test_path_with_space_is_quoted(self):
        jobs = _workflows(
            "on:\n  pull_request:\ndefaults:\n  run:\n    working-directory: my app\n"
            "jobs:\n  lint:\n    runs-on: ubuntu-latest\n"
            "    steps:\n      - run: echo hi\n"
        )
        self.assertIn("cd 'my app'", render_script(jobs[0], "ci.yml"))


if __name__ == "__main__":
    unittest.main()
