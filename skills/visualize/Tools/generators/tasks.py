"""tasks generator — renders docs/tasks/registry.json as a kanban board.

Two layers:
  Layer 1 (default): epic-level kanban — columns by epic status, cards are
    epics with progress bars + task counts.
  Layer 2: drill into one epic — columns by task status, cards are individual
    tasks with deps + blocked-by indicators.

No Cytoscape dependency — pure HTML/CSS Grid + vanilla JS.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _shared import (
    default_output,
    ensure_output_dir,
    json_safe,
    project_root,
)


GENERATOR_NAME = "tasks"
DESCRIPTION = "Render docs/tasks/registry.json as a kanban board (epics → tasks, columns by status)."


STATE_COLORS = {
    "pending":      "#6b7280",
    "ready":        "#0ea5e9",
    "in_progress":  "#d97706",
    "continuation": "#d97706",
    "pr_pending":   "#9333ea",
    "completed":    "#16a34a",
    "blocked":      "#dc2626",
}


def render(args) -> Path:
    root = project_root()
    input_path: Path = args.input or (root / "docs" / "tasks" / "registry.json")
    output_path: Path = args.output or default_output("tasks", root)

    if not input_path.exists():
        raise FileNotFoundError(
            f"input not found: {input_path}\n"
            f"This project doesn't use a task registry. Pass --input to point at one, "
            f"or run `forge task add ...` to scaffold it."
        )

    data = json.loads(input_path.read_text(encoding="utf-8"))
    if "tasks" not in data or "epics" not in data:
        raise FileNotFoundError(
            f"{input_path} is not a recognizable Forge registry (missing tasks/epics keys)."
        )

    payload = {
        "epics": data.get("epics", []),
        "tasks": data.get("tasks", []),
        "stats": data.get("stats", {}),
        "state_colors": STATE_COLORS,
        "generated_at": data.get("lastUpdated", ""),
        "project": data.get("project", ""),
    }

    template = (Path(__file__).resolve().parent.parent
                / "templates" / "tasks.html").read_text(encoding="utf-8")

    html = template.replace("__DATA_JSON__", json_safe(payload))

    ensure_output_dir(output_path)
    output_path.write_text(html, encoding="utf-8")
    return output_path


def register():
    return {
        "name": GENERATOR_NAME,
        "description": DESCRIPTION,
        "render": render,
    }
