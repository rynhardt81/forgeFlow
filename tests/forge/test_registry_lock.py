"""Tests for registry_ops.registry_write_lock — cross-process mutual exclusion.

Two things are being verified:

  1. Lost-update regression: without the lock, N concurrent processes each
     adding a distinct task to the same registry can stomp on each other's
     writes (classic load -> modify -> save race). With the lock in place,
     all N tasks must survive.
  2. Timeout: a process holding the lock blocks another acquirer, which
     raises RegistryLockTimeout once its deadline elapses rather than
     hanging forever.

POSIX-only (fcntl). multiprocessing on macOS/py3.8+ defaults to "spawn",
which re-imports THIS ENTIRE MODULE fresh in each child (spawn pickles a
`module.function` reference, then re-executes the module top-to-bottom to
resolve it — no inherited parent sys.path/sys.modules state). Two
consequences that shape this file:

  - Worker functions must be module-level (importable by qualified name;
    no lambdas/closures — those can't be pickled for spawn).
  - This module must NOT import the shared `conftest` helpers at module
    level. Several test dirs under tests/ (forge, wiring, dashboard) each
    have their own conftest.py with no package __init__.py, so the bare
    module name "conftest" is ambiguous once the full suite has been
    collected — a spawned child's re-exec of `from conftest import X` can
    resolve to a DIFFERENT directory's conftest.py depending on
    sys.path/sys.modules state at fork time. This caused real failures
    under the full `pytest tests/` run (import error inside the spawned
    child) even though this file passed in isolation. Fix: this file
    builds its own tiny fixture registry inline instead of importing
    conftest.make_repo/base_registry, and loads registry_ops via an
    explicit file path rather than relying on sys.path order.
"""

from __future__ import annotations

import importlib.util
import json
import multiprocessing
import sys
import time
from pathlib import Path
from types import ModuleType

import pytest

import registry_ops as ops

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="advisory lock contention tests are POSIX-only (fcntl); "
           "the msvcrt branch is best-effort and not unit-tested",
)

_REGISTRY_OPS_PATH = Path(__file__).resolve().parents[2] / "scripts" / "forge" / "registry_ops.py"


def _load_registry_ops() -> ModuleType:
    """Load registry_ops.py by explicit file path.

    Bypasses sys.path/import-name resolution entirely: under spawn's
    module re-exec, ambient sys.path order is not trustworthy (see module
    docstring). A path-based load is unambiguous regardless of what else
    pytest has collected in the parent process.
    """
    spec = importlib.util.spec_from_file_location(
        "registry_ops_lock_worker", _REGISTRY_OPS_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_minimal_repo(tmp_path: Path) -> Path:
    """Build the smallest fixture registry_write_lock tests need: one
    empty epic E1, ready for add_task to file tasks under.

    Deliberately not reusing conftest.make_repo/base_registry — see
    module docstring for why this file avoids importing conftest.
    """
    (tmp_path / "docs" / "tasks").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "epics").mkdir(parents=True, exist_ok=True)
    registry = {
        "project": "test",
        "version": "1",
        "settings": {"lockTimeoutSeconds": 3600},
        "stats": {
            "epics": {
                "total": 1, "completed": 0, "in_progress": 1,
                "blocked": 0, "ready": 0, "pending": 0,
            },
            "tasks": {
                "total": 0, "completed": 0, "in_progress": 0,
                "pr_pending": 0, "continuation": 0, "ready": 0, "pending": 0,
            },
        },
        "epics": [{"id": "E1", "status": "in_progress", "tasks": []}],
        "tasks": [],
    }
    registry_path = tmp_path / "docs" / "tasks" / "registry.json"
    registry_path.write_text(json.dumps(registry, indent=2) + "\n")
    return tmp_path


def _registry_path(repo: Path) -> Path:
    return repo / "docs" / "tasks" / "registry.json"


def _worker_add_task(registry_path_str: str, task_id: str) -> None:
    """Module-level worker: add one distinct task to the shared registry."""
    worker_ops = _load_registry_ops()
    worker_ops.add_task(
        Path(registry_path_str),
        task_id=task_id,
        epic_id="E1",
        name=f"task {task_id}",
    )


def _worker_hold_lock(registry_path_str: str, hold_seconds: float, ready_flag: str) -> None:
    """Module-level worker: acquire the lock and hold it for hold_seconds.

    Writes `ready_flag` to disk once the lock is actually held, so the
    parent can synchronize on real acquisition rather than guessing with
    a sleep.
    """
    worker_ops = _load_registry_ops()
    with worker_ops.registry_write_lock(Path(registry_path_str)):
        Path(ready_flag).write_text("ready")
        time.sleep(hold_seconds)


# --- Lost-update regression -------------------------------------------------


def test_concurrent_add_task_no_lost_updates(tmp_path):
    """8 processes each add a distinct task; all 8 must survive.

    Without registry_write_lock, this test flakes: two workers can both
    load the registry before either saves, and the second save clobbers
    the first worker's appended task (last-writer-wins on the whole
    document). The lock makes each add_task's load->modify->save atomic
    with respect to other writers. (Verified manually against a
    lock-disabled copy of registry_ops: the unlocked version reliably
    drops 2-4 of 8 tasks per run; this test is green 5/5 with the real
    lock in place.)
    """
    repo = _make_minimal_repo(tmp_path)
    registry_path = _registry_path(repo)
    task_ids = [f"T{i}" for i in range(8)]

    ctx = multiprocessing.get_context("spawn")
    procs = [
        ctx.Process(target=_worker_add_task, args=(str(registry_path), tid))
        for tid in task_ids
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=30)
        assert p.exitcode == 0, f"worker for a task exited with {p.exitcode}"

    final = json.loads(registry_path.read_text())
    final_ids = {t["id"] for t in final.get("tasks", [])}
    assert final_ids == set(task_ids), (
        f"lost update(s): expected {sorted(task_ids)}, got {sorted(final_ids)}"
    )


# --- Timeout -----------------------------------------------------------------


def test_lock_timeout_raises_when_held(tmp_path):
    """A second acquirer with a short timeout raises RegistryLockTimeout
    quickly rather than hanging, while another process holds the lock.
    """
    repo = _make_minimal_repo(tmp_path)
    registry_path = _registry_path(repo)
    ready_flag = tmp_path / "holder_ready.flag"

    ctx = multiprocessing.get_context("spawn")
    holder = ctx.Process(
        target=_worker_hold_lock, args=(str(registry_path), 2.0, str(ready_flag))
    )
    holder.start()
    try:
        deadline = time.monotonic() + 10
        while not ready_flag.exists():
            assert time.monotonic() < deadline, "holder never signalled lock acquired"
            time.sleep(0.02)

        start = time.monotonic()
        with pytest.raises(ops.RegistryLockTimeout):
            with ops.registry_write_lock(registry_path, timeout=0.3):
                pass  # pragma: no cover — should never be reached
        elapsed = time.monotonic() - start
        assert elapsed < 2.0, f"timeout took {elapsed:.2f}s, expected ~0.3s"
    finally:
        holder.join(timeout=10)
