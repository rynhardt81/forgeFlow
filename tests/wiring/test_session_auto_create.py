"""Tests for the SessionStart auto-create-session-file behavior.

Closes the gap surfaced 2026-05-12: the 'Session Protocol First' rule in
`skills/reflect/SKILL.md` was aspirational — nothing actually created the
session file. After this change, `hooks/session/session-context.py`
auto-creates a minimal session file when `active/` is empty.

These tests run the hook against synthetic tmp projects and assert the
file lands in the right place with the right shape, and that running the
hook again is a no-op (does not duplicate).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK = REPO_ROOT / "hooks" / "session" / "session-context.py"


def _make_project(layout: str) -> Path:
    """Create a tmp project. `layout` is 'consumer' (.claude/) or 'dev' (root)."""
    tmp = Path(tempfile.mkdtemp())
    subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@x", "-c", "user.name=t",
         "commit", "-q", "--allow-empty", "-m", "base"],
        cwd=tmp, check=True,
    )
    if layout == "consumer":
        (tmp / ".claude" / "memories" / "sessions" / "active").mkdir(parents=True)
        (tmp / ".claude" / "memories" / "sessions" / "completed").mkdir(parents=True)
    return tmp


def _run_hook(project: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = str(project)
    return subprocess.run(
        ["python3", str(HOOK)],
        cwd=project, env=env, capture_output=True, text=True, check=False,
    )


def _active_dir(project: Path, layout: str) -> Path:
    if layout == "consumer":
        return project / ".claude" / "memories" / "sessions" / "active"
    return project / "memories" / "sessions" / "active"


@pytest.fixture
def consumer_project():
    p = _make_project("consumer")
    yield p
    shutil.rmtree(p, ignore_errors=True)


def test_auto_create_when_active_empty(consumer_project):
    """Hook creates a session file when active/ is empty."""
    active = _active_dir(consumer_project, "consumer")
    assert not list(active.glob("session-*.md"))  # baseline

    result = _run_hook(consumer_project)
    assert result.returncode == 0, result.stderr

    sessions = sorted(active.glob("session-*.md"))
    assert len(sessions) == 1, f"expected exactly one session file, got {sessions}"
    assert sessions[0].name.startswith("session-")
    assert sessions[0].name.endswith(".md")


def test_session_file_shape(consumer_project):
    """Auto-created file has the fields downstream hooks parse for."""
    _run_hook(consumer_project)
    active = _active_dir(consumer_project, "consumer")
    sessions = list(active.glob("session-*.md"))
    assert len(sessions) == 1
    content = sessions[0].read_text(encoding="utf-8")

    # Header line with the session ID
    assert re.search(r"^# Session \d{8}-\d{6}-[a-z0-9]{4}$", content, re.MULTILINE), (
        f"missing session header. Content head:\n{content[:200]}"
    )

    # Required scaffolding sections (the hook itself + /reflect rely on these)
    for required in [
        "**Started**:",
        "**Branch**:",
        "**Status**: active",
        "**Created by**: session-context.py auto-create",
        "## Scope Declaration",
        "## Conflict Check",
        "## Active Skill",
        "## Active Agent",
    ]:
        assert required in content, f"missing required scaffolding: {required!r}"


def test_idempotent_on_rerun(consumer_project):
    """A second hook invocation does not create a duplicate file."""
    _run_hook(consumer_project)
    active = _active_dir(consumer_project, "consumer")
    first = sorted(active.glob("session-*.md"))
    assert len(first) == 1

    # Different filename if duplicate is created (random suffix + timestamp)
    _run_hook(consumer_project)
    second = sorted(active.glob("session-*.md"))
    assert second == first, f"hook duplicated session file: {second}"


def test_session_id_in_stdout(consumer_project):
    """Hook prints S:<id> for the freshly-created file (downstream context)."""
    result = _run_hook(consumer_project)
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "S:" in out and "S:NONE" not in out, (
        f"hook should report a real session id, not S:NONE. stdout:\n{out}"
    )
    assert re.search(r"S:\d{8}-\d{6}-[a-z0-9]{4}", out), (
        f"S: line did not match session-id shape. stdout:\n{out}"
    )


def test_creates_active_dir_if_missing():
    """If .claude/memories/sessions/active/ does not exist, hook creates it."""
    tmp = Path(tempfile.mkdtemp())
    try:
        subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)
        subprocess.run(
            ["git", "-c", "user.email=t@x", "-c", "user.name=t",
             "commit", "-q", "--allow-empty", "-m", "base"],
            cwd=tmp, check=True,
        )
        # No .claude/ at all — framework-dev layout fallback should kick in
        # and write under <project_root>/memories/sessions/active/
        result = _run_hook(tmp)
        assert result.returncode == 0, result.stderr

        # Either layout is acceptable; framework-dev layout is the fallback
        # when .claude/memories doesn't exist.
        consumer = tmp / ".claude" / "memories" / "sessions" / "active"
        dev = tmp / "memories" / "sessions" / "active"
        assert (
            list(consumer.glob("session-*.md")) or list(dev.glob("session-*.md"))
        ), f"no session file created under either layout (consumer={consumer.exists()}, dev={dev.exists()})"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
