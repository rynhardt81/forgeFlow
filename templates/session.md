# Session {id}

> Operational scaffold — the full session-file template referenced by `reference/10-parallel-sessions.md`. The SessionStart hook (`hooks/session/session-context.py`) auto-creates a minimal version of this file in `.claude/memories/sessions/active/`; `/reflect resume` and the agent enrich it as work progresses. This template documents every section the file may carry.

**Started**: YYYY-MM-DD HH:MM
**Branch**: {git-branch}
**Scope**: {declared working area}
**Status**: active | completed | blocked

## Scope Declaration
- **Branch**: `feature/my-feature`
- **Directories**: [`src/components/`, `src/lib/utils/`]
- **Files**: [`src/config.ts`] (if specific)
- **Features**: [Feature areas being worked on]

## Conflict Check
- [ ] Scanned active/ directory
- [ ] No branch conflicts
- [ ] No directory conflicts (or user approved)
- [ ] No file conflicts (or user approved)

## Active Skill

| Field | Value |
|-------|-------|
| **Skill** | none |
| **Phase** | - |
| **Artifact** | - |
| **Checkpoint** | - |
| **Started** | - |

## Active Agent

| Field | Value |
|-------|-------|
| **Agent** | none |
| **Workflow** | - |
| **Phase** | - |
| **Menu Selection** | - |
| **Checkpoint** | - |
| **Started** | - |

## Working On
- [ ] Current task

## Completed
- [x] Done item (commit: abc123)

## Continuation Context
- **Stopped at**: <what was mid-flight when the session paused>
- **Next action**: <the single next concrete step>

## Handoff Notes

> Fixed 5-field schema. `/reflect handoff` projects and refreshes this section; `/reflect resume` reads it first under a tight budget. Keep each field to a brief — this is a cold-start pointer, not a dump.

### Goal
<intended outcome — one or two lines>

### Current Progress
<what is done; what is mid-flight>

### What Worked
<approaches that succeeded>

### What Didn't Work
<failed approaches to avoid repeating>

### Next Steps
<the ready queue + the next concrete action>
