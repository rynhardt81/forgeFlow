"""Regression: `task ls` must not crash on a registry that mixes v3 word
priorities ("critical", "high", ...) and None with v4 ints.

Reproduced 2026-09-05 against a consumer install (181 word-valued tasks,
4 None) right after a framework refresh: v4.4.0's sort key compared the raw
field and raised TypeError. The rank helper is the single comparison path.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from conftest import base_registry, make_repo

import registry_ops as ops

FORGE = Path(__file__).resolve().parents[2] / "scripts" / "forge" / "forge.py"


def _run(repo, *args):
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(repo)}
    return subprocess.run(
        [sys.executable, str(FORGE), *args],
        cwd=repo, capture_output=True, text=True, env=env,
    )


def _ids(stdout):
    return [
        line.split()[0] for line in stdout.splitlines()
        if line.split() and line.split()[0].startswith("T")
    ]


def _task(tid, prio):
    return {"id": tid, "status": "ready", "epic": "E1", "priority": prio,
            "dependencies": [], "lock": None, "createdAt": "2026-01-01T00:00:00Z"}


def test_priority_rank_orders_words_ints_and_none():
    assert ops.priority_rank("critical") < ops.priority_rank("high")
    assert ops.priority_rank("high") < ops.priority_rank("medium")
    assert ops.priority_rank("medium") < ops.priority_rank("low")
    assert ops.priority_rank(2) == 2
    assert ops.priority_rank("2") == 2
    assert ops.priority_rank(None) == ops.DEFAULT_EPIC_PRIORITY
    assert ops.priority_rank("weird") == ops.DEFAULT_EPIC_PRIORITY


def test_task_ls_survives_mixed_priority_shapes(tmp_path):
    repo = make_repo(tmp_path, base_registry(
        epics=[{"id": "E1", "name": "Mixed", "status": "in_progress",
                "priority": 1, "tasks": ["T1", "T2", "T3", "T4"]}],
        tasks=[_task("T1", "low"), _task("T2", None),
               _task("T3", "critical"), _task("T4", 2)],
    ))
    r = _run(repo, "task", "ls")
    assert r.returncode == 0, r.stderr
    assert "TypeError" not in r.stderr
    # critical(1) and None(1) tie on rank, then id; int 2 and "low"(4) follow.
    assert _ids(r.stdout) == ["T2", "T3", "T4", "T1"]
