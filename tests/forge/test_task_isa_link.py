"""Tests for the task→ISA link: set_task_isa, task_has_isa, and the
advisory task-without-isa consistency check. (T302)

These cover the 'track + nudge' tightening — the registry records an ISA
path, a helper resolves spec-state from registry OR disk, and the
consistency checker reports (never auto-fixes) an in_progress task with no
ISA. The CLI lock-nudge itself is exercised via cmd_lock in the forge tests;
here we cover the underlying primitives the nudge and checker rely on.
"""

from __future__ import annotations

import json

import registry_ops as ops
import check_consistency as cc
from conftest import base_registry, make_repo


def _registry_path(repo):
    return repo / "docs" / "tasks" / "registry.json"


def _read(repo):
    return json.loads(_registry_path(repo).read_text())


def _make_isa_on_disk(repo, task_id):
    isa = ops.task_isa_path(repo, task_id)
    isa.parent.mkdir(parents=True, exist_ok=True)
    isa.write_text("# ISA\n")
    return isa


# --- set_task_isa --------------------------------------------------------


def test_set_task_isa_records_path(tmp_path):
    repo = make_repo(tmp_path, base_registry(
        epics=[{"id": "E1", "status": "in_progress", "tasks": ["T1"]}],
        tasks=[{"id": "T1", "epic": "E1", "name": "Foo", "status": "ready"}],
    ))
    ops.set_task_isa(_registry_path(repo), "T1", "docs/tasks/T1/ISA.md")
    out = _read(repo)
    assert out["tasks"][0]["isa"] == "docs/tasks/T1/ISA.md"


def test_set_task_isa_is_idempotent(tmp_path):
    repo = make_repo(tmp_path, base_registry(
        epics=[{"id": "E1", "status": "in_progress", "tasks": ["T1"]}],
        tasks=[{"id": "T1", "epic": "E1", "name": "Foo", "status": "ready"}],
    ))
    p = "docs/tasks/T1/ISA.md"
    ops.set_task_isa(_registry_path(repo), "T1", p)
    ops.set_task_isa(_registry_path(repo), "T1", p)
    assert _read(repo)["tasks"][0]["isa"] == p


# --- task_has_isa --------------------------------------------------------


def test_task_has_isa_true_from_registry_field(tmp_path):
    repo = make_repo(tmp_path, base_registry())
    task = {"id": "T1", "isa": "docs/tasks/T1/ISA.md"}
    assert ops.task_has_isa(repo, task) is True


def test_task_has_isa_true_from_disk_fallback(tmp_path):
    repo = make_repo(tmp_path, base_registry())
    _make_isa_on_disk(repo, "T1")
    task = {"id": "T1"}  # no registry field, but ISA on disk
    assert ops.task_has_isa(repo, task) is True


def test_task_has_isa_false_when_absent(tmp_path):
    repo = make_repo(tmp_path, base_registry())
    task = {"id": "T1"}
    assert ops.task_has_isa(repo, task) is False


# --- backward compatibility (Anti: ISC-4) --------------------------------


def test_registry_with_no_isa_field_still_operates(tmp_path):
    # A pre-existing registry where no task has ever carried an `isa` field.
    repo = make_repo(tmp_path, base_registry(
        epics=[{"id": "E1", "status": "in_progress", "tasks": ["T1"]}],
        tasks=[{"id": "T1", "epic": "E1", "name": "Foo", "status": "ready"}],
    ))
    # Normal ops keep working; absence of `isa` is simply treated as no-ISA.
    task = ops.find_task(_read(repo), "T1")
    assert "isa" not in task
    assert ops.task_has_isa(repo, task) is False


# --- advisory consistency check ------------------------------------------


def test_check_fires_on_in_progress_without_isa(tmp_path):
    repo = make_repo(tmp_path, base_registry(
        tasks=[{"id": "T1", "epic": "E1", "name": "Foo",
                "status": "in_progress"}],
    ))
    findings = cc.check_task_without_isa(_read(repo), repo)
    assert len(findings) == 1
    f = findings[0]
    assert f.cls == cc.CLS_TASK_WITHOUT_ISA
    assert f.severity == cc.SEV_INFO
    assert f.auto_fixable is False  # Anti: report-only, never auto-fixed
    assert f.target == "T1"


def test_check_silent_when_isa_present_via_field(tmp_path):
    repo = make_repo(tmp_path, base_registry(
        tasks=[{"id": "T1", "epic": "E1", "name": "Foo",
                "status": "in_progress", "isa": "docs/tasks/T1/ISA.md"}],
    ))
    assert cc.check_task_without_isa(_read(repo), repo) == []


def test_check_silent_when_isa_present_on_disk(tmp_path):
    repo = make_repo(tmp_path, base_registry(
        tasks=[{"id": "T1", "epic": "E1", "name": "Foo",
                "status": "in_progress"}],
    ))
    _make_isa_on_disk(repo, "T1")
    assert cc.check_task_without_isa(_read(repo), repo) == []


def test_check_does_not_fire_on_non_started_tasks(tmp_path):
    # Backlog quiet: ready/pending/completed without ISA do NOT nudge.
    repo = make_repo(tmp_path, base_registry(
        tasks=[
            {"id": "T1", "epic": "E1", "name": "A", "status": "ready"},
            {"id": "T2", "epic": "E1", "name": "B", "status": "pending"},
            {"id": "T3", "epic": "E1", "name": "C", "status": "completed"},
        ],
    ))
    assert cc.check_task_without_isa(_read(repo), repo) == []
