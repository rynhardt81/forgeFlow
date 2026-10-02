# Skill Authoring

> How a framework skill is laid out. Enforced by `tests/wiring/test_skill_structure.py`. Sources: Anthropic's [skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) and the [Claude Code skills reference](https://code.claude.com/docs/en/skills).

## Why the layout matters

A skill loads in three levels:
1. **Description** (frontmatter): always in context, in every session.
2. **SKILL.md body**: loaded when the skill is invoked. It then stays in context for the rest of the session.
3. **Bundled files**: cost nothing until read.

Two harness facts make the body's size and order load-bearing:
- **Compaction:** after auto-compaction, Claude Code keeps only the **first 5,000 tokens** of each invoked skill. Anything below that is gone for the rest of the session.
- **Partial reads:** Claude may read a long reference file only partly (`head -100`) and act on what it saw. A file whose scope isn't visible at the top gets used incompletely.

So SKILL.md is a router: the core that must always apply, plus an index that sends the reader to the one file it needs now.

## SKILL.md layout, in order

1. **Frontmatter:** `name`, `description`, plus any Claude Code fields the skill needs (`allowed-tools`, `hooks`, `model`, `effort`, `when_to_use`, …).
2. **Title and a short purpose:** one paragraph at most.
3. **`## Index`:** a table of `File or section | Read when…`. List every bundled `.md` file **and** every `skills/_shared/*.md` file the skill uses. If a skill has nothing to route to, the index lists its own sections.
4. **The core:** invocation, steps, gates, key rules.
5. **The sidecar pointer line:** stays the last line of the file (`test_skill_sidecar_pointer.py`).

## Budgets

- **SKILL.md: ≤ 200 lines and ≤ 10 KB.** This is stricter than Anthropic's 500-line ceiling on purpose, so the compaction-kept first 5,000 tokens hold the whole core.
- **Any bundled `.md` over 100 lines** opens with a `## Contents` list within its first 15 lines.

## What stays in SKILL.md and what moves out

Rule of thumb: a partial read of the skill must never skip a gate.

**Stays:**
- Every gate, hard floor and blocking check, stated as a rule with its trigger.
- Verification requirements.
- The step sequence.
- Exit codes and statuses a caller depends on.
- Key rules.

**Moves to a bundled file:**
- Templates and output skeletons.
- Worked examples.
- Long sub-flows behind a subcommand or flag.
- Config and lookup tables.
- Version quirks and rationale ("why this exists").
- Gotchas lists longer than a handful of lines.

When a gate moves its *mechanics* out, the SKILL.md step keeps the gate itself in one or two lines: what blocks, and when. It then points to the file that holds the commands.

## References stay one level deep

- SKILL.md is the only file that points at other files.
- A bundled file may point back to SKILL.md, and to nothing else. If a sub-flow needs `_shared/task-triage.md`, list it in the SKILL.md index against that step instead.
- Pointing into **another skill's** files is not allowed. Name the other skill (`/new-feature`) or the shared file instead.

## Description

- Third person. It says what the skill does **and** when to use it, with an explicit `Use when …` clause (or a `when_to_use` field).
- At most 1,024 characters. Claude Code truncates `description` + `when_to_use` at 1,536 in the listing, and under a full skill listing drops the descriptions of the least-used skills first.
- Add a `NOT FOR …` clause when a neighbouring skill is easy to confuse with this one.

## File naming

- Bundled files are uppercase topic names (`PHASES.md`, `TEMPLATES.md`, `GATES.md`) or a lowercase folder for a family (`flows/`, `cookbook/`, `Workflows/`).
- Use forward-slash relative paths in the index.
- Say whether a bundled script is to be **run** or **read**.

---

**Project-specific overrides:** if `skill-authoring.local.md` exists in this directory, read it — it is consumer-owned, survives framework refresh, and **wins on conflict**.
