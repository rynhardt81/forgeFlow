# Forge Flow Cheatsheet

> **v4.1.0** | Daily-use reference. For the entry point, see [CLAUDE.md](CLAUDE.md). New users: start with [docs/USER-GUIDE.md](docs/USER-GUIDE.md).

---

## Install

```bash
git clone https://github.com/rynhardt81/forgeFlow.git .claude && rm -rf .claude/.git && claude
```

Then: `/new-project "idea"` (new) or `/new-project --current` (existing codebase).

Upgrade/refresh: `./scripts/install/install.sh --mode refresh-framework /path/to/project` (or `refresh-v3` for a v3→v4 upgrade — see [MIGRATION-GUIDE.md](MIGRATION-GUIDE.md)).

---

## Modes

**Native is the default** — reply directly, tight intent → change → verify loop. **Algorithm mode** (`.claude/ALGORITHM/LATEST`) fires only on explicit signals: nontrivial debugging, multi-file feature/refactor, schema/auth/money-path changes, architectural work, or the user asking for rigor / setting `/e3`–`/e4`. No banners, no floors — stay Native until the work reveals multi-file/multi-risk shape.

---

## Daily spine

```bash
/reflect status              # task/epic overview
/reflect resume T###         # resume a task with full context
/reflect handoff             # read-only cold-start brief for a fresh session
/reflect unlock T###         # release a stale lock
```

```bash
/create-pr                   # pre-flight review gate → push
/create-pr review            # review-feedback triage loop on an open PR
/create-pr merge-order        # merge-order plan for multiple open PRs
```

```bash
/run-epic E##                 # drain one epic autonomously — caps, 3-failure halt, PR per task
/run-epic E## --dry-run       # preview without executing
/run-epic E## --resume        # continue a halted run
```

---

## Forge CLI (task lifecycle)

The forge CLI is the only sanctioned mutation path for task state. Never hand-edit `docs/tasks/registry.json` — the consistency-banner hook auto-fixes drift on every write and at SessionStart.

```bash
python3 .claude/scripts/forge/forge.py epic add E0X --name "..." \
  [--description "..."] [--deps E0Y] [--priority p] [--category C] [--status pending]
python3 .claude/scripts/forge/forge.py task add T### --epic E0X --name "..." \
  [--isa] [--deps T###,T###] [--scope-dirs path/] [--scope-files f1,f2] [--priority p] [--preflight]
  # the epic must exist first (else EpicNotFound); --allow-missing-epic overrides for imports/fixtures
python3 .claude/scripts/forge/forge.py task lock T### --session <id>   # file-scope conflicts fail here
python3 .claude/scripts/forge/forge.py task pr T###
python3 .claude/scripts/forge/forge.py task complete T###
python3 .claude/scripts/forge/forge.py task ls --ready
python3 .claude/scripts/forge/forge.py task show T###
python3 .claude/scripts/forge/forge.py task reconcile-files [--apply]
python3 .claude/scripts/forge/forge.py version                         # installed framework version
python3 .claude/scripts/forge/forge.py doctor [--json] [--all DIR]     # install health: version, retired paths, registry, hook wiring
```

States: `pending → ready → in_progress → pr_pending → completed`.

```bash
# Specialists (per-project domain experts, never touched by refresh)
python3 .claude/scripts/forge/forge.py specialist add <name> --domain "..."

# Dashboard
python3 .claude/scripts/forge/forge.py dashboard              # http://127.0.0.1:4847/
```

---

## Lifecycle skills (all 24)

| Skill | Purpose |
|-------|---------|
| `/reflect` | Session continuity — resume, status, handoff, unlock |
| `/create-pr` | PR with pre-flight review gate + review-feedback loop + merge-order |
| `/run-epic E##` | Drain one epic autonomously — caps, 3-failure halt, PR per task |
| `/fix-bug` | Reproduce → root-cause → fix → regression test → verify |
| `/triage-incident` | Production incident → stabilize → fix → verify in prod → postmortem |
| `/new-feature` | Scoped feature flow, ISA at E3+, ships via `/create-pr` |
| `/new-project` | Initialize project — PRD, ADRs, tasks, populated reference docs |
| `/migrate` | Onboard existing project / upgrade framework version |
| `/refactor` | Risk-scaled refactoring, behavior verified |
| `/release` | Version + changelog + tag + release-safety checklist |
| `/build` | Stack-aware build routing (EAS/Vercel/Supabase/Docker) |
| `/preflight-ci` | Mirror GitHub Actions locally before push; pre-push hook |
| `/diagnose-ci` | Diagnose failed Actions runs locally — no blind retry-pushing |
| `/vet-idea` | GO / NO-GO / RECONSIDER council verdict BEFORE building |
| ISA (skill) | Ideal-state criteria + verification trail (Scaffold, CheckCompleteness, Interview) |
| `/security-review` | Business-logic security pass (IDOR, race, state bypass) + secrets scan |
| `/audit-rules` | Advisory audit of CLAUDE.md + rules for staleness/contradiction |
| `/audit-task-status` | Reconcile statuses against the registry (registry is truth) |
| `/audit-code-map` | (Re)generate `docs/code-map.md` + JSON for the MCP server |
| `/remember` | Manual knowledge capture → `docs/project-memory/` |
| `/refresh-project-context` | Sync CLAUDE.md + project docs with reality |
| `/frontend-design` | Design direction (defers to native plugin when installed) |
| `/ui-ux-pro-max` | Searchable local design DB — styles, palettes, fonts |
| `/damage-control` | Install defense-in-depth blocking security hooks |
| `forge dashboard` | Local cockpit at `http://127.0.0.1:4847/` (`forge` = `python3 .claude/scripts/forge/forge.py` — alias it) |

Canonical roster: `skills/skills-manifest.json` (24 skills). Human index: `skills/README.md`.

---

## Effort tiers

| Tier | Scope | ISA |
|------|-------|-----|
| E1 | Trivial, fast-path | none |
| E2 | Single-domain substantial | inline criteria checklist |
| E3 | Multi-file, planned | ISA document |
| E4 | Architectural, cross-cutting | ISA document |

Override: `/e1`–`/e4`. No time budgets, no ISC floors — criterion count is judgment, gated by the splitting test and quality gates (nameable probe, every deliverable mapped, ≥1 `Anti:` criterion).

---

## Rules (on-demand, in `.claude/rules/`)

Active directives read when relevant — not auto-loaded at session start. Domain gates pull them in:

| Rule | Gate |
|------|------|
| `migrations.md` | Schema/DDL/model changes in scope — Algorithm Gate E |
| `release-engineering.md` | Shipping to users — feature flags, staged rollout, rollback |
| `privacy.md` | Personal data (incl. children's/health data) — POPIA/GDPR |
| `security.md`, `coding-style.md`, `patterns.md`, `dependencies.md`, `git-workflow.md`, `testing.md`, `error-handling.md`, `observability.md`, `framework-vs-project-root.md` | General discipline, read as relevant |

Project-specific content goes in sidecar `rules/<name>.local.md` files — framework refresh overwrites the framework rule, never the sidecar.

---

## Agents

| Agent | Specialization | Bound validator |
|-------|----------------|-----------------|
| `@architect` | System design, ADRs, tech-stack | `architect_adr.py` |
| `@project-manager` | Requirements, scope, PRDs | — |
| `@quality-engineer` | Test strategy, code review | `quality_coverage.py`, `tdd_aaa.py` |
| `@security-boss` | Auth, secrets, security review | `security_secrets.py` |
| `@devops` | CI/CD, deployment, infra | `build_deps.py` |

Specialists (project-owned, never touched by refresh): `python3 .claude/scripts/forge/forge.py specialist add <name> --domain "..."`.

---

## Dashboard (`forge dashboard`)

Read-only cockpit at `http://127.0.0.1:4847/`; mutation flows only through the forge CLI.

| Tab | Source |
|-----|--------|
| Tasks | `docs/tasks/registry.json` (kanban) |
| Code Map | `docs/code-map.json` (graph) |
| ISAs | `docs/tasks/<id>/ISA.md` |
| Memory | `docs/project-memory/{bugs,decisions,patterns,key-facts,index}.md` |
| Daily | `daily/YYYY-MM-DD.md` (seven newest) |
| Registry | Raw `docs/tasks/registry.json` tree |
| Burndown | `git log` + registry history → completions SVG |

Flags: `--host`, `--port`, `--no-open`, `--once` (CI/snapshot). SSE live-reload; zero external deps.

---

## Documentation governance (4-tier)

| Tier | Files | Role |
|------|-------|------|
| 1 — Governance | `reference/00` | Rules for how docs work |
| 2 — Source-of-truth | `reference/01-09` | What the system IS |
| 3 — Processed | `docs/processed/` | Background/evidence |
| 4 — Execution | `CLAUDE.md`, `.claude/*` | Guides execution; does not define truth |

Tier 2 wins conflicts with ISA constraints until reconciled via ADR.

---

## Commit format

```
type(scope): description

Task: T###
Co-Authored-By: Claude <noreply@anthropic.com>
```

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `archive`.

---

## Tests

```bash
python3 -m pytest .claude/tests/ -v      # whole suite (forge, wiring, dashboard, etc. — read-only static analysis)
```

---

*Main entry point: [CLAUDE.md](CLAUDE.md) | Project ISA: [ISA.md](ISA.md) | v3 archive: git tag `v3.2.0`*
