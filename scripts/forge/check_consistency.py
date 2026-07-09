#!/usr/bin/env python3
"""
check_consistency.py
Claude Forge consistency checker — closes the disk/registry drift gap.

Detects 7 classes of drift between docs/tasks/registry.json and
docs/epics/E*/tasks/T*.md task files:

  Auto-fixable (--fix applies them deterministically):
    #4  registry.stats numbers don't match actual task/epic counts
    #5  pending tasks whose dependencies are all done -> ready
    #6  task file status frontmatter disagrees with registry status
    #7  in_progress tasks with stale lock past lockTimeoutSeconds

  Blocking (--strict exits 1):
    #1  task file exists on disk, ID missing from registry.tasks
    #2  epic dir exists, ID missing from registry.epics
    #3  completedAt < createdAt (only flagged when both timestamps present)

Usage:
  check_consistency.py            human-readable findings, exit 0
  check_consistency.py --fix      apply auto-fixes, exit 0
  check_consistency.py --strict   exit 1 if blocking findings remain
  check_consistency.py --summary  one-paragraph banner (SessionStart use)
  check_consistency.py --json     machine-readable structured output

Schema assumptions (Claude Forge v2.0.0):
  - registry.tasks is a list of {id, status, dependencies, lock, ...}
  - registry.epics is a list of {id, status, tasks: [...]}
  - tasks have a single `lock: {...}|null` object, not flat lockedBy/lockedAt
  - task files use YAML frontmatter delimited by `---` lines, with `status: X`
  - lockTimeoutSeconds lives at registry.settings.lockTimeoutSeconds (default 3600)

Shares its registry/frontmatter/lock primitives with the sibling module
registry_ops.py (both live in scripts/forge/, so `import registry_ops`
resolves whether this file is invoked as a script or imported by tests) —
see registry_ops.py for the canonical implementations.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import registry_ops

# Pre-compiled regex (perf budget <2s on 500-task synthetic registries).
# Match strictly Tnnn-... or Tnnn.md — exclude split-task suffixes (T149a, T149b)
# so they don't get mistaken for duplicates of T149.
_TASK_FILENAME_RE = re.compile(r"^T(\d+)(?=[-.])")
_EPIC_DIR_RE = re.compile(r"^E(\d+)")

# Frontmatter parsers. Scope to the first `---` ... `---` block at the top
# of the file so a stray `status:` later in the body doesn't get rewritten.
# The status pattern uses [ \t]* (NOT \s*) for trailing whitespace because
# \s includes \n — and at end of the frontmatter block, \s*$ would gobble
# the closing newline, fusing the next line onto the status row.
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?\n)---\s*(?:\n|$)", re.DOTALL)
_FRONTMATTER_STATUS_RE = re.compile(r"^(status[ \t]*:[ \t]*)(\S+)[ \t]*$", re.MULTILINE)
_FRONTMATTER_NAME_RE = re.compile(r"^(name[ \t]*:[ \t]*)(.+?)[ \t]*$", re.MULTILINE)

# Severities.
SEV_BLOCKING = "blocking"
SEV_AUTO = "auto-fix"
SEV_INFO = "info"

# Drift class identifiers.
CLS_FILE_NOT_IN_REGISTRY = "file-not-in-registry"
CLS_EPIC_NOT_IN_REGISTRY = "epic-not-in-registry"
CLS_COMPLETEDAT_MONOTONIC = "completedat-monotonic"
CLS_STATS_DRIFT = "stats-drift"
CLS_PENDING_READY = "pending-ready"
CLS_FILE_VS_REGISTRY_STATUS = "file-vs-registry-status"
CLS_FILE_VS_REGISTRY_NAME = "file-vs-registry-name"
CLS_STALE_LOCK = "stale-lock"
CLS_TASK_WITHOUT_ISA = "task-without-isa"

DEFAULT_LOCK_TIMEOUT = 3600

# Status values that count as "done" for the purpose of unblocking
# downstream dependencies. `pr_pending` qualifies because the
# implementation is finished — only the merge step remains, and
# downstream tasks can start in parallel with review.
DONE_FOR_DEPS = frozenset({"completed", "pr_pending"})


@dataclass
class Finding:
    cls: str
    severity: str
    message: str
    auto_fixable: bool
    target: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def get_project_root(override: Path | None = None) -> Path:
    """Resolve project root.

    Order: explicit override -> CLAUDE_PROJECT_DIR env -> docs/tasks/registry.json
    walk -> git toplevel -> cwd. Anchoring on registry.json (not CLAUDE.md)
    avoids the .claude/CLAUDE.md trap that bites helpers in installed projects.
    """
    if override is not None:
        return override
    env_root = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_root and Path(env_root).exists():
        return Path(env_root)
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "docs" / "tasks" / "registry.json").exists():
            return current
        current = current.parent
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True
        )
        return Path(out.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path.cwd()


def parse_rfc3339(value: str) -> datetime | None:
    """Parse RFC3339 timestamps. Returns a tz-aware datetime (UTC if naive)."""
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def load_registry(path: Path) -> dict[str, Any] | None:
    """None-on-error wrapper around registry_ops.load_registry.

    The checker no-ops on a missing/corrupt registry.json (new projects
    that haven't initialized one yet), unlike registry_ops.load_registry
    which raises — that's a deliberate, preserved contract difference.
    """
    try:
        return registry_ops.load_registry(path)
    except (OSError, json.JSONDecodeError):
        return None


def _parse_frontmatter_status(content: str) -> str:
    """Return the status value from a task file's YAML frontmatter, lower-cased.

    Empty string when the file has no frontmatter or no status field.
    """
    fm = _FRONTMATTER_RE.match(content)
    if not fm:
        return ""
    m = _FRONTMATTER_STATUS_RE.search(fm.group(1))
    if not m:
        return ""
    return m.group(2).strip().lower()


def _parse_frontmatter_name(content: str) -> str:
    """Return the (unquoted, unescaped) name value from frontmatter."""
    fm = _FRONTMATTER_RE.match(content)
    if not fm:
        return ""
    m = _FRONTMATTER_NAME_RE.search(fm.group(1))
    if not m:
        return ""
    return registry_ops._yaml_unquote_scalar(m.group(2).strip())


def gather_task_files(epics_dir: Path) -> list[tuple[Path, str, str, str]]:
    """Return (file_path, id_from_filename, status, name) for each task file.

    Reads each file once and caches the parsed status + name, so the
    per-check helpers don't re-walk the disk. `name` is empty string when
    the frontmatter has no `name:` field.
    """
    out: list[tuple[Path, str, str, str]] = []
    if not epics_dir.exists():
        return out
    for epic_dir in sorted(epics_dir.iterdir()):
        if not (epic_dir.is_dir() and _EPIC_DIR_RE.match(epic_dir.name)):
            continue
        tasks_dir = epic_dir / "tasks"
        if not tasks_dir.exists():
            continue
        for tf in sorted(tasks_dir.glob("T*.md")):
            m = _TASK_FILENAME_RE.match(tf.name)
            if not m:
                continue
            tid = f"T{m.group(1)}"
            try:
                content = tf.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                content = ""
            out.append((
                tf,
                tid,
                _parse_frontmatter_status(content),
                _parse_frontmatter_name(content),
            ))
    return out


def gather_epic_dirs(epics_dir: Path) -> list[str]:
    if not epics_dir.exists():
        return []
    out = []
    for epic_dir in sorted(epics_dir.iterdir()):
        if not epic_dir.is_dir():
            continue
        m = _EPIC_DIR_RE.match(epic_dir.name)
        if m:
            out.append(f"E{m.group(1)}")
    return out


# --- Check functions -------------------------------------------------------


def check_file_not_in_registry(
    registry: dict[str, Any],
    task_files: list[tuple[Path, str, str, str]],
) -> list[Finding]:
    """Drift #1: task file on disk but ID missing from registry.tasks."""
    registry_ids = {t.get("id") for t in registry.get("tasks", [])}
    findings = []
    for tf, tid, _, _ in task_files:
        if tid not in registry_ids:
            findings.append(Finding(
                cls=CLS_FILE_NOT_IN_REGISTRY,
                severity=SEV_BLOCKING,
                message=(
                    f"blocking: {tid} task file exists at "
                    f"{tf.relative_to(tf.parents[3]) if len(tf.parents) >= 4 else tf} "
                    f"but is not in registry.json. "
                    f"Add a registry entry or remove the file."
                ),
                auto_fixable=False,
                target=tid,
                extra={"file": str(tf)},
            ))
    return findings


def check_epic_not_in_registry(
    registry: dict[str, Any],
    epic_ids_on_disk: list[str],
) -> list[Finding]:
    """Drift #2: epic dir exists but ID missing from registry.epics."""
    registry_ids = {e.get("id") for e in registry.get("epics", [])}
    findings = []
    for eid in epic_ids_on_disk:
        if eid not in registry_ids:
            findings.append(Finding(
                cls=CLS_EPIC_NOT_IN_REGISTRY,
                severity=SEV_BLOCKING,
                message=(
                    f"blocking: epic {eid} directory exists under docs/epics/ "
                    f"but is not in registry.epics. "
                    f"Add an entry to registry.json or remove the dir."
                ),
                auto_fixable=False,
                target=eid,
            ))
    return findings


def check_completedat_monotonic(registry: dict[str, Any]) -> list[Finding]:
    """Drift #3: completedAt < createdAt.

    Only flagged when BOTH timestamps are present and parseable. Older
    registries often lack `createdAt` on historical entries, and we don't
    want the check to flood findings on legacy data — strict ordering only
    applies to records new enough to have both fields.
    """
    findings = []
    for t in registry.get("tasks", []):
        completed = t.get("completedAt")
        created = t.get("createdAt")
        if not completed or not created:
            continue
        cdt = parse_rfc3339(completed)
        ndt = parse_rfc3339(created)
        if cdt is None or ndt is None:
            findings.append(Finding(
                cls=CLS_COMPLETEDAT_MONOTONIC,
                severity=SEV_BLOCKING,
                message=(
                    f"blocking: {t.get('id')} has unparseable RFC3339 timestamp "
                    f"(createdAt={created!r}, completedAt={completed!r})."
                ),
                auto_fixable=False,
                target=t.get("id"),
            ))
            continue
        if cdt < ndt:
            findings.append(Finding(
                cls=CLS_COMPLETEDAT_MONOTONIC,
                severity=SEV_BLOCKING,
                message=(
                    f"blocking: {t.get('id')} has completedAt ({completed}) "
                    f"earlier than createdAt ({created})."
                ),
                auto_fixable=False,
                target=t.get("id"),
            ))
    return findings


def check_stats_drift(registry: dict[str, Any]) -> list[Finding]:
    """Drift #4: registry.stats disagrees with actual task/epic counts."""
    expected = registry_ops._expected_stats(registry)
    findings = []
    actual = registry.get("stats", {})
    if actual.get("epics") != expected["epics"]:
        findings.append(Finding(
            cls=CLS_STATS_DRIFT,
            severity=SEV_AUTO,
            message=(
                f"auto-fixable: stats.epics drift "
                f"(actual={actual.get('epics')}, expected={expected['epics']})."
            ),
            auto_fixable=True,
            target="stats.epics",
        ))
    if actual.get("tasks") != expected["tasks"]:
        findings.append(Finding(
            cls=CLS_STATS_DRIFT,
            severity=SEV_AUTO,
            message=(
                f"auto-fixable: stats.tasks drift "
                f"(actual={actual.get('tasks')}, expected={expected['tasks']})."
            ),
            auto_fixable=True,
            target="stats.tasks",
        ))
    return findings


def fix_stats_drift(registry: dict[str, Any]) -> bool:
    """Recompute stats. Returns True if any change was applied."""
    expected = registry_ops._expected_stats(registry)
    changed = False
    stats = registry.setdefault("stats", {})
    if stats.get("epics") != expected["epics"]:
        stats["epics"] = expected["epics"]
        changed = True
    if stats.get("tasks") != expected["tasks"]:
        stats["tasks"] = expected["tasks"]
        changed = True
    return changed


def check_pending_ready(registry: dict[str, Any]) -> list[Finding]:
    """Drift #5: pending task with all deps done -> should be ready."""
    done_ids = {
        t["id"] for t in registry.get("tasks", [])
        if t.get("status") in DONE_FOR_DEPS
    }
    findings = []
    for t in registry.get("tasks", []):
        if t.get("status") != "pending":
            continue
        deps = t.get("dependencies") or []
        if not deps:
            continue
        if all(d in done_ids for d in deps):
            findings.append(Finding(
                cls=CLS_PENDING_READY,
                severity=SEV_AUTO,
                message=(
                    f"auto-fixable: {t.get('id')} status=pending but all "
                    f"dependencies {deps} are done; flip to ready."
                ),
                auto_fixable=True,
                target=t.get("id"),
            ))
    return findings


def fix_pending_ready(
    registry: dict[str, Any],
    task_files_index: dict[str, Path],
) -> bool:
    """Flip pending->ready in registry and patch the task file's frontmatter."""
    done_ids = {
        t["id"] for t in registry.get("tasks", [])
        if t.get("status") in DONE_FOR_DEPS
    }
    changed = False
    for t in registry.get("tasks", []):
        if t.get("status") != "pending":
            continue
        deps = t.get("dependencies") or []
        if not deps:
            continue
        if not all(d in done_ids for d in deps):
            continue
        t["status"] = "ready"
        changed = True
        tf = task_files_index.get(t.get("id"))
        if tf and tf.exists():
            try:
                body = tf.read_text(encoding="utf-8")
                new_body, did_change = registry_ops._rewrite_frontmatter_status(body, "ready")
                if did_change:
                    tf.write_text(new_body, encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                # Best-effort file rewrite — registry is the source of truth,
                # and the file-vs-registry check will surface any mismatch.
                pass
    return changed


def check_file_vs_registry_status(
    registry: dict[str, Any],
    task_files: list[tuple[Path, str, str, str]],
) -> list[Finding]:
    """Drift #6: task file frontmatter status != registry status.

    Auto-fixable in the registry-wins direction. The workflow reality is that
    agents update the registry when they lock/complete a task but rarely
    update the file's frontmatter; making this blocking floods the commit
    gate with false positives. Auto-fix keeps both sides in sync silently.
    """
    by_id = {t.get("id"): t for t in registry.get("tasks", [])}
    findings = []
    for tf, tid, file_status, _ in task_files:
        if not file_status:
            continue
        reg = by_id.get(tid)
        if not reg:
            # Already covered by drift #1.
            continue
        reg_status = (reg.get("status") or "").lower()
        if reg_status and file_status != reg_status:
            findings.append(Finding(
                cls=CLS_FILE_VS_REGISTRY_STATUS,
                severity=SEV_AUTO,
                message=(
                    f"auto-fixable: {tid} status mismatch — "
                    f"file says '{file_status}', registry says '{reg_status}'. "
                    f"Updating task file to match registry."
                ),
                auto_fixable=True,
                target=tid,
                extra={"file": str(tf), "file_status": file_status, "registry_status": reg_status},
            ))
    return findings


def fix_file_vs_registry_status(
    registry: dict[str, Any],
    task_files: list[tuple[Path, str, str, str]],
) -> bool:
    """Rewrite each drifted task file's frontmatter status to match registry."""
    by_id = {t.get("id"): t for t in registry.get("tasks", [])}
    changed = False
    for tf, tid, file_status, _ in task_files:
        if not file_status:
            continue
        reg = by_id.get(tid)
        if not reg:
            continue
        reg_status = (reg.get("status") or "").lower()
        if not reg_status or file_status == reg_status:
            continue
        try:
            content = tf.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        new_content, did_change = registry_ops._rewrite_frontmatter_status(content, reg_status)
        if did_change:
            tf.write_text(new_content, encoding="utf-8")
            changed = True
    return changed


def check_file_vs_registry_name(
    registry: dict[str, Any],
    task_files: list[tuple[Path, str, str, str]],
) -> list[Finding]:
    """Drift #8: task file frontmatter name != registry name.

    Auto-fixable in the registry-wins direction, mirroring drift #6 (status).
    Same rationale: hand-edits to frontmatter `name:` are common; making
    this blocking floods the commit gate. Auto-fix keeps both sides in sync
    silently.

    Files without a `name:` frontmatter field are skipped — we don't
    invent structure that wasn't there.
    """
    by_id = {t.get("id"): t for t in registry.get("tasks", [])}
    findings = []
    for tf, tid, _, file_name in task_files:
        if not file_name:
            continue
        reg = by_id.get(tid)
        if not reg:
            # Covered by drift #1.
            continue
        reg_name = reg.get("name") or ""
        if reg_name and file_name != reg_name:
            findings.append(Finding(
                cls=CLS_FILE_VS_REGISTRY_NAME,
                severity=SEV_AUTO,
                message=(
                    f"auto-fixable: {tid} name mismatch — "
                    f"file says {file_name!r}, registry says {reg_name!r}. "
                    f"Updating task file to match registry."
                ),
                auto_fixable=True,
                target=tid,
                extra={"file": str(tf), "file_name": file_name, "registry_name": reg_name},
            ))
    return findings


def fix_file_vs_registry_name(
    registry: dict[str, Any],
    task_files: list[tuple[Path, str, str, str]],
) -> bool:
    """Rewrite each drifted task file's frontmatter name to match registry."""
    by_id = {t.get("id"): t for t in registry.get("tasks", [])}
    changed = False
    for tf, tid, _, file_name in task_files:
        if not file_name:
            continue
        reg = by_id.get(tid)
        if not reg:
            continue
        reg_name = reg.get("name") or ""
        if not reg_name or file_name == reg_name:
            continue
        try:
            content = tf.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        new_content, did_change = registry_ops._rewrite_frontmatter_name(content, reg_name)
        if did_change:
            tf.write_text(new_content, encoding="utf-8")
            changed = True
    return changed


def _lock_locked_at(task: dict[str, Any]) -> str | None:
    """Extract lockedAt timestamp from the canonical `lock` object."""
    lock = task.get("lock")
    if isinstance(lock, dict):
        return lock.get("lockedAt") or lock.get("locked_at")
    return None


def check_stale_lock(
    registry: dict[str, Any],
    lock_timeout: int,
) -> list[Finding]:
    """Drift #7: in_progress with lock past lockTimeoutSeconds.

    Status remains in_progress on auto-fix — only the lock object is cleared.
    Rationale: in_progress here genuinely means "session active." If a PR is
    open and merging, the task should be in pr_pending (which doesn't take a
    session lock), so stale-lock-on-in_progress is unambiguously a stuck
    session, not a long-lived PR.
    """
    findings = []
    now = datetime.now(timezone.utc)
    for t in registry.get("tasks", []):
        if t.get("status") != "in_progress":
            continue
        locked_at = _lock_locked_at(t)
        if not locked_at:
            continue
        lt = parse_rfc3339(locked_at)
        if lt is None:
            continue
        age = (now - lt).total_seconds()
        if age > lock_timeout:
            findings.append(Finding(
                cls=CLS_STALE_LOCK,
                severity=SEV_AUTO,
                message=(
                    f"auto-fixable: {t.get('id')} lock is {int(age)}s old "
                    f"(>{lock_timeout}s timeout); clearing lock "
                    f"(status remains in_progress for session resume)."
                ),
                auto_fixable=True,
                target=t.get("id"),
            ))
    return findings


def fix_stale_lock(registry: dict[str, Any], lock_timeout: int) -> bool:
    """Clear stale `lock` objects on in_progress tasks. Status preserved."""
    changed = False
    now = datetime.now(timezone.utc)
    for t in registry.get("tasks", []):
        if t.get("status") != "in_progress":
            continue
        locked_at = _lock_locked_at(t)
        if not locked_at:
            continue
        lt = parse_rfc3339(locked_at)
        if lt is None:
            continue
        if (now - lt).total_seconds() > lock_timeout:
            t["lock"] = None
            changed = True
    return changed


def check_task_without_isa(
    registry: dict[str, Any],
    project_root: Path,
) -> list[Finding]:
    """Advisory: in_progress task has no ISA (spec) attached.

    REPORT-ONLY — `severity=SEV_INFO`, `auto_fixable=False`. Never mutates:
    we do not auto-scaffold ISAs (that would create empty stubs). Fires only
    for tasks that have actually STARTED (`in_progress`) without a spec, to
    keep the backlog quiet. A task counts as having an ISA if the registry
    records an `isa` path OR the canonical `docs/tasks/<id>/ISA.md` exists.
    """
    findings = []
    for t in registry.get("tasks", []):
        if t.get("status") != "in_progress":
            continue
        if t.get("isa"):
            continue
        task_id = t.get("id")
        if not task_id:
            continue
        isa_on_disk = project_root / "docs" / "tasks" / task_id / "ISA.md"
        if isa_on_disk.exists():
            continue
        findings.append(Finding(
            cls=CLS_TASK_WITHOUT_ISA,
            severity=SEV_INFO,
            message=(
                f"advisory: {task_id} is in_progress with no ISA. "
                f"Substantial work should have a spec — attach via "
                f"`forge task add {task_id} ... --isa` or `/ISA scaffold`. "
                f"(report-only; not auto-fixed)"
            ),
            auto_fixable=False,
            target=task_id,
        ))
    return findings


# --- Orchestration ---------------------------------------------------------


def run_all_checks(
    registry: dict[str, Any],
    epics_dir: Path,
    lock_timeout: int,
) -> tuple[list[Finding], list[tuple[Path, str, str, str]], list[str]]:
    """Run every check and return (findings, task_files, epic_ids)."""
    task_files = gather_task_files(epics_dir)
    epic_ids = gather_epic_dirs(epics_dir)

    findings: list[Finding] = []
    findings.extend(check_file_not_in_registry(registry, task_files))
    findings.extend(check_epic_not_in_registry(registry, epic_ids))
    findings.extend(check_completedat_monotonic(registry))
    findings.extend(check_stats_drift(registry))
    findings.extend(check_pending_ready(registry))
    findings.extend(check_file_vs_registry_status(registry, task_files))
    findings.extend(check_file_vs_registry_name(registry, task_files))
    findings.extend(check_stale_lock(registry, lock_timeout))
    # epics_dir is <project_root>/docs/epics — project root is its grandparent.
    findings.extend(check_task_without_isa(registry, epics_dir.parent.parent))
    return findings, task_files, epic_ids


def apply_fixes(
    registry: dict[str, Any],
    task_files: list[tuple[Path, str, str, str]],
    lock_timeout: int,
) -> tuple[bool, bool]:
    """Apply auto-fixes. Returns (registry_changed, files_changed).

    Fix order is load-bearing:
      1. stale_lock — clears lock on in_progress tasks (no status change,
         no impact on other checks; do it first to not muddy later logic).
      2. pending_ready — flips pending->ready; updates done set indirectly,
         and writes task-file frontmatter to "ready".
      3. file_vs_registry_status — runs AFTER pending_ready so the new
         "ready" state is the canonical one; rewrites any remaining drifted
         files to match registry.
      4. file_vs_registry_name — independent of status; runs alongside #3.
      5. stats_drift — runs LAST so all status changes from #2 are reflected.
    """
    file_index = {tid: tf for tf, tid, _, _ in task_files}
    registry_changed = False
    files_changed = False
    if fix_stale_lock(registry, lock_timeout):
        registry_changed = True
    if fix_pending_ready(registry, file_index):
        registry_changed = True
        files_changed = True
    if fix_file_vs_registry_status(registry, task_files):
        files_changed = True
    if fix_file_vs_registry_name(registry, task_files):
        files_changed = True
    if fix_stats_drift(registry):
        registry_changed = True
    return registry_changed, files_changed


def get_lock_timeout(registry: dict[str, Any]) -> int:
    """Read lockTimeoutSeconds from registry.settings, default 3600."""
    settings = registry.get("settings") or {}
    if isinstance(settings.get("lockTimeoutSeconds"), int):
        return settings["lockTimeoutSeconds"]
    return DEFAULT_LOCK_TIMEOUT


def format_summary(findings: list[Finding]) -> str:
    """Compact one-line banner. Hard-capped at 300 chars for SessionStart use."""
    if not findings:
        return ""
    blocking = sum(1 for f in findings if f.severity == SEV_BLOCKING)
    auto = sum(1 for f in findings if f.severity == SEV_AUTO)
    parts = []
    if blocking:
        parts.append(f"{blocking} blocking")
    if auto:
        parts.append(f"{auto} auto-fixable")
    summary = (
        f"FORGE-CONSISTENCY: {', '.join(parts)} drift finding(s). "
        f"Run: python3 .claude/scripts/forge/check_consistency.py"
    )
    return summary[:300]


def format_human(findings: list[Finding]) -> str:
    if not findings:
        return "consistency: no drift detected."
    lines = ["consistency: drift findings"]
    for f in findings:
        lines.append(f"  [{f.severity}] {f.cls}: {f.message}")
    return "\n".join(lines)


def format_json(findings: list[Finding]) -> str:
    return json.dumps(
        {"findings": [asdict(f) for f in findings]},
        indent=2,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Claude Forge consistency checker.")
    parser.add_argument("--fix", action="store_true", help="apply auto-fixable findings")
    parser.add_argument("--strict", action="store_true", help="exit 1 if blocking findings remain")
    parser.add_argument("--summary", action="store_true", help="emit one-line banner")
    parser.add_argument("--json", action="store_true", dest="as_json", help="emit machine-readable JSON")
    parser.add_argument("--project-root", type=Path, default=None, help="(testing) override project root")
    args = parser.parse_args(argv)

    project_root = get_project_root(args.project_root)
    registry_path = project_root / "docs" / "tasks" / "registry.json"
    epics_dir = project_root / "docs" / "epics"

    registry = load_registry(registry_path)
    if registry is None:
        # Missing registry: graceful no-op so the hook doesn't break new
        # projects that haven't initialized a registry yet.
        if args.summary:
            return 0
        if args.as_json:
            print(json.dumps({"findings": [], "warning": "registry.json not found"}))
        else:
            print("consistency: registry.json not found; skipping.")
        return 0

    lock_timeout = get_lock_timeout(registry)

    findings, task_files, _ = run_all_checks(registry, epics_dir, lock_timeout)

    if args.fix:
        try:
            with registry_ops.registry_write_lock(registry_path, timeout=1.0):
                # Re-load under the lock: another writer may have changed
                # the registry between the unlocked read above and here.
                locked_registry = load_registry(registry_path)
                if locked_registry is not None:
                    registry = locked_registry
                    lock_timeout = get_lock_timeout(registry)
                    findings, task_files, _ = run_all_checks(
                        registry, epics_dir, lock_timeout
                    )
                    registry_changed, files_changed = apply_fixes(
                        registry, task_files, lock_timeout
                    )
                    if registry_changed:
                        registry_ops.save_registry(registry_path, registry)
                    if registry_changed or files_changed:
                        # Re-run for post-fix view; cached task-file metadata
                        # is stale if any file rewrites happened, so re-gather.
                        findings, task_files, _ = run_all_checks(
                            registry, epics_dir, lock_timeout
                        )
        except registry_ops.RegistryLockTimeout:
            # Hooks are informational and must never stall a session: skip
            # applying fixes this run and fall through with the unfixed,
            # already-gathered read-only findings from above.
            pass

    blocking = [f for f in findings if f.severity == SEV_BLOCKING]

    if args.summary:
        msg = format_summary(findings)
        if msg:
            print(msg)
        return 0

    if args.as_json:
        print(format_json(findings))
    else:
        print(format_human(findings))

    if args.strict and blocking:
        sys.stderr.write(
            "\n".join(f.message for f in blocking) + "\n"
        )
        # The PreToolUse hook wrapper converts checker exit 1 -> hook exit 2
        # so Claude Code blocks the offending tool call.
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
