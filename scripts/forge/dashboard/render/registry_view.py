"""Render docs/tasks/registry.json as a collapsible HTML tree."""

from __future__ import annotations

import html as html_escape
import json
from pathlib import Path


def render_index(project_root: Path) -> str:
    registry_path = project_root / "docs" / "tasks" / "registry.json"
    if not registry_path.exists():
        body = (
            '<div class="empty-state">'
            '<h2>No registry yet</h2>'
            '<p>This project has no <code>docs/tasks/registry.json</code> yet. '
            'The registry is created when you run <code>forge task add ...</code> '
            'for the first time, or via <code>/new-project</code>.</p>'
            '</div>'
        )
        return _wrap(body, title="Registry")

    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        body = (
            f'<div class="empty-state">'
            f'<h2>Registry is not valid JSON</h2>'
            f'<p><code>docs/tasks/registry.json</code> exists but failed to parse: '
            f'<code>{html_escape.escape(str(exc))}</code></p>'
            f'</div>'
        )
        return _wrap(body, title="Registry")

    # Stats summary at top
    stats = data.get("stats", {})
    epic_count = len(data.get("epics", []))
    task_count = len(data.get("tasks", []))
    summary = _summary_strip(epic_count, task_count, stats)

    # Render tree
    tree = _render_value(data, open_depth=2)

    body = f"""
      <header class="registry-header">
        <h1>Registry</h1>
        <div class="registry-meta-line">
          <code>docs/tasks/registry.json</code>
          <span class="registry-meta-sep">·</span>
          {epic_count} epic{"s" if epic_count != 1 else ""}, {task_count} task{"s" if task_count != 1 else ""}
        </div>
      </header>
      {summary}
      <div class="registry-tree-frame">
        <div class="registry-tree">
          {tree}
        </div>
      </div>
    """
    return _wrap(body, title="Registry")


def _summary_strip(epic_count: int, task_count: int, stats: dict) -> str:
    tasks_stats = stats.get("tasks", {}) if isinstance(stats, dict) else {}
    chips = []
    for label, val in [
        ("epics", epic_count),
        ("tasks", task_count),
    ]:
        chips.append(f'<span class="reg-chip"><span class="reg-chip-key">{label}</span>'
                     f'<span class="reg-chip-val">{val}</span></span>')
    for status, count in (tasks_stats.items() if isinstance(tasks_stats, dict) else []):
        if not count:
            continue
        chips.append(f'<span class="reg-chip task-{html_escape.escape(str(status))}">'
                     f'<span class="reg-chip-key">{html_escape.escape(str(status))}</span>'
                     f'<span class="reg-chip-val">{count}</span></span>')
    if not chips:
        return ""
    return f'<div class="reg-summary">{"".join(chips)}</div>'


def _render_value(value, depth: int = 0, open_depth: int = 2) -> str:
    """Render a JSON value as collapsible HTML."""
    if isinstance(value, dict):
        return _render_dict(value, depth, open_depth)
    if isinstance(value, list):
        return _render_list(value, depth, open_depth)
    return _render_scalar(value)


def _render_dict(d: dict, depth: int, open_depth: int) -> str:
    if not d:
        return '<span class="json-empty">{}</span>'
    is_open = depth < open_depth
    open_attr = " open" if is_open else ""
    summary = (f'<summary class="json-summary">'
               f'<span class="json-toggle"></span>'
               f'<span class="json-brace">{{</span>'
               f'<span class="json-preview"> {len(d)} key{"s" if len(d) != 1 else ""} </span>'
               f'<span class="json-brace">}}</span></summary>')
    items = []
    for k, v in d.items():
        key_html = (f'<span class="json-key">"{html_escape.escape(str(k))}"</span>'
                    f'<span class="json-colon">:</span> ')
        items.append(f'<div class="json-item">{key_html}{_render_value(v, depth + 1, open_depth)}</div>')
    return f'<details class="json-block"{open_attr}>{summary}<div class="json-body">{"".join(items)}</div></details>'


def _render_list(lst: list, depth: int, open_depth: int) -> str:
    if not lst:
        return '<span class="json-empty">[]</span>'
    # Lists of scalars get rendered inline (compact)
    if all(not isinstance(x, (dict, list)) for x in lst) and len(lst) <= 8:
        scalars = ", ".join(_render_scalar(x) for x in lst)
        return f'<span class="json-list-inline">[{scalars}]</span>'

    is_open = depth < open_depth
    open_attr = " open" if is_open else ""
    summary = (f'<summary class="json-summary">'
               f'<span class="json-toggle"></span>'
               f'<span class="json-bracket">[</span>'
               f'<span class="json-preview"> {len(lst)} item{"s" if len(lst) != 1 else ""} </span>'
               f'<span class="json-bracket">]</span></summary>')
    items = []
    for i, v in enumerate(lst):
        idx_html = f'<span class="json-index">[{i}]</span><span class="json-colon">:</span> '
        items.append(f'<div class="json-item">{idx_html}{_render_value(v, depth + 1, open_depth)}</div>')
    return f'<details class="json-block"{open_attr}>{summary}<div class="json-body">{"".join(items)}</div></details>'


def _render_scalar(v) -> str:
    if v is None:
        return '<span class="json-null">null</span>'
    if isinstance(v, bool):
        return f'<span class="json-bool">{str(v).lower()}</span>'
    if isinstance(v, (int, float)):
        return f'<span class="json-number">{html_escape.escape(str(v))}</span>'
    if isinstance(v, str):
        return f'<span class="json-string">"{html_escape.escape(v)}"</span>'
    return f'<span class="json-other">{html_escape.escape(str(v))}</span>'


def _wrap(body: str, title: str = "Registry") -> str:
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8">
<title>{html_escape.escape(title)} · Forge</title>
<link rel="stylesheet" href="/static/dashboard.css">
<link rel="stylesheet" href="/static/content.css">
<link rel="stylesheet" href="/static/registry.css">
</head><body class="content-page">
{body}
</body></html>"""
