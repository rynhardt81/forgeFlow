# Migration Guide

## v3 → v4

> v4 is a subtractive release: the task CLI, ISA trail, preflight-ci, and all daily-spine skills are unchanged in their interfaces. Upgrading is a framework refresh plus awareness of what no longer exists.

**Upgrade:** `./scripts/install/install.sh --mode refresh-v3 /path/to/project` (the refresh path handles v3→v4; your registry, ISAs, project-memory, specialists, and `rules/*.local.md` sidecars are untouched).

**Removed in v4 — and what replaces it:**

| Removed | Use instead |
|---------|-------------|
| `/implement-features` + features.db | The forge registry + `/run-epic` (the one task system) |
| Automatic memory capture (SessionEnd/PreCompact transcript pipeline) | `/remember` — manual, intentional, committed |
| `/pdf` | Claude Code's native Read tool (handles PDFs) |
| `/permissions` | Claude Code's native `/permissions` |
| `/post-implementation-check` | `/create-pr` Step 3.7 pre-flight (runs on every PR) |
| `/visualize` slash-skill | `forge dashboard` (same renderers, one UI) |
| `security/` command pipeline + `security-check.py` | `/damage-control` hooks (the one blocking layer) |
| `claude-md-reflect.py` Stop hook | `/audit-rules`, run manually |
| ISC floors / thinking floors / feature-count floors | Judgment, gated by the splitting test + quality gates |
| Emoji phase banners + mandatory final format | Plain prose; the checks survive, the formats don't |
| ALGORITHM v1.1.0 | v1.2.0 (`ALGORITHM/LATEST`) |

**Added in v4:** `/triage-incident`; `rules/migrations.md`, `rules/release-engineering.md`, `rules/privacy.md`; `templates/renovate.json` + `templates/dependency-scan.yml`; Algorithm Gate E (schema changes); validator advice now reaches the model via `additionalContext`.

**Behavior change to expect:** Native mode is the default; Algorithm fires on explicit signals (multi-file work, debugging, schema/auth/money paths, `/e3`+). If you relied on every session opening with phase banners — that was the bug, not the feature.

---

# v2 → Forge Flow v3

> Upgrade an existing Claude Forge v2 project to Forge Flow v3 without losing task state, project memory, specialists, or daily logs.

## When to use this guide

| Situation | Path |
|-----------|------|
| Existing v2 project with `.claude/` | `install.sh --mode refresh-v3` (below) |
| Existing v2 project, want content merge from old config | `install.sh --mode refresh-v3` then `/migrate` |
| Brand-new project | Skip this guide — use `/new-project` in [USER-GUIDE.md](docs/USER-GUIDE.md) |
| Already on v3, just updating framework files | `install.sh --mode refresh-v3` |

## What changes in v3

Forge Flow v3 rebuilds the framework around deterministic primitives:

- **Algorithm** — phase-disciplined doctrine (OBSERVE → LEARN)
- **ISA** — ideal-state articulation per task and per project
- **Forge CLI** — atomic task-state operations with consistency-banner drift repair
- **5 thinned agents** — architect, project-manager, quality-engineer, security-boss, devops
- **Rules on-demand** — `.claude/rules/` are active directives read when needed, not auto-loaded at session start
- **Removed v2 surfaces** — legacy `commands/`, `features/`, 13 ghost agents, `.claude/cross-repo/` config

Removed v2 surfaces are backed up locally by the installer (see Step 1) — they are not preserved in this repo's history.

## Before you start

1. **Commit or stash** all project changes — the installer backs up `.claude/` but not your application code.
2. **Note your specialists** — user-owned agents under `.claude/agents/specialists/` are preserved automatically.
3. **Have Python 3.10+** and `rsync` available (macOS/Linux). Windows: use `install.ps1`.

## Step 1 — Run the v3 installer

From a clone of this repository:

```bash
cd /path/to/forgeFlow
./scripts/install/install.sh --mode refresh-v3 --yes /path/to/your-project
```

What the installer does:

1. Backs up the existing `.claude/` to `.claude/backups/<timestamp>/` (unless `--no-backup`)
2. Rsyncs v3 framework files into `.claude/`
3. Removes legacy v2 surfaces (backed up under `.claude/backups/<timestamp>/cut-v2/`)
4. Runs `verify.sh --fix` to repair trivial drift

### Preserved (never overwritten)

| Path | Contents |
|------|----------|
| `.claude/agents/specialists/*` | User-owned specialist agents |
| `docs/tasks/registry.json` | Task registry state |
| `docs/epics/**` | Epic and task body files |
| `docs/project-memory/**` | Compiled project knowledge |
| `daily/**` | Per-user conversation digests |
| `.claude/knowledge/**` | Project knowledge (if present) |
| `.claude/worktrees/**` | Worktree state (if present) |
| Project-specific MCP servers under `.claude/mcp-servers/` | Not replaced by framework refresh |

### Replaced (framework-owned)

| Path | Notes |
|------|-------|
| `.claude/agents/*.md` (5 framework agents) | Thinned v3 versions |
| `.claude/skills/**` | v3 skill bodies with deterministic wiring |
| `.claude/hooks/**` | Session, memory, consistency, validators |
| `.claude/reference/**` | Tier 1+2 templates (populated copies stay in project) |
| `.claude/rules/**` | Framework rules (`.local.md` sidecars preserved) |
| Root `CLAUDE.md` import | `install.sh` ensures `@.claude/CLAUDE.md` import exists |

## Step 2 — Verify the install

```bash
cd /path/to/your-project
bash .claude/scripts/install/verify.sh
python3 .claude/scripts/forge/forge.py doctor
python3 .claude/scripts/forge/forge.py task ls
```

Expected: verify reports no blocking drift; `task ls` shows your existing registry entries.

## Step 3 — Run `/migrate` (optional)

If you had a pre-v2 `.claude/` backed up to `.claude_old/` or need brownfield analysis:

```
/migrate
/migrate --skip-analysis    # merge only, no /new-project --current pass
/migrate --dry-run          # preview without changes
```

The `/migrate` skill merges content from `.claude_old/` (framework files refreshed; user content — specialists, registry, project-memory, `rules/*.local.md` — preserved):

- **Preserve** — registry, epics, PRD, databases
- **Append** — session history, progress notes
- **Replace** — framework files with v3 versions
- **Ask** — unknown files prompt for a decision

See [skills/migrate/SKILL.md](skills/migrate/SKILL.md) for the full checkpoint flow.

## Step 4 — Reconcile drift (if needed)

After migration, two reconcile commands help recover from v2 → v3 schema gaps:

```bash
# Registry entries missing body files on disk → creates STUB bodies
python3 .claude/scripts/forge/forge.py task reconcile-files --apply

# Orphan task files on disk missing registry entries → seeds registry
python3 .claude/scripts/forge/forge.py task reconcile-from-files
```

The consistency-banner hook (PostToolUse on Write/Edit) auto-fixes eight drift classes during normal work.

## Common post-migration fixes

### Specialists in the wrong location

v2 sometimes placed project specialists at `.claude/agents/*.md` instead of `.claude/agents/specialists/`. Move them:

```bash
mv .claude/agents/my-specialist.md .claude/agents/specialists/
```

### Registry timestamp monotonicity

Pre-v3 registries may have `completedAt` earlier than `createdAt` on some tasks. Fix manually in `docs/tasks/registry.json` or use `forge task` commands — never hand-edit without understanding the schema.

### Cross-repo config removed

v3 removes `.claude/cross-repo/` in favor of portable `EXPERT.md` artifacts. Re-vendor external project knowledge as specialist exports if needed:

```bash
python3 .claude/scripts/forge/forge.py specialist add my-expert --domain "..."
```

### Root CLAUDE.md import

Ensure your project root `CLAUDE.md` contains:

```markdown
@.claude/CLAUDE.md
```

`install.sh` creates or amends this on every install.

## Rollback

If refresh-v3 causes problems:

```bash
# Restore from the timestamped backup
cp -a /path/to/your-project/.claude/backups/<timestamp>/. /path/to/your-project/.claude/
```

For cut-v2 removals specifically, files are under `.claude/backups/<timestamp>/cut-v2/`.

## Windows

```powershell
.\scripts\install\install.ps1 -Mode refresh-v3 -Yes C:\path\to\your-project
```

Mirrors `install.sh` behavior.

## Further reading

- [RELEASES.md](RELEASES.md) — v3.0.0 architecture changes and phase history
- [docs/USER-GUIDE.md](docs/USER-GUIDE.md) — first project walkthrough on v3
- [CHEATSHEET.md](CHEATSHEET.md) — daily command reference
- [MEMORY-SCHEMA.md](MEMORY-SCHEMA.md) — memory pipeline after upgrade

---

*Last updated: 2026-06-21*
