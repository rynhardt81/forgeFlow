"""Render the daily-log tab — most recent N daily/YYYY-MM-DD.md files as a timeline."""

from __future__ import annotations

import re
from pathlib import Path

from .markdown import render as md_render


_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")


def list_recent_days(project_root: Path, limit: int = 7) -> list[dict]:
    daily_dir = project_root / "daily"
    if not daily_dir.exists():
        return []
    days = []
    for f in daily_dir.iterdir():
        if not f.is_file():
            continue
        m = _DATE_RE.match(f.name)
        if not m:
            continue
        days.append({"date": m.group(1), "path": f})
    days.sort(key=lambda d: d["date"], reverse=True)
    return days[:limit]


def render_index(project_root: Path, limit: int = 7) -> str:
    days = list_recent_days(project_root, limit)
    if not days:
        body = (
            '<div class="empty-state">'
            '<h2>No daily logs yet</h2>'
            '<p>The memory pipeline writes <code>daily/YYYY-MM-DD.md</code> entries as you work. '
            'Once entries accrue, they\'ll appear here as a timeline of recent days '
            '(newest first).</p>'
            '</div>'
        )
        return _wrap(body, title="Daily")

    entries = []
    for d in days:
        try:
            md = d["path"].read_text(encoding="utf-8")
        except OSError:
            continue
        html = md_render(md)
        entries.append(f"""
          <article class="daily-entry">
            <header class="daily-date"><h2>{_esc(d["date"])}</h2></header>
            <div class="daily-body">{html}</div>
          </article>
        """)

    body = (
        f'<header class="daily-header"><h1>Daily</h1>'
        f'<div class="daily-meta-line">{len(days)} most recent days</div></header>'
        f'<div class="daily-timeline">{"".join(entries)}</div>'
    )
    return _wrap(body, title="Daily")


def _esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&#39;"))


def _wrap(body: str, title: str = "Daily") -> str:
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8">
<title>{_esc(title)} · Forge</title>
<link rel="stylesheet" href="/static/dashboard.css">
<link rel="stylesheet" href="/static/content.css">
</head><body class="content-page">
{body}
</body></html>"""
