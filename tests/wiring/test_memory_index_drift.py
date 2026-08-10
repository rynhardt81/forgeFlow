"""Tests for the project-memory index drift warning.

Closes the gap filed 2026-08-10 (`docs/debug/2026-08-10-project-memory-index-
never-healed.md`): `docs/project-memory/index.md` is the only file the
SessionStart hook injects as the knowledge catalog, and when it was missing or
still a skeleton the hook said nothing — so a project could accumulate real
entries for months while none of them ever reached a session.

Three states, one assertion each: entries without a usable index must warn, a
real index must inject, and a pristine install must stay silent.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK = REPO_ROOT / "hooks" / "session" / "session-context.py"
SKELETON = "<!-- /remember appends a one-line pointer here per capture -->\n"


@pytest.fixture()
def project():
    tmp = Path(tempfile.mkdtemp())
    subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)
    (tmp / "docs" / "project-memory").mkdir(parents=True)
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


def _run_hook(project: Path) -> str:
    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = str(project)
    return subprocess.run(
        ["python3", str(HOOK)],
        cwd=project, env=env, capture_output=True, text=True, check=False,
    ).stdout


def test_entries_without_index_warn(project):
    (project / "docs" / "project-memory" / "bugs.md").write_text(
        "# Bugs\n\n## first\n## second\n", encoding="utf-8"
    )
    out = _run_hook(project)
    assert "project memory: 2 entries exist" in out
    assert "=== PROJECT MEMORY ===" not in out


def test_skeleton_index_still_warns(project):
    """The state a refresh leaves behind: index present, catalog empty."""
    (project / "docs" / "project-memory" / "bugs.md").write_text(
        "# Bugs\n\n## first\n", encoding="utf-8"
    )
    (project / "docs" / "project-memory" / "index.md").write_text(
        "# Project Memory — Index\n\n" + SKELETON, encoding="utf-8"
    )
    out = _run_hook(project)
    assert "project memory: 1 entries exist" in out
    assert "=== PROJECT MEMORY ===" not in out


def test_populated_index_injects_and_does_not_warn(project):
    (project / "docs" / "project-memory" / "bugs.md").write_text(
        "# Bugs\n\n## first\n", encoding="utf-8"
    )
    (project / "docs" / "project-memory" / "index.md").write_text(
        "# Project Memory — Index\n\n" + SKELETON + "- 2026-08-10 [bug] first\n",
        encoding="utf-8",
    )
    out = _run_hook(project)
    assert "=== PROJECT MEMORY ===" in out
    assert "project memory:" not in out


def test_pristine_install_is_silent(project):
    """No entries anywhere — no warning, and no empty catalog injected."""
    (project / "docs" / "project-memory" / "index.md").write_text(
        "# Project Memory — Index\n\n" + SKELETON, encoding="utf-8"
    )
    out = _run_hook(project)
    assert "project memory:" not in out
    assert "=== PROJECT MEMORY ===" not in out
