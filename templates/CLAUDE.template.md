# [Project Name]

> [brief description]

This project uses the Claude Forge framework. Framework rules load via `@.claude/CLAUDE.md` (added to the project-root `CLAUDE.md` on install). This file holds project-specific execution guidance.

## Tech stack

- **Language / runtime:** [e.g. TypeScript / Node 20]
- **Framework:** [e.g. Next.js 16]
- **Data:** [e.g. Postgres + Supabase]
- **Test:** [e.g. vitest]

_(Replace the above with this project's real stack — keep it terse.)_

## Verifying your work

_(The commands the "no claim without a probe" rule runs. `/new-project` fills these from detected scripts; keep them current — a stale command here is a probe that lies. Prefer quiet flags: output stays in context for the whole session.)_

- **Build:** `[make build]` — healthy: `[Build succeeded]`
- **Test:** `[bun test]` — healthy: `[N pass, 0 fail]`; never skip or delete a test to get here
- **Lint:** `[bun lint]` — healthy: `[zero warnings]`
- **Single test file:** `[bunx vitest run <file> --reporter=dot]`

Run build, test, and lint before reporting any task complete, and paste the output. A bug fix starts with a failing test committed **before** the fix.

## Modes

Mode selection is heuristic. Pick by request shape:

| Mode | When |
|------|------|
| **Minimal** | Greetings, ratings, single-token acknowledgments |
| **Native** | Single-fact lookup, one-line edit, one command, no new artifact |
| **Algorithm** | Anything else: build, design, refactor, debug, multi-file, ambiguous |

Bias toward Algorithm in doubt.

## Feedback level

`medium`

_(How much prose a finished-work report carries — `low` | `medium` | `high`. Four fields either way: Problem/Task · Action · Result + evidence pointer · Recommends. Levels cap prose, never evidence. Session override: `/fb low|medium|high`. Spec: `.claude/skills/_shared/report-format.md`.)_

## Algorithm

`.claude/ALGORITHM/LATEST` points to the current version. At the start of any Algorithm-mode task, read `.claude/ALGORITHM/v{VERSION}.md` and follow it exactly. Phase order is fixed: OBSERVE → THINK → PLAN → BUILD → EXECUTE → VERIFY → LEARN.

## Session hygiene

Set model and effort tier once at session start; changing either mid-session invalidates the prompt cache. `/clear` between unrelated tasks. Run `/context` once in a fresh session to see what the SessionStart hooks inject.

**Compact instructions:** on `/compact`, keep the active task id and its ISA path, the last verified probe outputs, and any decision made this session. Drop file contents and command output that a re-read can recover.

## Project-specific rules

_(Add invariants that bite repeatedly here — "always use the X helper, never bare Y" — so the rule lives next to the code it governs.)_

## See also

- `.claude/CLAUDE.md` — framework rules (imported)
- `.claude/ALGORITHM/LATEST` → `v{VERSION}.md` — Algorithm doctrine
- `.claude/skills/_shared/report-format.md` — report contract + feedback levels
- `ISA.md` (project root) — this project's ISA
