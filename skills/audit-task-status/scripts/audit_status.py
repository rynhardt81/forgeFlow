#!/usr/bin/env python3
"""Audit Forge Flow task-status alignment across the three layers.

The registry (docs/tasks/registry.json) is the source of truth. This script is
READ-ONLY — it detects drift and prints a report; it never edits anything. The
fixes (epic-file counters, stale table rows) are small targeted edits the skill
applies by hand, because epic files are human-authored prose.

Reports:
  1. task-file frontmatter `status:` that disagrees with the registry
  2. epic-file per-task table rows whose status disagrees with the registry
  3. epic-file progress counters vs the registry's completed/total per epic
  4. registry tasks with no body file on disk (registry-health, not a status bug)

Exit code: 0 if no status mismatches (layers agree); 1 if any mismatch found.
Counter staleness and missing-body-files are reported but do NOT fail the exit
code on their own — run with --strict to also fail on those.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


def find_project_root(start: Path) -> Path:
    """Walk up for docs/tasks/registry.json — the unambiguous project marker."""
    for p in [start, *start.parents]:
        if (p / "docs" / "tasks" / "registry.json").exists():
            return p
    raise SystemExit("error: could not find docs/tasks/registry.json above cwd")


def load_registry(root: Path) -> list[dict]:
    reg = root / "docs" / "tasks" / "registry.json"
    if not reg.exists():
        # Clean exit instead of a raw FileNotFoundError traceback — covers an
        # explicit --project-root that points at a non-Forge tree.
        raise SystemExit(f"error: no task registry at {reg}")
    raw = json.loads(reg.read_text())
    return raw["tasks"] if isinstance(raw, dict) else raw


# Match a task id at a token boundary. Forge IDs take several suffix shapes,
# all of which are DISTINCT registry entries (so the glob index must key on the
# full id, not a truncated prefix):
#   T123              base
#   T123a             letter sub-task
#   T412e-N4          "-N#" review-round suffix
#   T412g-1, T414a-3  "-#" split suffix   ← earlier regex missed these, so
#                     `T412g-1` indexed under `T412g` and its body file was
#                     falsely reported missing.
_TASK_ID = r"T\d+[a-z]?(?:-N?\d+)?"

# The Forge task-state enum. Epic tables put the status in a column whose
# POSITION varies by epic (5-col vs 6-col layouts exist), so we identify the
# status cell by its VALUE, not its position. Order longest-first isn't needed
# since we match whole cells.
_VALID_STATUSES = {
    "pending",
    "ready",
    "in_progress",
    "pr_pending",
    "completed",
    "continuation",
    "closed",
    "superseded",
}


def resolve_body_file(root: Path, task: dict, glob_index: dict[str, list[Path]]) -> Path | None:
    """Find a task's body file. The registry `file` field is authoritative — it
    points at the real path wherever it lives (docs/epics/**/tasks/, the
    docs/tasks/orphan/ dir, etc.). Earlier this script only globbed
    docs/epics/**/tasks/ and so falsely reported orphan-dir tasks (T110-T114…)
    and suffixed IDs (T247e1…) as "missing". Resolution order:
      1. registry `file` field, resolved against project root → if it exists, use it.
      2. fall back to a glob index over the whole docs/ tree (for tasks whose
         `file` field is null — `forge task add` without --isa never sets it).
    Returns None only when neither resolves (a genuinely missing body file).
    """
    fld = task.get("file")
    if fld:
        p = (root / fld) if not Path(fld).is_absolute() else Path(fld)
        if p.exists():
            return p
        # file field set but path missing — fall through to glob, then report.
    hits = glob_index.get(task["id"])
    return hits[0] if hits else None


# A real task BODY file lives in one of these location shapes. Files matching a
# `T###-…md` name elsewhere (docs/debug/, docs/processed/, planning notes) are
# NOT body files and must not shadow the real one — that collision falsely
# flipped T475 (a docs/debug/ triage doc, status: draft) over its real body
# file (status: completed).
_BODY_DIR_HINTS = ("/tasks/", "/orphan/")
# id-then-boundary: the id is followed by `-` (slug separator) or end-of-stem.
# Critically the boundary is OUTSIDE the captured id and the id pattern now
# includes `-#`/`-N#` suffixes, so `T412g-1` captures fully (not as `T412g`).
_BODY_NAME = re.compile(rf"^({_TASK_ID})(?:-|\.md$)")


def build_glob_index(root: Path) -> dict[str, list[Path]]:
    """Map task id -> candidate body files under docs/, ranked so a real body
    file beats a same-prefix non-body file. Used only as the fallback when a
    task's registry `file` field is null.

    Two guards learned from eval false positives:
      - Only files in a `/tasks/` or `/orphan/` path count as body files; a
        `docs/debug/T###-*.md` triage note no longer shadows the real body.
      - The id is matched with the full suffix (`T412g-1`, not `T412g`) so
        split sub-tasks index under their own id.
    """
    out: dict[str, list[Path]] = defaultdict(list)
    docs = root / "docs"
    if not docs.exists():
        return out
    for f in docs.rglob("T*.md"):
        posix = f.as_posix()
        if not any(h in posix for h in _BODY_DIR_HINTS):
            continue  # not in a body-file location — skip (debug/processed/etc.)
        m = _BODY_NAME.match(f.name)
        if m:
            out[m.group(1)].append(f)
    return out


def frontmatter_status(path: Path) -> str | None:
    m = re.search(r"^status:\s*(\S+)", path.read_text(), re.M)
    return m.group(1) if m else None


def epic_files(root: Path) -> dict[str, Path]:
    """Map epic id -> its epic file (docs/epics/<epic>/<epic>.md)."""
    out: dict[str, Path] = {}
    epics = root / "docs" / "epics"
    if not epics.exists():
        return out
    for d in epics.iterdir():
        if not d.is_dir():
            continue
        f = d / f"{d.name}.md"
        if f.exists():
            m = re.match(r"(E\d+)", d.name)
            if m:
                out[m.group(1)] = f
    return out


def _cell_status(cell: str) -> str | None:
    """Extract a status enum from a table/list cell, tolerant of annotations.

    Epic authors decorate status cells: `completed (PR #254)`, `closed — phantom
    task`, `~~completed~~`, `completed ✅`. Take the LEADING token (before any
    `(`, em-dash, or whitespace) and check it against the enum. Returns None if
    the leading token isn't a status. (Earlier this required the whole cell to
    equal a status, so it silently skipped every annotated cell — under-reporting.)
    """
    c = cell.strip().strip("~").strip().lower()
    # leading token = up to the first annotation boundary
    token = re.split(r"[\s(—–-]", c, maxsplit=1)[0]
    return token if token in _VALID_STATUSES else None


def epic_row_statuses(text: str) -> dict[str, str]:
    """First-occurrence task-id -> status across BOTH epic idioms:

    1. Pipe tables: `| T### | desc | <status> | … |` — column position varies
       per epic (5/6 cols, E38 has Track before Status), so we scan cells and
       take the one whose LEADING token is a status enum (annotation-tolerant).
    2. Checklist epics (e.g. E25): `- [x] T###: … ✅` / `- [~] T###a: …`. The
       checkbox marker maps to a status: [x]→completed, [ ]→pending/ready,
       [~]→in_progress/superseded — ambiguous, so we DON'T infer status from the
       box alone; we only record a checklist row when the line ALSO contains an
       explicit status word (e.g. "superseded", "completed"). This avoids
       guessing while still catching the real drift (E25 T149a checkbox says
       done but registry says superseded — the line's words reveal it).

    Only the first row per id is taken — later occurrences are usually the dated
    progress-log, which is history, not current state.
    """
    rows: dict[str, str] = {}

    table_id = re.compile(rf"^\|\s*~?~?({_TASK_ID})~?~?\s*\|", re.M)
    checklist_id = re.compile(rf"^\s*[-*]\s*\[[ x~\-]\]\s*~?~?({_TASK_ID})~?~?\b", re.M)

    for raw in text.splitlines():
        line = raw.strip()

        # --- pipe table row ---
        tm = table_id.match(line)
        if tm:
            tid = tm.group(1)
            if tid in rows:
                continue
            cells = line.strip("|").split("|")
            found = [s for c in cells if (s := _cell_status(c))]
            if len(found) == 1:
                rows[tid] = found[0]
            # 0 or >1 status cells → ambiguous, skip (don't guess)
            continue

        # --- checklist row (E25-style) ---
        cm = checklist_id.match(line)
        if cm:
            tid = cm.group(1)
            if tid in rows:
                continue
            # only record if an explicit status word appears in the line text
            words = re.findall(r"[a-z_]+", line.lower())
            statuses_in_line = [w for w in words if w in _VALID_STATUSES]
            # de-dupe; require exactly one distinct status word to stay unambiguous
            distinct = set(statuses_in_line)
            if len(distinct) == 1:
                rows[tid] = distinct.pop()
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project-root", type=Path, default=None)
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument(
        "--strict",
        action="store_true",
        help="also fail (rc=1) on stale counters / missing body files",
    )
    args = ap.parse_args()

    root = args.project_root or find_project_root(Path.cwd())
    tasks = load_registry(root)
    reg = {t["id"]: t["status"] for t in tasks}
    by_id = {t["id"]: t for t in tasks}
    glob_index = build_glob_index(root)

    # 1. task-file frontmatter mismatches + genuinely-missing body files.
    # Resolution prefers the registry `file` field (authoritative — covers the
    # docs/tasks/orphan/ dir + suffixed IDs), falling back to the docs-wide glob.
    file_mismatches = []
    missing_files = []
    for tid, rstatus in reg.items():
        f = resolve_body_file(root, by_id[tid], glob_index)
        if f is None:
            missing_files.append(tid)
            continue
        fstatus = frontmatter_status(f)
        if fstatus != rstatus:
            file_mismatches.append(
                {"id": tid, "registry": rstatus, "file": fstatus, "path": str(f)}
            )

    # 2 + 3. epic-file rows + counters + prose status header
    epic_counts: dict[str, Counter] = defaultdict(Counter)
    for t in tasks:
        epic_counts[t.get("epic")][t["status"]] += 1
    # Epic-level status: an epic is "completed" when every task it owns is in a
    # terminal state (completed/superseded/closed); otherwise in_progress. Used
    # to check the epic file's prose `**Status:**` header.
    TERMINAL = {"completed", "superseded", "closed"}

    epic_row_mismatches = []
    epic_counter_report = []
    epic_header_mismatches = []
    for eid, ef in epic_files(root).items():
        text = ef.read_text()
        rows = epic_row_statuses(text)
        for tid, tstatus in rows.items():
            if tid in reg and reg[tid] != tstatus:
                epic_row_mismatches.append(
                    {
                        "id": tid,
                        "epic": eid,
                        "table": tstatus,
                        "registry": reg[tid],
                        "path": str(ef),
                    }
                )
        c = epic_counts.get(eid, Counter())
        total = sum(c.values())
        done = c.get("completed", 0)
        # Pull the epic file's claimed "M completed ... N total" if present.
        claim = re.search(r"(\d+)\s+total[^\d]*?(\d+)\s+completed", text)
        claimed = (
            {"total": int(claim.group(1)), "completed": int(claim.group(2))}
            if claim
            else None
        )
        stale = claimed is not None and (
            claimed["total"] != total or claimed["completed"] != done
        )
        if total:  # only epics that actually own tasks
            epic_counter_report.append(
                {
                    "epic": eid,
                    "registry_completed": done,
                    "registry_total": total,
                    "claimed": claimed,
                    "stale": stale,
                    "path": str(ef),
                }
            )

            # Prose `**Status:** <x>` header (and a plain `status:` frontmatter
            # line, if present in the epic file). The epic is terminal when all
            # its tasks are terminal. We only flag a clear contradiction:
            # header says in_progress/pending while every task is done, or
            # header says completed while open tasks remain.
            all_terminal = bool(c) and all(s in TERMINAL for s in c.keys())
            for label, pat in (
                ("prose", r"\*\*Status:\*\*\s*`?([a-z_]+)`?"),
                ("frontmatter", r"^status:\s*([a-z_]+)"),
            ):
                hm = re.search(pat, text, re.M)
                if not hm:
                    continue
                claimed_status = hm.group(1)
                expected = "completed" if all_terminal else "in_progress"
                # Only flag the unambiguous contradictions, not every nuance:
                contradiction = (
                    all_terminal and claimed_status in {"in_progress", "pending", "ready"}
                ) or (
                    not all_terminal and claimed_status in {"completed", "closed"}
                )
                if contradiction:
                    epic_header_mismatches.append(
                        {
                            "epic": eid,
                            "where": label,
                            "claimed": claimed_status,
                            "expected": expected,
                            "path": str(ef),
                        }
                    )

    result = {
        "task_file_mismatches": file_mismatches,
        "epic_row_mismatches": epic_row_mismatches,
        "epic_header_mismatches": epic_header_mismatches,
        "epic_counters": epic_counter_report,
        "tasks_without_body_file": missing_files,
        "registry_task_count": len(reg),
    }

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Registry: {len(reg)} tasks (source of truth)\n")

        print(f"[1] Task-file frontmatter mismatches: {len(file_mismatches)}")
        for m in file_mismatches:
            print(f"    ⚠ {m['id']}: registry={m['registry']} file={m['file']}")
        if not file_mismatches:
            print("    ✅ all task files match the registry")

        print(f"\n[2] Epic-file table-row mismatches: {len(epic_row_mismatches)}")
        for m in epic_row_mismatches:
            print(
                f"    ⚠ {m['epic']} {m['id']}: table={m['table']} "
                f"registry={m['registry']}"
            )
        if not epic_row_mismatches:
            print("    ✅ all epic-file rows match the registry")

        print(
            f"\n[2b] Epic prose/frontmatter status-header contradictions: "
            f"{len(epic_header_mismatches)}"
        )
        for m in epic_header_mismatches:
            print(
                f"    ⚠ {m['epic']} ({m['where']}): says '{m['claimed']}' but "
                f"all tasks imply '{m['expected']}'"
            )
        if not epic_header_mismatches:
            print("    ✅ all epic status headers consistent with task rollup")

        stale_counters = [e for e in epic_counter_report if e["stale"]]
        print(f"\n[3] Stale epic counters: {len(stale_counters)}")
        for e in epic_counter_report:
            flag = "⚠ STALE" if e["stale"] else "✅"
            claimed = (
                f" (file claims {e['claimed']['completed']}/{e['claimed']['total']})"
                if e["claimed"]
                else " (no counter line found)"
            )
            print(
                f"    {flag} {e['epic']}: registry "
                f"{e['registry_completed']}/{e['registry_total']}{claimed}"
            )

        print(f"\n[4] Registry tasks with NO body file: {len(missing_files)}")
        if missing_files:
            print(f"    {missing_files}")
            print(
                "    (registry-health, not a status bug — fix via "
                "`forge task reconcile-files [--apply]` if the user wants)"
            )

    status_drift = (
        bool(file_mismatches)
        or bool(epic_row_mismatches)
        or bool(epic_header_mismatches)
    )
    extra_drift = args.strict and (
        any(e["stale"] for e in epic_counter_report) or bool(missing_files)
    )
    return 1 if (status_drift or extra_drift) else 0


if __name__ == "__main__":
    sys.exit(main())
