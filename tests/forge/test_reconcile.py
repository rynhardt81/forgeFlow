"""registry_ops.reconcile owns every auto-fix and their order (T963).

check_consistency only detects; `--fix` calls reconcile. These tests drive
reconcile directly, then once through the checker's CLI.
"""

from __future__ import annotations

import inspect
import json

import check_consistency as cc
import registry_ops as ops
from conftest import base_registry, make_repo

OLD = "2000-01-01T00:00:00Z"


def _repo(tmp_path, tasks, files):
    reg = base_registry(tasks=tasks)
    root = make_repo(tmp_path, reg, task_files=files)
    return root, json.loads((root / "docs/tasks/registry.json").read_text())


def _fm(root, tid):
    return next(root.rglob(f"{tid}-fixture.md")).read_text()


def test_checker_defines_no_fixers():
    names = [n for n, f in inspect.getmembers(cc, inspect.isfunction) if f.__module__ == cc.__name__]
    assert not [n for n in names if n.startswith("fix_") or n == "apply_fixes"], names


def test_flip_is_mirrored_and_status_compared_case_insensitively(tmp_path):
    root, reg = _repo(tmp_path, [
        {"id": "T1", "status": "completed", "dependencies": []},
        {"id": "T2", "status": "pending", "dependencies": ["T1"]},
        {"id": "T3", "status": "ready", "dependencies": []},
    ], {
        "E1/T1": {"id": "T1", "status": "completed"},
        "E1/T2": {"id": "T2", "status": "pending"},
        "E1/T3": {"id": "T3", "status": "Ready"},
    })
    reg_changed, files_changed = ops.reconcile(reg, root, lock_timeout=3600)
    assert (reg_changed, files_changed) == (True, True)
    assert ops.find_task(reg, "T2")["status"] == "ready"
    assert "status: ready" in _fm(root, "T2")
    assert "status: Ready" in _fm(root, "T3"), "case-only difference is not drift"


def test_stale_lock_cleared_status_kept(tmp_path):
    root, reg = _repo(tmp_path, [
        {"id": "T1", "status": "in_progress", "dependencies": [], "lock": {"session": "s", "lockedAt": OLD}},
    ], {"E1/T1": {"id": "T1", "status": "in_progress"}})
    ops.reconcile(reg, root, lock_timeout=3600)
    t = ops.find_task(reg, "T1")
    assert t["lock"] is None and t["status"] == "in_progress"


def test_stats_last_and_extra_keys_survive(tmp_path):
    root, reg = _repo(tmp_path, [
        {"id": "T1", "status": "completed", "dependencies": []},
        {"id": "T2", "status": "pending", "dependencies": ["T1"]},
    ], {})
    reg["stats"]["custom"] = 7
    ops.reconcile(reg, root, lock_timeout=3600)
    assert reg["stats"]["tasks"]["ready"] == 1, "stats must count the flip made earlier in the same pass"
    assert reg["stats"]["custom"] == 7


def test_name_mirrored_only_where_the_field_exists(tmp_path):
    root, reg = _repo(tmp_path, [
        {"id": "T1", "status": "ready", "dependencies": [], "name": "Registry name"},
        {"id": "T2", "status": "ready", "dependencies": [], "name": "Other"},
    ], {
        "E1/T1": {"id": "T1", "status": "ready", "name": "Old name"},
        "E1/T2": {"id": "T2", "status": "ready"},
    })
    ops.reconcile(reg, root, lock_timeout=3600)
    assert "name: Registry name" in _fm(root, "T1")
    assert "name:" not in _fm(root, "T2")


def test_clean_registry_reports_no_change(tmp_path):
    root, reg = _repo(tmp_path, [{"id": "T1", "status": "ready", "dependencies": []}],
                      {"E1/T1": {"id": "T1", "status": "ready"}})
    ops.reconcile(reg, root, lock_timeout=3600)
    assert ops.reconcile(reg, root, lock_timeout=3600) == (False, False)


def test_cli_fix_goes_through_reconcile(tmp_path, monkeypatch):
    root, _ = _repo(tmp_path, [
        {"id": "T1", "status": "completed", "dependencies": []},
        {"id": "T2", "status": "pending", "dependencies": ["T1"]},
    ], {"E1/T2": {"id": "T2", "status": "pending"}})
    calls = []
    real = ops.reconcile
    monkeypatch.setattr(ops, "reconcile", lambda *a, **k: calls.append(1) or real(*a, **k))
    assert cc.main(["--fix", "--project-root", str(root)]) == 0
    assert calls
    saved = json.loads((root / "docs/tasks/registry.json").read_text())
    assert ops.find_task(saved, "T2")["status"] == "ready"
