# Forge Flow

> Claude Forge v4 — project-portable framework for AI-assisted software development. Deterministic primitives (task-state CLI, ISA verification trail, CI preflight) + documentation governance + focused agents. Installs into any project; works identically on personal and work machines, with no dependency on globally-installed plugins.

## Three kinds of documents

| Kind | Where | Time horizon | Purpose |
|------|-------|--------------|---------|
| **Operational scaffolds** | `templates/` (session.md, task.md, CLAUDE.template.md) | Per-session / per-task | Define runtime behavior of the project's Claude integration |
| **Source-of-truth docs** | `.claude/reference/01-09.md` (populated at setup) + Tier 1 governance at `00` | Per-project, long-lived | What the project IS — architecture, security, NFRs, ADRs |
| **Ideal-state articulation** | `<project>/ISA.md` + `docs/tasks/<id>/ISA.md` | Per-project / per-task | What the project SHOULD BE — testable criteria + verification trail |

Decision rule: architecture decision → `reference/06`; tech-stack constraint → `reference/02`; test strategy for a feature → ISA Test Strategy; acceptance criteria → ISA Criteria; "when skill X runs do Y" → operational scaffold.

## Modes

**Native is the default.** Reply directly, use tools, keep the loop tight: intent → change → verify. Most work — questions, single-domain edits, routine task execution — lives here.

**Algorithm mode** (read `.claude/ALGORITHM/LATEST` and follow it through all phases) fires on explicit signals only:

- Debugging with a nontrivial reproduction (Gate A work)
- Multi-file feature or refactor where planning has real value
- Schema, auth, or money-path changes (Gates apply)
- Architectural/doctrine work
- The user asks for rigor or sets `/e3`–`/e4`

When in doubt, stay Native and escalate the moment the work reveals multi-file/multi-risk shape — escalation mid-task is cheap; ceremony on a simple task is pure cost.

**Effort tiers** (user-overridable with `/e1`–`/e4`):

| Tier | Scope | ISA |
|------|-------|-----|
| E1 | Trivial | none |
| E2 | Single-domain substantial | inline criteria checklist |
| E3 | Multi-file, planned | ISA document |
| E4 | Architectural, cross-cutting | ISA document |

## ISA — Ideal State Articulation

The verification trail. Project ISA at `<project>/ISA.md`; task ISA at `docs/tasks/<id>/ISA.md` (created by `forge task add --isa`). ISCs are atomic (one nameable tool probe each), ≥1 `Anti:` criterion required, `[x]` requires evidence in `## Verification` — never "tests pass". Workflows: Scaffold, CheckCompleteness, Interview (`.claude/skills/ISA/`). Criterion count is judgment — there are no floors.

## Skills

Invoke via `/<skill-name>`. Canonical roster: `skills/skills-manifest.json`; human index: `skills/README.md`.

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
| `/release` | Version + changelog + tag + release-safety checklist (rollback verified, staged rollout, flag inventory) |
| `/build` | Stack-aware build routing (EAS/Vercel/Supabase/Docker) |
| `/preflight-ci` | Mirror GitHub Actions locally before push; pre-push hook |
| `/diagnose-ci` | Diagnose failed Actions runs locally — no blind retry-pushing |
| `/vet-idea` | GO / NO-GO / RECONSIDER council verdict BEFORE building |
| `/security-review` | Business-logic security pass (IDOR, race, state bypass) + secrets scan |
| `/audit-rules` | Advisory audit of CLAUDE.md + rules for staleness/contradiction |
| `/audit-task-status` | Reconcile statuses against the registry (registry is truth) |
| `/audit-code-map` | (Re)generate `docs/code-map.md` + JSON for the MCP server |
| `/remember` | Manual knowledge capture → `docs/project-memory/` |
| `/refresh-project-context` | Sync CLAUDE.md + project docs with reality |
| `/frontend-design` | Design direction (defers to native plugin when installed) |
| `/ui-ux-pro-max` | Searchable local design DB — styles, palettes, fonts |
| `/damage-control` | Install defense-in-depth blocking security hooks |
| `forge dashboard`* | Local cockpit at `http://127.0.0.1:4847/` — tasks, code map, ISAs, memory, registry, burndown (read-only; SSE live-reload). *`forge` = `python3 .claude/scripts/forge/forge.py` — alias it once per machine |

## Agents

Framework agents in `.claude/agents/` (replaced on refresh); specialists in `.claude/agents/specialists/` (user-owned, never touched). Each agent's frontmatter binds a PostToolUse validator whose advice arrives as `additionalContext` — read it. Agents accept `model:` frontmatter; per-task model routing for subagent dispatch (used by `/run-epic --parallel`) is defined in `skills/_shared/model-routing.md`.

| Agent | Specialization | Bound validator |
|-------|----------------|-----------------|
| `@architect` | System design, ADRs, tech-stack | `architect_adr.py` |
| `@project-manager` | Requirements, scope, PRDs | — |
| `@quality-engineer` | Test strategy, code review | `quality_coverage.py`, `tdd_aaa.py` |
| `@security-boss` | Auth, secrets, security review | `security_secrets.py` |
| `@devops` | CI/CD, deployment, infra | `build_deps.py` |

Scaffold specialists: `python3 .claude/scripts/forge/forge.py specialist add <name> --domain "..."` (paired `EXPERT.md` for vendoring into sibling projects).

## Project memory

Manual and intentional: `/remember bug|decision|pattern|fact "..."` writes to `docs/project-memory/`; the SessionStart hook injects `index.md` + `key-facts.md` back. Schema: `MEMORY-SCHEMA.md`. There is no automatic transcript capture, and **no hook ever spawns an LLM subprocess**.

## Task lifecycle

Atomic state via `python3 .claude/scripts/forge/forge.py`:

- `epic add E0X --name "..."` (+`--description`, `--deps`, `--priority`, `--category`, `--status`) — create the epic (registry entry + `docs/epics/<id>-<slug>/` dir + body file) **before** filing tasks under it
- `task add T### --epic E0X --name "..."` (+`--isa`, `--deps`, `--scope-dirs`, `--scope-files`, `--priority`, `--preflight`) — the epic must already exist, else it raises `EpicNotFound` (override with `--allow-missing-epic` only for staged imports / fixtures)
- `task lock T### --session <id>` — file-scope conflicts fail here
- `task pr T###` / `task complete T###` / `task ls --ready` / `task show T###`
- `task reconcile-files [--apply]`

States: `pending → ready → in_progress → pr_pending → completed`. Never hand-edit `docs/tasks/registry.json` — create epics with `epic add` and tasks with `task add`; the consistency-banner hook auto-fixes drift on every write and at SessionStart.

## Documentation governance (4-tier)

| Tier | Files | Role |
|------|-------|------|
| 1 — Governance | `reference/00` | Rules for how docs work |
| 2 — Source-of-truth | `reference/01-09` | What the system IS (populated at setup) |
| 3 — Processed | `docs/processed/` | Background/evidence, referenced by Tier 2 |
| 4 — Execution | `CLAUDE.md`, `.claude/*` | Guides execution; does not define truth |

**Tier 2 wins** conflicts with ISA constraints until reconciled via ADR.

## Operational rules

- The forge CLI is the only sanctioned mutation path for task state.
- Custom specialists live in `.claude/agents/specialists/` to survive refresh.
- Framework-wired hooks are informational and never blocking, and no hook ever spawns an LLM subprocess. Blocking layers exist only as explicit opt-ins: `/damage-control` hooks and `consistency-banner --strict`.
- For UI/web verification use a real browser probe — never theorize from code.
- Rules in `.claude/rules/` are active directives read on-demand; treat as binding when encountered. Domain gates pull them in: schema work → `migrations.md`, shipping → `release-engineering.md`, personal data → `privacy.md`, **adding or updating any dependency → `dependencies.md`** (exact pins; refuse versions published in the last 7 days — supply-chain compromises are usually caught within that window; new dependencies require explicit justification before install).
- **Project-specific rule content goes in sidecar files** `rules/<name>.local.md` — refresh overwrites framework rules, never sidecars. Applies to: patterns, coding-style, dependencies, git-workflow, security, testing, error-handling, observability, migrations, release-engineering, privacy.
- `.claude/` is `framework_root` (CODE); the parent is `project_root` (DATA: docs/tasks, docs/epics, docs/project-memory, daily/, ISA.md). Never write project data under `.claude/`. Doctrine: `rules/framework-vs-project-root.md`.
- Framework rules load via a root `CLAUDE.md` containing `@.claude/CLAUDE.md` — `install.sh` creates or amends this import on every install/refresh.

## See also

- `.claude/ALGORITHM/v1.2.0.md` — full Algorithm doctrine (LATEST)
- `.claude/skills/ISA/SKILL.md` — ISA workflows
- `MEMORY-SCHEMA.md` — project-memory spec
- `MIGRATION-GUIDE.md` — version upgrade walkthrough
