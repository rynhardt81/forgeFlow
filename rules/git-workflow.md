# Git Workflow Rules

> Active directive. Discovered on-demand via the `rules/*.md` glob — read by `/audit-rules` and any agent reasoning about git workflow. Treat as binding when encountered.

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

Add project-specific examples, exceptions, and conventions to `rules/git-workflow.local.md` alongside this file. Sidecar `*.local.md` files are excluded from framework refresh — they survive `install.sh --mode refresh-v3`. Readers (skills, agents, `/audit-rules`) pick up both via the `rules/*.md` glob.
