# Parallel Sessions & Session Protocol

How multiple Claude sessions work on the same project simultaneously without conflicts, and how any session (single or parallel) starts, runs, and ends cleanly.

---

## Overview

When multiple Claude sessions run in parallel (different terminal windows, IDE instances, or background worktree agents), they must avoid:

1. **Race conditions** on shared files
2. **State conflicts** when updating session state
3. **Overlapping work** on the same features
4. **Merge conflicts** from simultaneous changes

The system provides session isolation with explicit scope boundaries, conflict detection before work begins, an append-only audit trail, and coordination rules for branch/directory/file access. With only one session active, everything below still runs but passes silently — the system is fully backwards compatible with single-session use.

---

## Session files — executable truth lives elsewhere

A session file is guaranteed present after SessionStart: `hooks/session/session-context.py` generates the session ID (`{YYYYMMDD-HHMMSS}-{4-random-chars}`) and auto-creates a minimal `session-{id}.md` in `.claude/memories/sessions/active/` when none exists (race-safe, never blocks SessionStart). `/reflect resume` and the agent enrich it as work progresses.

**Do not restate the file format from memory.** The canonical section-by-section format is `templates/session.md`; the auto-creation behavior is `hooks/session/session-context.py`. Those two files are the executable truth — this document only describes coordination semantics.

```
.claude/memories/
├── progress-notes.md           # Append-only log (NEVER overwrite)
├── general.md                  # Project preferences
└── sessions/
    ├── active/session-{id}.md     # Running sessions (gitignored)
    ├── completed/session-{id}.md  # Archived sessions (gitignored)
    └── latest.md                  # Most recent (single-session compat)
```

---

## Session lifecycle

**Start** *(steps 1–2 automatic via the SessionStart hook)*:

1. Generate session ID
2. Create session file in `active/`
3. Declare scope — branch, directories, specific files, feature areas
4. Scan for conflicts — parse every other file in `active/`, compare scopes, apply the matrix below
5. Load context — `progress-notes.md`, relevant completed sessions, `docs/tasks/registry.json`, `docs/plans/`
6. Proceed only if no blocking conflicts (or user approved)

**During:** update the session file in real time — "Working On" when starting, "Completed" when done, commits and key decisions as they land. Re-check conflicts before modifying files outside declared scope; expanding scope means updating the declaration and re-running detection first.

**End:**

1. Update the session file — completed work, handoff notes, status `completed`
2. Move it from `active/` to `completed/` (the SessionEnd hook `session/session-end-cleanup.py` archives atomically)
3. Append a summary to `progress-notes.md` with a `---` separator — **never overwrite existing content**; corrections are new entries, not edits
4. Update `latest.md` only if no other active sessions exist

---

## Conflict resolution matrix

| Conflict type | Detection | Resolution |
|---------------|-----------|------------|
| **Branch collision** | Same branch name in another active session | **BLOCK** — cannot proceed; user chooses which session continues |
| **Directory overlap** | Declared paths intersect | **WARN** — user confirms or narrows scope |
| **File collision** | Same specific file declared | **ASK** — user decides priority |
| **Merge/PR collision** | Both sessions merging | **QUEUE** — first completes, second waits |

Scope granularity: branch (exact match), directory (path containment/overlap), file (exact match), feature area (name match → warning).

### Resolution strategies

1. **Branch isolation (preferred)** — each session on its own branch; no conflicts possible, clear ownership.
2. **Directory partitioning** — non-overlapping areas (e.g. `src/backend/` vs `src/frontend/`) on the same branch.
3. **Time slicing** — one session pauses while the other completes; use when the same files are genuinely needed sequentially.
4. **Merge coordination** — both finish on separate branches; the user merges the PRs and resolves overlap once.

---

## Lock rules

- **Task locks:** `forge task lock T### --session <id>` is the work-claim mechanism — it fails on file-scope overlap with another locked task. Never bypass it by editing `docs/tasks/registry.json`.
- **Stale sessions:** a session is stale when its file is older than `sessionStaleTimeout` (default 86400 s / 24 h) with no corresponding Claude process. Inspect with `/reflect status --locked`; clean with `/reflect cleanup` (confirmation required, `allowManualUnlock` default true). Manual cleanup: read the stale file, note uncommitted work, move to `completed/` with status `abandoned`, append a summary to `progress-notes.md`.
- **Concurrency ceiling:** `maxParallelAgents` (default 3) caps concurrent active sessions.
- **Recovery after a crash:** check `git status` for uncommitted work, `/reflect status --locked` for stale locks, clean up orphaned `active/` files, then `/reflect resume`.

Configure via `/reflect config`.

---

## Best practices

1. **Declare narrow scopes** — only claim what you'll actually modify
2. **Use branch isolation** — safest strategy for parallel work
3. **Update session files in real time** — progress isn't lost on crash, handoff is always current
4. **Complete sessions cleanly** — always run the end protocol
5. **Check for conflicts before file modifications** — not just at start
6. **Keep progress-note entries concise** — a log, not an essay

---

## See also

- `templates/session.md` — the canonical session-file format (operational scaffold)
- `hooks/session/session-context.py` — SessionStart auto-creation (executable truth)
- `hooks/session/session-end-cleanup.py` — SessionEnd atomic archival
- `ALGORITHM/v1.2.0.md` → "Background Agent Checkpoint Discipline" — commit contract for background worktree sessions
- `reference/13-task-management.md` — task locking via the forge CLI
