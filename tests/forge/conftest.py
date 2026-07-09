"""Pytest config: add scripts/forge to sys.path so we can import the checker."""
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = _REPO_ROOT / "scripts" / "forge"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def make_repo(tmp_path, registry, task_files=None, extra_dirs=None):
    """Create a synthetic project under tmp_path.

    `task_files` is a dict mapping "E##/T###" specs to {id, status, ...}.
    Each spec creates docs/epics/E##-fixture/tasks/T###-fixture.md with
    YAML frontmatter. The epic dir is auto-seeded into registry.epics
    so tests that aren't specifically exercising drift #2 (epic-not-in-
    registry) don't need to manage epic stubs by hand.

    `extra_dirs` adds bare epic directories for drift #2 testing — those
    are NOT auto-seeded into the registry.
    """
    (tmp_path / "docs" / "tasks").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "epics").mkdir(parents=True, exist_ok=True)

    seen_epics = {e.get("id") for e in registry.get("epics", [])}
    tasks_by_id = {t.get("id"): t for t in registry.get("tasks", [])}
    for spec, meta in (task_files or {}).items():
        epic, _ = spec.split("/")
        epic_dir = tmp_path / "docs" / "epics" / f"{epic}-fixture"
        (epic_dir / "tasks").mkdir(parents=True, exist_ok=True)
        # Optionally embed `name:` in frontmatter when meta has it.
        # Legacy fixtures omit the field; new tests for name-drift opt in.
        name_line = f"name: {meta['name']}\n" if "name" in meta else ""
        body = (
            f"---\n"
            f"id: {meta['id']}\n"
            f"{name_line}"
            f"status: {meta['status']}\n"
            f"---\n\n"
            f"# {meta.get('name', meta['id'])}\n"
        )
        (epic_dir / "tasks" / f"{meta['id']}-fixture.md").write_text(body)
        if epic not in seen_epics:
            registry.setdefault("epics", []).append({
                "id": epic, "status": "in_progress", "tasks": []
            })
            seen_epics.add(epic)
        # Backfill the epic field on the matching registry task so
        # registry_ops can locate the file via discovery.
        if meta["id"] in tasks_by_id and not tasks_by_id[meta["id"]].get("epic"):
            tasks_by_id[meta["id"]]["epic"] = epic

    for d in extra_dirs or []:
        (tmp_path / "docs" / "epics" / d).mkdir(parents=True, exist_ok=True)

    with open(tmp_path / "docs" / "tasks" / "registry.json", "w") as f:
        json.dump(registry, f, indent=2)
        f.write("\n")
    return tmp_path


def base_registry(tasks=None, epics=None, settings=None):
    """Build a registry skeleton with pre-computed stats."""
    tasks = tasks or []
    epics = epics or []
    return {
        "project": "test",
        "version": "1",
        "settings": settings or {"lockTimeoutSeconds": 3600},
        "stats": {
            "epics": {
                "total": len(epics),
                "completed": 0, "in_progress": 0, "blocked": 0,
                "ready": 0, "pending": 0,
            },
            "tasks": {
                "total": len(tasks),
                "completed": 0, "in_progress": 0, "pr_pending": 0,
                "continuation": 0, "ready": 0, "pending": 0,
            },
        },
        "epics": epics,
        "tasks": tasks,
    }
