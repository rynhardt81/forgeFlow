# Project Memory — Schema

> How Forge Flow persists project knowledge. **Capture is manual and intentional** — the `/remember` skill writes it, the SessionStart hook reads it back. There is no automatic transcript capture: v3's capture→flush→compile pipeline was removed in v4 (it silently failed in the field, and its design required spawning LLM subprocesses from hooks — forbidden).

## Storage layout

```
docs/project-memory/          # Committed, shared with the team
├── index.md                  # Master catalog — loaded at SessionStart
├── key-facts.md              # Always loaded at SessionStart
├── decisions.md              # On-demand: architectural + product decisions
├── bugs.md                   # On-demand: root-caused bugs worth remembering
└── patterns.md               # On-demand: codebase patterns and conventions

daily/                        # Gitignored, per-user
└── algorithm-reflections.jsonl   # Auto-appended by isa-reflection-emit.py hook
```

## Write path — `/remember`

```
/remember bug "Session token refresh loops when clock skew > 30s"
/remember decision "Chose SQLite over Postgres for the CLI cache — zero-config wins"
/remember pattern "All route handlers return Result<T, ApiError>, never throw"
/remember fact "Staging Supabase project is nn-staging, prod is nn-prod"
```

The skill classifies the entry, appends it to the matching file under `docs/project-memory/`, and updates `index.md`. Entries are dated. Dedup before adding — check the target file for an existing entry covering the same fact.

## Read path — SessionStart

`hooks/session/session-context.py` injects at every session start:

1. `docs/project-memory/index.md` — the catalog (what knowledge exists)
2. `docs/project-memory/key-facts.md` — the always-relevant facts

Everything else (`bugs.md`, `decisions.md`, `patterns.md`) is read on-demand when the work touches that territory.

## Entry format

```markdown
## <one-line title>
- **Date:** YYYY-MM-DD
- **Context:** <one sentence — when does this matter>
- <the fact / decision / pattern, stated plainly>
```

Keep entries atomic: one fact per entry. `key-facts.md` entries are single lines — if it needs a paragraph, it belongs in `decisions.md` or a Tier 2 reference doc, with a one-line pointer in key-facts.

## What belongs where

| Content | Home |
|---------|------|
| "This bit us once, root cause was X" | `bugs.md` |
| "We chose X over Y because Z" | `decisions.md` (mirror significant ones to `reference/06-architecture-decisions.md` as ADRs) |
| "This codebase always does X this way" | `patterns.md` |
| "The staging URL / account / magic value is X" | `key-facts.md` |
| Architecture truth | NOT here — `reference/02` (Tier 2 wins over memory) |
| Secrets, tokens, credentials | NEVER — memory is committed to git |
