"""Render the project-memory tab — bugs / decisions / patterns / facts feeds."""

from __future__ import annotations

from pathlib import Path

from .markdown import render as md_render


# Files we look for inside docs/project-memory/
KNOWN_FEEDS = [
    ("bugs.md",      "Bugs"),
    ("decisions.md", "Decisions"),
    ("patterns.md",  "Patterns"),
    ("key-facts.md", "Key facts"),
    ("index.md",     "Index"),
]


def render_index(project_root: Path) -> str:
    memory_dir = project_root / "docs" / "project-memory"
    if not memory_dir.exists():
        body = (
            '<div class="empty-state">'
            '<h2>No project memory yet</h2>'
            '<p>Once <code>/remember</code> is invoked or the memory pipeline ingests entries, '
            'feeds will appear here: bugs, decisions, patterns, facts. Memory lives at '
            '<code>docs/project-memory/</code>.</p>'
            '</div>'
        )
        return _wrap(body, title="Memory")

    sections = []
    for filename, label in KNOWN_FEEDS:
        path = memory_dir / filename
        if not path.exists():
            continue
        try:
            md = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if not md.strip():
            continue
        html = md_render(md)
        sections.append(f"""
          <section class="memory-section">
            <h2 class="memory-section-title">{_esc(label)}</h2>
            <div class="memory-content">{html}</div>
          </section>
        """)

    if not sections:
        body = (
            '<div class="empty-state">'
            '<h2>Project memory directory is empty</h2>'
            '<p>The directory exists but no <code>bugs.md / decisions.md / patterns.md / key-facts.md</code> '
            'files have content yet.</p>'
            '</div>'
        )
    else:
        body = (
            f'<header class="memory-header"><h1>Project memory</h1></header>'
            f'<div class="memory-feeds">{"".join(sections)}</div>'
        )
    return _wrap(body, title="Memory")


def _esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&#39;"))


def _wrap(body: str, title: str = "Memory") -> str:
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8">
<title>{_esc(title)} · Forge</title>
<link rel="stylesheet" href="/static/dashboard.css">
<link rel="stylesheet" href="/static/content.css">
</head><body class="content-page">
{body}
</body></html>"""
