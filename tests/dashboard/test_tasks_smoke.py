"""End-to-end smoke test for the dashboard's Tasks tab.

This is the reporter's catch-the-fixture-leak assertion: synthesize a
project with a registry whose epic IDs deliberately avoid `E01`/`E02`, ask
the tasks generator to render it, and assert:

  - The rendered HTML mentions every real epic ID
  - The rendered HTML does NOT contain the literal `User authentication system`
    (the marker string from tests/dispatch/sample-registry.json)
  - The rendered HTML lands under PROJECT root's docs/visualizations/, not
    the framework root's
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TASKS_GEN = REPO_ROOT / "skills" / "visualize" / "Tools" / "generators" / "tasks.py"
TOOLS_DIR = REPO_ROOT / "skills" / "visualize" / "Tools"


def _load_tasks_generator():
    """Import the tasks.py generator as a fresh module each time."""
    # Ensure Tools/ is importable for the generator's `from _shared import …`
    if str(TOOLS_DIR) not in sys.path:
        sys.path.insert(0, str(TOOLS_DIR))
    # Drop any cached copy so monkeypatched __file__ takes effect
    for mod in ("tasks", "_shared"):
        sys.modules.pop(mod, None)

    spec = importlib.util.spec_from_file_location("tasks_gen", TASKS_GEN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_real_project(tmp_path: Path) -> Path:
    """Build a project with a non-fixture registry."""
    project = tmp_path / "demo-project"
    (project / ".git").mkdir(parents=True)
    (project / "docs" / "tasks").mkdir(parents=True)

    registry = {
        "project": "demo-project",
        "version": "1.0.0",
        "lastUpdated": "2026-05-23T10:00:00Z",
        "settings": {},
        "stats": {
            "epics": {"total": 2, "completed": 0, "in_progress": 2,
                      "blocked": 0, "ready": 0, "pending": 0},
            "tasks": {"total": 3, "completed": 0, "in_progress": 0,
                      "pr_pending": 0, "continuation": 0, "ready": 3,
                      "pending": 0},
        },
        "epics": [
            {"id": "E42", "name": "Bespoke Telemetry",
             "description": "Custom metrics pipeline.",
             "category": "I", "status": "in_progress", "dependencies": [],
             "priority": 1, "tasks": ["T100", "T101"]},
            {"id": "E99", "name": "Outbound Webhooks",
             "description": "Webhook dispatcher.",
             "category": "F", "status": "in_progress", "dependencies": [],
             "priority": 2, "tasks": ["T200"]},
        ],
        "tasks": [
            {"id": "T100", "epic": "E42", "name": "Wire up metrics",
             "status": "ready", "dependencies": []},
            {"id": "T101", "epic": "E42", "name": "Add dashboards",
             "status": "ready", "dependencies": ["T100"]},
            {"id": "T200", "epic": "E99", "name": "Outbound queue",
             "status": "ready", "dependencies": []},
        ],
    }
    (project / "docs" / "tasks" / "registry.json").write_text(json.dumps(registry))
    return project


def test_tasks_render_contains_real_epics_not_fixture(tmp_path, monkeypatch):
    project = _make_real_project(tmp_path)
    gen = _load_tasks_generator()

    # tasks.py does `from _shared import project_root` — Python binds the
    # name into tasks.py's module namespace, so patching `_shared.project_root`
    # alone has no effect. Patch BOTH: the source binding (so any future code
    # path that calls _shared.project_root() also sees the override) AND
    # tasks.py's own bound name.
    import _shared  # type: ignore
    monkeypatch.setattr(_shared, "project_root", lambda: project)
    monkeypatch.setattr(gen, "project_root", lambda: project)

    out_path = project / "docs" / "visualizations" / "tasks.html"
    args = argparse.Namespace(input=None, output=out_path, open=False, extra=[])
    result = gen.render(args)

    assert result == out_path
    assert out_path.exists()

    html = out_path.read_text()

    # Real epic IDs present
    assert "E42" in html, "Real epic E42 missing from rendered HTML"
    assert "E99" in html, "Real epic E99 missing from rendered HTML"
    assert "Bespoke Telemetry" in html
    assert "Outbound Webhooks" in html

    # Fixture-leak guards — these strings come from
    # tests/dispatch/sample-registry.json and must NEVER appear when a real
    # registry is rendered.
    assert "User authentication system" not in html, (
        "Fixture leak detected: 'User authentication system' appears in "
        "rendered HTML for a real (non-fixture) registry."
    )
    assert "User dashboard with analytics" not in html, (
        "Fixture leak detected: 'User dashboard with analytics' appears in "
        "rendered HTML for a real (non-fixture) registry."
    )
