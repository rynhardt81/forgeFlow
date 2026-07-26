"""Tests for scripts/forge/registry_ops.py — the atomic task state ops."""

from __future__ import annotations

import json
import pytest

import registry_ops as ops
from conftest import base_registry, make_repo


def _registry_path(repo):
    return repo / "docs" / "tasks" / "registry.json"


def _read(repo):
    return json.loads(_registry_path(repo).read_text())


def _read_file_status(repo, task_file_glob):
    f = next(repo.rglob(task_file_glob))
    for line in f.read_text().splitlines():
        if line.startswith("status:"):
            return line.split(":", 1)[1].strip()
    return None


# --- add_task ------------------------------------------------------------


def test_add_task_no_deps_starts_ready(tmp_path):
    repo = make_repo(tmp_path, base_registry(epics=[{"id": "E1", "status": "in_progress", "tasks": []}]))
    task = ops.add_task(_registry_path(repo), task_id="T1", epic_id="E1", name="Foo")
    assert task["status"] == "ready"
    out = _read(repo)
    assert out["tasks"][0]["id"] == "T1"
    assert "T1" in out["epics"][0]["tasks"]
    # Stats recomputed
    assert out["stats"]["tasks"]["ready"] == 1


def test_add_task_with_deps_starts_pending(tmp_path):
    repo = make_repo(tmp_path, base_registry(epics=[{"id": "E1", "status": "in_progress", "tasks": []}]))
    task = ops.add_task(
        _registry_path(repo), task_id="T2", epic_id="E1", name="Bar",
        dependencies=["T1"],
    )
    assert task["status"] == "pending"


def test_add_task_records_scope_and_file(tmp_path):
    repo = make_repo(tmp_path, base_registry(epics=[{"id": "E1", "status": "in_progress", "tasks": []}]))
    task = ops.add_task(
        _registry_path(repo), task_id="T1", epic_id="E1", name="Foo",
        scope_directories=["src/components/"],
        scope_files=["src/index.ts"],
        file_path="docs/epics/E1-foo/tasks/T1-foo.md",
    )
    assert task["scope"]["directories"] == ["src/components/"]
    assert task["scope"]["files"] == ["src/index.ts"]
    assert task["file"] == "docs/epics/E1-foo/tasks/T1-foo.md"


def test_add_task_duplicate_raises(tmp_path):
    repo = make_repo(tmp_path, base_registry(
        tasks=[{"id": "T1", "status": "ready", "dependencies": []}],
        epics=[{"id": "E1", "status": "in_progress", "tasks": ["T1"]}],
    ))
    with pytest.raises(ops.TaskAlreadyExists):
        ops.add_task(_registry_path(repo), task_id="T1", epic_id="E1", name="dup")


def test_add_task_missing_epic_raises(tmp_path):
    # Regression: a task added under an epic not in the registry used to
    # succeed silently, orphaning the task (no back-reference, epic
    # unrepresented). Now it must raise EpicNotFound.
    repo = make_repo(tmp_path, base_registry(epics=[{"id": "E1", "status": "in_progress", "tasks": []}]))
    with pytest.raises(ops.EpicNotFound):
        ops.add_task(_registry_path(repo), task_id="T1", epic_id="E99", name="orphan")
    # Nothing was written — the registry is unchanged.
    assert _read(repo)["tasks"] == []


def test_add_task_allow_missing_epic_bypasses(tmp_path):
    repo = make_repo(tmp_path, base_registry(epics=[{"id": "E1", "status": "in_progress", "tasks": []}]))
    task = ops.add_task(
        _registry_path(repo), task_id="T1", epic_id="E99", name="deliberate",
        allow_missing_epic=True,
    )
    assert task["epic"] == "E99"
    out = _read(repo)
    assert out["tasks"][0]["id"] == "T1"
    # No phantom epic was created; the task is a known orphan.
    assert all(e["id"] != "E99" for e in out["epics"])


# --- add_epic ------------------------------------------------------------


def test_add_epic_creates_entry(tmp_path):
    repo = make_repo(tmp_path, base_registry())
    epic = ops.add_epic(
        _registry_path(repo), epic_id="E14", name="Integration Hardening",
        description="Fix the core loop", priority=14, category="C",
        dependencies=["E01"],
    )
    assert epic["id"] == "E14"
    assert epic["status"] == "pending"
    assert epic["tasks"] == []
    out = _read(repo)
    assert out["epics"][0]["id"] == "E14"
    assert out["epics"][0]["dependencies"] == ["E01"]
    assert out["stats"]["epics"]["total"] == 1
    assert out["stats"]["epics"]["pending"] == 1


def test_add_epic_duplicate_raises(tmp_path):
    repo = make_repo(tmp_path, base_registry(epics=[{"id": "E14", "status": "pending", "tasks": []}]))
    with pytest.raises(ops.EpicAlreadyExists):
        ops.add_epic(_registry_path(repo), epic_id="E14", name="dup")


def test_add_epic_then_task_wires_backref(tmp_path):
    # The full happy path the fix enables: create epic, then file a task
    # under it — the back-reference lands, no orphan.
    repo = make_repo(tmp_path, base_registry())
    ops.add_epic(_registry_path(repo), epic_id="E14", name="Integration Hardening")
    ops.add_task(_registry_path(repo), task_id="T098", epic_id="E14", name="secrets")
    out = _read(repo)
    epic = next(e for e in out["epics"] if e["id"] == "E14")
    assert "T098" in epic["tasks"]


def test_create_epic_dir_writes_dir_and_body(tmp_path):
    repo = make_repo(tmp_path, base_registry())
    epic = ops.add_epic(_registry_path(repo), epic_id="E14", name="Integration Hardening")
    epic_dir = ops.create_epic_dir(repo, epic)
    assert epic_dir.name == "E14-integration-hardening"
    assert (epic_dir / "tasks").is_dir()
    body = epic_dir / "E14-integration-hardening.md"
    assert body.exists()
    assert "id: E14" in body.read_text()


def test_create_epic_dir_reuses_existing_untitled(tmp_path):
    # If a prior task-add created an -untitled fallback dir, epic-add must
    # reuse it, not create a second dir for the same id.
    repo = make_repo(tmp_path, base_registry())
    (repo / "docs" / "epics" / "E14-untitled" / "tasks").mkdir(parents=True)
    epic = ops.add_epic(_registry_path(repo), epic_id="E14", name="Integration Hardening")
    epic_dir = ops.create_epic_dir(repo, epic)
    assert epic_dir.name == "E14-untitled"
    dirs = sorted(p.name for p in (repo / "docs" / "epics").glob("E14-*"))
    assert dirs == ["E14-untitled"]


# --- lock_task -----------------------------------------------------------


def test_lock_task_from_ready(tmp_path):
    repo = make_repo(tmp_path, base_registry(
        tasks=[{"id": "T1", "status": "ready", "dependencies": [], "lock": None}],
    ), task_files={"E1/T1": {"id": "T1", "status": "ready"}})
    task = ops.lock_task(_registry_path(repo), repo, "T1", session_id="s1")
    assert task["status"] == "in_progress"
    assert task["lock"]["session"] == "s1"
    assert task["lock"]["lockedAt"]
    # File mirrored
    assert _read_file_status(repo, "T1-fixture.md") == "in_progress"


def test_lock_task_from_continuation(tmp_path):
    repo = make_repo(tmp_path, base_registry(
        tasks=[{"id": "T1", "status": "continuation", "dependencies": [], "lock": None}],
    ), task_files={"E1/T1": {"id": "T1", "status": "continuation"}})
    task = ops.lock_task(_registry_path(repo), repo, "T1", session_id="s2")
    assert task["status"] == "in_progress"


def test_lock_task_illegal_from_pending(tmp_path):
    repo = make_repo(tmp_path, base_registry(
        tasks=[{"id": "T1", "status": "pending", "dependencies": ["T0"], "lock": None}],
    ))
    with pytest.raises(ops.IllegalTransition):
        ops.lock_task(_registry_path(repo), repo, "T1", session_id="s1")


def test_lock_task_not_found(tmp_path):
    repo = make_repo(tmp_path, base_registry())
    with pytest.raises(ops.TaskNotFound):
        ops.lock_task(_registry_path(repo), repo, "T999", session_id="s1")


# --- unlock_task ----------------------------------------------------------


def test_unlock_default_continuation(tmp_path):
    repo = make_repo(tmp_path, base_registry(
        tasks=[{"id": "T1", "status": "in_progress", "dependencies": [],
                "lock": {"session": "s1", "lockedAt": "2026-01-01T00:00:00Z"}}],
    ), task_files={"E1/T1": {"id": "T1", "status": "in_progress"}})
    task = ops.unlock_task(_registry_path(repo), repo, "T1")
    assert task["status"] == "continuation"
    assert task["lock"] is None
    assert _read_file_status(repo, "T1-fixture.md") == "continuation"


def test_unlock_to_ready(tmp_path):
    repo = make_repo(tmp_path, base_registry(
        tasks=[{"id": "T1", "status": "in_progress", "dependencies": [],
                "lock": {"session": "s1", "lockedAt": "2026-01-01T00:00:00Z"}}],
    ), task_files={"E1/T1": {"id": "T1", "status": "in_progress"}})
    task = ops.unlock_task(_registry_path(repo), repo, "T1", to_status="ready")
    assert task["status"] == "ready"
    assert task["lock"] is None


def test_unlock_when_not_in_progress_raises(tmp_path):
    repo = make_repo(tmp_path, base_registry(
        tasks=[{"id": "T1", "status": "ready", "dependencies": [], "lock": None}],
    ))
    with pytest.raises(ops.IllegalTransition):
        ops.unlock_task(_registry_path(repo), repo, "T1")


# --- complete_task --------------------------------------------------------


def test_complete_task_unblocks_dependents(tmp_path):
    repo = make_repo(tmp_path, base_registry(
        tasks=[
            {"id": "T1", "status": "in_progress", "dependencies": [],
             "lock": {"session": "s1", "lockedAt": "2026-01-01T00:00:00Z"}},
            {"id": "T2", "status": "pending", "dependencies": ["T1"], "lock": None},
        ],
    ), task_files={
        "E1/T1": {"id": "T1", "status": "in_progress"},
        "E1/T2": {"id": "T2", "status": "pending"},
    })
    task, unblocked = ops.complete_task(_registry_path(repo), repo, "T1")
    assert task["status"] == "completed"
    assert task["lock"] is None
    assert task["completedAt"]
    assert unblocked == ["T2"]
    assert _read_file_status(repo, "T2-fixture.md") == "ready"
    out = _read(repo)
    t2 = next(t for t in out["tasks"] if t["id"] == "T2")
    assert t2["status"] == "ready"


def test_complete_from_pr_pending(tmp_path):
    """PR-merged path: pr_pending -> completed."""
    repo = make_repo(tmp_path, base_registry(
        tasks=[{"id": "T1", "status": "pr_pending", "dependencies": [], "lock": None}],
    ), task_files={"E1/T1": {"id": "T1", "status": "pr_pending"}})
    task, _ = ops.complete_task(_registry_path(repo), repo, "T1")
    assert task["status"] == "completed"


def test_complete_illegal_from_ready(tmp_path):
    repo = make_repo(tmp_path, base_registry(
        tasks=[{"id": "T1", "status": "ready", "dependencies": [], "lock": None}],
    ))
    with pytest.raises(ops.IllegalTransition):
        ops.complete_task(_registry_path(repo), repo, "T1")


# --- pr_task --------------------------------------------------------------


def test_pr_task_clears_lock_and_unblocks(tmp_path):
    """pr_pending counts as done-for-deps; dependents flip to ready."""
    repo = make_repo(tmp_path, base_registry(
        tasks=[
            {"id": "T1", "status": "in_progress", "dependencies": [],
             "lock": {"session": "s1", "lockedAt": "2026-01-01T00:00:00Z"}},
            {"id": "T2", "status": "pending", "dependencies": ["T1"], "lock": None},
        ],
    ), task_files={
        "E1/T1": {"id": "T1", "status": "in_progress"},
        "E1/T2": {"id": "T2", "status": "pending"},
    })
    task, unblocked = ops.pr_task(_registry_path(repo), repo, "T1")
    assert task["status"] == "pr_pending"
    assert task["lock"] is None
    assert task["prOpenedAt"]
    assert unblocked == ["T2"]


def test_pr_task_illegal_from_ready(tmp_path):
    repo = make_repo(tmp_path, base_registry(
        tasks=[{"id": "T1", "status": "ready", "dependencies": [], "lock": None}],
    ))
    with pytest.raises(ops.IllegalTransition):
        ops.pr_task(_registry_path(repo), repo, "T1")


# --- transition_task generic ---------------------------------------------


def test_transition_legal(tmp_path):
    repo = make_repo(tmp_path, base_registry(
        tasks=[{"id": "T1", "status": "pending", "dependencies": ["T0"], "lock": None}],
    ), task_files={"E1/T1": {"id": "T1", "status": "pending"}})
    task = ops.transition_task(_registry_path(repo), repo, "T1", "ready")
    assert task["status"] == "ready"
    assert _read_file_status(repo, "T1-fixture.md") == "ready"


def test_transition_illegal(tmp_path):
    """Can't jump from ready directly to completed."""
    repo = make_repo(tmp_path, base_registry(
        tasks=[{"id": "T1", "status": "ready", "dependencies": [], "lock": None}],
    ))
    with pytest.raises(ops.IllegalTransition):
        ops.transition_task(_registry_path(repo), repo, "T1", "completed")


# --- list_tasks read-only ------------------------------------------------


def test_list_tasks_filters(tmp_path):
    repo = make_repo(tmp_path, base_registry(tasks=[
        {"id": "T1", "status": "ready", "dependencies": [], "lock": None, "epic": "E1"},
        {"id": "T2", "status": "completed", "dependencies": [], "lock": None, "epic": "E1"},
        {"id": "T3", "status": "in_progress", "dependencies": [], "epic": "E2",
         "lock": {"session": "s", "lockedAt": "2026-01-01T00:00:00Z"}},
    ]))
    ready = ops.list_tasks(_registry_path(repo), status_filter="ready")
    assert [t["id"] for t in ready] == ["T1"]
    e2 = ops.list_tasks(_registry_path(repo), epic_filter="E2")
    assert [t["id"] for t in e2] == ["T3"]
    locked = ops.list_tasks(_registry_path(repo), locked_only=True)
    assert [t["id"] for t in locked] == ["T3"]


# --- Atomic write durability ---------------------------------------------


def test_save_registry_is_atomic_no_tmp_left_behind(tmp_path):
    """Successful saves leave no .tmp file in docs/tasks/."""
    repo = make_repo(tmp_path, base_registry(tasks=[
        {"id": "T1", "status": "ready", "dependencies": [], "lock": None}
    ]))
    ops.transition_task(_registry_path(repo), repo, "T1", "in_progress")
    leftover = list((repo / "docs" / "tasks").glob(".registry-*.tmp"))
    assert leftover == []


# --- Stats kept in sync on every mutation --------------------------------


def test_stats_updated_after_complete(tmp_path):
    repo = make_repo(tmp_path, base_registry(
        tasks=[
            {"id": "T1", "status": "in_progress", "dependencies": [],
             "lock": {"session": "s", "lockedAt": "2026-01-01T00:00:00Z"}},
            {"id": "T2", "status": "pending", "dependencies": ["T1"], "lock": None},
        ],
    ), task_files={
        "E1/T1": {"id": "T1", "status": "in_progress"},
        "E1/T2": {"id": "T2", "status": "pending"},
    })
    ops.complete_task(_registry_path(repo), repo, "T1")
    out = _read(repo)
    s = out["stats"]["tasks"]
    assert s["completed"] == 1
    assert s["ready"] == 1  # T2 flipped
    assert s["in_progress"] == 0
    assert s["pending"] == 0


# --- Frontmatter mirroring preserves file structure ----------------------


def test_mirror_preserves_frontmatter_terminator(tmp_path):
    """Regression for the \\s*$ bug: closing --- must remain on its own line."""
    repo = make_repo(tmp_path, base_registry(tasks=[
        {"id": "T1", "status": "ready", "dependencies": [], "lock": None}
    ]), task_files={"E1/T1": {"id": "T1", "status": "ready"}})
    ops.lock_task(_registry_path(repo), repo, "T1", session_id="s")
    f = next(repo.rglob("T1-fixture.md"))
    lines = f.read_text().splitlines()
    assert lines[0] == "---"
    closing_idx = next(i for i, line in enumerate(lines[1:], start=1) if line == "---")
    status_lines = [l for l in lines[1:closing_idx] if l.startswith("status:")]
    assert status_lines == ["status: in_progress"]


# --- rename_task ---------------------------------------------------------


def test_rename_task_updates_registry_and_file(tmp_path):
    repo = make_repo(tmp_path, base_registry(tasks=[
        {"id": "T1", "status": "ready", "name": "Old Name",
         "dependencies": [], "lock": None}
    ]), task_files={"E1/T1": {"id": "T1", "status": "ready", "name": "Old Name"}})
    task = ops.rename_task(_registry_path(repo), repo, "T1", "New Name")
    assert task["name"] == "New Name"
    assert _read(repo)["tasks"][0]["name"] == "New Name"
    f = next(repo.rglob("T1-fixture.md"))
    fm = f.read_text()
    assert "name: New Name" in fm
    assert "name: Old Name" not in fm


def test_rename_task_not_found(tmp_path):
    repo = make_repo(tmp_path, base_registry())
    with pytest.raises(ops.TaskNotFound):
        ops.rename_task(_registry_path(repo), repo, "T999", "anything")


def test_rename_task_empty_name_rejected(tmp_path):
    repo = make_repo(tmp_path, base_registry(tasks=[
        {"id": "T1", "status": "ready", "name": "X",
         "dependencies": [], "lock": None}
    ]), task_files={"E1/T1": {"id": "T1", "status": "ready", "name": "X"}})
    with pytest.raises(ValueError):
        ops.rename_task(_registry_path(repo), repo, "T1", "   ")


def test_rename_task_silent_when_file_missing(tmp_path):
    """File deleted between registry add and rename — registry still updates."""
    repo = make_repo(tmp_path, base_registry(tasks=[
        {"id": "T1", "status": "ready", "name": "Old",
         "dependencies": [], "lock": None}
    ]), task_files={"E1/T1": {"id": "T1", "status": "ready", "name": "Old"}})
    f = next(repo.rglob("T1-fixture.md"))
    f.unlink()
    task = ops.rename_task(_registry_path(repo), repo, "T1", "New")
    assert task["name"] == "New"
    assert _read(repo)["tasks"][0]["name"] == "New"


def test_rename_task_quotes_when_needed(tmp_path):
    """Names with `:` get YAML-quoted to avoid breaking the frontmatter."""
    repo = make_repo(tmp_path, base_registry(tasks=[
        {"id": "T1", "status": "ready", "name": "Old",
         "dependencies": [], "lock": None}
    ]), task_files={"E1/T1": {"id": "T1", "status": "ready", "name": "Old"}})
    ops.rename_task(_registry_path(repo), repo, "T1", "Refactor: split routes")
    f = next(repo.rglob("T1-fixture.md"))
    fm = f.read_text()
    assert 'name: "Refactor: split routes"' in fm


def test_rename_task_preserves_identity(tmp_path):
    """ISC-A5: rename must not change id, epic, or file."""
    repo = make_repo(tmp_path, base_registry(tasks=[
        {"id": "T1", "epic": "E1", "status": "ready", "name": "Old",
         "dependencies": [], "lock": None, "category": "A", "priority": 2}
    ]), task_files={"E1/T1": {"id": "T1", "status": "ready", "name": "Old"}})
    before = _read(repo)["tasks"][0].copy()
    ops.rename_task(_registry_path(repo), repo, "T1", "Brand New")
    after = _read(repo)["tasks"][0]
    assert after["id"] == before["id"]
    assert after["epic"] == before["epic"]
    assert after.get("file") == before.get("file")
    assert after["category"] == before["category"]
    assert after["priority"] == before["priority"]
    diff_keys = [k for k in after if after.get(k) != before.get(k)]
    assert diff_keys == ["name"]


# --- set_task_file -------------------------------------------------------


def test_set_task_file_records_relative_path(tmp_path):
    repo = make_repo(tmp_path, base_registry(tasks=[
        {"id": "T1", "epic": "E1", "status": "ready", "name": "X",
         "dependencies": [], "lock": None}
    ]), task_files={"E1/T1": {"id": "T1", "status": "ready", "name": "X"}})
    rel = "docs/epics/E1-fixture/tasks/T1-fixture.md"
    task = ops.set_task_file(_registry_path(repo), repo, "T1", rel)
    assert task["file"] == rel
    assert _read(repo)["tasks"][0]["file"] == rel


def test_set_task_file_converts_absolute_to_relative(tmp_path):
    repo = make_repo(tmp_path, base_registry(tasks=[
        {"id": "T1", "epic": "E1", "status": "ready", "name": "X",
         "dependencies": [], "lock": None}
    ]), task_files={"E1/T1": {"id": "T1", "status": "ready", "name": "X"}})
    abs_path = next(repo.rglob("T1-fixture.md"))
    task = ops.set_task_file(_registry_path(repo), repo, "T1", str(abs_path))
    assert task["file"] == "docs/epics/E1-fixture/tasks/T1-fixture.md"


def test_set_task_file_rejects_path_outside_project(tmp_path):
    repo = make_repo(tmp_path, base_registry(tasks=[
        {"id": "T1", "epic": "E1", "status": "ready", "name": "X",
         "dependencies": [], "lock": None}
    ]), task_files={"E1/T1": {"id": "T1", "status": "ready", "name": "X"}})
    outside = tmp_path.parent / "elsewhere.md"
    outside.write_text("# elsewhere\n")
    with pytest.raises(ValueError):
        ops.set_task_file(_registry_path(repo), repo, "T1", str(outside))


def test_set_task_file_strips_legacy_path_field(tmp_path):
    repo = make_repo(tmp_path, base_registry(tasks=[
        {"id": "T1", "epic": "E1", "status": "ready", "name": "X",
         "dependencies": [], "lock": None,
         "path": "old/legacy/location.md"}
    ]), task_files={"E1/T1": {"id": "T1", "status": "ready", "name": "X"}})
    rel = "docs/epics/E1-fixture/tasks/T1-fixture.md"
    ops.set_task_file(_registry_path(repo), repo, "T1", rel)
    entry = _read(repo)["tasks"][0]
    assert entry["file"] == rel
    assert "path" not in entry


def test_set_task_file_overwrites_existing_value(tmp_path):
    repo = make_repo(tmp_path, base_registry(tasks=[
        {"id": "T1", "epic": "E1", "status": "ready", "name": "X",
         "file": "docs/epics/E1-fixture/tasks/T1-old.md",
         "dependencies": [], "lock": None}
    ]), task_files={"E1/T1": {"id": "T1", "status": "ready", "name": "X"}})
    new_rel = "docs/epics/E1-fixture/tasks/T1-fixture.md"
    ops.set_task_file(_registry_path(repo), repo, "T1", new_rel)
    assert _read(repo)["tasks"][0]["file"] == new_rel


def test_set_task_file_not_found(tmp_path):
    repo = make_repo(tmp_path, base_registry())
    with pytest.raises(ops.TaskNotFound):
        ops.set_task_file(_registry_path(repo), repo, "T999", "any/path.md")


def test_set_task_file_empty_path_rejected(tmp_path):
    repo = make_repo(tmp_path, base_registry(tasks=[
        {"id": "T1", "epic": "E1", "status": "ready", "name": "X",
         "dependencies": [], "lock": None}
    ]), task_files={"E1/T1": {"id": "T1", "status": "ready", "name": "X"}})
    with pytest.raises(ValueError):
        ops.set_task_file(_registry_path(repo), repo, "T1", "   ")


def test_set_task_file_require_exists_passes_when_present(tmp_path):
    repo = make_repo(tmp_path, base_registry(tasks=[
        {"id": "T1", "epic": "E1", "status": "ready", "name": "X",
         "dependencies": [], "lock": None}
    ]), task_files={"E1/T1": {"id": "T1", "status": "ready", "name": "X"}})
    rel = "docs/epics/E1-fixture/tasks/T1-fixture.md"
    task = ops.set_task_file(
        _registry_path(repo), repo, "T1", rel, require_exists=True,
    )
    assert task["file"] == rel


def test_set_task_file_require_exists_fails_when_missing(tmp_path):
    repo = make_repo(tmp_path, base_registry(tasks=[
        {"id": "T1", "epic": "E1", "status": "ready", "name": "X",
         "dependencies": [], "lock": None}
    ]), task_files={"E1/T1": {"id": "T1", "status": "ready", "name": "X"}})
    with pytest.raises(FileNotFoundError):
        ops.set_task_file(
            _registry_path(repo), repo, "T1",
            "docs/epics/E1-fixture/tasks/T1-nope.md",
            require_exists=True,
        )


# --- reconcile_orphan_files ---------------------------------------------


def test_reconcile_seeds_orphan_files(tmp_path):
    repo = make_repo(
        tmp_path,
        base_registry(epics=[{"id": "E1", "status": "in_progress", "tasks": []}]),
        task_files={
            "E1/T9": {"id": "T9", "status": "ready", "name": "Recovered Task"},
        },
    )
    reg_path = _registry_path(repo)
    reg = json.loads(reg_path.read_text())
    reg["tasks"] = []
    reg_path.write_text(json.dumps(reg, indent=2))

    seeded = ops.reconcile_orphan_files(reg_path, repo)
    assert seeded == ["T9"]
    out = _read(repo)["tasks"]
    assert len(out) == 1
    assert out[0]["id"] == "T9"
    assert out[0]["name"] == "Recovered Task"
    assert out[0]["status"] == "ready"
    assert out[0]["epic"] == "E1"


def test_reconcile_idempotent(tmp_path):
    repo = make_repo(
        tmp_path,
        base_registry(epics=[{"id": "E1", "status": "in_progress", "tasks": []}]),
        task_files={
            "E1/T9": {"id": "T9", "status": "ready", "name": "Recovered"},
        },
    )
    reg_path = _registry_path(repo)
    reg = json.loads(reg_path.read_text())
    reg["tasks"] = []
    reg_path.write_text(json.dumps(reg, indent=2))

    first = ops.reconcile_orphan_files(reg_path, repo)
    second = ops.reconcile_orphan_files(reg_path, repo)
    assert first == ["T9"]
    assert second == []
    assert len(_read(repo)["tasks"]) == 1


def test_reconcile_defaults_missing_name_and_status(tmp_path):
    repo = make_repo(tmp_path, base_registry(
        epics=[{"id": "E1", "status": "in_progress", "tasks": []}]
    ))
    epic_dir = repo / "docs" / "epics" / "E1-fixture"
    (epic_dir / "tasks").mkdir(parents=True, exist_ok=True)
    (epic_dir / "tasks" / "T7-bare.md").write_text("---\nid: T7\n---\n\n# T7\n")
    seeded = ops.reconcile_orphan_files(_registry_path(repo), repo)
    assert seeded == ["T7"]
    out = _read(repo)["tasks"][0]
    assert out["status"] == "pending"
    assert out["name"] == "T7 (reconciled)"


def test_reconcile_skips_already_registered(tmp_path):
    """ISC-A4: existing registry entry untouched, even if file name differs."""
    repo = make_repo(
        tmp_path,
        base_registry(tasks=[
            {"id": "T9", "epic": "E1", "status": "ready", "name": "Registry Wins",
             "dependencies": [], "lock": None}
        ]),
        task_files={
            "E1/T9": {"id": "T9", "status": "ready", "name": "File Says Different"},
        },
    )
    seeded = ops.reconcile_orphan_files(_registry_path(repo), repo)
    assert seeded == []
    assert _read(repo)["tasks"][0]["name"] == "Registry Wins"




# --- complete_epic (T622) -------------------------------------------------


def test_complete_epic_when_all_tasks_terminal(tmp_path):
    # E33 drift fix: an epic whose every task is terminal transitions to
    # completed and stats recompute.
    repo = make_repo(tmp_path, base_registry(
        tasks=[
            {"id": "T1", "epic": "E1", "status": "completed", "dependencies": []},
            {"id": "T2", "epic": "E1", "status": "superseded", "dependencies": []},
            {"id": "T3", "epic": "E1", "status": "closed", "dependencies": []},
        ],
        epics=[{"id": "E1", "status": "in_progress", "tasks": ["T1", "T2", "T3"]}],
    ))
    epic, non_terminal = ops.complete_epic(_registry_path(repo), repo, "E1")
    assert epic["status"] == "completed"
    assert "completedAt" in epic
    assert non_terminal == []
    out = _read(repo)
    assert next(e for e in out["epics"] if e["id"] == "E1")["status"] == "completed"
    assert out["stats"]["epics"]["completed"] == 1
    assert out["stats"]["epics"]["in_progress"] == 0


def test_complete_epic_refuses_when_task_nonterminal(tmp_path):
    # Anti: a still-ready/in_progress/continuation task blocks completion.
    for live in ("ready", "in_progress", "pr_pending", "continuation", "pending"):
        repo = make_repo(tmp_path / live, base_registry(
            tasks=[
                {"id": "T1", "epic": "E1", "status": "completed", "dependencies": []},
                {"id": "T2", "epic": "E1", "status": live, "dependencies": []},
            ],
            epics=[{"id": "E1", "status": "in_progress", "tasks": ["T1", "T2"]}],
        ))
        with pytest.raises(ops.IllegalTransition) as exc:
            ops.complete_epic(_registry_path(repo), repo, "E1")
        # The message names the offender (the only user feedback) — and NOT
        # the terminal task.
        assert "T2" in str(exc.value)
        assert "T1" not in str(exc.value)
        # Registry unchanged — epic still in_progress.
        assert _read(repo)["epics"][0]["status"] == "in_progress"


def test_complete_epic_lists_only_nonterminal_offenders(tmp_path):
    # The guard's list-comprehension must name exactly the live tasks, not the
    # terminal ones (off-by-filter regression guard).
    repo = make_repo(tmp_path, base_registry(
        tasks=[
            {"id": "T1", "epic": "E1", "status": "completed", "dependencies": []},
            {"id": "T2", "epic": "E1", "status": "ready", "dependencies": []},
            {"id": "T3", "epic": "E1", "status": "in_progress", "dependencies": []},
        ],
        epics=[{"id": "E1", "status": "in_progress", "tasks": ["T1", "T2", "T3"]}],
    ))
    with pytest.raises(ops.IllegalTransition) as exc:
        ops.complete_epic(_registry_path(repo), repo, "E1")
    msg = str(exc.value)
    assert "T2" in msg and "T3" in msg
    assert "T1" not in msg


def test_complete_epic_scopes_to_its_own_tasks(tmp_path):
    # The guard filters on epic == epic_id; a live task under a SIBLING epic
    # must not block this epic (the E33 driver is a multi-epic registry).
    repo = make_repo(tmp_path, base_registry(
        tasks=[
            {"id": "T1", "epic": "E1", "status": "completed", "dependencies": []},
            {"id": "T2", "epic": "E2", "status": "in_progress", "dependencies": []},
        ],
        epics=[
            {"id": "E1", "status": "in_progress", "tasks": ["T1"]},
            {"id": "E2", "status": "in_progress", "tasks": ["T2"]},
        ],
    ))
    epic, non_terminal = ops.complete_epic(_registry_path(repo), repo, "E1")
    assert epic["status"] == "completed"
    assert non_terminal == []
    # Sibling E2 untouched.
    assert next(e for e in _read(repo)["epics"] if e["id"] == "E2")["status"] == "in_progress"


def test_complete_epic_with_no_tasks_is_allowed(tmp_path):
    # Documented behaviour: an epic with zero tasks has nothing keeping it open.
    repo = make_repo(tmp_path, base_registry(
        epics=[{"id": "E1", "status": "in_progress", "tasks": []}],
    ))
    epic, non_terminal = ops.complete_epic(_registry_path(repo), repo, "E1")
    assert epic["status"] == "completed"
    assert non_terminal == []


def test_complete_epic_idempotent_when_already_completed(tmp_path):
    repo = make_repo(tmp_path, base_registry(
        tasks=[{"id": "T1", "epic": "E1", "status": "completed", "dependencies": []}],
        epics=[{
            "id": "E1", "status": "completed", "tasks": ["T1"],
            "completedAt": "2020-01-01T00:00:00Z",
        }],
    ))
    epic, non_terminal = ops.complete_epic(_registry_path(repo), repo, "E1")
    assert epic["status"] == "completed"
    assert non_terminal == []
    # Idempotent: the original completedAt is NOT overwritten with a fresh one.
    assert epic["completedAt"] == "2020-01-01T00:00:00Z"
    assert _read(repo)["epics"][0]["completedAt"] == "2020-01-01T00:00:00Z"


def test_complete_epic_completed_with_live_task_raises(tmp_path):
    # Drift case (codex P2, PR #527): an already-completed epic that has since
    # gained a live task must NOT silently no-op — the guard runs first and
    # surfaces the drift as IllegalTransition rather than re-affirming "done".
    repo = make_repo(tmp_path, base_registry(
        tasks=[
            {"id": "T1", "epic": "E1", "status": "completed", "dependencies": []},
            {"id": "T2", "epic": "E1", "status": "in_progress", "dependencies": []},
        ],
        epics=[{"id": "E1", "status": "completed", "tasks": ["T1", "T2"]}],
    ))
    with pytest.raises(ops.IllegalTransition) as exc:
        ops.complete_epic(_registry_path(repo), repo, "E1")
    assert "T2" in str(exc.value)


def test_complete_epic_missing_raises(tmp_path):
    repo = make_repo(tmp_path, base_registry())
    with pytest.raises(ops.EpicNotFound):
        ops.complete_epic(_registry_path(repo), repo, "E99")




# --- set_preflight (T483: post-hoc preflight_required mutator) ------------


def _pf_repo(tmp_path, *, scope=None, preflight=True):
    """Single-task repo with a known scope + preflight_required for the
    set_preflight tests."""
    return make_repo(tmp_path, base_registry(tasks=[
        {"id": "T1", "epic": "E1", "status": "ready", "name": "X",
         "dependencies": [], "lock": None, "preflight_required": preflight,
         "scope": scope or {"directories": [], "files": []}},
    ]), task_files={"E1/T1": {"id": "T1", "status": "ready", "name": "X"}})


def test_set_preflight_skip_forces_false(tmp_path):
    repo = _pf_repo(tmp_path, preflight=True)
    task = ops.set_preflight(_registry_path(repo), repo, "T1", "skip")
    assert task["preflight_required"] is False
    assert _read(repo)["tasks"][0]["preflight_required"] is False


def test_set_preflight_required_forces_true(tmp_path):
    repo = _pf_repo(tmp_path, scope={"directories": ["docs/"], "files": []},
                    preflight=False)
    task = ops.set_preflight(_registry_path(repo), repo, "T1", "required")
    assert task["preflight_required"] is True
    assert _read(repo)["tasks"][0]["preflight_required"] is True


def test_set_preflight_auto_doc_only_scope_derives_false(tmp_path):
    """auto re-derives from scope: a doc-only scope ⇒ False."""
    repo = _pf_repo(tmp_path, scope={"directories": ["docs/"], "files": ["README.md"]},
                    preflight=True)
    task = ops.set_preflight(_registry_path(repo), repo, "T1", "auto")
    assert task["preflight_required"] is False


def test_set_preflight_auto_code_scope_derives_true(tmp_path):
    """auto re-derives from scope: any code path ⇒ True."""
    repo = _pf_repo(tmp_path, scope={"directories": ["app/"], "files": []},
                    preflight=False)
    task = ops.set_preflight(_registry_path(repo), repo, "T1", "auto")
    assert task["preflight_required"] is True


def test_set_preflight_auto_empty_scope_derives_true(tmp_path):
    """auto on empty scope ⇒ True (unknown scope is code-touching by default —
    this is exactly why T483 was mis-flagged; `skip` is the correct fix, not
    `auto`)."""
    repo = _pf_repo(tmp_path, scope={"directories": [], "files": []},
                    preflight=False)
    task = ops.set_preflight(_registry_path(repo), repo, "T1", "auto")
    assert task["preflight_required"] is True


def test_set_preflight_invalid_mode_rejected(tmp_path):
    repo = _pf_repo(tmp_path)
    with pytest.raises(ValueError):
        ops.set_preflight(_registry_path(repo), repo, "T1", "bogus")


def test_set_preflight_not_found(tmp_path):
    repo = make_repo(tmp_path, base_registry())
    with pytest.raises(ops.TaskNotFound):
        ops.set_preflight(_registry_path(repo), repo, "T999", "skip")


def test_set_preflight_touches_only_the_flag(tmp_path):
    """Regression guard: id, epic, status, scope unchanged — only the flag flips."""
    repo = _pf_repo(tmp_path, scope={"directories": ["app/"], "files": []},
                    preflight=True)
    before = _read(repo)["tasks"][0].copy()
    ops.set_preflight(_registry_path(repo), repo, "T1", "skip")
    after = _read(repo)["tasks"][0]
    diff_keys = [k for k in after if after.get(k) != before.get(k)]
    assert diff_keys == ["preflight_required"]


