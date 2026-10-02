# Why audit-task-status exists

Forge Flow tracks task state in **three places that can drift apart**:

1. **`docs/tasks/registry.json`** — the authoritative source of truth. The `forge`
   CLI is the only sanctioned writer; never hand-edit it.
2. **Task-file frontmatter** (`docs/epics/<epic>/tasks/T###-*.md`, `status:` field) —
   mirrors the registry. The `consistency-banner.py` hook auto-syncs this on every
   Write/Edit and at SessionStart, so it's *usually* aligned — but verify, don't assume.
3. **Epic files** (`docs/epics/<epic>/<epic>.md`) — the human-readable progress
   counters and per-task status tables. **The framework never touches these** — they
   drift the moment a task completes and nobody updates the prose. This is where the
   real, invisible drift accumulates.

The registry is correct by construction (atomic CLI mutations). The job is to make
layers 2 and 3 tell the same truth, and to flag the one structural gap the registry
can have (tasks with no body file). The point is trust: if the epic file says
"7/10 completed" and the registry says "14/19", nobody can rely on the docs.
