"""Tests for create_task_body_file / scaffold_task_isa / reconcile_task_files.

The user-visible contract these guard:

  - `forge task add` (default) creates BOTH a registry entry AND a body
    file at `docs/epics/<epic>-<slug>/tasks/<task-id>-<slug>.md`.
  - `forge task add --isa` additionally scaffolds an ISA at
    `docs/tasks/<task-id>/ISA.md`.
  - `forge task reconcile-files` finds registry-tracked tasks with no body
    file on disk and (with --apply) creates stub bodies marked as such.

These functions are pure helpers — the CLI composes them around the
atomic registry primitive `add_task()`.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import registry_ops as ops
from conftest import base_registry, make_repo


def _registry_path(repo: Path) -> Path:
    return repo / "docs" / "tasks" / "registry.json"


# --- create_task_body_file ----------------------------------------------

def test_body_file_lands_under_existing_epic_dir(tmp_path):
    repo = make_repo(tmp_path, base_registry(
        epics=[{"id": "E11", "status": "in_progress", "tasks": []}]))
    # Simulate an existing epic dir from a previous /new-project run
    (repo / "docs" / "epics" / "E11-datatable-enhancement" / "tasks").mkdir(parents=True)

    task = ops.add_task(_registry_path(repo), task_id="T100", epic_id="E11",
                       name="Wire metrics dashboard")
    body_path = ops.create_task_body_file(repo, task)

    assert body_path.exists()
    assert body_path.parent.name == "tasks"
    assert body_path.parent.parent.name == "E11-datatable-enhancement"
    assert body_path.name == "T100-wire-metrics-dashboard.md"


def test_body_file_creates_untitled_epic_dir_when_missing(tmp_path):
    """If no epic dir exists, _resolve_epic_dir creates `<epic>-untitled/`."""
    repo = make_repo(tmp_path, base_registry(
        epics=[{"id": "E42", "status": "in_progress", "tasks": []}]))
    task = ops.add_task(_registry_path(repo), task_id="T1", epic_id="E42", name="bootstrap")
    body_path = ops.create_task_body_file(repo, task)

    assert body_path.exists()
    assert body_path.parent.parent.name == "E42-untitled"


def test_body_file_frontmatter_matches_task(tmp_path):
    repo = make_repo(tmp_path, base_registry(
        epics=[{"id": "E1", "status": "in_progress", "tasks": []}]))
    (repo / "docs" / "epics" / "E1-fixture" / "tasks").mkdir(parents=True)

    task = ops.add_task(_registry_path(repo), task_id="T7", epic_id="E1",
                       name="rename helper", priority=2, category="A",
                       scope_directories=["src/helpers/"])
    body_path = ops.create_task_body_file(repo, task)
    content = body_path.read_text(encoding="utf-8")

    assert "id: T7" in content
    assert "epic: E1" in content
    assert "name: rename helper" in content
    assert "priority: 2" in content
    assert "category: A" in content
    assert "src/helpers/" in content
    assert "# T7 — rename helper" in content


def test_body_file_refuses_to_clobber_unless_overwrite(tmp_path):
    repo = make_repo(tmp_path, base_registry(
        epics=[{"id": "E1", "status": "in_progress", "tasks": []}]))
    (repo / "docs" / "epics" / "E1-fixture" / "tasks").mkdir(parents=True)

    task = ops.add_task(_registry_path(repo), task_id="T1", epic_id="E1", name="hello")
    path1 = ops.create_task_body_file(repo, task)
    assert path1.exists()

    with pytest.raises(FileExistsError):
        ops.create_task_body_file(repo, task)

    # Overwrite path
    ops.create_task_body_file(repo, task, overwrite=True)


def test_body_file_stub_marker_present(tmp_path):
    repo = make_repo(tmp_path, base_registry(
        epics=[{"id": "E1", "status": "in_progress", "tasks": []}]))
    (repo / "docs" / "epics" / "E1-fixture" / "tasks").mkdir(parents=True)

    task = ops.add_task(_registry_path(repo), task_id="T1", epic_id="E1", name="reconciled")
    body_path = ops.create_task_body_file(repo, task, stub=True)

    text = body_path.read_text(encoding="utf-8")
    assert "STUB" in text
    assert "reconcile-files" in text


# --- scaffold_task_isa --------------------------------------------------

def test_scaffold_isa_writes_to_docs_tasks(tmp_path):
    repo = make_repo(tmp_path, base_registry(
        epics=[{"id": "E1", "status": "in_progress", "tasks": []}]))
    task = ops.add_task(_registry_path(repo), task_id="T42", epic_id="E1",
                       name="atomic refactor")

    isa_path = ops.scaffold_task_isa(repo, task)

    assert isa_path == repo / "docs" / "tasks" / "T42" / "ISA.md"
    assert isa_path.exists()


def test_isa_frontmatter_carries_task_id_and_name(tmp_path):
    repo = make_repo(tmp_path, base_registry(
        epics=[{"id": "E1", "status": "in_progress", "tasks": []}]))
    task = ops.add_task(_registry_path(repo), task_id="T9", epic_id="E1",
                       name="dashboard root fix")
    isa_path = ops.scaffold_task_isa(repo, task)

    content = isa_path.read_text(encoding="utf-8")
    assert "id: T9" in content
    assert "kind: task-isa" in content
    assert "name: dashboard root fix" in content
    assert "phase: observe" in content


def test_isa_refuses_to_clobber_unless_overwrite(tmp_path):
    repo = make_repo(tmp_path, base_registry(
        epics=[{"id": "E1", "status": "in_progress", "tasks": []}]))
    task = ops.add_task(_registry_path(repo), task_id="T1", epic_id="E1", name="x")
    ops.scaffold_task_isa(repo, task)

    with pytest.raises(FileExistsError):
        ops.scaffold_task_isa(repo, task)

    ops.scaffold_task_isa(repo, task, overwrite=True)


# --- reconcile_task_files ----------------------------------------------

def test_reconcile_dry_run_lists_missing_does_not_create(tmp_path):
    repo = make_repo(tmp_path, base_registry(
        epics=[{"id": "E1", "status": "in_progress", "tasks": []}]))
    # Add tasks via the registry primitive directly (bypassing the CLI body
    # creation) so we simulate the v2→v3 registry/file drift state.
    ops.add_task(_registry_path(repo), task_id="T1", epic_id="E1", name="missing one")
    ops.add_task(_registry_path(repo), task_id="T2", epic_id="E1", name="missing two")

    result = ops.reconcile_task_files(_registry_path(repo), repo, apply=False)
    assert set(result["missing"]) == {"T1", "T2"}
    assert result["created"] == []
    assert (repo / "docs" / "epics" / "E1-untitled").exists() is False, \
        "dry-run must not create epic dirs"


def test_reconcile_apply_creates_stub_files(tmp_path):
    repo = make_repo(tmp_path, base_registry(
        epics=[{"id": "E1", "status": "in_progress", "tasks": []}]))
    (repo / "docs" / "epics" / "E1-fixture" / "tasks").mkdir(parents=True)
    ops.add_task(_registry_path(repo), task_id="T1", epic_id="E1", name="alpha")
    ops.add_task(_registry_path(repo), task_id="T2", epic_id="E1", name="beta")

    result = ops.reconcile_task_files(_registry_path(repo), repo, apply=True)
    assert set(result["missing"]) == {"T1", "T2"}
    assert len(result["created"]) == 2
    for path_str in result["created"]:
        full = repo / path_str
        assert full.exists()
        assert "STUB" in full.read_text(encoding="utf-8")


def test_reconcile_skips_tasks_with_existing_files(tmp_path):
    """If `forge task add` already created the body, reconcile is a no-op."""
    repo = make_repo(tmp_path, base_registry(
        epics=[{"id": "E1", "status": "in_progress", "tasks": []}]))
    (repo / "docs" / "epics" / "E1-fixture" / "tasks").mkdir(parents=True)

    task = ops.add_task(_registry_path(repo), task_id="T1", epic_id="E1", name="has body")
    ops.create_task_body_file(repo, task)  # body now exists on disk

    result = ops.reconcile_task_files(_registry_path(repo), repo, apply=True)
    assert result["missing"] == []
    assert result["created"] == []
