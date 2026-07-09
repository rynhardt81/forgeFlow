---
name: migrate
description: Onboard an existing project to Claude Forge or upgrade a project across framework versions (v2 → v3 → v4), preserving and merging existing .claude content. Use after the installer has placed the framework; /migrate completes the content merge and optional brownfield analysis.
---

# Migrate

Thin driver over the installer. The setup mechanics live in **`scripts/install/install.sh`** (Windows: `install.ps1`); `/migrate` completes what the script can't do mechanically — content-aware merging from the old configuration and brownfield project analysis.

## When to use

- Onboarding an existing project (with or without a previous `.claude/`) onto Claude Forge.
- Upgrading a Forge project across framework versions (v2 → v3 → v4).

## Setup first: the installer

```bash
git clone https://github.com/rynhardt81/forgeFlow.git
./forgeFlow/scripts/install/install.sh /path/to/project        # interactive mode menu
./forgeFlow/scripts/install/install.sh --mode refresh --yes /path/to/project
```

What the installer does:

- **Full install** — backs up any existing `.claude/` to `.claude_old/`, installs the framework fresh, and writes a `.claude_restore.sh` rollback script in the project root.
- **Refresh modes** — snapshot the current `.claude/` to `.claude/backups/<timestamp>/` (default; `--no-backup` skips it and is irreversible), then overwrite framework-owned files while preserving `settings.json` (merged), specialists, and consumer-owned `rules/*.local.md` sidecars.
- Creates or amends the root `CLAUDE.md` with the `@.claude/CLAUDE.md` import.

Then start Claude Code in the project and run `/migrate`.

## Invocation

```
/migrate                    # standard: merge + analysis
/migrate --skip-analysis    # content merge only
/migrate --dry-run          # preview every action, no changes
```

## What /migrate does

**1. Verify + plan.** Confirm `.claude_old/` (the backup) and the framework in `.claude/` both exist — if not, point back to the installer and stop. Scan `.claude_old/` and categorize:

| Content | Action |
|---------|--------|
| Project docs, PRD, ADRs, `docs/tasks/registry.json`, epics | **PRESERVE** — copy into place unchanged |
| Project memory (`docs/project-memory/`, legacy `memories/`) | **MERGE** — append old knowledge under a "migrated" marker; legacy entries reformat to `MEMORY-SCHEMA.md` |
| `settings.local.json`, user permissions | **MERGE** — user settings win; framework hooks are added, never replace user hooks |
| Custom skills / specialist agents | **PRESERVE** — `.claude/agents/specialists/` and custom skill dirs are user-owned |
| Framework files (templates, framework agents, framework skills) | **REPLACE** — the new framework version wins |
| Anything unrecognized | **ASK** — see decision points |

**⛔ Decision point: present the migration plan (preserve / merge / replace / ask lists) and get approval before mutating anything.**

**2. Execute the merge** per the approved plan. Two situations surface to the user instead of being auto-resolved:

- **Unknown files** — show a preview; user picks keep (in `.claude/custom/`) / discard / show full content.
- **Merge conflicts** — same file, materially different content on both sides; show both versions; user picks mine / framework / combined / manual edit.

**3. Brownfield analysis** (skipped with `--skip-analysis`). For gaps only — existing docs are respected, never regenerated: no PRD → run `/new-project --current` requirements discovery from the codebase; no ADRs → architecture analysis; no task registry → build one from the PRD or codebase. If project state is unclear (what's done vs planned), ask rather than infer.

**4. Verify + cleanup.** Confirm the framework is operational (CLAUDE.md readable, skills present, `forge task ls` runs), write `migration-report.md` (what was preserved / merged / replaced, post-migration checklist), then **⛔ decision point:** keep `.claude_old/` for now (recommended for the first week), delete it, or archive to a tarball.

## Rollback

- **Full install:** `./claude_restore.sh` — or manually: `rm -rf .claude && mv .claude_old .claude`.
- **Refresh:** restore from the snapshot at `.claude/backups/<timestamp>/`.
- `/migrate`'s own merge steps only add or ask — preserved and merged content is never deleted from the backup until the user approves cleanup.

## Version-specific notes (v2/v3 → v4)

- v4 removed the automatic memory pipeline — old `daily/` extraction output and `memories/` content merge into `docs/project-memory/` (manual `/remember` is the only capture path going forward).
- Skills removed in v4 (e.g. post-implementation-check, implement-features) have no merge target; references to them in old project docs are flagged in `migration-report.md`, not silently rewritten.
- The task registry format is stable; `forge task reconcile-files` after migration catches registry/body drift.
