# Handoff Flow

Handles `/reflect handoff`.

> **Read-only projection.** This flow GENERATES a transient cold-start brief by reading existing continuity stores and printing it to stdout for paste into a fresh session. It writes nothing new beyond optionally refreshing the live session file's `## Handoff Notes` section. It does **not** create a standalone `HANDOFF.md` artifact — a separate file would become a fourth competing home for "what's next" (alongside the session file, `progress-notes.md`, and `docs/project-memory/`), the exact content-drift the CLAUDE.md "three kinds of documents" rule guards against.

---

## What the brief must preserve

`/reflect handoff` is client-side compaction: the session is discarded and this brief stands in for it. **`skills/_shared/continuity-preservation.md` is binding on every field below** — the six categories that must survive, the 7-field mapping, and the rule that counts are re-derived from their probe rather than copied from a prior brief. Read it before projecting. The field caps in this flow are prose budgets; they never license dropping a category.

## Why this exists

Long sessions bloat context. The escape is to start a fresh session pointed at a compact brief — which is what `/reflect resume` already does off the existing stores. This flow adds the missing ergonomics: a single, consistently-structured brief in a fixed 7-field schema, projected on demand. It does **not** replace the SessionStart auto-injection (`hooks/session/session-context.py`) or the budgeted resume load — it complements them.

## `/reflect handoff`

Project the current continuity state into a fixed 7-field brief.

### Sources (read-only)

| Field | Read from |
|-------|-----------|
| **Goal** | The active ISA `## Goal` / `task:` frontmatter, or the active session file's Scope Declaration |
| **Current Progress** | The active session file's `## Completed` + `## Continuation Context` |
| **What Worked** | Top `[PAT]` / `[DEC]` entries from `docs/project-memory/patterns.md` + `decisions.md` |
| **What Didn't Work** | Top `[BUG]` entries from `docs/project-memory/bugs.md` |
| **Constraints & Decisions** | What the user asked for, decided, agreed, or ruled out — from the session file's Scope Declaration, the ISA's constraints, and `[DEC]` entries. Stated exactly, never paraphrased |
| **Next Steps** | `forge task ls --ready` (the ready queue) + the session `## Continuation Context` next actions |
| **Specifics** | Names, numbers, dates, exact wording, links that would be hard to reconstruct — each with its provenance |

### Steps

1. Read the active session file (`.claude/memories/sessions/active/session-{id}.md`) — `## Completed`, `## Continuation Context`, Scope Declaration.
2. Read the active ISA if one is in scope (its `## Goal`).
3. Query the ready queue: `python3 .claude/scripts/forge/forge.py task ls --ready` (skip silently if no registry). **This query is the source of every task count in the brief** — never carry a count forward from the section you are about to overwrite. Stamp what it returns with the command and the date.
4. Pull the top few `[PAT]` / `[DEC]` / `[BUG]` lines from `docs/project-memory/` (cap at ~5 each — this is a brief, not a dump).
5. Emit the brief in the fixed schema below to stdout.
6. **Optionally** refresh the live session file's `## Handoff Notes` section with the same 7 fields (in-place edit of the existing section — never a new file). This keeps the next `/reflect resume` reading a consistently-structured block.

### Fixed schema

```markdown
## Handoff Notes

### Goal
<intended outcome — one or two lines>

### Current Progress
<what is done; what is mid-flight>

### What Worked
<approaches that succeeded — from project-memory patterns/decisions>

### What Didn't Work
<failed approaches to avoid repeating — from project-memory bugs>

### Constraints & Decisions
<what was asked for, decided, agreed, or ruled out — in the user's own words, not paraphrased>

### Next Steps
<the ready queue + the next concrete action>

### Specifics
<names, numbers, dates, exact wording, links — each stamped with where it came from and when>
```

### Usage

Paste the printed brief — or just point the fresh session at the session file whose `## Handoff Notes` this refreshed — into a new conversation. The fresh session's SessionStart hook still injects project-memory + key-facts automatically; this brief is the human-readable "what's next" layer on top, not a replacement for that load.

## Anti-criteria for this flow

- **Anti:** Does NOT create a standalone `HANDOFF.md` (or any new persisted artifact). It projects existing stores and at most refreshes the session file's existing `## Handoff Notes` section.
- **Anti:** Does NOT instruct the fresh session to "read ONLY this file" — it integrates with the budgeted `/reflect resume` load and the SessionStart auto-injection, which deliberately load more than one source.
- **Anti:** Does NOT dump entire memory files — each field is capped to a brief.
- **Anti:** Does NOT carry a count forward from the previous brief. Every re-derivable number comes from the probe re-run in step 3, stamped with its command and date; see `skills/_shared/continuity-preservation.md`.
- **Anti:** Does NOT paraphrase a constraint or decision the user stated. Category (3) is *stated exactly*.
- **Anti:** Does NOT drop a preservation category to stay inside a field's budget. The budget yields first.
