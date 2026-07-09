# Resume Flow

Handles `/reflect resume`, `/reflect resume E##`, and `/reflect resume T###`.

---

## `/reflect resume`

Resume from last session with full context.

1. **Check existing sessions first.** `ls .claude/memories/sessions/active/`

   | Found | Action |
   |-------|--------|
   | No sessions | Create new session (generate ID, create file from `templates/session.md`, declare scope, scan for conflicts) |
   | `status: active` or `continuation` | **RESUME that session** — read it, extract "Working On", do NOT create a new one |
   | `status: completed` | `mv` to `completed/`, then create new |
   | Multiple active | List all, ask user which to resume |

2. **Gather context:**

   ```bash
   git log --oneline -20
   git diff --stat
   git status --short
   ```

3. **Read memory files:** `sessions/latest.md`, `progress-notes.md` (append-only), `general.md`, recent `sessions/completed/`.

4. **Load project memory (if `docs/project-memory/` exists):** always load `key-facts.md`; then infer task type from title keywords and load the primary category (ToC scan + keyword matches), secondary ToC only:

   | Task type (keywords) | Primary | Secondary |
   |-----------|---------|-----------|
   | bug/fix | bugs.md | decisions.md |
   | feature/add/implement | patterns.md | decisions.md |
   | architecture/design | decisions.md | patterns.md |
   | refactor/clean | patterns.md | bugs.md |

5. **Read task registry via forge CLI** (never parse the JSON by hand):

   ```bash
   python3 .claude/scripts/forge/forge.py task ls --in-progress
   python3 .claude/scripts/forge/forge.py task ls --continuation
   python3 .claude/scripts/forge/forge.py task ls --ready
   ```

   `task show <id>` for detail. `pr_pending` tasks are implementation-done with a PR open — don't resume them; `task ls --pr-pending` tracks review status.

6. **Present combined context** — session ID, active sessions, git activity, task status (in-progress / continuation / ready), last-worked-on + blockers from progress notes, next steps from latest.md.

7. **Check for unregistered work:** if the session file has plan checkboxes (`- [ ]`) but the registry is empty/missing, offer: (1) create tasks in registry — `forge epic add E01 --name "..."` first when the epic isn't in the registry (`task add` raises `EpicNotFound` otherwise), then `forge task add T### --epic E01 --name "..." --deps ...` (no `--deps` → starts `ready`; with `--deps` → `pending`); (2) work from session plan only; (3) skip. Plans from brainstorming sessions often contain work that never became tasks — this closes that gap.

8. **Confirm:** "Continue from here?" — then load context and proceed.

---

## `/reflect resume E##`

1. **Session Start Protocol** — declare scope to include the epic's directories.
2. **Load epic file** `docs/epics/E##-*/E##-*.md`; status must be `in_progress` or have incomplete tasks.
3. **Verify task files exist (guard):** every registry task of this epic must have a file at its `file` path. If any are missing, run `python3 .claude/scripts/forge/forge.py task reconcile-files --apply` (creates stubs from `templates/task.md`), announce it, re-verify, then continue.
4. **Load minimal context:** epic summary/scope, task list with status, dependencies and blockers.
5. **Identify next task** — first `ready` or `continuation` — and present:

   ```markdown
   ## Resuming Epic E01: [Name]
   **Progress:** 3/8 tasks completed
   | ID | Name | Status |
   |----|------|--------|
   | T004 | [Name] | ready <- NEXT |
   Continue with T004?
   ```

---

## `/reflect resume T###`

1. **Session Start Protocol** — declare scope to include the task's files.
2. **Validate:** read task file from registry path; status must be `ready`, `in_progress`, or `continuation`; dependencies met.
3. **Check lock:** if locked by another session and not stale, warn; if stale (> lockTimeout), offer `/reflect unlock`.
4. **Acquire lock IMMEDIATELY** — before loading context or presenting anything:

   ```bash
   python3 .claude/scripts/forge/forge.py task lock T### --session <session-id>
   ```

   File-scope conflicts fail here. The task is now yours.
5. **Load minimal context:** task objective, requirements, acceptance criteria, files to modify, continuation context (if `continuation`), and the task ISA at `docs/tasks/T###/ISA.md` if present — the ISA is the verification trail for this task.
6. **Load relevant project memory** per the task-type table above; note what was loaded (e.g. "3 key facts, 2 relevant bugs").
7. **Check the session file's `## Active Skill` / `## Active Agent` sections.** If Skill is not "none": **re-invoke that skill via the Skill tool** — do not rely on memory; multi-phase skills lose checkpoints and documentation steps otherwise. Resume from the saved checkpoint, not the beginning. If Agent is not "none": re-read that agent definition from `.claude/agents/` before continuing its work.
8. **Present task context** — task/epic, status transition (`→ in_progress (locked)`), continuation context + resume point, remaining work, acceptance criteria. "Ready to continue?"

---

## Wrap-up Handoff to `/create-pr` (code-shipping tasks)

`/reflect` itself never ships code. But when the resumed task produces a code commit, the resuming agent MUST invoke `Skill("create-pr")` at the wrap-up commit — never raw `gh pr create`, which bypasses the DRY check, the specialist pre-flight, and the mandatory `@codex` mention (failure observed 2026-05-12). Doc-only tasks are exempt.

## Task Completion

### Step 1 — Verify acceptance criteria
All checked (`- [x]`). If any cannot be met, **stop**: follow "If Task Cannot Be Completed" below.

### Step 2 — Edit the task file BODY (`docs/epics/{epic}/tasks/{id}-*.md`)

**Do NOT change `status:` in the frontmatter yourself** — Step 4's `forge task complete` mirrors that atomically. If you flip it here first, the `consistency-banner.py` hook sees registry still saying `in_progress` and silently reverts your edit. Edit only what forge doesn't touch:
- Check off acceptance criteria and requirements
- Add completion notes under "Implementation Notes"
- Clear "Continuation Context"; append a Lock History row

### Step 3 — Update the epic file (`docs/epics/{epic}/{epic}.md`)
Forge doesn't touch it and it's how humans see progress: task-row status, progress counter (3/8 → 4/8), epic `status: completed` + note if this was the last task, one progress-log line.

### Step 4 — Run `forge task complete` (atomic; never hand-edit registry.json)

```bash
python3 .claude/scripts/forge/forge.py task complete T###
```

**This single command does all of the following atomically:**
- Sets `status: "completed"` in registry; clears the `lock` object (v3 uses single `lock: {...}|null`)
- Sets `completedAt` (UTC RFC3339); recomputes `stats.tasks.*` / `stats.epics.*`
- Flips any fully-unblocked dependents `pending → ready`
- Mirrors status changes into this task file's frontmatter AND each unblocked task's frontmatter
- Reports unblocked task IDs to stdout (`completed T015` / `unblocked: T016, T019`)

If it errors with `IllegalTransition`, the registry says the task isn't `in_progress`/`pr_pending` — investigate before forcing. Glance at the `unblocked:` line — if an expected task isn't listed, its dependencies aren't all done.

### Step 5 — Update the session file
Add the task to the completed list with a one-line summary; note handoff info for dependent tasks.

### Step 6 — Commit
`feat({epic}): {task.name} [Task-ID: {task.id}]` (or `fix:`/`refactor:`). Task file, epic file, and `registry.json` change atomically in the same commit.

### Step 7 — Open PR via `/create-pr` (mandatory for code-shipping tasks)

Invoke `Skill("create-pr")`. On success it flips the task to `pr_pending` via `forge task pr T###` — in that case **skip Step 4's `forge task complete`**; `pr_pending` is the right terminal state until the PR merges. Doc-only tasks: skip this step.

### Step 8 — Verification (REQUIRED before claiming done)
If any check fails, fixing it is part of completing the task — do NOT report success:

- [ ] Task file frontmatter shows `status: completed` (or `pr_pending`) with `completedAt`/`prAt` populated
- [ ] Registry entry shows the matching terminal status with `lock: null`
- [ ] Registry `stats.tasks.*` counts reflect this task (`forge task show T###`)
- [ ] Epic file progress counter updated; task row shows the terminal status
- [ ] Every unblocked dependent has `status: ready` in BOTH registry and its task file
- [ ] Session file lists this task under completed (or pr_pending) work
- [ ] `git status` shows task file, epic file, and `registry.json` committed together
- [ ] **Code-shipping tasks:** PR opened via `Skill("create-pr")` — never raw `gh pr create`

**If Task Cannot Be Completed:**

1. `forge task unlock T###` (releases lock, defaults to `continuation`) — or `--to-status ready` if no progress was made. Never hand-edit the registry; the CLI mirrors changes to the task file atomically.
2. Document the blocker under "Continuation Context" (done / remaining / resume point).
3. Add the blocker to the session file; note the continuation in the epic progress log.
4. Do NOT run the completion steps — dependents must not unblock.
