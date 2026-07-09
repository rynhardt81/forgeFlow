"""Render ISA list + per-feature ISA page."""

from __future__ import annotations

from pathlib import Path

from .markdown import parse_frontmatter, render as md_render


def _isa_dir(project_root: Path) -> Path:
    return project_root / "docs" / "tasks"


def list_features(project_root: Path) -> list[dict]:
    """Discover every ISA in the project.

    Three sources, in priority order:
      1. `<project_root>/ISA.md` — the project-level ISA (long-lived
         system of record), if present. Surfaces with id `"project"`.
      2. `<project_root>/docs/tasks/<task-id>/ISA.md` — per-task ISAs.
         `<task-id>` can be any shape: `F-<name>` (framework convention),
         `T<n>` (numeric tasks), `T<n>-<slug>`, etc. The glob matches
         every direct child of `docs/tasks/` containing an `ISA.md`.

    Returns list of dicts {id, title, phase, effort, path, feature_dir,
    mtime} sorted by mtime descending (newest first).
    """
    features: list[dict] = []

    # (1) Project-level ISA
    project_isa = project_root / "ISA.md"
    if project_isa.exists():
        try:
            fm, _ = parse_frontmatter(project_isa.read_text(encoding="utf-8"))
            features.append({
                "id": fm.get("id", "project"),
                "title": fm.get("title") or fm.get("name") or "Project ISA",
                "phase": fm.get("phase", "unknown"),
                "effort": fm.get("effort", ""),
                "owner": fm.get("owner", ""),
                "updated": fm.get("updated", ""),
                "feature_dir": "__project__",
                "mtime": project_isa.stat().st_mtime,
            })
        except OSError:
            pass

    # (2) Per-task ISAs under docs/tasks/<task-id>/ISA.md
    isa_dir = _isa_dir(project_root)
    if isa_dir.exists():
        for task_dir in sorted(isa_dir.iterdir()):
            if not task_dir.is_dir():
                continue
            isa = task_dir / "ISA.md"
            if not isa.exists():
                continue
            try:
                fm, _ = parse_frontmatter(isa.read_text(encoding="utf-8"))
            except OSError:
                continue
            features.append({
                "id": fm.get("id", task_dir.name),
                "title": fm.get("title") or fm.get("name") or task_dir.name,
                "phase": fm.get("phase", "unknown"),
                "effort": fm.get("effort", ""),
                "owner": fm.get("owner", ""),
                "updated": fm.get("updated", ""),
                "feature_dir": task_dir.name,
                "mtime": isa.stat().st_mtime,
            })

    features.sort(key=lambda f: f["mtime"], reverse=True)
    return features


def render_index(project_root: Path) -> str:
    features = list_features(project_root)
    if not features:
        body = (
            '<div class="empty-state">'
            '<h2>No ISAs found</h2>'
            '<p>This project has no ISAs yet. Locations the dashboard scans:</p>'
            '<ul>'
            '<li><code>&lt;project&gt;/ISA.md</code> — project-level ISA</li>'
            '<li><code>docs/tasks/&lt;task-id&gt;/ISA.md</code> — per-task ISAs '
            '(<code>F-NAME</code>, <code>T###</code>, or any task ID)</li>'
            '</ul>'
            '<p>Scaffold an ISA via <code>forge task add &lt;id&gt; --isa</code> '
            'or with the <code>/new-feature</code> skill.</p>'
            '</div>'
        )
    else:
        rows = []
        for f in features:
            phase_class = _phase_class(f["phase"])
            rows.append(f"""
              <a class="isa-row" href="/isa/{_esc(f["feature_dir"])}">
                <div class="isa-id">{_esc(f["id"])}</div>
                <div class="isa-title">{_esc(f["title"])}</div>
                <div class="isa-meta">
                  <span class="isa-phase {phase_class}">{_esc(f["phase"])}</span>
                  {f'<span class="isa-effort">{_esc(f["effort"])}</span>' if f["effort"] else ""}
                  {f'<span class="isa-updated">updated {_esc(f["updated"])}</span>' if f["updated"] else ""}
                </div>
              </a>
            """)
        body = (
            f'<header class="isa-header">'
            f'<h1>ISAs</h1>'
            f'<div class="isa-meta-line">{len(features)} feature{"s" if len(features) != 1 else ""}</div>'
            f'</header>'
            f'<div class="isa-list">{"".join(rows)}</div>'
        )
    return _wrap(body, title="ISAs")


def render_one(project_root: Path, feature_dir: str) -> str:
    """Render a single per-task ISA, or the project-level ISA.

    `feature_dir` is the URL slug returned by `list_features()`:
      - `__project__` → `<project_root>/ISA.md`
      - any other value → `<project_root>/docs/tasks/<feature_dir>/ISA.md`

    Traversal-safe: rejects path separators and parent refs.
    """
    if "/" in feature_dir or "\\" in feature_dir or ".." in feature_dir or not feature_dir:
        raise FileNotFoundError(f"invalid ISA id: {feature_dir}")

    if feature_dir == "__project__":
        isa_path = project_root / "ISA.md"
        if not isa_path.exists():
            raise FileNotFoundError("ISA not found: ISA.md (project-level)")
    else:
        isa_path = _isa_dir(project_root) / feature_dir / "ISA.md"
        if not isa_path.exists():
            raise FileNotFoundError(f"ISA not found: docs/tasks/{feature_dir}/ISA.md")

    raw = isa_path.read_text(encoding="utf-8")
    fm, body_md = parse_frontmatter(raw)
    body_html = md_render(body_md)

    # Metadata strip at the top
    meta_pills = []
    for key in ("id", "phase", "effort", "owner", "created", "updated"):
        if fm.get(key):
            meta_pills.append(
                f'<span class="meta-pill"><span class="meta-key">{_esc(key)}</span>'
                f'<span class="meta-val">{_esc(fm[key])}</span></span>'
            )

    body = f"""
      <header class="isa-doc-header">
        <a class="back-link" href="/isas">← all ISAs</a>
        <h1>{_esc(fm.get("title", feature_dir))}</h1>
        <div class="meta-strip">{"".join(meta_pills)}</div>
      </header>
      <article class="isa-doc">
        {body_html}
      </article>
    """
    return _wrap(body, title=fm.get("title", feature_dir))


def _phase_class(phase: str) -> str:
    return {
        "planning":     "phase-planning",
        "in_progress":  "phase-active",
        "active":       "phase-active",
        "complete":     "phase-complete",
        "completed":    "phase-complete",
        "blocked":      "phase-blocked",
    }.get(phase, "phase-unknown")


def _esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&#39;"))


def _wrap(body: str, title: str = "Dashboard") -> str:
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8">
<title>{_esc(title)} · Forge</title>
<link rel="stylesheet" href="/static/dashboard.css">
<link rel="stylesheet" href="/static/content.css">
</head><body class="content-page">
{body}
</body></html>"""
