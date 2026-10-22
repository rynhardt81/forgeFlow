# Git Workflow Rules

> **Loaded at every session start.** Binding.

## Commit Format

```
type(scope): description

Task: T###
Co-Authored-By: Claude <noreply@anthropic.com>
```

## Branch Naming

| Type | Pattern |
|------|---------|
| Feature | `feature/<description>` |
| Bug fix | `fix/<description>` |
| Task-based | `feature/T###-<description>` |

## Project rules

- Commit after each task with the task ID in the body
- WIP commit before context compact

## Commit Checkpoints

| Event | Commit? |
|-------|---------|
| Task completed | YES |
| Tests passing | YES |
| Before refactoring | YES |
| Before context compact | YES (WIP) |
| Mid-feature | NO — carve-out: background worktree agents under Checkpoint Discipline commit `wip:` checkpoints (see `ALGORITHM/LATEST`) |
