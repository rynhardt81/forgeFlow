#!/usr/bin/env python3
"""
registry_ops.py
Atomic task state mutations for Claude Forge registries.

This module is the canonical "transition this task" implementation. It
mutates docs/tasks/registry.json AND the task file's YAML frontmatter in
one atomic write each, so the two sides don't drift. The CLI in forge.py
wraps these functions; the consistency checker can also call into them
when it needs to apply a fix.

Design notes:

  - **Atomic per-file write**: each save uses a tmp file + os.replace,
    so a crash mid-write leaves the previous version intact. No half-
    written JSON.
  - **Cross-process safety**: every mutator acquires `registry_write_lock()`
    (advisory `flock`/`msvcrt` exclusive lock on a `.registry.lock` sidecar)
    around its full load -> mutate -> save(+mirror) span. This closes the
    lost-update window that atomic-per-file writes alone don't: two
    overlapping writers (e.g. `/run-epic --parallel` plus the consistency
    checker's `--fix` pass) can no longer silently drop each other's
    changes. `RegistryLockTimeout` propagates to the CLI, which fails
    loudly rather than writing unlocked.
  - **Registry-wins on disagreement**: if the task file frontmatter is
    out of sync at write time, the registry value wins and we rewrite
    the file. This matches the consistency checker's drift #6 contract.
  - **Stats recomputed on every mutation**: every function that changes
    a task's status calls `_recompute_stats(registry)` before saving,
    so stats can never lag.

Status transitions:

    pending → ready                   (when deps complete; auto)
    ready → in_progress               (lock_task)
    in_progress → completed           (complete_task; skip-PR path)
    in_progress → pr_pending          (pr_task)
    in_progress → continuation        (unlock_task with --to-status continuation)
    pr_pending → completed            (complete_task; PR merged)
    pr_pending → in_progress          (when reviewers request changes)
    continuation → in_progress        (lock_task on resumed task)
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


# ---------------------------------------------------------------------------
# Framework root resolution — for locating templates/. Follows the doctrine
# in rules/framework-vs-project-root.md: derived structurally from __file__,
# no marker-file walk. registry_ops.py is at <framework_root>/scripts/forge/
# so framework_root = parents[2].
# ---------------------------------------------------------------------------

def _framework_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _template_path(name: str) -> Path:
    return _framework_root() / "templates" / name


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(value: str, *, max_len: int = 48) -> str:
    """Filesystem-safe slug for task / epic dir names.

    Lowercased, non-alphanumeric runs collapsed to single dashes, trimmed
    edges, length-capped. Empty input yields "untitled" so we never write
    a bare "T1-.md" file.
    """
    s = _SLUG_RE.sub("-", value.lower()).strip("-")
    s = s[:max_len].rstrip("-")
    return s or "untitled"


def _render_template(name: str, substitutions: dict[str, str]) -> str:
    """Read a template under templates/ and substitute {{KEY}} placeholders.

    Any placeholders not present in `substitutions` are left untouched so
    the user can fill them in manually. Lines containing `{{...}}` after
    substitution are kept verbatim — we don't error on missing values.
    """
    template = _template_path(name).read_text(encoding="utf-8")
    for key, value in substitutions.items():
        template = template.replace("{{" + key + "}}", value)
    return template


# Status values that count as "done" for the purpose of unblocking downstream
# dependencies. SINGLE SOURCE -- check_consistency imports this name rather
# than redeclaring it; a second copy kept in sync "by code review" is the
# one-rule-two-lists shape rules/agent-verification.md exists to prevent.
#
# `pr_pending` counts as satisfied DELIBERATELY: the implementation is finished
# and only the merge remains, so dependents can start in parallel with review.
# The practical consequence, which surprises people: **every dependency gate
# releases when the PR is OPENED, not when it merges.**
DONE_FOR_DEPS = frozenset({"completed", "pr_pending"})

# Legal status transitions. Used by transition_task() to reject illegal
# jumps. Auto-transitions (pending → ready when deps complete) live in
# scan_unblocked_tasks() and are applied by callers that opt in.
LEGAL_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": frozenset({"ready"}),
    "ready": frozenset({"in_progress"}),
    "in_progress": frozenset({"completed", "pr_pending", "continuation"}),
    "pr_pending": frozenset({"completed", "in_progress"}),
    "continuation": frozenset({"in_progress"}),
    "completed": frozenset(),  # terminal
}

# Task statuses that count as terminal for the purpose of rolling an epic up
# to `completed`. `completed` is the CLI-set terminal; `superseded`/`closed`
# are data-only tombstones the audit sweep applies (never set by a CLI
# transition, but nothing resumes from them). `continuation` is deliberately
# EXCLUDED — it is resumable (continuation → in_progress), so an epic with a
# continuation task still has live work.
EPIC_TERMINAL_TASK_STATES = frozenset({"completed", "superseded", "closed"})

# Epic status meaning "parked -- its tasks are deferred and out of the ready
# queue until the owner promotes the epic". A task is deferred iff its epic
# carries this status; tasks have no backlog field of their own.
EPIC_BACKLOG_STATUS = "backlog"

# Epic statuses settable via `forge epic status`. `completed` is deliberately
# absent -- it is reachable only through `complete_epic()`, which guards on all
# tasks being terminal, and it is terminal once reached.
EPIC_SETTABLE_STATUSES = frozenset({"pending", "in_progress", EPIC_BACKLOG_STATUS})

# Default priority for a `backlog` epic (lower = higher). Deliberately the far
# end of the range: promoting a backlog makes its work ELIGIBLE, not URGENT, so
# a promoted epic sits behind the roadmap until someone runs `epic set-priority`.
# Without this, the copy-pasteable command in skills/_shared/task-triage.md
# creates a priority-1 epic that jumps the whole queue the moment it is
# promoted -- reported from a consumer install against v4.4.0.
BACKLOG_EPIC_DEFAULT_PRIORITY = 99
DEFAULT_EPIC_PRIORITY = 1


_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?\n)---\s*(?:\n|$)", re.DOTALL)
# `[ \t]*` (not `\s*`) at end so we don't consume the closing newline
# that separates the field line from the closing `---` delimiter.
_FRONTMATTER_STATUS_RE = re.compile(
    r"^(status[ \t]*:[ \t]*)(\S+)[ \t]*$", re.MULTILINE
)
# Name field captures the rest of the line (allows spaces). Quoted values
# get the quotes stripped on read; on write we re-quote when the value
# contains characters YAML would interpret (`:`, `#`, leading `-`, etc.).
_FRONTMATTER_NAME_RE = re.compile(
    r"^(name[ \t]*:[ \t]*)(.+?)[ \t]*$", re.MULTILINE
)
_FRONTMATTER_EPIC_RE = re.compile(r"^(epic:\s*)(.*)$", re.MULTILINE)


# --- Errors ----------------------------------------------------------------


class RegistryOpError(Exception):
    """Base error for registry operations."""


class TaskNotFound(RegistryOpError):
    pass


class IllegalTransition(RegistryOpError):
    pass


class TaskAlreadyExists(RegistryOpError):
    pass


class EpicNotFound(RegistryOpError):
    pass


class EpicAlreadyExists(RegistryOpError):
    pass


class RegistryLockTimeout(RuntimeError):
    """Raised when registry_write_lock() can't acquire the lock in time.

    Not a RegistryOpError: this is a contention/infra failure, not a
    validation error about task/epic state, so callers distinguish it
    from TaskNotFound/IllegalTransition/etc.
    """


# --- Time helpers ----------------------------------------------------------


def utcnow() -> str:
    """Return current UTC time as RFC3339 with Z suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- Registry I/O ----------------------------------------------------------


def load_registry(registry_path: Path) -> dict[str, Any]:
    """Load registry JSON. Raises FileNotFoundError if missing."""
    with open(registry_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_registry(registry_path: Path, registry: dict[str, Any]) -> None:
    """Write registry atomically (tmp + rename).

    A crash mid-write leaves the previous registry version intact rather
    than corrupting it.
    """
    registry_path = Path(registry_path)
    fd, tmp_path = tempfile.mkstemp(
        prefix=".registry-", suffix=".tmp", dir=str(registry_path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(registry, f, indent=2, ensure_ascii=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, registry_path)
    except Exception:
        # Best-effort cleanup of the tmp file on any failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


_LOCK_RETRY_INTERVAL = 0.05  # seconds between acquisition attempts


@contextmanager
def registry_write_lock(registry_path: Path, *, timeout: float = 5.0) -> Iterator[None]:
    """Advisory exclusive lock on `<registry dir>/.registry.lock`.

    Every registry mutator must wrap its full load -> mutate -> save(+mirror)
    span in `with registry_write_lock(registry_path):` so two overlapping
    writers (parallel CLI invocations, the consistency checker's --fix pass,
    concurrent agent sessions) can't produce a last-writer-wins lost update.
    Atomic per-file writes (save_registry above) prevent corruption; only
    this mutual exclusion prevents lost updates.

    POSIX: `fcntl.flock(LOCK_EX | LOCK_NB)`, retried on `BlockingIOError`
    every `_LOCK_RETRY_INTERVAL` seconds until `timeout` elapses.
    Windows (no `fcntl`): `msvcrt.locking()` on the same sidecar file, same
    retry loop, best-effort (unit-tested only on POSIX).

    Raises `RegistryLockTimeout` if the lock can't be acquired within
    `timeout` seconds.

    The lock file itself is never deleted — deleting it while another
    process holds a lock on the old inode "unlocks" that other process
    racily on some platforms (a new process can create + lock a
    fresh-inode file of the same name while the old lock is still held).
    Leaving a zero-byte `.registry.lock` sidecar behind is harmless; flock
    releases automatically when the holding process exits or closes the
    fd, so a crashed process can never leave the registry permanently
    locked.
    """
    registry_path = Path(registry_path)
    lock_path = registry_path.parent / ".registry.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        deadline = time.monotonic() + timeout
        acquired = False
        if os.name == "nt":
            import msvcrt

            while True:
                try:
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                    acquired = True
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        break
                    time.sleep(_LOCK_RETRY_INTERVAL)
            if not acquired:
                raise RegistryLockTimeout(
                    f"could not acquire registry lock at {lock_path} "
                    f"within {timeout}s (Windows msvcrt)"
                )
            try:
                yield
            finally:
                try:
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
        else:
            import fcntl

            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        break
                    time.sleep(_LOCK_RETRY_INTERVAL)
            if not acquired:
                raise RegistryLockTimeout(
                    f"could not acquire registry lock at {lock_path} "
                    f"within {timeout}s"
                )
            try:
                yield
            finally:
                try:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                except OSError:
                    pass
    finally:
        os.close(fd)


# --- Task lookup -----------------------------------------------------------


def find_task(registry: dict[str, Any], task_id: str) -> dict[str, Any]:
    """Return the task dict by id, or raise TaskNotFound."""
    for t in registry.get("tasks", []):
        if t.get("id") == task_id:
            return t
    raise TaskNotFound(f"Task {task_id} not found in registry")


def find_epic(registry: dict[str, Any], epic_id: str) -> dict[str, Any] | None:
    """Return the epic dict by id, or None."""
    for e in registry.get("epics", []):
        if e.get("id") == epic_id:
            return e
    return None


def task_file_path(registry: dict[str, Any], task: dict[str, Any]) -> str | None:
    """Return the registry-recorded file path (relative) for a task.

    The schema field is `file`; tolerate legacy `path` for older registries.
    """
    return task.get("file") or task.get("path")


# --- Task file frontmatter mirroring ---------------------------------------


def _rewrite_frontmatter_status(content: str, new_status: str) -> tuple[str, bool]:
    """Rewrite `status:` inside the first frontmatter block.

    Returns (new_content, changed). No-op (changed=False) when the file
    has no frontmatter or no status field — we don't invent structure
    that wasn't there.
    """
    fm = _FRONTMATTER_RE.match(content)
    if not fm:
        return content, False
    block = fm.group(1)
    new_block, n = _FRONTMATTER_STATUS_RE.subn(rf"\g<1>{new_status}", block, count=1)
    if n == 0 or new_block == block:
        return content, False
    return content[: fm.start(1)] + new_block + content[fm.end(1) :], True


def _yaml_quote_if_needed(value: str) -> str:
    """Quote a YAML scalar if it contains chars YAML would interpret.

    Conservative: only quote when needed so common names round-trip
    unquoted. Uses double-quotes and escapes embedded `"` and backslashes.
    """
    if not value:
        return '""'
    needs_quote = (
        value[0] in ("-", "?", ":", ",", "[", "]", "{", "}", "#", "&", "*",
                     "!", "|", ">", "'", "\"", "%", "@", "`")
        or ":" in value
        or "#" in value
        or value.strip() != value
    )
    if not needs_quote:
        return value
    escaped = value.replace("\\", "\\\\").replace("\"", "\\\"")
    return f"\"{escaped}\""


def _rewrite_frontmatter_name(content: str, new_name: str) -> tuple[str, bool]:
    """Rewrite `name:` inside the first frontmatter block.

    Returns (new_content, changed). No-op when the file has no frontmatter
    or no `name:` field. The new value is YAML-quoted only when it contains
    characters YAML would otherwise interpret.
    """
    fm = _FRONTMATTER_RE.match(content)
    if not fm:
        return content, False
    block = fm.group(1)
    quoted = _yaml_quote_if_needed(new_name)
    new_block, n = _FRONTMATTER_NAME_RE.subn(
        lambda m: f"{m.group(1)}{quoted}", block, count=1
    )
    if n == 0 or new_block == block:
        return content, False
    return content[: fm.start(1)] + new_block + content[fm.end(1) :], True


def _rewrite_frontmatter_epic(content: str, new_epic: str) -> tuple[str, bool]:
    """Rewrite `epic:` inside the first frontmatter block.

    Returns (new_content, changed). No-op when the file has no frontmatter or
    no `epic:` field -- same contract as the status and name rewriters.
    """
    fm = _FRONTMATTER_RE.match(content)
    if not fm:
        return content, False
    block = fm.group(1)
    new_block, n = _FRONTMATTER_EPIC_RE.subn(
        lambda m: f"{m.group(1)}{new_epic}", block, count=1
    )
    if n == 0 or new_block == block:
        return content, False
    return content[: fm.start(1)] + new_block + content[fm.end(1) :], True


def _parse_frontmatter_field(content: str, field_re: re.Pattern[str]) -> str:
    """Return the unquoted, unescaped value of a frontmatter field."""
    fm = _FRONTMATTER_RE.match(content)
    if not fm:
        return ""
    m = field_re.search(fm.group(1))
    if not m:
        return ""
    return _yaml_unquote_scalar(m.group(2).strip())


def _yaml_unquote_scalar(raw: str) -> str:
    # Inverse of _yaml_quote_if_needed: strip a balanced surrounding pair
    # of `"` or `'` and reverse the encoder's escapes in opposite order
    # (\" before \\). Without this, names containing `"` or `\` round-trip
    # asymmetrically and re-fire drift #8 on every consistency pass.
    if len(raw) >= 2 and raw[0] == raw[-1]:
        if raw[0] == '"':
            return raw[1:-1].replace('\\"', '"').replace("\\\\", "\\")
        if raw[0] == "'":
            return raw[1:-1].replace("''", "'")
    return raw


def _discover_task_file(project_root: Path, task: dict[str, Any]) -> Path | None:
    """Locate a task's markdown file when the registry doesn't record `file:`.

    Walks docs/epics/{epic_id}-*/tasks/T{n}-*.md, matching the same naming
    convention the consistency checker uses. Returns the first match.
    """
    epic_id = task.get("epic")
    task_id = task.get("id")
    if not (epic_id and task_id):
        return None
    epics_dir = project_root / "docs" / "epics"
    if not epics_dir.exists():
        return None
    for epic_dir in epics_dir.glob(f"{epic_id}-*"):
        if not epic_dir.is_dir():
            continue
        candidates = list((epic_dir / "tasks").glob(f"{task_id}-*.md"))
        if candidates:
            return candidates[0]
    return None


def mirror_status_to_file(project_root: Path, task: dict[str, Any], new_status: str) -> bool:
    """Update the task file's frontmatter status to match the registry.

    Returns True if a file write happened. Best-effort: missing file or
    unwritable file is silent — the consistency checker will surface it
    as drift #6 on the next pass.

    Resolution order: registry's `file:` field, then disk discovery via
    the docs/epics/{epic}-*/tasks/{id}-*.md glob.
    """
    rel = task_file_path({}, task)
    full: Path | None = (project_root / rel) if rel else None
    if full is None or not full.exists():
        full = _discover_task_file(project_root, task)
    if full is None or not full.exists():
        return False
    try:
        content = full.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    new_content, changed = _rewrite_frontmatter_status(content, new_status)
    if not changed:
        return False
    try:
        full.write_text(new_content, encoding="utf-8")
    except OSError:
        return False
    return True


def mirror_name_to_file(project_root: Path, task: dict[str, Any], new_name: str) -> bool:
    """Update the task file's frontmatter `name:` to match the registry.

    Best-effort, same contract as `mirror_status_to_file`. Returns True
    when a file write happened.
    """
    rel = task_file_path({}, task)
    full: Path | None = (project_root / rel) if rel else None
    if full is None or not full.exists():
        full = _discover_task_file(project_root, task)
    if full is None or not full.exists():
        return False
    try:
        content = full.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    new_content, changed = _rewrite_frontmatter_name(content, new_name)
    if not changed:
        return False
    try:
        full.write_text(new_content, encoding="utf-8")
    except OSError:
        return False
    return True


# --- Stats -----------------------------------------------------------------


def _expected_stats(registry: dict[str, Any]) -> dict[str, Any]:
    tc = Counter(t.get("status", "pending") for t in registry.get("tasks", []))
    ec = Counter(e.get("status", "pending") for e in registry.get("epics", []))
    return {
        "epics": {
            "total": len(registry.get("epics", [])),
            "completed": ec.get("completed", 0),
            "in_progress": ec.get("in_progress", 0),
            "blocked": ec.get("blocked", 0),
            "ready": ec.get("ready", 0),
            "pending": ec.get("pending", 0),
        },
        "tasks": {
            "total": len(registry.get("tasks", [])),
            "completed": tc.get("completed", 0),
            "in_progress": tc.get("in_progress", 0),
            "pr_pending": tc.get("pr_pending", 0),
            "continuation": tc.get("continuation", 0),
            "ready": tc.get("ready", 0),
            "pending": tc.get("pending", 0),
        },
    }


def recompute_stats(registry: dict[str, Any]) -> None:
    """Update registry.stats in place to match the actual task/epic lists."""
    registry["stats"] = _expected_stats(registry)


# --- Dependency scanning ---------------------------------------------------


def scan_unblocked_tasks(registry: dict[str, Any]) -> list[str]:
    """Return IDs of pending tasks whose dependencies are all done.

    Used after complete/pr to flip newly-unblocked dependents to ready.
    Empty deps lists don't qualify (those start as ready, not pending).
    """
    done_ids = {
        t["id"] for t in registry.get("tasks", [])
        if t.get("status") in DONE_FOR_DEPS
    }
    unblocked = []
    for t in registry.get("tasks", []):
        if t.get("status") != "pending":
            continue
        deps = t.get("dependencies") or []
        if not deps:
            continue
        if all(d in done_ids for d in deps):
            unblocked.append(t["id"])
    return unblocked


# --- Mutation operations ---------------------------------------------------


DOC_ONLY_PATTERNS = ("docs/", "README", "CHANGELOG", "RELEASES")


def detect_preflight_required(
    scope_directories: list[str] | None,
    scope_files: list[str] | None,
) -> bool:
    """Return True iff any scope path is outside the doc-only allowlist.

    Allowlist: paths starting with `docs/`, files named `README*`,
    `CHANGELOG*`, `RELEASES*`, or any *.md/*.mdx file. Anything else
    counts as code-touching and demands preflight.

    Empty scope (no dirs, no files) defaults to True — unknown scope is
    treated as code-touching to keep doc-only opt-out explicit.
    """
    dirs = list(scope_directories or [])
    files = list(scope_files or [])
    if not dirs and not files:
        return True
    for path in dirs + files:
        if not _is_doc_only_path(path):
            return True
    return False


def _is_doc_only_path(path: str) -> bool:
    p = path.lstrip("./").strip()
    if not p:
        return False
    if p.endswith((".md", ".mdx")):
        return True
    base = p.split("/")[-1]
    if any(base.startswith(prefix) for prefix in ("README", "CHANGELOG", "RELEASES")):
        return True
    if p.startswith("docs/") or p == "docs":
        return True
    return False


def add_task(
    registry_path: Path,
    *,
    task_id: str,
    epic_id: str,
    name: str,
    dependencies: list[str] | None = None,
    scope_directories: list[str] | None = None,
    scope_files: list[str] | None = None,
    file_path: str | None = None,
    priority: int = 1,
    category: str = "",
    preflight: str = "auto",
    allow_missing_epic: bool = False,
) -> dict[str, Any]:
    """Add a new task to the registry. Returns the created task dict.

    Atomic registry mutation only. The CLI composes this with
    `create_task_body_file()` and optionally `scaffold_task_isa()` so
    `forge task add` creates the on-disk artifacts that match the
    registry entry by default. If `file_path` is given, it's recorded in
    the registry; otherwise omitted and the consistency checker / file
    discovery fall back to docs/epics/{E}-*/tasks/{T}-*.md.

    The task's epic MUST already exist in the registry, otherwise the task
    is orphaned from `registry.epics` (no back-reference) and the epic goes
    unrepresented — a `blocking` consistency finding with no auto-fix. Raises
    `EpicNotFound` in that case. Pass `allow_missing_epic=True` only when the
    caller knowingly wants an epic-less registry entry (test fixtures, staged
    imports that create the epic afterward). Create the epic first with
    `add_epic()` / `forge epic add`.
    """
    with registry_write_lock(registry_path):
        registry = load_registry(registry_path)
        try:
            find_task(registry, task_id)
            raise TaskAlreadyExists(f"Task {task_id} already in registry")
        except TaskNotFound:
            pass

        epic = find_epic(registry, epic_id)
        if epic is None and not allow_missing_epic:
            raise EpicNotFound(
                f"Epic {epic_id} is not in the registry. Create it first with "
                f"`forge epic add {epic_id} --name \"...\"`, or pass "
                f"--allow-missing-epic to add an orphaned task deliberately."
            )

        initial_status = "pending" if (dependencies or []) else "ready"
        task: dict[str, Any] = {
            "id": task_id,
            "epic": epic_id,
            "name": name,
            "category": category,
            "priority": priority,
            "status": initial_status,
            "dependencies": list(dependencies or []),
            "scope": {
                "directories": list(scope_directories or []),
                "files": list(scope_files or []),
            },
            "lock": None,
            "createdAt": utcnow(),
        }
        if file_path:
            task["file"] = file_path

        if preflight not in ("auto", "required", "skip"):
            raise ValueError(f"invalid preflight value: {preflight!r}")
        if preflight == "required":
            task["preflight_required"] = True
        elif preflight == "skip":
            task["preflight_required"] = False
        else:  # auto
            task["preflight_required"] = detect_preflight_required(
                scope_directories, scope_files
            )

        registry.setdefault("tasks", []).append(task)
        if epic is not None:  # None only when allow_missing_epic=True
            epic.setdefault("tasks", []).append(task_id)

        recompute_stats(registry)
        save_registry(registry_path, registry)
    return task


def add_epic(
    registry_path: Path,
    *,
    epic_id: str,
    name: str,
    description: str = "",
    dependencies: list[str] | None = None,
    priority: int | None = None,
    category: str = "",
    status: str = "pending",
) -> dict[str, Any]:
    """Add a new epic to the registry. Returns the created epic dict.

    `priority=None` resolves by status: a `backlog` epic defaults to
    BACKLOG_EPIC_DEFAULT_PRIORITY (last), everything else to
    DEFAULT_EPIC_PRIORITY. An explicit value always wins. This keeps the
    documented `epic add E99 --status backlog` from inverting the queue.

    The counterpart to `add_task` at the epic level — the sanctioned atomic
    path for creating an epic, so no caller ever has to hand-edit
    registry.json. Mirrors the epic schema E01-E13 use: id, name,
    description, category, status, dependencies, priority, tasks (empty).
    Raises `EpicAlreadyExists` if the id is taken.

    Does NOT create the on-disk `docs/epics/<id>-<slug>/` directory — that is
    the CLI's job (`cmd_epic_add`), same division of labour as `add_task` vs
    `create_task_body_file`.
    """
    if priority is None:
        priority = (
            BACKLOG_EPIC_DEFAULT_PRIORITY
            if status == EPIC_BACKLOG_STATUS
            else DEFAULT_EPIC_PRIORITY
        )

    with registry_write_lock(registry_path):
        registry = load_registry(registry_path)
        if find_epic(registry, epic_id) is not None:
            raise EpicAlreadyExists(f"Epic {epic_id} already in registry")

        epic: dict[str, Any] = {
            "id": epic_id,
            "name": name,
            "description": description,
            "category": category,
            "status": status,
            "dependencies": list(dependencies or []),
            "priority": priority,
            "tasks": [],
            "createdAt": utcnow(),
        }
        registry.setdefault("epics", []).append(epic)
        recompute_stats(registry)
        save_registry(registry_path, registry)
    return epic


def _resolve_epic_dir(project_root: Path, epic_id: str, *, create_if_missing: bool = True) -> Path | None:
    """Find the on-disk epic directory matching `<epic_id>-<slug>/`.

    Looks under `<project_root>/docs/epics/`. Returns the first directory
    whose name starts with `<epic_id>-`. If none exists and
    `create_if_missing=True`, creates `<epic_id>-untitled/` so the task
    file has a home (the user can rename the dir later; the consistency
    checker handles file moves).

    Returns None only when `create_if_missing=False` and no match exists.
    """
    epics_dir = project_root / "docs" / "epics"
    if epics_dir.exists():
        for candidate in epics_dir.glob(f"{epic_id}-*"):
            if candidate.is_dir():
                return candidate
    if not create_if_missing:
        return None
    epic_dir = epics_dir / f"{epic_id}-untitled"
    (epic_dir / "tasks").mkdir(parents=True, exist_ok=True)
    return epic_dir


def create_epic_dir(project_root: Path, epic: dict[str, Any]) -> Path:
    """Create `docs/epics/<id>-<slug>/tasks/` and a minimal epic body file.

    Idempotent on the directory (mkdir exist_ok); the body file is written
    only if absent so a hand-authored epic file is never clobbered. Returns
    the epic directory. Paired with `add_epic()` the same way
    `create_task_body_file()` is paired with `add_task()`.

    If an epic dir for this id already exists under any slug (e.g. the CLI's
    `-untitled` fallback from a prior task-add), that existing dir is reused
    rather than creating a second one.
    """
    epic_id = epic["id"]
    existing = _resolve_epic_dir(project_root, epic_id, create_if_missing=False)
    if existing is not None:
        epic_dir = existing
    else:
        slug = _slugify(epic.get("name", ""))
        epic_dir = project_root / "docs" / "epics" / f"{epic_id}-{slug}"
    (epic_dir / "tasks").mkdir(parents=True, exist_ok=True)

    body = epic_dir / f"{epic_dir.name}.md"
    if not body.exists():
        deps = epic.get("dependencies") or []
        deps_line = ", ".join(deps) if deps else "None"
        body.write_text(
            f"---\n"
            f"id: {epic_id}\n"
            f"name: \"{epic.get('name', '')}\"\n"
            f"category: {epic.get('category', '')}\n"
            f"status: {epic.get('status', 'pending')}\n"
            f"priority: {epic.get('priority', 1)}\n"
            f"dependencies: {json.dumps(deps)}\n"
            f"createdAt: \"{epic.get('createdAt', utcnow())}\"\n"
            f"---\n\n"
            f"# {epic_id}: {epic.get('name', '')}\n\n"
            f"## Overview\n\n"
            f"**Status:** {epic.get('status', 'pending')}\n"
            f"**Dependencies:** {deps_line}\n\n"
            f"## Summary\n\n"
            f"{epic.get('description', '')}\n\n"
            f"## Tasks\n\n"
            f"_(populated as tasks are filed under this epic)_\n",
            encoding="utf-8",
        )
    return epic_dir


def create_task_body_file(
    project_root: Path,
    task: dict[str, Any],
    *,
    overwrite: bool = False,
    stub: bool = False,
) -> Path:
    """Write the canonical task body file from templates/task.md.

    Path: `<project_root>/docs/epics/<epic-id>-<slug>/tasks/<task-id>-<slug>.md`.

    Returns the path written. Raises FileExistsError if the file already
    exists and `overwrite` is False — callers should check `task["file"]`
    first or pre-resolve via `_discover_task_file` if they want idempotence.

    `stub=True` marks the file as auto-generated by `forge task
    reconcile-files`, so a human reading it knows to fill in the scope
    and objective before locking.
    """
    epic_id = task["epic"]
    task_id = task["id"]
    name = task.get("name", task_id)

    epic_dir = _resolve_epic_dir(project_root, epic_id, create_if_missing=True)
    tasks_dir = epic_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)

    file_path = tasks_dir / f"{task_id}-{_slugify(name)}.md"
    if file_path.exists() and not overwrite:
        raise FileExistsError(f"task file already exists: {file_path}")

    scope = task.get("scope", {})
    deps = task.get("dependencies", [])
    substitutions = {
        "TASK_ID": task_id,
        "EPIC_ID": epic_id,
        "TASK_NAME": name,
        "STATUS": task.get("status", "ready"),
        "PRIORITY": str(task.get("priority", 1)),
        "CATEGORY": task.get("category", ""),
        "DEPENDENCIES": "[" + ", ".join(deps) + "]" if deps else "[]",
        "SCOPE_DIRS": "[" + ", ".join(scope.get("directories", [])) + "]"
                      if scope.get("directories") else "[]",
        "SCOPE_FILES": "[" + ", ".join(scope.get("files", [])) + "]"
                       if scope.get("files") else "[]",
        "CREATED_AT": task.get("createdAt", utcnow()),
    }

    body = _render_template("task.md", substitutions)
    if stub:
        marker = (
            f"\n> **STUB** — auto-created by `forge task reconcile-files` "
            f"on {utcnow()[:10]}. Fill in scope + objective before locking.\n"
        )
        # Insert the stub marker just after the H1, before the rest
        body = body.replace(f"# {task_id} — {name}\n",
                            f"# {task_id} — {name}\n{marker}", 1)

    file_path.write_text(body, encoding="utf-8")
    return file_path


def scaffold_task_isa(
    project_root: Path,
    task: dict[str, Any],
    *,
    overwrite: bool = False,
) -> Path:
    """Write the per-task ISA file from templates/isa.md.

    Path: `<project_root>/docs/tasks/<task-id>/ISA.md`.

    The ISA tree (`docs/tasks/`) is intentionally separate from the task
    body tree (`docs/epics/<epic>/tasks/`). The ISA is the test harness;
    the body is the human-readable description. They reference each other
    by task ID, not by colocation.

    Returns the path written. Raises FileExistsError if it already exists
    and `overwrite` is False.
    """
    task_id = task["id"]
    name = task.get("name", task_id)

    isa_dir = project_root / "docs" / "tasks" / task_id
    isa_dir.mkdir(parents=True, exist_ok=True)
    isa_path = isa_dir / "ISA.md"
    if isa_path.exists() and not overwrite:
        raise FileExistsError(f"ISA already exists: {isa_path}")

    substitutions = {
        "TASK_ID": task_id,
        "TASK_NAME": name,
        "CREATED_AT": task.get("createdAt", utcnow()),
    }
    isa_path.write_text(_render_template("isa.md", substitutions), encoding="utf-8")
    return isa_path


def task_isa_path(project_root: Path, task_id: str) -> Path:
    """Canonical per-task ISA path: `<project_root>/docs/tasks/<id>/ISA.md`."""
    return project_root / "docs" / "tasks" / task_id / "ISA.md"


def task_has_isa(project_root: Path, task: dict[str, Any]) -> bool:
    """Whether a task has a spec attached.

    True if the registry records an `isa` path for the task, OR the
    canonical per-task ISA exists on disk. Backward compatible: a task
    with no `isa` field and no on-disk ISA is treated as having none.
    The disk fallback means an ISA scaffolded out-of-band (e.g. via the
    Algorithm or `/ISA scaffold`) still counts even if the registry
    field was never set.
    """
    if task.get("isa"):
        return True
    return task_isa_path(project_root, task["id"]).exists()


def reconcile_task_files(
    registry_path: Path,
    project_root: Path,
    *,
    apply: bool = False,
) -> dict[str, Any]:
    """For every registry-tracked task without a `.md` body on disk, create
    a stub body file. Dry-run by default.

    Returns `{"missing": [task_ids], "created": [paths], "errors": [...]}`.
    When `apply=False`, `created` is empty and `missing` lists what WOULD
    be created. Each created file is marked with the STUB header so the
    user knows it's a placeholder, not a real task description.

    Does NOT touch registry entries — this is a one-way disk-from-registry
    operation. The inverse (file → registry) is `task reconcile-from-files`
    which already exists.
    """
    registry = load_registry(registry_path)
    missing: list[str] = []
    created: list[str] = []
    errors: list[dict[str, str]] = []

    for task in registry.get("tasks", []):
        existing = _discover_task_file(project_root, task)
        if existing is not None:
            continue
        # Honor explicit file: field if it points somewhere real
        if task.get("file"):
            recorded = project_root / task["file"]
            if recorded.exists():
                continue
        missing.append(task["id"])
        if not apply:
            continue
        try:
            path = create_task_body_file(project_root, task, stub=True)
            created.append(str(path.relative_to(project_root)))
        except Exception as exc:  # noqa: BLE001 — surface all failures
            errors.append({"task": task["id"], "error": str(exc)})

    return {"missing": missing, "created": created, "errors": errors}


def lock_task(
    registry_path: Path,
    project_root: Path,
    task_id: str,
    *,
    session_id: str,
    now: str | None = None,
) -> dict[str, Any]:
    """Lock a task: set lock object, transition to in_progress.

    Legal source statuses: ready, continuation. Anything else raises
    IllegalTransition (the caller should resolve first via unlock or
    a status query).
    """
    with registry_write_lock(registry_path):
        registry = load_registry(registry_path)
        task = find_task(registry, task_id)
        current = task.get("status", "pending")
        if current not in {"ready", "continuation"}:
            raise IllegalTransition(
                f"Cannot lock {task_id} from status '{current}' "
                f"(expected: ready or continuation)"
            )
        task["status"] = "in_progress"
        task["lock"] = {
            "session": session_id,
            "lockedAt": now or utcnow(),
        }
        recompute_stats(registry)
        save_registry(registry_path, registry)
        mirror_status_to_file(project_root, task, "in_progress")
    return task


def unlock_task(
    registry_path: Path,
    project_root: Path,
    task_id: str,
    *,
    to_status: str = "continuation",
) -> dict[str, Any]:
    """Clear the lock on a task.

    Defaults the new status to `continuation` (preserves partial work).
    Pass `to_status="ready"` for a clean abandon (no progress was made),
    or `to_status="in_progress"` to clear lock without changing status
    (rare; used by the consistency checker's drift #7 stale-lock fix).
    """
    with registry_write_lock(registry_path):
        registry = load_registry(registry_path)
        task = find_task(registry, task_id)
        current = task.get("status", "pending")
        if current != "in_progress":
            raise IllegalTransition(
                f"Cannot unlock {task_id}: status is '{current}', not 'in_progress'"
            )
        if to_status not in {"continuation", "ready", "in_progress"}:
            raise IllegalTransition(
                f"unlock_task to_status must be continuation, ready, or in_progress "
                f"(got {to_status!r})"
            )
        task["lock"] = None
        if task["status"] != to_status:
            task["status"] = to_status
        recompute_stats(registry)
        save_registry(registry_path, registry)
        mirror_status_to_file(project_root, task, task["status"])
    return task


def complete_task(
    registry_path: Path,
    project_root: Path,
    task_id: str,
    *,
    now: str | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Mark a task completed. Returns (task, newly_unblocked_ids).

    Legal source statuses: in_progress, pr_pending. Sets completedAt,
    clears any lock, then scans dependents and flips eligible ones from
    pending to ready.
    """
    with registry_write_lock(registry_path):
        registry = load_registry(registry_path)
        task = find_task(registry, task_id)
        current = task.get("status", "pending")
        if current not in {"in_progress", "pr_pending"}:
            raise IllegalTransition(
                f"Cannot complete {task_id} from status '{current}' "
                f"(expected: in_progress or pr_pending)"
            )

        task["status"] = "completed"
        task["lock"] = None
        task["completedAt"] = now or utcnow()

        unblocked = _flip_unblocked_pending(registry, project_root)

        recompute_stats(registry)
        save_registry(registry_path, registry)
        mirror_status_to_file(project_root, task, "completed")
    return task, unblocked


def pr_task(
    registry_path: Path,
    project_root: Path,
    task_id: str,
    *,
    now: str | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Transition in_progress task to pr_pending. Returns (task, unblocked_ids).

    Clears the session lock — pr_pending tasks don't take a session lock
    (the work has moved out of any specific session into review). Scans
    dependents and unblocks them since pr_pending counts as done-for-deps.
    """
    with registry_write_lock(registry_path):
        registry = load_registry(registry_path)
        task = find_task(registry, task_id)
        current = task.get("status", "pending")
        if current != "in_progress":
            raise IllegalTransition(
                f"Cannot transition {task_id} to pr_pending from '{current}' "
                f"(expected: in_progress)"
            )

        task["status"] = "pr_pending"
        task["lock"] = None
        task["prOpenedAt"] = now or utcnow()

        unblocked = _flip_unblocked_pending(registry, project_root)

        recompute_stats(registry)
        save_registry(registry_path, registry)
        mirror_status_to_file(project_root, task, "pr_pending")
    return task, unblocked


def set_epic_status(
    registry_path: Path,
    project_root: Path,
    epic_id: str,
    new_status: str,
) -> dict[str, Any]:
    """Move an epic between `pending`, `in_progress` and `backlog`. Atomic.

    Parking an epic in `backlog` defers all its tasks out of the ready queue;
    promoting it back returns them in one command. `completed` is not settable
    here -- `complete_epic()` owns that transition and its all-tasks-terminal
    guard -- and a completed epic is terminal.
    """
    if new_status not in EPIC_SETTABLE_STATUSES:
        if new_status == "completed":
            raise IllegalTransition(
                "set_epic_status: use `forge epic complete` to complete an epic "
                "(it guards on every task being terminal)."
            )
        raise ValueError(
            f"set_epic_status: invalid status {new_status!r}; "
            f"expected one of {sorted(EPIC_SETTABLE_STATUSES)}"
        )
    with registry_write_lock(registry_path):
        registry = load_registry(registry_path)
        epic = find_epic(registry, epic_id)
        if epic is None:
            raise EpicNotFound(f"Epic {epic_id} is not in the registry")
        if epic.get("status") == "completed":
            raise IllegalTransition(
                f"Epic {epic_id} is completed; completed is terminal."
            )
        epic["status"] = new_status
        recompute_stats(registry)
        save_registry(registry_path, registry)
    return epic


def set_epic_priority(
    registry_path: Path,
    epic_id: str,
    priority: int,
) -> dict[str, Any]:
    """Set an epic's priority. Atomic.

    Epic priority is the PRIMARY sort key for `task ls` as of v4.4.0, so it
    needs a sanctioned mutator -- hand-editing registry.json is forbidden.
    Lower ranks higher; must be >= 1.
    """
    if not isinstance(priority, int) or isinstance(priority, bool) or priority < 1:
        raise ValueError(
            f"set_epic_priority: priority must be an int >= 1, got {priority!r}"
        )
    with registry_write_lock(registry_path):
        registry = load_registry(registry_path)
        epic = find_epic(registry, epic_id)
        if epic is None:
            raise EpicNotFound(f"Epic {epic_id} is not in the registry")
        epic["priority"] = priority
        save_registry(registry_path, registry)
    return epic


def complete_epic(
    registry_path: Path,
    project_root: Path,
    epic_id: str,
    *,
    now: str | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Mark an epic completed in the registry. Returns (epic, non_terminal_task_ids).

    The sanctioned epic-status transition path (T622): `epic add` set the
    status at creation, but nothing could move it afterward, so an epic stayed
    `in_progress` in registry.json even after every task under it went terminal
    (E33 drift). Registry can only be mutated through this module, so this is
    the only correct fix.

    Guard (the Anti criterion): refuse unless every task under the epic is in
    EPIC_TERMINAL_TASK_STATES. Raises IllegalTransition listing the offenders.
    An epic with no tasks is allowed (nothing keeps it open).

    Idempotent: an already-`completed` epic returns cleanly (no-op).

    Registry-only. The epic FILE frontmatter/header is reconciled by
    `/audit-task-status` (Req 3) — this does not rewrite the epic body.
    """
    with registry_write_lock(registry_path):
        registry = load_registry(registry_path)
        epic = find_epic(registry, epic_id)
        if epic is None:
            raise EpicNotFound(f"Epic {epic_id} not found in registry")

        non_terminal = [
            t["id"]
            for t in registry.get("tasks", [])
            if t.get("epic") == epic_id
            and t.get("status") not in EPIC_TERMINAL_TASK_STATES
        ]

        # Guard runs BEFORE the idempotent-return so a *completed* epic that
        # has since gained a live task (reopened/new — real drift) surfaces as
        # IllegalTransition rather than being silently re-affirmed as done.
        # (codex P2, PR #527.) A clean already-completed epic (non_terminal
        # empty) still hits the no-op below — idempotency preserved.
        if non_terminal:
            raise IllegalTransition(
                f"Cannot complete epic {epic_id}: "
                f"{len(non_terminal)} non-terminal task(s): "
                f"{', '.join(sorted(non_terminal))}. "
                f"Terminal states: {', '.join(sorted(EPIC_TERMINAL_TASK_STATES))}."
            )

        if epic.get("status") == "completed":
            return epic, non_terminal  # idempotent no-op (all tasks terminal)

        epic["status"] = "completed"
        epic["completedAt"] = now or utcnow()

        recompute_stats(registry)
        save_registry(registry_path, registry)
    return epic, non_terminal


def rename_task(
    registry_path: Path,
    project_root: Path,
    task_id: str,
    new_name: str,
) -> dict[str, Any]:
    """Rename a task. Atomic update of registry name + frontmatter name.

    Identity (`id`, `epic`, `file`) is preserved — only the human-readable
    `name` label changes. Empty / whitespace-only names are rejected.
    """
    if not new_name or not new_name.strip():
        raise ValueError("rename_task: new_name must be a non-empty string")
    new_name = new_name.strip()
    with registry_write_lock(registry_path):
        registry = load_registry(registry_path)
        task = find_task(registry, task_id)
        task["name"] = new_name
        save_registry(registry_path, registry)
        mirror_name_to_file(project_root, task, new_name)
    return task


def move_task(
    registry_path: Path,
    project_root: Path,
    task_id: str,
    new_epic_id: str,
) -> dict[str, Any]:
    """Reassign a task to a different epic. Atomic across registry and disk.

    Four mutations, all required for the task to stay findable:
      1. the task's `epic` field;
      2. both epics' `tasks` lists;
      3. the body file, moved into the target epic's `tasks/` dir, and the
         recorded `file` path;
      4. the body file's `epic:` frontmatter.

    `_discover_task_file` globs by epic dir and the consistency checker mirrors
    frontmatter against the registry, so skipping (3) or (4) produces drift.

    Refuses a locked task (unlock it first) and an unknown target epic. Moving
    a task to the epic it is already in is a no-op.
    """
    with registry_write_lock(registry_path):
        registry = load_registry(registry_path)
        task = find_task(registry, task_id)
        old_epic_id = task.get("epic")
        if old_epic_id == new_epic_id:
            return task
        if task.get("lock"):
            raise RegistryOpError(
                f"Task {task_id} is locked by session "
                f"{task['lock'].get('session', '?')}; unlock it before moving."
            )
        target = find_epic(registry, new_epic_id)
        if target is None:
            raise EpicNotFound(
                f"Epic {new_epic_id} is not in the registry. Create it first "
                f"with `forge epic add {new_epic_id} --name \"...\"`."
            )

        # Resolve the body file BEFORE mutating `epic` -- discovery globs by
        # epic dir, so afterwards it would look in the wrong place.
        rel = task_file_path(registry, task)
        src: Path | None = (project_root / rel) if rel else None
        if src is None or not src.exists():
            src = _discover_task_file(project_root, task)

        task["epic"] = new_epic_id
        source = find_epic(registry, old_epic_id)
        if source is not None and task_id in source.get("tasks", []):
            source["tasks"].remove(task_id)
        if task_id not in target.setdefault("tasks", []):
            target["tasks"].append(task_id)

        if src is not None and src.exists():
            dest_dir = _resolve_epic_dir(
                project_root, new_epic_id, create_if_missing=True
            ) / "tasks"
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / src.name
            content = src.read_text(encoding="utf-8")
            new_content, _ = _rewrite_frontmatter_epic(content, new_epic_id)
            dest.write_text(new_content, encoding="utf-8")
            if dest.resolve() != src.resolve():
                src.unlink()
            task["file"] = str(dest.relative_to(project_root))
            task.pop("path", None)
        else:
            # No body file found: drop any recorded path rather than leave one
            # pointing into the old epic's dir. `task reconcile-files --apply`
            # regenerates a stub in the right place.
            task.pop("file", None)
            task.pop("path", None)

        recompute_stats(registry)
        save_registry(registry_path, registry)
    return task


def _would_cycle(registry: dict[str, Any], task_id: str, new_deps: list[str]) -> list[str] | None:
    """Return the offending path if `task_id` depending on `new_deps` closes a
    cycle, else None. DFS over the registry's dependency edges.
    """
    edges = {
        t["id"]: list(t.get("dependencies") or [])
        for t in registry.get("tasks", []) if t.get("id")
    }
    edges[task_id] = list(new_deps)

    seen: set[str] = set()
    def walk(node: str, path: list[str]) -> list[str] | None:
        if node == task_id and path:
            return path + [node]
        if node in seen:
            return None
        seen.add(node)
        for nxt in edges.get(node, []):
            hit = walk(nxt, path + [node])
            if hit:
                return hit
        return None

    for dep in new_deps:
        seen.clear()
        hit = walk(dep, [task_id])
        if hit:
            return hit
    return None


def set_task_deps(
    registry_path: Path,
    project_root: Path,
    task_id: str,
    dependencies: list[str],
) -> dict[str, Any]:
    """Replace a task's dependency list. Atomic, with status reconciliation.

    Exists because a task's deps were previously fixed at `task add` time, so
    the triage rule's Blocker answer ("make it a --deps edge") was unreachable
    for anything already in the queue -- and the `active-task-deps-on-backlog`
    advisory told you to drop a dependency with no command that could.

    **Status moves in both directions**, or `ready` starts lying:
      - a `ready` task given an unmet dep returns to `pending`;
      - a `pending` task whose last unmet dep is removed (or satisfied)
        promotes to `ready`.
    A dep already in DONE_FOR_DEPS is satisfied and does not demote.

    Refuses: a locked task, a terminal task, an unknown dependency id, and any
    edge that would close a cycle.
    """
    with registry_write_lock(registry_path):
        registry = load_registry(registry_path)
        task = find_task(registry, task_id)

        if task.get("lock"):
            raise RegistryOpError(
                f"Task {task_id} is locked by session "
                f"{task['lock'].get('session', '?')}; unlock it before editing deps."
            )
        if task.get("status") in EPIC_TERMINAL_TASK_STATES:
            raise RegistryOpError(
                f"Task {task_id} is {task.get('status')}; its dependencies are history."
            )

        deps = list(dict.fromkeys(dependencies or []))   # de-dup, keep order
        if task_id in deps:
            raise RegistryOpError(f"Task {task_id} cannot depend on itself (cycle).")
        for d in deps:
            find_task(registry, d)          # raises TaskNotFound on unknown id

        cycle = _would_cycle(registry, task_id, deps)
        if cycle is not None:
            raise RegistryOpError(
                f"Refusing: {task_id} -> {', '.join(deps)} closes a dependency "
                f"cycle ({' -> '.join(cycle)})."
            )

        task["dependencies"] = deps

        # Reconcile status with the new edges. Only the ready<->pending pair
        # moves; in_progress/pr_pending/continuation are the user's business.
        done = {
            t["id"] for t in registry.get("tasks", [])
            if t.get("status") in DONE_FOR_DEPS
        }
        unmet = [d for d in deps if d not in done]
        if task.get("status") == "ready" and unmet:
            task["status"] = "pending"
        elif task.get("status") == "pending" and not unmet:
            task["status"] = "ready"

        recompute_stats(registry)
        save_registry(registry_path, registry)
        mirror_status_to_file(project_root, task, task["status"])
    return task


def set_task_isa(
    registry_path: Path,
    task_id: str,
    isa_rel_path: str,
) -> dict[str, Any]:
    """Record the per-task ISA path on the registry task. Atomic.

    `isa_rel_path` is stored relative to project root (e.g.
    `docs/tasks/T042/ISA.md`). Idempotent — setting the same value twice
    is a no-op write. This makes a task's spec-state queryable from the
    registry without a disk walk; `task_has_isa` still falls back to disk
    for ISAs attached out-of-band.
    """
    with registry_write_lock(registry_path):
        registry = load_registry(registry_path)
        task = find_task(registry, task_id)
        task["isa"] = isa_rel_path
        save_registry(registry_path, registry)
    return task


def set_preflight(
    registry_path: Path,
    project_root: Path,
    task_id: str,
    mode: str,
) -> dict[str, Any]:
    """Set a task's ``preflight_required`` flag after creation.

    The flag is otherwise only ever written at ``task add`` time (auto-derived
    from scope by ``detect_preflight_required``), so there was no sanctioned way
    to retune it on an existing task without hand-editing ``registry.json``
    (forbidden). This is that path.

    ``mode`` mirrors ``task add``'s ``--preflight``:

    - ``required`` → force ``preflight_required = True``
    - ``skip``     → force ``preflight_required = False``
    - ``auto``     → re-derive from the task's current scope via
      ``detect_preflight_required`` (doc-only scope ⇒ False; any code path or
      empty scope ⇒ True)

    Registry-only field — not mirrored to task-file frontmatter (the flag has no
    frontmatter representation). Atomic save under the write lock, like
    ``rename_task`` and ``set_task_isa``.
    """
    if mode not in ("auto", "required", "skip"):
        raise ValueError(
            f"set_preflight: invalid mode {mode!r} (expected auto|required|skip)"
        )
    with registry_write_lock(registry_path):
        registry = load_registry(registry_path)
        task = find_task(registry, task_id)
        if mode == "required":
            task["preflight_required"] = True
        elif mode == "skip":
            task["preflight_required"] = False
        else:  # auto
            scope = task.get("scope") or {}
            task["preflight_required"] = detect_preflight_required(
                scope.get("directories"), scope.get("files")
            )
        save_registry(registry_path, registry)
    return task


def _mirror_scope_to_frontmatter(
    project_root: Path, task: dict[str, Any], scope: dict[str, Any]
) -> None:
    """Best-effort frontmatter sync for scope; never fails the registry write.

    The registry is the source of truth and has already been saved by the time
    this runs — a missing or unparseable body file must not undo that.
    """
    # Same resolver as mirror_name_to_file: the registry `file:` field is
    # unreliable (fixtures and older entries omit it), so fall back to disk
    # discovery rather than silently skipping the mirror.
    rel = task_file_path({}, task)
    body: Path | None = (project_root / rel) if rel else None
    if body is None or not body.exists():
        body = _discover_task_file(project_root, task)
    if body is None or not body.exists():
        return
    try:
        text = body.read_text(encoding="utf-8")
        if not text.startswith("---"):
            return
        end = text.index("\n---", 3)
        head, rest = text[:end], text[end:]
        block = [
            "scope:",
            f"  directories: [{', '.join(scope['directories'])}]",
            f"  files: [{', '.join(scope['files'])}]",
        ]
        out, skipping, found = [], False, False
        for line in head.splitlines():
            if line.startswith("scope:"):
                skipping, found = True, True
                out.extend(block)
                continue
            if skipping:
                # Consume the old block's indented children only.
                if line.startswith(("  ", "\t")):
                    continue
                skipping = False
            out.append(line)
        if not found:
            # No scope block yet (older task files, fixtures). Append rather
            # than skip — frontmatter that omits scope is what let registry and
            # file disagree silently in the first place.
            out.extend(block)
        body.write_text("\n".join(out) + rest)
    except (OSError, ValueError):
        return


def set_scope(
    registry_path: Path,
    project_root: Path,
    task_id: str,
    *,
    directories: str | None = None,
    files: str | None = None,
) -> dict[str, Any]:
    """Retune a task's ``scope`` after creation.

    Scope was write-once at ``task add`` time, so a task filed against the wrong
    paths — easy when it is filed before the code is located — could only be
    corrected by hand-editing ``registry.json``, which is forbidden. Siblings
    already existed for every other post-hoc field (``rename_task``,
    ``set_task_file``, ``set_preflight``); this closes the set.

    It matters beyond tidiness: scope is what ``task lock`` uses to detect
    file-level conflicts between parallel sessions, so a wrong scope means a
    real conflict goes undetected.

    Comma-separated strings, matching ``task add``'s ``--scope-dirs`` /
    ``--scope-files``. An omitted argument leaves that half untouched; an empty
    string clears it. ``preflight_required`` is re-derived, because it is a
    function of scope and would otherwise keep a value computed from old paths.
    """
    if directories is None and files is None:
        raise ValueError("set_scope: pass at least one of directories/files")

    def _split(raw: str | None) -> list[str] | None:
        return None if raw is None else [p.strip() for p in raw.split(",") if p.strip()]

    with registry_write_lock(registry_path):
        registry = load_registry(registry_path)
        task = find_task(registry, task_id)
        scope = dict(task.get("scope") or {})
        new_dirs, new_files = _split(directories), _split(files)
        if new_dirs is not None:
            scope["directories"] = new_dirs
        if new_files is not None:
            scope["files"] = new_files
        scope.setdefault("directories", [])
        scope.setdefault("files", [])
        task["scope"] = scope
        task["preflight_required"] = detect_preflight_required(
            scope.get("directories"), scope.get("files")
        )
        save_registry(registry_path, registry)
        _mirror_scope_to_frontmatter(project_root, task, scope)
    return task


def set_task_file(
    registry_path: Path,
    project_root: Path,
    task_id: str,
    file_path: str,
    *,
    require_exists: bool = False,
) -> dict[str, Any]:
    """Set or update the registry's `file:` field for a task.

    Stores the path relative to project_root. If `file_path` is given as
    an absolute path inside project_root, it's converted to relative. Any
    legacy `path:` field is removed so the schema stays single-source.

    `require_exists=True` raises FileNotFoundError when the target file
    isn't present on disk; default is permissive (the file may be created
    by a downstream skill flow after the registry entry is recorded).
    """
    if not file_path or not file_path.strip():
        raise ValueError("set_task_file: file_path must be a non-empty string")
    file_path = file_path.strip()

    candidate = Path(file_path)
    if candidate.is_absolute():
        try:
            rel = str(candidate.resolve().relative_to(project_root.resolve()))
        except ValueError as e:
            raise ValueError(
                f"set_task_file: absolute path {candidate} is outside project root {project_root}"
            ) from e
    else:
        rel = file_path

    if require_exists and not (project_root / rel).exists():
        raise FileNotFoundError(
            f"set_task_file: target file does not exist: {project_root / rel}"
        )

    with registry_write_lock(registry_path):
        registry = load_registry(registry_path)
        task = find_task(registry, task_id)
        task["file"] = rel
        if "path" in task:
            del task["path"]
        save_registry(registry_path, registry)
    return task


def reconcile_orphan_files(
    registry_path: Path,
    project_root: Path,
) -> list[str]:
    """Seed registry entries from task files that exist on disk but are
    missing from registry.tasks. Idempotent — already-registered IDs are
    skipped.

    Use case: v2 → v3 migration where task files predate the v3 registry
    schema and the registry is empty or partial. Reads each orphan file's
    frontmatter `id`/`name`/`status` and creates a minimal registry entry.

    Returns the list of newly-seeded task IDs (empty if nothing to do).

    Does NOT auto-create epic entries; if the orphan task references an
    epic that's missing from the registry, drift #2 (epic-not-in-registry)
    surfaces it as blocking on the next consistency check.
    """
    with registry_write_lock(registry_path):
        registry = load_registry(registry_path)
        existing_ids = {t.get("id") for t in registry.get("tasks", [])}

        epics_dir = project_root / "docs" / "epics"
        if not epics_dir.exists():
            return []

        seeded: list[str] = []
        epic_re = re.compile(r"^E(\d+)")
        task_filename_re = re.compile(r"^T(\d+)(?=[-.])")

        for epic_dir in sorted(epics_dir.iterdir()):
            if not (epic_dir.is_dir() and epic_re.match(epic_dir.name)):
                continue
            epic_id = "E" + epic_re.match(epic_dir.name).group(1)
            tasks_dir = epic_dir / "tasks"
            if not tasks_dir.exists():
                continue
            for tf in sorted(tasks_dir.glob("T*.md")):
                m = task_filename_re.match(tf.name)
                if not m:
                    continue
                tid = f"T{m.group(1)}"
                if tid in existing_ids:
                    continue
                try:
                    content = tf.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                fm_name = _parse_frontmatter_field(content, _FRONTMATTER_NAME_RE)
                fm_status = _parse_frontmatter_field(content, _FRONTMATTER_STATUS_RE)
                entry: dict[str, Any] = {
                    "id": tid,
                    "epic": epic_id,
                    "name": fm_name or f"{tid} (reconciled)",
                    "category": "",
                    "priority": 1,
                    "status": (fm_status or "pending").lower(),
                    "dependencies": [],
                    "scope": {"directories": [], "files": []},
                    "lock": None,
                    "createdAt": utcnow(),
                    "file": str(tf.relative_to(project_root)),
                }
                registry.setdefault("tasks", []).append(entry)
                existing_ids.add(tid)
                seeded.append(tid)

        if seeded:
            recompute_stats(registry)
            save_registry(registry_path, registry)
    return seeded


def transition_task(
    registry_path: Path,
    project_root: Path,
    task_id: str,
    new_status: str,
) -> dict[str, Any]:
    """Generic legal status transition. Use the specific helpers above
    when possible; this is the escape hatch for unusual transitions.

    Does NOT scan dependents; that's a higher-level concern handled by
    complete_task and pr_task.
    """
    with registry_write_lock(registry_path):
        registry = load_registry(registry_path)
        task = find_task(registry, task_id)
        current = task.get("status", "pending")
        legal = LEGAL_TRANSITIONS.get(current, frozenset())
        if new_status not in legal:
            raise IllegalTransition(
                f"Illegal transition {current} → {new_status} for {task_id}. "
                f"Legal next states from {current}: {sorted(legal) or 'none (terminal)'}"
            )
        task["status"] = new_status
        recompute_stats(registry)
        save_registry(registry_path, registry)
        mirror_status_to_file(project_root, task, new_status)
    return task


# --- Internal helpers ------------------------------------------------------


def _flip_unblocked_pending(
    registry: dict[str, Any],
    project_root: Path,
) -> list[str]:
    """Flip pending->ready for any task whose deps just became done.

    Mutates registry in place; mirrors each flipped task's file. Returns
    the IDs that were flipped, for caller-side reporting.
    """
    unblocked = scan_unblocked_tasks(registry)
    for tid in unblocked:
        t = find_task(registry, tid)
        t["status"] = "ready"
        mirror_status_to_file(project_root, t, "ready")
    return unblocked


# --- Read-only queries -----------------------------------------------------


def backlog_epic_ids(registry: dict[str, Any]) -> set[str]:
    """Return the ids of epics parked in `backlog` status.

    A task is *deferred* iff its epic is in this set -- that is the single
    source of truth for deferral; tasks carry no backlog field of their own.
    """
    return {
        e["id"]
        for e in registry.get("epics", [])
        if e.get("status") == EPIC_BACKLOG_STATUS and e.get("id")
    }


def list_tasks(
    registry_path: Path,
    *,
    status_filter: str | None = None,
    epic_filter: str | None = None,
    locked_only: bool = False,
    include_backlog: bool = False,
) -> list[dict[str, Any]]:
    """Return tasks matching the filters. Read-only.

    Tasks belonging to a `backlog` epic are excluded unless
    `include_backlog=True` -- deferred work is not queue work. Naming an epic
    explicitly via `epic_filter` overrides this: asking for E99 by id is an
    explicit request to see it.
    """
    registry = load_registry(registry_path)
    hidden = set() if (include_backlog or epic_filter) else backlog_epic_ids(registry)
    out = []
    for t in registry.get("tasks", []):
        if status_filter and t.get("status") != status_filter:
            continue
        if epic_filter and t.get("epic") != epic_filter:
            continue
        if locked_only and not t.get("lock"):
            continue
        if t.get("epic") in hidden:
            continue
        out.append(t)
    return out
