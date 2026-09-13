# Git Workflow Rules

> **Loaded at every session start** — all of `.claude/rules/*.md` is. Binding. Keep it short: opt-in depth belongs in a skill or `reference/`. See CONTRIBUTING.md "The rules budget".

## Commit Format

```
type(scope): description

Task: T###
Co-Authored-By: Claude <noreply@anthropic.com>
```

## Types

| Type | Use |
|------|-----|
| `feat` | New feature |
| `fix` | Bug fix |
| `refactor` | Code restructure |
| `test` | Tests only |
| `docs` | Documentation |
| `chore` | Maintenance |

## Branch Naming

| Type | Pattern |
|------|---------|
| Feature | `feature/<description>` |
| Bug fix | `fix/<description>` |
| Task-based | `feature/T###-<description>` |

## Project rules

- Commit after each task with the task ID in the body
- Keep commits atomic
- WIP commit before context compact

## Commit Checkpoints

| Event | Commit? |
|-------|---------|
| Task completed | YES |
| Tests passing | YES |
| Before refactoring | YES |
| Before context compact | YES (WIP) |
| Mid-feature | NO — carve-out: background worktree agents under Checkpoint Discipline commit `wip:` checkpoints (see `ALGORITHM/v1.2.0.md`) |

## Project-specific extensions

`rules/git-workflow.local.md` — survives refresh, wins on conflict.
