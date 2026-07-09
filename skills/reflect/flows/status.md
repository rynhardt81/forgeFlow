# Status Flow

Handles `/reflect status` and its variants.

> **Data source:** query via the forge CLI — `task ls --status <state>`, `task ls --locked`, `task ls --ready`, `task show <id>`; add `--json` for filtering. Never parse `docs/tasks/registry.json` by hand.

---

## `/reflect status`

Overview of all epics, tasks, and active sessions (session files from `.claude/memories/sessions/active/`).

```markdown
## Project Status

**Epics:** 4 total (1 completed, 2 in_progress, 1 pending)
**Tasks:** 32 total (12 completed, 2 in_progress, 8 ready, 10 pending)
**Active Sessions:** 2

### Active Sessions
| Session ID | Branch | Scope | Started |
|------------|--------|-------|---------|

### Epic Overview
| ID | Name | Status | Progress |
|----|------|--------|----------|

### Ready Tasks (available to work on)
| ID | Epic | Name | Priority |
|----|------|------|----------|

### In Progress
| ID | Name | Locked By | Since |
|----|------|-----------|-------|
```

---

## `/reflect status --sessions`

Detail per active session: branch, directories, working-on, commit count — plus a "Potential Conflicts" line from the conflict matrix.

---

## `/reflect status --locked`

`forge task ls --locked`. Output:

```markdown
| ID | Name | Locked By | Since | Stale? |
|----|------|-----------|-------|--------|
```

Stale locks (> lockTimeout) can be released with `/reflect unlock <id>`.

---

## `/reflect status --ready`

`forge task ls --ready` — dependencies met, not locked. Output:

```markdown
| ID | Epic | Name | Priority | Category |
|----|------|------|----------|----------|
```

Footer: "Use `/reflect resume T###` to start working on a task."
