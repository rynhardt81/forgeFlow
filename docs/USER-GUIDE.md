# Forge Flow User Guide

> Install Forge Flow into your project and ship your first feature in about 30 minutes.

After this guide you will have Forge Flow installed, a task in the registry with an ISA, and know how to use the core skills and dashboard.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| [Claude Code](https://claude.ai) | The framework runs inside Claude Code sessions |
| Python 3.10+ | Forge CLI, hooks, and tests |
| git | Clone and version control |
| rsync | Used by `install.sh` (macOS/Linux; Windows uses `install.ps1`) |
| Optional: `gh` CLI | For `/create-pr` and `/diagnose-ci` |

**Time:** ~30 minutes for sections 1–4; the rest is reference.

---

## 1. Install

### New project

```bash
mkdir my-app && cd my-app
git init
git clone https://github.com/rynhardt81/forgeFlow.git .claude
rm -rf .claude/.git
claude
```

In Claude Code:

```
/new-project "My awesome app"
```

This scaffolds PRD, ADRs, 4-tier reference docs, tasks, and registry entries.

### Existing project

```bash
cd /path/to/existing-project
git clone https://github.com/rynhardt81/forgeFlow.git .claude
rm -rf .claude/.git
claude
```

In Claude Code:

```
/new-project --current
```

Or use the installer from a framework clone:

```bash
/path/to/forgeFlow/scripts/install/install.sh /path/to/existing-project
```

### Install modes

Running `install.sh` with no `--mode` opens an interactive menu: **fresh install** (or **full reinstall** if `.claude/` already exists — backs up to `.claude_old/` first), **refresh framework files** (in-place update, preserves user content), or **quit**.

| `--mode` value | When to use |
|------|-------------|
| `full` | Fresh install, or full overwrite with backup |
| `refresh` | Re-copy framework files in-place, preserve user content |
| `refresh-v3` | Upgrade v3 → Forge Flow v4 — see [MIGRATION-GUIDE.md](../MIGRATION-GUIDE.md) |

```bash
./scripts/install/install.sh --mode refresh-v3 --yes /path/to/project
```

### Verify

```bash
python3 .claude/scripts/forge/forge.py --help
python3 .claude/scripts/forge/forge.py doctor
bash .claude/scripts/install/verify.sh
```

You'll know install succeeded when `forge --help` lists subcommands and `verify.sh` reports no blocking issues.

### Two roots

Forge Flow separates **framework code** from **project data**:

| Root | Path | Contains |
|------|------|----------|
| Framework | `.claude/` | Skills, hooks, agents, scripts, reference templates |
| Project | Parent of `.claude/` | `docs/tasks/`, `docs/project-memory/`, `ISA.md`, `daily/` |

Never write project data under `.claude/`. See [rules/framework-vs-project-root.md](../rules/framework-vs-project-root.md).

---

## 2. Mental model

### Modes

**Native mode is the default.** Claude replies directly, uses tools, and keeps a tight intent → change → verify loop — most work (questions, single-domain edits, routine task execution) lives here, with no phase banners or ceremony.

**Algorithm mode** fires only on explicit signals: nontrivial debugging (reproduce-first), a multi-file feature or refactor where planning has real value, schema/auth/money-path changes, architectural/doctrine work, or the user asking for rigor / setting `/e3`–`/e4`. When in doubt, stay Native and escalate mid-task if the work reveals multi-file/multi-risk shape — escalation is cheap, ceremony on a simple task is pure cost.

When Algorithm mode fires, Claude follows seven phases: **OBSERVE → THINK → PLAN → BUILD → EXECUTE → VERIFY → LEARN**, reading `.claude/ALGORITHM/LATEST` and following it through.

At higher effort tiers (E3/E4) the Algorithm offers three optional, skippable steps that never fire on trivial work:
- **Idea-vetting** (`/vet-idea`) at OBSERVE — vet *whether* an idea is worth building before scaffolding; a NO-GO halts the run.
- **Design Interview** (ISA `Interview` workflow) at OBSERVE — a dependency-ordered design interview that resolves design decisions before the ISCs freeze.
- **Assumption stress-test** in THINK — pressure the riskiest assumptions (make measurable → counter-evidence → survival check → hedge).

There are no ISC floors, no time budgets, and no mandatory output ceremony (no emoji phase banners, no fixed final-summary format) — criterion count and phase depth are judgment, gated by the splitting test and quality gates, not a quota.

Full doctrine: [.claude/ALGORITHM/v1.2.0.md](../ALGORITHM/v1.2.0.md) (also `.claude/ALGORITHM/LATEST`)

### ISA (Ideal State Articulation)

An ISA describes what *done* looks like — testable criteria (ISCs), constraints, and a verification trail.

| ISA type | Location |
|----------|----------|
| Project-level | `ISA.md` at project root |
| Task-level | `docs/tasks/<id>/ISA.md` (created with `forge task add --isa`) |

Full spec: [skills/ISA/SKILL.md](../skills/ISA/SKILL.md)

### Tasks and the forge CLI

- **Registry** (`docs/tasks/registry.json`) — atomic task state (status, deps, scope)
- **Body files** (`docs/epics/.../tasks/<id>-<slug>.md`) — task detail and notes
- **Consistency banner** — hook that auto-fixes drift between registry and files

Epics must exist before tasks are filed under them — `task add` raises `EpicNotFound` otherwise.

```bash
python3 .claude/scripts/forge/forge.py epic add E01 --name "CLI foundations"
python3 .claude/scripts/forge/forge.py task add T001 --epic E01 --name "Add CLI parser" --isa
python3 .claude/scripts/forge/forge.py task lock T001 --session my-session
python3 .claude/scripts/forge/forge.py task ls --ready
python3 .claude/scripts/forge/forge.py task pr T001
python3 .claude/scripts/forge/forge.py task complete T001
```

### Skills

Invoke with `/skill-name` inside Claude Code — workflow primitives like `/new-feature`, `/fix-bug`, `/create-pr`.

### Agents

Five framework agents (architect, project-manager, quality-engineer, security-boss, devops) fire automatically on high-value flows. User-owned **specialists** live in `.claude/agents/specialists/` and survive framework refresh.

### Dashboard

Read-only local cockpit — all artifacts in one browser UI:

```bash
python3 .claude/scripts/forge/forge.py dashboard
# → http://127.0.0.1:4847/
```

Details: [scripts/forge/dashboard/README.md](../scripts/forge/dashboard/README.md)

---

## 3. First feature walkthrough

Example: add a word-frequency counter to a new CLI project.

### 3.1 Scaffold the project

```
/new-project "CLI word frequency counter"
```

Review generated artifacts:

- `docs/prd.md` — requirements
- `.claude/reference/01-09.md` — populated source-of-truth docs
- `docs/tasks/registry.json` — initial task backlog

### 3.2 Add a feature

```
/new-feature "Word frequency command with file and stdin input"
```

This creates a registry entry, body file, and ISA at `docs/tasks/<id>/ISA.md`.

### 3.3 Implement

```
/reflect resume T001
```

Work through the ISA criteria. The Algorithm phases scaffold verification as you go.

### 3.4 Open a PR

```
/create-pr
```

Runs the Step 3.7 `pr-review-toolkit` specialist pre-flight before push, then offers a review-feedback loop (`/create-pr review`) and merge-order planning (`/create-pr merge-order`) for multi-PR days.

You'll know this worked when the PR is open, ISCs are checked off in the task ISA, and `forge task show T001` shows `pr_pending` or `completed`.

---

## 4. Minimal task (existing project)

Skip `/new-project` if you already have a codebase. The epic must exist first — create it with `epic add` before filing the task:

```bash
python3 .claude/scripts/forge/forge.py epic add E03 --name "Parser fixes"
python3 .claude/scripts/forge/forge.py task add T042 \
  --epic E03 --name "Fix null handling in parser" --isa \
  --scope-files src/parser.py
python3 .claude/scripts/forge/forge.py task lock T042 --session $(date +%s)
```

Edit `docs/tasks/T042/ISA.md` and the body file, implement, then:

```bash
python3 .claude/scripts/forge/forge.py task pr T042
# or
python3 .claude/scripts/forge/forge.py task complete T042
```

---

## 5. Core skills reference

24 skills total (23 slash-invocable plus the ISA skill, which workflows invoke); canonical roster is `skills/skills-manifest.json`, human index `skills/README.md`.

| Skill | When to use |
|-------|-------------|
| `/new-project` | Initialize PRD, ADRs, tasks, 4-tier docs |
| `/new-feature` | Add feature with ISA scaffold at E3+ |
| `/fix-bug` | Reproduce → root cause → fix → regression test → verify |
| `/triage-incident` | Production incident → stabilize → reproduce → fix → verify in prod → postmortem |
| `/run-epic E##` | Autonomously work through an epic — caps, 3-failure halt, PR per task |
| `/refactor` | Risk-scaled refactor with behavior verification |
| `/create-pr` | PR with pre-flight review gate + review-feedback loop + merge-order |
| `/diagnose-ci` | Debug failed GitHub Actions locally |
| `/preflight-ci` | Mirror CI locally before push |
| `/release` | Version bump, changelog, tag + release-safety checklist |
| `/build` | Stack-aware production build routing (EAS/Vercel/Supabase/Docker) |
| `/reflect resume` | Resume task with full context |
| `/reflect handoff` | Read-only cold-start brief for a fresh session |
| `/vet-idea "idea"` | Vet an idea *before* building → GO/NO-GO/RECONSIDER verdict |
| `/security-review` | Business-logic security pass (IDOR, race, state bypass) + secrets scan |
| `/migrate` | Onboard an existing project or upgrade framework version |
| `/remember` | Manual knowledge capture → `docs/project-memory/` |
| `/refresh-project-context` | Sync CLAUDE.md + project docs with reality |
| `/damage-control` | Install/configure defense-in-depth blocking security hooks |
| `/audit-code-map` | (Re)generate `docs/code-map.md` + JSON for the MCP server |
| `/audit-rules` | Advisory audit of rules and CLAUDE.md for staleness/contradiction |
| `/audit-task-status` | Align task/epic statuses with the registry (registry is truth) |
| `/frontend-design` | Design direction (defers to native plugin when installed) |
| `/ui-ux-pro-max` | Searchable local design DB — styles, palettes, fonts |

Full command index: [CHEATSHEET.md](../CHEATSHEET.md)

---

## 6. Dashboard tour

Seven tabs at `http://127.0.0.1:4847/`:

| Tab | Shows |
|-----|-------|
| **Tasks** | Kanban by epic and status |
| **Code Map** | Module graph and DRY hotspots |
| **ISAs** | Task ideal-state docs with verification trails |
| **Memory** | Compiled project knowledge |
| **Daily** | Recent conversation digests |
| **Registry** | Raw `registry.json` tree |
| **Burndown** | Completions over time from git history |

The dashboard is **read-only** — mutate state only through `forge task ...` or skills.

Flags: `--port`, `--host`, `--no-open`, `--once`.

---

## 7. Specialists

Build project-specific expertise that survives framework refresh:

```bash
python3 .claude/scripts/forge/forge.py specialist add payments-expert \
  --domain "Stripe integration, webhook idempotency, PCI boundaries"
```

Creates:

- `.claude/agents/specialists/payments-expert.md`
- `docs/EXPERT.md` (portable artifact for sibling projects)

Specialists are never overwritten by `install.sh --mode refresh-v3`.

---

## 8. Common workflows

### Fix a bug

```
/fix-bug "Login fails when email contains plus sign"
```

Follows reproduce → root-cause → fix → verify. Fires `@quality-engineer` and `@security-boss` where appropriate.

### Ship a feature

```
/new-feature "Export CSV from dashboard"
/reflect resume T###
/create-pr
```

### Refactor safely

```
/refactor
```

Choose scope; Structural mode runs undefined-name checks on Python projects.

---

## 9. Production lifecycle

Forge Flow's lifecycle doesn't end at the merge. For work in production:

- **`/triage-incident`** — production incident workflow: assess (Sentry/logs) → stabilize → reproduce → fix via `/fix-bug`'s prod fast path → verify in prod → postmortem + prevention tasks filed back to the registry.
- **Domain rules** (`.claude/rules/`, read on-demand, not auto-loaded): `migrations.md` gates any schema/DDL/model change (Algorithm Gate E — backup verified, paired rollback, expand/contract shape); `release-engineering.md` covers rollback mechanics, staged rollout, and feature-flag inventory before anything ships; `privacy.md` covers POPIA/GDPR — data inventory, lawful basis, and children's/health data handling for any work touching personal data.
- **Dependency hygiene templates**: `templates/renovate.json` and `templates/dependency-scan.yml` — drop into a project for automated dependency updates and CVE surveillance.

---

## 10. Troubleshooting

| Symptom | Fix |
|---------|-----|
| Not sure what state the install is in | Run `forge doctor` — reports installed version, retired paths still on disk, registry consistency, and hook wiring (read-only; `--all DIR` sweeps every install under a directory) |
| Consistency banner reports drift | Run `forge task ls`; read banner summary; use `task reconcile-files --apply` or `task reconcile-from-files` |
| Dashboard `/tasks` empty | Confirm `docs/tasks/registry.json` exists at **project root**, not under `.claude/` |
| Hook errors at SessionStart | Re-run `verify.sh --fix`; check `.claude/settings.json` hook paths |
| Tests fail after refresh | Expected if you modified framework skills locally — diff against backup in `.claude/backups/` |
| `forge task lock` conflict | Another session holds overlapping scope — `/reflect status` to see locks |

Migration issues: [MIGRATION-GUIDE.md](../MIGRATION-GUIDE.md)

---

## 11. Going deeper

| Topic | Document |
|-------|----------|
| Quick reference | [CHEATSHEET.md](../CHEATSHEET.md) |
| Runtime doctrine | [CLAUDE.md](../CLAUDE.md) |
| Algorithm doctrine | `.claude/ALGORITHM/v1.2.0.md` (also `.claude/ALGORITHM/LATEST`) |
| Version history | [RELEASES.md](../RELEASES.md) |
| Memory pipeline | [MEMORY-SCHEMA.md](../MEMORY-SCHEMA.md) |
| Contributing | [CONTRIBUTING.md](../CONTRIBUTING.md) |
| Framework ISA (meta) | [ISA.md](../ISA.md) |
| Hook internals | [hooks/README.md](../hooks/README.md) |
| Dashboard internals | [scripts/forge/dashboard/README.md](../scripts/forge/dashboard/README.md) |
| Skill bodies | `skills/<name>/SKILL.md` |
| Project source-of-truth | `.claude/reference/01-09.md` (populated at setup) |

---

*Last updated: 2026-07-09*
