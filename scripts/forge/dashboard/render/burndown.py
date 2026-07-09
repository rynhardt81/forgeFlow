"""Burndown view — tasks completed per day, derived from git history of
docs/tasks/registry.json.

Approach:
- `git log --format='%H %ct'` on the registry file → list of (sha, unix_ts).
- For each commit, `git show <sha>:docs/tasks/registry.json` → parse → count
  tasks whose status is "completed".
- Day-over-day delta = tasks newly completed on that day.
- Cumulative line = total completed at end of each day.
- Cache the derived series to .forge/cache/burndown.json keyed by latest sha;
  invalidate when HEAD's registry sha changes.

Empty states:
- No git history at all → friendly empty-state card.
- <2 distinct days → render the single point + an empty-bars hint.
- registry.json missing → empty-state.

Stdlib-only. Inline SVG (no chart libraries).
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

REGISTRY_REL = "docs/tasks/registry.json"
CACHE_REL = ".forge/cache/burndown.json"


# ---- Data model ----------------------------------------------------------

@dataclass(frozen=True)
class DayPoint:
    day: str          # "YYYY-MM-DD" (UTC)
    completed: int    # tasks in "completed" status at end of that day
    delta: int        # net change vs previous day (can be negative)


# ---- Git extraction ------------------------------------------------------

def _git(args: list[str], project_root: Path) -> str:
    """Run a git command in project_root; return stdout (or '' on failure)."""
    try:
        out = subprocess.run(
            ["git", *args],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""
    if out.returncode != 0:
        return ""
    return out.stdout


def _registry_commits(project_root: Path) -> list[tuple[str, int]]:
    """Return [(sha, unix_ts), ...] for commits touching registry.json,
    oldest first."""
    raw = _git(
        ["log", "--reverse", "--format=%H %ct", "--", REGISTRY_REL],
        project_root,
    )
    out: list[tuple[str, int]] = []
    for line in raw.splitlines():
        parts = line.strip().split()
        if len(parts) != 2:
            continue
        sha, ts = parts
        try:
            out.append((sha, int(ts)))
        except ValueError:
            continue
    return out


def _completed_count_at(sha: str, project_root: Path) -> int | None:
    """Count tasks in 'completed' status in the registry at the given sha.
    Returns None if the file didn't exist or wasn't parseable."""
    raw = _git(["show", f"{sha}:{REGISTRY_REL}"], project_root)
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    tasks = data.get("tasks", [])
    # Schema is a list of task dicts (verified in current registry)
    if isinstance(tasks, dict):
        # Defensive — if some historical commit used the dict shape
        tasks = list(tasks.values())
    return sum(1 for t in tasks if isinstance(t, dict) and t.get("status") == "completed")


def _series_from_commits(commits: list[tuple[str, int]],
                        project_root: Path) -> list[DayPoint]:
    """Bucket commits by UTC day, take the LAST commit per day as that day's
    final state, then compute deltas vs the previous day."""
    # day → last (ts, completed_count)
    by_day: dict[str, tuple[int, int]] = {}
    for sha, ts in commits:
        day = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        count = _completed_count_at(sha, project_root)
        if count is None:
            continue
        prev = by_day.get(day)
        if prev is None or ts > prev[0]:
            by_day[day] = (ts, count)

    ordered_days = sorted(by_day.keys())
    out: list[DayPoint] = []
    prev_count = 0
    for day in ordered_days:
        _ts, count = by_day[day]
        delta = count - prev_count
        out.append(DayPoint(day=day, completed=count, delta=delta))
        prev_count = count
    return out


# ---- Cache ---------------------------------------------------------------

def _cache_path(project_root: Path) -> Path:
    return project_root / CACHE_REL


def _read_cache(project_root: Path) -> dict | None:
    p = _cache_path(project_root)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _write_cache(project_root: Path, payload: dict) -> None:
    p = _cache_path(project_root)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(payload, indent=2))
    except OSError:
        # Cache is best-effort — don't fail the request
        pass


def _build_series(project_root: Path) -> tuple[list[DayPoint], str | None, str]:
    """Return (series, latest_sha, source) where source is 'cache' or 'fresh'."""
    commits = _registry_commits(project_root)
    if not commits:
        return [], None, "fresh"

    latest_sha = commits[-1][0]

    cache = _read_cache(project_root)
    if cache and cache.get("latest_sha") == latest_sha:
        # Cache hit — rebuild DayPoint objects from raw dicts
        try:
            series = [
                DayPoint(day=p["day"], completed=int(p["completed"]),
                         delta=int(p["delta"]))
                for p in cache.get("series", [])
            ]
            return series, latest_sha, "cache"
        except (KeyError, TypeError, ValueError):
            pass  # Fall through to fresh build

    # Fresh build
    series = _series_from_commits(commits, project_root)
    _write_cache(project_root, {
        "latest_sha": latest_sha,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "series": [
            {"day": p.day, "completed": p.completed, "delta": p.delta}
            for p in series
        ],
    })
    return series, latest_sha, "fresh"


# ---- SVG render ----------------------------------------------------------

# Chart geometry (one SVG, two stacked panels: bars on top, cumulative below)
CHART_W = 920
CHART_H = 360
PAD_L = 56
PAD_R = 24
PAD_T = 28
PAD_B = 48
CUM_PANEL_H = 110

BAR_PANEL_H = CHART_H - PAD_T - PAD_B - CUM_PANEL_H - 24  # 24 = gap between panels


def _render_svg(series: list[DayPoint]) -> str:
    if not series:
        return ""

    n = len(series)
    deltas = [p.delta for p in series]
    cumulative = [p.completed for p in series]

    max_delta = max(max(deltas), 1)
    max_cum = max(max(cumulative), 1)

    inner_w = CHART_W - PAD_L - PAD_R

    # Bar panel placement
    bar_top = PAD_T
    bar_bot = bar_top + BAR_PANEL_H

    # Cumulative panel placement (below bars + gap)
    cum_top = bar_bot + 24
    cum_bot = cum_top + CUM_PANEL_H

    # X positions — center bars per slot
    if n == 1:
        slot_w = inner_w
        bar_w = min(40, inner_w * 0.5)
    else:
        slot_w = inner_w / n
        bar_w = max(6, min(slot_w * 0.7, 30))

    def x_for(i: int) -> float:
        return PAD_L + slot_w * i + slot_w / 2

    # ---- Build SVG ----
    parts: list[str] = []
    parts.append(
        f'<svg viewBox="0 0 {CHART_W} {CHART_H}" '
        f'xmlns="http://www.w3.org/2000/svg" class="burndown-svg" '
        f'role="img" aria-label="Burndown chart: tasks completed per day">'
    )

    # Axis labels (left edge — counts)
    parts.append(f'''
      <g class="axis">
        <text x="{PAD_L - 8}" y="{bar_top + 4}" text-anchor="end">{max_delta}</text>
        <text x="{PAD_L - 8}" y="{bar_bot}" text-anchor="end">0</text>
        <text x="{PAD_L - 8}" y="{cum_top + 4}" text-anchor="end">{max_cum}</text>
        <text x="{PAD_L - 8}" y="{cum_bot}" text-anchor="end">0</text>
      </g>
    ''')

    # Bar panel baseline
    parts.append(
        f'<line class="baseline" x1="{PAD_L}" y1="{bar_bot}" '
        f'x2="{PAD_L + inner_w}" y2="{bar_bot}" />'
    )
    parts.append(
        f'<line class="baseline" x1="{PAD_L}" y1="{cum_bot}" '
        f'x2="{PAD_L + inner_w}" y2="{cum_bot}" />'
    )

    # Panel labels (top-left of each panel)
    parts.append(
        f'<text class="panel-label" x="{PAD_L}" y="{bar_top - 8}">'
        f'Per-day completions</text>'
    )
    parts.append(
        f'<text class="panel-label" x="{PAD_L}" y="{cum_top - 8}">'
        f'Cumulative completed</text>'
    )

    # ---- Bars ----
    for i, p in enumerate(series):
        cx = x_for(i)
        d = p.delta
        if d == 0:
            # Empty marker (small dot at baseline) so the day still registers
            parts.append(
                f'<circle class="bar-empty" cx="{cx:.1f}" cy="{bar_bot}" r="1.5">'
                f'<title>{p.day}: no completions</title></circle>'
            )
            continue
        h = (abs(d) / max_delta) * (BAR_PANEL_H - 4)
        if d > 0:
            y = bar_bot - h
            cls = "bar bar-positive"
        else:
            y = bar_bot  # negative bar grows downward (rare — task un-completed)
            cls = "bar bar-negative"
        parts.append(
            f'<rect class="{cls}" x="{cx - bar_w/2:.1f}" y="{y:.1f}" '
            f'width="{bar_w:.1f}" height="{h:.1f}" rx="2">'
            f'<title>{p.day}: {"+" if d > 0 else ""}{d} '
            f'(total {p.completed})</title></rect>'
        )

    # ---- Cumulative line ----
    if n >= 2:
        # Build polyline points
        pts = []
        for i, p in enumerate(series):
            cx = x_for(i)
            cy = cum_bot - (p.completed / max_cum) * (CUM_PANEL_H - 4)
            pts.append(f"{cx:.1f},{cy:.1f}")
        # Area fill (under the line)
        area_pts = [f"{x_for(0):.1f},{cum_bot}"] + pts + [f"{x_for(n-1):.1f},{cum_bot}"]
        parts.append(
            f'<polygon class="cum-area" points="{" ".join(area_pts)}" />'
        )
        parts.append(
            f'<polyline class="cum-line" points="{" ".join(pts)}" />'
        )
    # Cumulative dots
    for i, p in enumerate(series):
        cx = x_for(i)
        cy = cum_bot - (p.completed / max_cum) * (CUM_PANEL_H - 4)
        parts.append(
            f'<circle class="cum-dot" cx="{cx:.1f}" cy="{cy:.1f}" r="3">'
            f'<title>{p.day}: {p.completed} total completed</title></circle>'
        )

    # ---- X-axis day labels (sparse if many days) ----
    if n <= 14:
        step = 1
    elif n <= 28:
        step = 2
    else:
        step = max(1, n // 12)

    for i, p in enumerate(series):
        if i % step != 0 and i != n - 1:
            continue
        cx = x_for(i)
        # Show only MM-DD if all in same year, else full
        label = p.day[5:]  # strip year for brevity
        parts.append(
            f'<text class="x-label" x="{cx:.1f}" y="{cum_bot + 16}" '
            f'text-anchor="middle">{label}</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts)


# ---- Empty-state -------------------------------------------------------

_EMPTY_NO_GIT = """
<div class="empty-state">
  <div class="empty-state-mark">∅</div>
  <h2>No history yet</h2>
  <p>The burndown chart is built from git commits that touch
     <code>docs/tasks/registry.json</code>. There aren't any committed changes
     to that file yet.</p>
  <p class="empty-state-hint">Commit some forge task state changes and reload —
     the chart will populate automatically.</p>
</div>
"""

_EMPTY_NO_REGISTRY = """
<div class="empty-state">
  <div class="empty-state-mark">∅</div>
  <h2>No registry</h2>
  <p><code>docs/tasks/registry.json</code> doesn't exist in this project yet.</p>
  <p class="empty-state-hint">Run <code>forge task add T001 --epic E01 --name "first task"</code>
     to bootstrap the registry.</p>
</div>
"""

_EMPTY_INSUFFICIENT = """
<div class="empty-state empty-state-soft">
  <div class="empty-state-mark">·</div>
  <h2>One day of history</h2>
  <p>Only one calendar day of registry changes is recorded so far.
     The bar chart needs at least two days to be meaningful.</p>
  <p class="empty-state-hint">Reload tomorrow.</p>
</div>
"""


# ---- Page render -------------------------------------------------------

def render_index(project_root: Path) -> str:
    """Render the /burndown HTML page."""
    registry = project_root / REGISTRY_REL
    if not registry.exists():
        body = _EMPTY_NO_REGISTRY
        summary = ""
    else:
        series, latest_sha, source = _build_series(project_root)
        if not series:
            body = _EMPTY_NO_GIT
            summary = ""
        elif len(series) == 1:
            body = _EMPTY_INSUFFICIENT
            summary = _summary_html(series, source)
        else:
            chart = _render_svg(series)
            body = f'<div class="burndown-chart">{chart}</div>{_table_html(series)}'
            summary = _summary_html(series, source)

    return _PAGE_TEMPLATE.replace("__SUMMARY__", summary).replace("__BODY__", body)


def _summary_html(series: list[DayPoint], source: str) -> str:
    if not series:
        return ""
    total = series[-1].completed
    days = len(series)
    last_delta = series[-1].delta
    # Average completions per day (over days that had ≥1 completion)
    active_days = [p for p in series if p.delta > 0]
    if active_days:
        avg = sum(p.delta for p in active_days) / len(active_days)
        avg_str = f"{avg:.1f}/day"
    else:
        avg_str = "—"

    delta_class = "pos" if last_delta > 0 else ("neg" if last_delta < 0 else "zero")
    delta_sign = "+" if last_delta > 0 else ""

    return f"""
    <div class="burndown-summary">
      <div class="bd-chip">
        <div class="bd-chip-key">Total completed</div>
        <div class="bd-chip-val">{total}</div>
      </div>
      <div class="bd-chip">
        <div class="bd-chip-key">Days of history</div>
        <div class="bd-chip-val">{days}</div>
      </div>
      <div class="bd-chip">
        <div class="bd-chip-key">Latest day</div>
        <div class="bd-chip-val">{series[-1].day}</div>
      </div>
      <div class="bd-chip">
        <div class="bd-chip-key">Latest delta</div>
        <div class="bd-chip-val bd-delta-{delta_class}">{delta_sign}{last_delta}</div>
      </div>
      <div class="bd-chip">
        <div class="bd-chip-key">Avg / active day</div>
        <div class="bd-chip-val">{avg_str}</div>
      </div>
      <div class="bd-chip bd-chip-soft" title="Series source">
        <div class="bd-chip-key">Source</div>
        <div class="bd-chip-val">{source}</div>
      </div>
    </div>
    """


def _table_html(series: list[DayPoint]) -> str:
    """Recent days table (last 14) for skim-reading next to the chart."""
    recent = series[-14:][::-1]  # newest first
    rows = []
    for p in recent:
        delta_class = "pos" if p.delta > 0 else ("neg" if p.delta < 0 else "zero")
        sign = "+" if p.delta > 0 else ""
        rows.append(
            f'<tr>'
            f'<td class="bd-day">{p.day}</td>'
            f'<td class="bd-delta bd-delta-{delta_class}">{sign}{p.delta}</td>'
            f'<td class="bd-cum">{p.completed}</td>'
            f'</tr>'
        )
    return f"""
    <div class="burndown-table-wrap">
      <h3 class="burndown-table-title">Recent days</h3>
      <table class="burndown-table">
        <thead>
          <tr><th>Day</th><th>Δ</th><th>Total</th></tr>
        </thead>
        <tbody>
          {''.join(rows)}
        </tbody>
      </table>
    </div>
    """


_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Burndown — Forge Dashboard</title>
<link rel="stylesheet" href="/static/dashboard.css">
<link rel="stylesheet" href="/static/content.css">
<link rel="stylesheet" href="/static/burndown.css">
</head>
<body class="doc-body">
  <header class="doc-header">
    <div class="doc-title">
      <h1>Burndown</h1>
      <p class="doc-subtitle">Tasks completed per day, derived from git history of
        <code>docs/tasks/registry.json</code>.</p>
    </div>
  </header>
  __SUMMARY__
  <main class="doc-main">
    __BODY__
  </main>
</body>
</html>
"""
