# Coding Style Rules

> **Loaded at every session start** — all of `.claude/rules/*.md` is. Binding. Keep it short: opt-in depth belongs in a skill or `reference/`. See CONTRIBUTING.md "The rules budget".

## File Size Limits

| Type | Max Lines | If Exceeded |
|------|-----------|-------------|
| Component | 300 | Split |
| Service | 400 | Extract |
| Utility | 200 | Break into modules |
| Test | 500 | Split by concern |

When a limit is hit, route through `/refactor` (Structural mode) — the skill picks the cleavage and runs `check_undefined_names.py` to catch slicing-bug regressions before they ship.

## Project-specific extensions

`rules/coding-style.local.md` — survives refresh, wins on conflict.
