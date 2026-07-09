# [Project Name]

> [brief description]

This project uses the Claude Forge framework. Framework rules load via `@.claude/CLAUDE.md` (added to the project-root `CLAUDE.md` on install). This file holds project-specific execution guidance.

## Tech stack

- **Language / runtime:** [e.g. TypeScript / Node 20]
- **Framework:** [e.g. Next.js 16]
- **Data:** [e.g. Postgres + Supabase]
- **Test:** [e.g. vitest]

_(Replace the above with this project's real stack — keep it terse.)_

## Modes

Mode selection is heuristic. Pick by request shape:

| Mode | When |
|------|------|
| **Minimal** | Greetings, ratings, single-token acknowledgments |
| **Native** | Single-fact lookup, one-line edit, one command, no new artifact |
| **Algorithm** | Anything else: build, design, refactor, debug, multi-file, ambiguous |

Bias toward Algorithm in doubt.

## Algorithm

`.claude/ALGORITHM/LATEST` points to the current version. At the start of any Algorithm-mode task, read `.claude/ALGORITHM/v{VERSION}.md` and follow it exactly. Phase order is fixed: OBSERVE → THINK → PLAN → BUILD → EXECUTE → VERIFY → LEARN.

## Project-specific rules

_(Add invariants that bite repeatedly here — "always use the X helper, never bare Y" — so the rule lives next to the code it governs.)_

## See also

- `.claude/CLAUDE.md` — framework rules (imported)
- `.claude/ALGORITHM/LATEST` → `v{VERSION}.md` — Algorithm doctrine
- `ISA.md` (project root) — this project's ISA
