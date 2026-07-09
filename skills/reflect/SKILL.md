---
name: reflect
description: Session continuity, task management, and skill improvement. Resume work, check status, manage locks, or capture learnings.
---

## Quick Scan

| | |
|---|---|
| **Purpose** | Manage sessions, resume work, track tasks, coordinate parallel work |
| **Inputs** | Command (resume, status, handoff, unlock, cleanup, config), optional task/epic ID |
| **Output** | Session context loaded, task status, configuration updates |
| **Flow** | Parse command → Load context → Execute → Update session |

---

# Reflect Skill

## Purpose

1. **Session Continuity:** Resume work seamlessly with context
2. **Task Management:** Track epics, tasks, and dependencies via the forge registry
3. **Parallel Session Coordination:** Prevent conflicts between concurrent sessions
4. **Skill Improvement:** Extract learnings to make skills better over time

## Command Routing

| Command | Flow File |
|---------|-----------|
| `/reflect resume` / `resume E##` / `resume T###` | [flows/resume.md](flows/resume.md) |
| `/reflect status` (`--locked`, `--ready`, `--sessions`) | [flows/status.md](flows/status.md) |
| `/reflect handoff` | [flows/handoff.md](flows/handoff.md) |
| `/reflect unlock T###` | [flows/unlock.md](flows/unlock.md) |
| `/reflect cleanup` | [flows/unlock.md](flows/unlock.md) |
| `/reflect config` / `config <key> <value>` | [flows/config.md](flows/config.md) |
| `/reflect` (no args) | [flows/manual-reflection.md](flows/manual-reflection.md) |

## Session Start Protocol

The SessionStart hook (`hooks/session/session-context.py`) auto-creates a minimal session file at `.claude/memories/sessions/active/session-{id}.md` (ID: `{YYYYMMDD-HHMMSS}-{4-random}`) whenever `active/` is empty, so a session file is guaranteed to exist before any work begins.

1. When real work begins, the agent (or `/reflect resume`) fills in the Scope Declaration (branch, directories, features) from the task being resumed.
2. Conflict Check: read all files in `active/`, apply the matrix below. Deferred until scope is declared.
3. Load context: progress-notes.md, completed sessions, registry (via forge CLI).
4. Proceed only if no blocking conflicts.

### Conflict Resolution

| Conflict | Action |
|----------|--------|
| Same branch | **BLOCK** - Cannot proceed |
| Same directory | **WARN** - User must confirm |
| Same file | **ASK** - User decides priority |
| Merge/PR | **QUEUE** - Wait for first to complete |

## Task States

`pending → ready → in_progress → pr_pending → completed`; interrupted sessions resume via `/reflect resume T###`. The forge CLI (`.claude/scripts/forge/forge.py`) enforces the state machine — never hand-edit `docs/tasks/registry.json`.

## Key Rules

- **Session file always exists:** the SessionStart hook bootstraps it; `/reflect` only enriches — never creates a duplicate when one is active.
- **Minimal context loading:** only load what the specific task/epic needs.
- **Lock via forge:** `forge task lock` before starting, `forge task complete`/`pr`/`unlock` on exit — the CLI is the only sanctioned registry writer.
- **Continuation context:** when stopping mid-task, populate the task file's Continuation Context (stopped-at + next action).
- **Append only:** never overwrite `progress-notes.md` — always append.
- **Session-file discipline:** update the session file as work progresses (Working On, Completed, Handoff Notes); move to `completed/` at session end.
- **Learnings:** append to the target skill's `## Learned Preferences` section (or `.claude/memories/general.md` if no skill matches), date-stamped. Never auto-delete existing learnings.
- **Deduplicate:** check for semantic duplicates before adding a learning; skip exact/subset matches.
- **Flag conflicts, don't replace:** a learning that contradicts an existing one gets flagged for manual resolution.
- **Always commit** continuity updates with clear messages.

## Storage Locations

```
.claude/
├── memories/
│   ├── general.md              # General preferences
│   ├── progress-notes.md       # Append-only session log
│   ├── sessions/
│   │   ├── active/session-{id}.md
│   │   ├── completed/session-{id}.md
│   │   └── latest.md           # Most recent completed
│   └── .session-skills         # Skills used (temp)
└── skills/[skill-name]/SKILL.md  # Learned preferences

docs/
├── tasks/
│   ├── registry.json           # Master task/epic registry (forge CLI only)
│   └── T###/ISA.md             # Per-task ISA (test harness), if scaffolded
└── epics/E##-name/
    ├── E##-name.md             # Epic file
    └── tasks/T###-task.md      # Task body files
```

Session-file template: `templates/session.md` (repo root).
