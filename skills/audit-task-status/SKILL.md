---
name: audit-task-status
description: >
  Align Forge Flow task/epic statuses with the authoritative task registry, and
  report registry health. Use this whenever the user asks to align/sync/reconcile
  task or epic statuses, to check whether the registry, task files, and epic files
  agree, or says things like "are the task statuses in sync", "the epic file is
  stale", "make the epics match the registry", "reconcile task state", or "audit
  task/registry consistency". The registry (docs/tasks/registry.json) is the single
  source of truth; this skill detects and fixes drift in the two layers that mirror
  it — task-file frontmatter (machine-maintained) and epic files (human-authored
  prose the framework never touches). Also surfaces registry tasks with no body
  file on disk. Reach for it after a batch of merges/completions, before a release,
  or any time someone doubts the task numbers are trustworthy.
---

# Audit & align task status

## Why this exists

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

## The authority rule

**The registry is ground truth. Always reconcile the other layers TO it, never the
reverse.** If a task file or epic file disagrees with the registry, the registry
wins — fix the doc. The only exception is if the registry itself looks wrong (a
status that contradicts a merged PR); in that case stop and surface it to the user,
because changing the registry means a `forge task` state transition, not a doc edit.

## Workflow

### 1. Sync the machine layer (registry ↔ task-file frontmatter)

Run the consistency hook with `--fix` — it auto-corrects trivial registry/task-file
drift and reports anything it can't fix:

```bash
python3 .claude/hooks/forge/consistency-banner.py --fix --json
```

`rc=0` with no findings means layers 1↔2 agree. If it reports blocking drift it
can't auto-fix, resolve that first (it usually means a task file was hand-edited to
a status the registry disagrees with — fix the file to match the registry).

**Do not trust `rc=0` alone as proof of full alignment** — this hook only checks
registry↔task-file. It is blind to epic files. The next steps are where the value is.

### 2. Independently verify task-file frontmatter (don't just trust the hook)

The hook is informational and has been wrong before. Confirm independently — for
every registry task, the body file's `status:` frontmatter must equal the registry
status. Use the bundled script:

```bash
python3 .claude/skills/audit-task-status/scripts/audit_status.py
```

It reads the registry, locates each task's body file, and reports three things:
- **task-file status mismatches** (frontmatter `status:` ≠ registry status),
- **epic-file drift** (see step 3),
- **registry tasks with no body file on disk**.

Read its output before editing anything — it tells you the exact scope.

### 3. Reconcile epic files (the layer the framework forgets)

For each epic with open or recently-changed work, the epic file (`<epic>/<epic>.md`)
has up to four things that drift — the bundled script reports the first three; you
verify and fix:

- **The progress counter** — a prose line like `**Tasks:** N total — M completed, …`.
  Recompute from the registry and rewrite it. Refresh any "as of <date>" stamp.
- **The per-task status — in TWO idioms**, depending on the epic:
  - *Pipe tables*: `| T### | … | <status> | … |`. Column position varies (5-col vs
    6-col; E38 puts a `Track` column before `Status`), and cells carry annotations
    (`completed (PR #254)`, `closed — phantom`). Fix any cell whose leading status
    token disagrees with the registry.
  - *Checklists* (e.g. E25): `- [x] T###: … ✅` / `- [~] T###a: … superseded`. The
    checkbox alone is ambiguous, so the script only flags a row when an explicit
    status word in the line contradicts the registry. Verify these by hand — a
    `[x]` next to a task the registry calls `superseded` is real drift; a `[x]`
    that's merely annotated `(commit pending)` while the registry says `completed`
    is cosmetic, not a status mismatch.
- **The prose `**Status:**` header** (and the epic's `status:` frontmatter). An epic
  whose every task is terminal (completed/superseded/closed) but whose prose header
  still says `in_progress`/`pending` is contradicting itself — fix the header to
  match the rollup. (This is distinct from the counter; an epic can have a right
  counter and a stale header, or vice-versa.)

**Watch for internal contradictions** — a counter saying "1 ready" while the table
row for the same task says `completed`, or a `**Status:** in_progress` header on an
all-terminal epic. Make every layer (header, counter, rows) AND the registry agree.

**Scope discipline — do NOT backfill missing table rows by default.** Epic files
routinely list only a subset of their tasks (the headline ones); the registry holds
the complete per-task detail. Many Forge epic files explicitly say "registry is
authoritative — counts drift as tasks are added". Adding a row for every
registry task is a large rewrite that fights the file's design. Fix the *counters*
and the *statuses of rows that already exist*; only backfill individual rows if the
user explicitly asks. When you skip a backfill, say so plainly (e.g. "counter now
reflects all N tasks; 35 of them don't have individual table rows, by design").

### 4. Report the registry-health extras

Beyond status, surface (don't fix unless asked):

- **Tasks with no body file** — registry entries created with `--no-file`, or whose body was later deleted/moved. The
  script lists them. These aren't a *status* problem, but they break resume/lock for
  those tasks. Offer the fix rather than doing it silently:
  `python3 .claude/scripts/forge/forge.py task reconcile-files` (dry-run) →
  `--apply` to create stub bodies.

### 5. Verify and commit

Re-run the audit script — every layer should now report **0 mismatches**. Re-run
the consistency hook (`rc=0`) to confirm your epic-file edits didn't disturb the
machine layer (they shouldn't — you only touched epic prose). Then commit the epic
files (and any task files the hook fixed) together:

```
docs(epics): align <epics> statuses with registry
```

Spell out in the commit what drifted and what you deliberately left (e.g. "fixed
counters + N stale rows + the T### contradiction; did NOT backfill the M missing
rows — epic defers per-task detail to the registry").

## What "aligned" means (the done condition)

- Registry ↔ task-file frontmatter: 0 status mismatches.
- Every epic-file counter matches the registry's completed/total for that epic.
- Every epic-file row that exists (table OR checklist) matches the registry status.
- Every epic's prose `**Status:**` header agrees with its task rollup.
- No internal contradictions within an epic file (header vs counter vs rows).
- Registry-tasks-without-body-files reported (and fixed only if the user opted in).

## Verify the script's findings — it is a first pass, not an oracle

The bundled `audit_status.py` is a fast detector, but it resolves body files by the
registry `file` field with a glob fallback, and parses heterogeneous human prose —
so it can mis-report at the edges. Treat its output as candidates to confirm, not
gospel. Two false-positive classes it has produced before (now guarded, but stay
alert): a `T###-*.md` file outside a `/tasks/`-or-`/orphan/` dir (e.g. a
`docs/debug/` triage note) shadowing the real body file; and a cosmetic annotation
(`[x] … (commit pending)`) read as a status. Before you edit anything, spot-check
each flagged item against the registry and the actual file line — the same
empirical-premise discipline any audit finding deserves.

## Notes

- This is a deterministic audit, not a judgment call — the registry decides every
  status. The only place judgment enters is the scope of epic-file backfill (step 3)
  and whether to create missing body files (step 4); both default to "ask, don't
  silently expand scope".
- The bundled `scripts/audit_status.py` does the read-only detection; the fixes are
  small targeted edits you apply by hand (epic prose is human-authored — an
  Edit-per-fix keeps the change reviewable). Don't try to regex-rewrite whole tables.
