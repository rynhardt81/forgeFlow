"""T918: the test-lock hook must block the escape and nothing else.

/fix-bug's discipline is reproduce -> failing test -> commit it -> fix source.
The escape is editing the test until it passes: the suite goes green and the bug
ships. fix_bug_regression.py only notices after the fact.

The three cases that matter are the acceptance criteria: the locked test is
denied, the source under test is not, and an absent or empty lock blocks nothing
— that last one is the common case, and a hook that fails closed there would
make every project that installed it unusable.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK = (REPO_ROOT / "skills" / "damage-control" / "hooks" /
        "damage-control-python" / "test-lock-damage-control.py")


def run(tmp: Path, tool: str, file_path: str) -> subprocess.CompletedProcess:
    payload = {"tool_name": tool, "tool_input": {"file_path": str(file_path)}}
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload), text=True, capture_output=True,
        env={"PATH": "/usr/bin:/bin", "CLAUDE_PROJECT_DIR": str(tmp)},
    )


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / ".claude").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src").mkdir()
    (tmp_path / "tests" / "test_bug.py").write_text("def test_bug(): assert False\n")
    (tmp_path / "src" / "thing.py").write_text("def thing(): ...\n")
    return tmp_path


def test_locked_test_file_is_denied_with_a_named_reason(project: Path):
    (project / ".claude" / ".test-lock").write_text("tests/test_bug.py\n")
    r = run(project, "Edit", project / "tests" / "test_bug.py")
    assert r.returncode == 2, r.stdout + r.stderr
    assert "tests/test_bug.py" in r.stderr, "block message must name the file"
    assert ".test-lock" in r.stderr, "block message must name how to clear the lock"


def test_source_under_test_still_edits_freely(project: Path):
    (project / ".claude" / ".test-lock").write_text("tests/test_bug.py\n")
    r = run(project, "Edit", project / "src" / "thing.py")
    assert r.returncode == 0, "the fix itself must not be blocked: " + r.stderr


@pytest.mark.parametrize(
    "content", ["", "\n\n", "# only a comment\n"],
    ids=["empty", "blank-lines", "comments-only"],
)
def test_empty_lock_blocks_nothing(project: Path, content: str):
    (project / ".claude" / ".test-lock").write_text(content)
    r = run(project, "Edit", project / "tests" / "test_bug.py")
    assert r.returncode == 0, "an empty lock must not block: " + r.stderr


def test_absent_lock_blocks_nothing(project: Path):
    r = run(project, "Edit", project / "tests" / "test_bug.py")
    assert r.returncode == 0, "no lock file means no enforcement: " + r.stderr


def test_non_write_tools_are_ignored(project: Path):
    (project / ".claude" / ".test-lock").write_text("tests/test_bug.py\n")
    payload = {"tool_name": "Read", "tool_input": {"file_path": "tests/test_bug.py"}}
    r = subprocess.run(
        [sys.executable, str(HOOK)], input=json.dumps(payload), text=True,
        capture_output=True,
        env={"PATH": "/usr/bin:/bin", "CLAUDE_PROJECT_DIR": str(project)},
    )
    assert r.returncode == 0, "reading a locked test is fine"


def test_multiedit_targets_are_checked(project: Path):
    """MultiEdit carries its paths in an edits list, not file_path — a hook that
    only reads file_path would wave the whole escape through."""
    (project / ".claude" / ".test-lock").write_text("tests/test_bug.py\n")
    payload = {"tool_name": "MultiEdit", "tool_input": {
        "edits": [{"file_path": str(project / "tests" / "test_bug.py")}]}}
    r = subprocess.run(
        [sys.executable, str(HOOK)], input=json.dumps(payload), text=True,
        capture_output=True,
        env={"PATH": "/usr/bin:/bin", "CLAUDE_PROJECT_DIR": str(project)},
    )
    assert r.returncode == 2, "MultiEdit must not bypass the lock"
