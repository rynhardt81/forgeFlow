---
name: remember
description: Save and retrieve project knowledge that persists across sessions — bug patterns, technical decisions, key facts, and code patterns. Use whenever the user wants to record a lesson learned, save a debugging insight, document a technical choice, note a convention, or search past memories. Triggers on "remember this", "save this for later", "note that", "don't forget", "have we seen this before".
---

# Remember

**`/remember` is the capture path** for project memory — capture is manual and intentional. (v4 removed the automatic session-end/pre-compact extraction pipeline; nothing captures for you.) Schema of record: `MEMORY-SCHEMA.md` at the framework root.

Four types, four target files under `docs/project-memory/` (committed, shared with the team):

| Type | Target | Belongs there |
|------|--------|---------------|
| `bug` | `bugs.md` | "This bit us once, root cause was X" |
| `decision` | `decisions.md` | "We chose X over Y because Z" (mirror significant ones to `reference/06-architecture-decisions.md` as ADRs) |
| `pattern` | `patterns.md` | "This codebase always does X this way" |
| `fact` | `key-facts.md` | "The staging URL / account / magic value is X" — single lines only; always loaded at SessionStart |

Not memory: architecture truth (Tier 2 `reference/02` wins) and **never secrets/tokens/credentials** — these files are committed to git.

## Commands

| Command | Purpose |
|---------|---------|
| `/remember bug\|decision\|pattern\|fact "description"` | Add an entry |
| `/remember search "query"` (`--archive` to include archived) | Search memories |
| `/remember show [category]` | Show a file's entries |
| `/remember archive [--before YYYY-MM-DD] [--dry-run]` | Move stale entries to `archive.md` |

## Adding an entry

1. **Extract from conversation context** — don't interrogate the user field-by-field. For bugs: symptoms, root cause, solution. For decisions: context, options, choice, rationale.
2. **Dedup before adding** — grep the target file for an existing entry covering the same fact. On a near-match, show it and ask: update it or add new?
3. **Format** per `MEMORY-SCHEMA.md` — atomic, one fact per entry:

```markdown
## <one-line title>
- **Date:** YYYY-MM-DD
- **Context:** <one sentence — when does this matter>
- <the fact / decision / pattern, stated plainly>
```

Bugs also carry root cause + solution lines; decisions also carry the rejected option + why. `key-facts.md` entries are single bullet lines — if it needs a paragraph, it belongs in `decisions.md` with a one-line pointer in key-facts.

4. **Present the draft** for confirmation before writing.
5. **Append** to the target file and **update `docs/project-memory/index.md`** — the master catalog loaded at SessionStart. An entry missing from the index is invisible to future sessions.

## Searching

Read `index.md` first (the catalog), match the query against titles/context there, then open only the matching target file(s). With `--archive`, also search `archive.md`.

## Archiving

When active files grow stale: entries older than the cutoff (prompted, or `--before`) move to `archive.md` with an `**Archived:** <date>` line, grouped by category. Confirm counts with the user first; `--dry-run` previews. Update `index.md` after. **`key-facts.md` is never archived** — it's current state; outdated facts get updated or deleted, not archived.

## Read path (for reference)

`hooks/session/session-context.py` injects `index.md` + `key-facts.md` at every SessionStart; `bugs.md`/`decisions.md`/`patterns.md` are read on demand — `/fix-bug` greps `bugs.md` before investigating, and Algorithm LEARN routes `knowledge`-type insights here through this skill.
