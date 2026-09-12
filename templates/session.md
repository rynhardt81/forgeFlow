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

> This section and `## Handoff Notes` below are compaction boundaries — what they drop, the next session never learns was missing. `skills/_shared/continuity-preservation.md` defines the six categories that must survive and is binding on both.

- **Stopped at**: <what was mid-flight when the session paused>
- **Next action**: <the single next concrete step>
- **Tried and set aside**: <approaches raised or abandoned, and why>
- **Constraints in force**: <what was asked for, decided, or ruled out — stated exactly, not paraphrased>

## Handoff Notes

> Fixed 7-field schema. `/reflect handoff` projects and refreshes this section; `/reflect resume` reads it first under a tight budget. Keep each field to a brief — this is a cold-start pointer, not a dump. The brief-length budget caps prose only: a preservation category from `skills/_shared/continuity-preservation.md` is never dropped to fit it.

### Goal
<intended outcome — one or two lines>

### Current Progress
<what is done; what is mid-flight>

### What Worked
<approaches that succeeded>

### What Didn't Work
<failed approaches to avoid repeating>

### Constraints & Decisions
<what was asked for, decided, agreed, or ruled out — in the user's own words>

### Next Steps
<the ready queue + the next concrete action>

### Specifics
<names, numbers, dates, exact wording, links — each stamped with its source and date, e.g. `39 ready (forge task ls --ready, 2026-09-12)`. Re-derivable counts are re-run at projection time, never copied from a prior brief.>
