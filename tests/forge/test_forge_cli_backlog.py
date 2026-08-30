"""CLI-level tests for backlog-aware task listing and promotion guidance."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from conftest import base_registry, make_repo

FORGE = Path(__file__).resolve().parents[2] / "scripts" / "forge" / "forge.py"


def _run(repo, *args):
    # forge.py resolves project root from the SCRIPT's location, not cwd
    # (forge.py:56), so cwd alone would point it at this repo's real
    # registry. CLAUDE_PROJECT_DIR is the sanctioned override.
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(repo)}
    return subprocess.run(
        [sys.executable, str(FORGE), *args],
        cwd=repo, capture_output=True, text=True, env=env,
    )


def _ids(stdout):
    """Task ids from a `task ls` listing (each line is lock-prefixed)."""
    out = []
    for line in stdout.splitlines():
        parts = line.strip().split()
        if parts and parts[0].startswith("T") and parts[0][1:].isdigit():
            out.append(parts[0])
    return out


def _repo(tmp_path):
    return make_repo(tmp_path, base_registry(
        epics=[
            {"id": "E1", "name": "Core", "status": "in_progress", "priority": 2,
             "tasks": ["T2", "T3"]},
            {"id": "E0", "name": "Base", "status": "in_progress", "priority": 1,
             "tasks": ["T1"]},
            {"id": "E99", "name": "Hardening", "status": "backlog", "priority": 9,
             "tasks": ["T9"]},
        ],
        tasks=[
            {"id": "T3", "status": "ready", "epic": "E1", "priority": 2,
             "dependencies": [], "lock": None, "createdAt": "2026-01-01T00:00:00Z"},
            {"id": "T2", "status": "ready", "epic": "E1", "priority": 1,
             "dependencies": [], "lock": None, "createdAt": "2026-01-01T00:00:00Z"},
            {"id": "T1", "status": "ready", "epic": "E0", "priority": 1,
             "dependencies": [], "lock": None, "createdAt": "2026-01-01T00:00:00Z"},
            {"id": "T9", "status": "ready", "epic": "E99", "priority": 1,
             "dependencies": [], "lock": None, "createdAt": "2026-01-01T00:00:00Z"},
        ],
    ))


def test_ls_ready_hides_backlog_and_sorts(tmp_path):
    r = _run(_repo(tmp_path), "task", "ls", "--ready")
    assert r.returncode == 0, r.stderr
    # epic priority 1 (E0) before 2 (E1); task priority within the epic
    assert _ids(r.stdout) == ["T1", "T2", "T3"]
    assert "T9" not in r.stdout


def test_ls_ready_prints_deferred_footer(tmp_path):
    r = _run(_repo(tmp_path), "task", "ls", "--ready")
    assert "1 deferred in E99-hardening" in r.stdout


def test_ls_all_shows_backlog_and_no_footer(tmp_path):
    r = _run(_repo(tmp_path), "task", "ls", "--ready", "--all")
    assert "T9" in r.stdout
    assert "deferred in" not in r.stdout


def test_ls_json_has_no_footer(tmp_path):
    r = _run(_repo(tmp_path), "task", "ls", "--ready", "--json")
    json.loads(r.stdout)          # must parse -- a footer would break it
    assert "deferred in" not in r.stdout


def test_ls_footer_absent_when_nothing_deferred(tmp_path):
    repo = make_repo(tmp_path, base_registry(
        epics=[{"id": "E1", "name": "Core", "status": "in_progress", "tasks": ["T1"]}],
        tasks=[{"id": "T1", "status": "ready", "epic": "E1",
                "dependencies": [], "lock": None}],
    ))
    r = _run(repo, "task", "ls", "--ready")
    assert "deferred" not in r.stdout


def test_ls_footer_shows_even_when_no_ready_work_left(tmp_path):
    """All queue work done and 1 parked -- this is exactly when you want the count."""
    repo = make_repo(tmp_path, base_registry(
        epics=[
            {"id": "E1", "name": "Core", "status": "in_progress", "tasks": ["T1"]},
            {"id": "E99", "name": "Hardening", "status": "backlog", "tasks": ["T9"]},
        ],
        tasks=[
            {"id": "T1", "status": "completed", "epic": "E1", "dependencies": [], "lock": None},
            {"id": "T9", "status": "ready", "epic": "E99", "dependencies": [], "lock": None,
             "createdAt": "2026-01-01T00:00:00Z"},
        ],
    ))
    r = _run(repo, "task", "ls", "--ready")
    assert "(no tasks match)" in r.stdout
    assert "1 deferred in E99-hardening" in r.stdout


def test_ls_no_promotion_recommendation_in_v1(tmp_path):
    """Spec 3.3: count-only. It reports, it never tells you when to act."""
    out = _run(_repo(tmp_path), "task", "ls", "--ready").stdout.lower()
    for nag in ("should", "consider", "overdue", "recommend"):
        assert nag not in out


def test_ls_exit_code_unaffected_by_footer(tmp_path):
    assert _run(_repo(tmp_path), "task", "ls", "--ready").returncode == 0
