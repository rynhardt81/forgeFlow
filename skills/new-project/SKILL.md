---
name: new-project
description: Initialize a new or existing project with Claude Forge — PRD, ADR seeds, populated reference docs (01-09), and a seeded task registry. Use when starting a project, bootstrapping project docs, or adding the framework to an existing codebase. NOT for adding a single feature (/new-feature) or upgrading framework versions (/migrate).
hooks:
  PostToolUse:
    - matcher: "Write"
      hooks:
        - type: command
          command: "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/validators/skills/new_project_prd.py"
---

## Quick Scan

| | |
|---|---|
| **Purpose** | Initialize Claude Forge: PRD, ADRs, populated reference docs, task registry |
| **Inputs** | Project description, or `--current` for an existing codebase |
| **Output** | `docs/prd.md`, ADRs in `reference/06`, reference docs 01-09, `docs/tasks/registry.json` + epics/tasks |
| **Flow** | Discovery → PRD → **confirm** → ADRs → reference docs → **confirm** → task seeding → summary |

---

# New Project Skill

## Purpose

Take a project from idea (or existing code) to a working Forge state: requirements captured in a PRD, architecture choices recorded as ADRs, the 4-tier reference docs populated, and the PRD's actual work seeded into the forge task registry so `/reflect resume T001` can start real work immediately.

There is exactly **one task system**: the forge registry (`docs/tasks/registry.json`) driven by `.claude/scripts/forge/forge.py`, drained per-epic by `/run-epic`. This skill seeds it; nothing else tracks features.

## Modes

```
/new-project "project description"    # Greenfield — interview the user, then build docs
/new-project --current                # Existing codebase — read the code FIRST, confirm findings, then build docs
```

**`--current` rule:** discovery starts by reading the codebase — dependency files (`package.json`, `pyproject.toml`, lockfiles), directory structure, existing commands (npm scripts, Makefile), existing docs and CI config — and presents detected findings (stack, project name, conventions, entry points) **for user confirmation before writing anything**. The PRD then reflects current state + planned enhancements, and reference docs are populated from what the code actually is, not what the user remembers it being.

## Confirmation Points (exactly two)

1. **After Discovery + PRD** — user reviews the PRD before architecture work builds on it.
2. **Before task seeding** — user reviews the proposed epic/task breakdown before the registry is written.

No other ceremony. No checkpoint banners between phases — just do the work and move on.

---

## Phase 1 — Setup (quick, mostly idempotent)

1. Verify the framework is installed (`.claude/` with `scripts/forge/forge.py` present). If not, stop and point at `install.sh` — installation is not this skill's job.
2. If the project `CLAUDE.md` is still placeholder text, populate it from `templates/CLAUDE.template.md` (project name, description, stack).
3. Ensure continuity structure exists: `.claude/memories/{sessions/active,sessions/completed}`, `progress-notes.md`, `general.md`; and `docs/project-memory/` (see `/remember` — `archive.db` is created on first use, not here).
4. `git init` + initial commit if not already a repo.

If `docs/prd.md` or a populated registry already exists, this is a re-run: report what exists, ask whether to resume from the first gap (e.g. PRD done, tasks not seeded) instead of starting over.

## Phase 2 — Discovery

Ask targeted questions. Greenfield: interview the user. `--current`: confirm what the code says; ask only what it can't answer.

- **What** — the problem, the outcome, the smallest version worth shipping
- **Who** — users/personas, and who is explicitly NOT a user
- **Stack** — languages, frameworks, database, hosting (`--current`: detected, present for confirmation)
- **Constraints** — deadlines, integrations, compliance, team conventions, budget for external services
- **Data sensitivity** — what data flows through this system, where it's stored, who can see it
- **Privacy** — ask verbatim: *"Does this handle personal data, children's data, or health data?"* → if yes, flag `rules/privacy.md` as an active directive for all subsequent work on this project and record the answer in the PRD's constraints.

Also capture explicit **non-goals** — the PRD's Out of Scope section is load-bearing; it is what keeps task seeding honest later.

Don't interrogate: 4-8 questions is the normal range. If the user's description already answers something, don't re-ask it.

## Phase 3 — PRD

Generate `docs/prd.md` from `templates/prd.md`.

- Keep the four `##` sections the validator requires: **Vision, Goals, User Stories, Success Criteria**. Alternative headers are accepted (Overview/Problem Statement; Objectives/Requirements; Users/Personas/Target Audience; Acceptance Criteria/Definition of Done/Metrics) — see `hooks/validators/skills/new_project_prd.py`. The validator fires on every Write while this skill is active and reports missing sections as `additionalContext`; read it.
- Fill Non-Goals / Out of Scope from Discovery. Record the privacy answer under constraints.
- `docs/prd.md` is a **Tier 2 master document** — downstream docs defer to it.

For substantial projects, delegate drafting via the Task tool; write it inline for small ones:

```
Use the Task tool:
- subagent_type: "project-manager"
- description: "Draft PRD from discovery"
- prompt: |
    Project: <name>   Mode: <new | --current>
    Discovery answers: <summarized>

    Draft docs/prd.md from templates/prd.md. Keep the validator's four
    sections (Vision, Goals, User Stories, Success Criteria). Include
    Non-Goals. Defer NFR detail to reference/07 once populated.
```

**CONFIRM #1:** present the PRD summary (goals, personas, story count, non-goals); user approves or amends before anything builds on it.

## Phase 4 — ADR Seeds

For each real stack/architecture choice the PRD implies, seed an ADR from `templates/adr-template.md` into `.claude/reference/06-architecture-decisions.md` (Nygard shape: Status / Context / Decision / Consequences / Alternatives).

Typical seeds — only where a decision is actually being made:

- Frontend framework / rendering approach
- Backend / API style (REST, GraphQL, tRPC, none)
- Database + data-modeling approach
- Authentication strategy
- Deployment target

An ADR with an empty Context is worse than no ADR — if the choice is genuinely open, record it as a `TODO(user)` in `reference/02` instead of fabricating a decision.

Delegation for multi-service or unfamiliar-stack projects:

```
Use the Task tool:
- subagent_type: "architect"
- description: "Seed ADRs from PRD"
- prompt: |
    Project: <name>. Read docs/prd.md first.
    Seed ADRs for the stack/architecture choices the PRD implies (Nygard
    format, templates/adr-template.md). Append to
    .claude/reference/06-architecture-decisions.md; update
    .claude/reference/02-architecture-and-tech-stack.md with the
    canonical stack. Seed only decisions actually being made.
```

**Security review (conditional):** if the project involves auth, payments, sensitive/personal data, or compliance requirements, have `@security-boss` review the auth/data ADRs — validate token/session strategy, define the threat model (assets / actors / vectors / mitigations) in `reference/08-security-model.md`, and update `reference/03-security-auth-and-access.md`. Unmitigated concerns get flagged to the user, not buried.

## Phase 5 — Populate Reference Docs (4-tier)

For each `reference/0N-*.template.md` (01-09):

1. Copy to the active name (drop `.template`), **then delete the `.template.md` original** — only active documents remain, so templates and content never get confused.
2. Populate from the PRD, ADRs, and (in `--current` mode) the codebase:

   | Doc | Populated from |
   |-----|----------------|
   | `01-system-overview` | PRD summary |
   | `02-architecture-and-tech-stack` | canonical stack from ADRs |
   | `03-security-auth-and-access` | auth decisions (+ security-boss input if invoked) |
   | `04-development-standards-and-structure` | conventions — detected from code in `--current` mode |
   | `05-operational-and-lifecycle` | deploy/runbook knowledge, as far as known |
   | `06-architecture-decisions` | already holds the ADR seeds from Phase 4 |
   | `07-non-functional-requirements` | PRD NFRs, made concrete where possible |
   | `08-security-model` | threat model if security-boss ran; skeleton + TODOs otherwise |
   | `09-autonomous-development` | `/run-epic` caps and halt rules for this project, if known |

3. **Honest TODO markers** where the user must decide: write `TODO(user): <the specific open question>` — never invent content to make a doc look finished. A visible gap is recoverable; fabricated "truth" in a Tier 2 doc poisons every later session, because Tier 2 wins conflicts.

## Phase 6 — Task Seeding

Break the PRD into epics (major feature areas, typically 2-5) and atomic tasks. **Seed the tasks the PRD actually implies — typically 10-30 for a real MVP. Quality over quota; there are no count floors.** Each task must be completable in a single session (context-window exhaustion is the failure mode); split anything bigger and wire the pieces with `--deps`.

**CONFIRM #2:** present the proposed breakdown BEFORE writing anything:

```markdown
## Proposed Tasks

| ID | Epic | Name | Deps | Scope |
|----|------|------|------|-------|
| T001 | E01 Auth | Set up auth scaffolding | — | src/auth/ |
| T002 | E01 Auth | Login + session flow | T001 | src/auth/, src/app/login/ |
| T003 | E02 Catalog | Product list + detail pages | — | src/app/products/ |
| ... |

[X] epics, [Y] tasks, [Z] immediately ready. Seed the registry?
```

User approves or edits. Then:

1. **Create the registry skeleton** — the forge CLI errors if `docs/tasks/registry.json` doesn't exist. Authoring the empty skeleton (settings only) is the one sanctioned hand-write; every epic and task entry after this goes through the forge CLI:

   ```json
   {
     "project": "[PROJECT_NAME]",
     "version": "1.0.0",
     "lastUpdated": "[UTC RFC3339]",
     "settings": {
       "lockTimeoutSeconds": 3600,
       "allowManualUnlock": true,
       "maxParallelAgents": 3,
       "autoAssignNext": true
     },
     "stats": {
       "epics": { "total": 0, "completed": 0, "in_progress": 0, "blocked": 0 },
       "tasks": { "total": 0, "completed": 0, "in_progress": 0, "continuation": 0, "ready": 0, "pending": 0 }
     },
     "epics": [],
     "tasks": []
   }
   ```

   (`stats` may be zeros — forge recomputes it on every mutation.)

2. **Create each epic via the forge CLI** — before its tasks; `forge task add` raises `EpicNotFound` for an epic that isn't in the registry:

   ```bash
   python3 .claude/scripts/forge/forge.py epic add E01 \
       --name "Authentication" --description "Login, session, RBAC" \
       --category A --priority 1
   python3 .claude/scripts/forge/forge.py epic add E02 \
       --name "Catalog" --deps E01 --category B
   ```

   One command creates the registry entry AND `docs/epics/E##-{slug}/` with its `tasks/` subdir and body file (`E##-{slug}.md`). Epic `--deps` express epic ordering (E02 depends on E01). After seeding, enrich each generated body — goal and in/out of scope under `## Summary`, the epic's task table under `## Tasks`. Edit body sections only; the frontmatter belongs to forge.

3. **Add each task via the forge CLI** — never hand-edit the registry for tasks:

   ```bash
   python3 .claude/scripts/forge/forge.py task add T001 --epic E01 \
       --name "Set up auth scaffolding" --category A --priority 1 \
       --scope-dirs src/auth/
   python3 .claude/scripts/forge/forge.py task add T002 --epic E01 \
       --name "Login + session flow" --deps T001 \
       --scope-dirs src/auth/,src/app/login/ --category A --isa
   ```

   - `forge task add` creates the task body file from `templates/task.md` at `docs/epics/E##-{slug}/tasks/T###-{slug}.md` by default — do NOT pass `--no-file` during seeding.
   - No `--deps` → task starts `ready`; with `--deps` → `pending` (auto-flips to `ready` as dependencies complete). Foundation and security tasks first; no circular dependencies — forge appends to the epic's `tasks[]` and recomputes stats for you.
   - `--scope-dirs`/`--scope-files` power lock-time conflict detection between parallel sessions — fill them honestly.
   - `--isa` scaffolds `docs/tasks/T###/ISA.md` — use it for E3+ tasks (multi-file, risk-bearing) where a verification trail earns its keep. Criterion count is judgment; there are no floors.
   - `--preflight` defaults to `auto` (CI preflight required iff scope touches non-doc paths) — leave it alone unless the task is odd.

4. **Fill in task bodies** — objective, requirements, acceptance criteria from the PRD breakdown. Edit the body only; the frontmatter `status:` belongs to forge.

5. **Verify before declaring done:**

   ```bash
   python3 .claude/scripts/forge/forge.py task ls          # every task present
   python3 .claude/scripts/forge/forge.py task ls --ready  # non-empty
   ```

   Every registry `file` path must exist on disk (`forge task reconcile-files` with no flag dry-runs the check).

**Category codes** (`--category`, used for priority ordering — security/data first, polish last; no per-category quotas):

> A Security/Auth · B Navigation · C Data/CRUD · D Workflows · E Error handling · F Forms/Validation · G Search/Filter · H Responsive/X-browser · I Performance · J Integrations · K Notifications · L Preferences/Settings · M Help/Docs · N Analytics · O Accessibility/i18n · P Payments · Q Admin/Moderation · R Collaboration · S Export/Reporting · T UI Polish

## Phase 7 — Optional Specialist Scaffold

If the project has a deep recurring domain (a specific WMS, a proprietary API, a design system), offer to scaffold a project specialist:

```bash
python3 .claude/scripts/forge/forge.py specialist add <name> --domain "..."
```

Specialists live in `.claude/agents/specialists/` (user-owned, survive framework refresh) with a paired `EXPERT.md` for vendoring into sibling projects. Skip silently if no domain warrants one.

## Phase 8 — Summary + Next Step

Present a compact summary and hand off:

```markdown
## Project Initialized

- PRD: docs/prd.md
- ADRs: .claude/reference/06-architecture-decisions.md ([N] seeded)
- Reference docs: 01-09 populated ([M] TODO(user) markers remain)
- Tasks: [Y] across [X] epics — [Z] ready

**Next:** /reflect resume T001
```

Commit everything (`docs/`, `.claude/reference/`, registry, epic/task files) with a clear message, e.g. `chore: initialize project — PRD, ADRs, reference docs, task registry`.

---

## Worked Example (greenfield)

```
User: /new-project "Invoice tracker for a small workshop — customers, invoices, payment status"

Phase 2 Discovery (5 questions):
  what's the smallest shippable version? who uses it (owner only, or staff)?
  stack preference? any accounting-system integration? personal data → yes
  (customer names/contacts) → rules/privacy.md flagged, recorded in PRD.

Phase 3 PRD → docs/prd.md
  Vision / Goals (G1 track invoices, G2 payment status at a glance) /
  User Stories (owner persona, 8 stories) / Success Criteria /
  Non-Goals: no multi-tenant, no e-invoicing compliance in v1.
CONFIRM #1 → user approves.

Phase 4 ADRs → reference/06
  ADR-001 Next.js app router · ADR-002 SQLite via Drizzle ·
  ADR-003 single-user session auth · ADR-004 deploy on VPS.
  security-boss skipped: auth is single-user, no payments processed —
  privacy.md still active for the customer-data handling.

Phase 5 reference docs 01-09 populated; 07 carries
  TODO(user): expected invoice volume/year — affects pagination + backup cadence.

Phase 6 seeding: 3 epics, 14 tasks proposed.
CONFIRM #2 → user drops 1 task (CSV import → backlog note in PRD), approves 13.
  Registry authored (E01 Foundation, E02 Invoicing, E03 Reporting) →
  epic dirs/files created → 13 × forge task add (T004 --isa: money-path
  status transitions) → task ls --ready shows T001-T003.

Phase 8: summary + "Next: /reflect resume T001" → committed.
```

## Error Recovery

- **PRD drafting stalls** (agent can't converge): save whatever analysis exists to `docs/prd.md` as a partial with `TODO(user)` markers, ask the user to fill the gaps, resume at Phase 4 once the validator passes.
- **User cancels mid-flow:** append current state to `.claude/memories/progress-notes.md` (which phases completed, which artifacts exist). Re-invoking `/new-project` later detects existing artifacts (Phase 1 re-run check) and offers to resume from the first gap.
- **Registry half-seeded** (interrupted during Phase 6): `forge task ls` shows what landed; add the missing tasks — `forge task add` rejects duplicate IDs, so re-running the remaining commands is safe.

## Key Rules

- **One task system.** The forge registry is the only tracker — no separate feature database, no parallel feature lists, no per-task TodoWrite mandates.
- **Two confirmations only:** after Discovery/PRD, and before task seeding.
- **Registry skeleton → epics → tasks, in that order:** `forge epic add` errors on a missing registry; `forge task add` errors (`EpicNotFound`) on a missing epic.
- **The empty registry skeleton is the one sanctioned hand-write.** Every epic and task entry mutates via the forge CLI only (`epic add` / `task add`).
- **Seed what the PRD implies** — typically 10-30 tasks for a real MVP; no numeric floors, no padding.
- **Honest TODOs:** `TODO(user): ...` where the user must decide; never fabricate Tier 2 content.
- **PRD keeps its four validator sections** (Vision, Goals, User Stories, Success Criteria).
- **Tier 2 wins:** once populated, reference docs 01-09 are source-of-truth; later conflicts get reconciled via ADR.

## Gotchas

- **Epics before tasks:** `forge epic add` creates the properly-slugged epic dir + body file atomically. Without it, `forge task add` fails with `EpicNotFound`; and if the registry entry exists but the dir was removed, task bodies get parked in an `E##-untitled/` fallback dir.
- **Never hand-set frontmatter `status:`** in task files — the consistency-banner hook treats the registry as truth and silently reverts frontmatter that disagrees with it.
- **Every registry task needs its file on disk** at the recorded `file` path — `/reflect resume E##` guards on this. `forge task add` creates it by default; if a gap sneaks in, `forge task reconcile-files --apply` creates stubs (works, but the user sees warning noise — do it right at seeding).
- **PRD validator fires on every Write** while this skill runs — it reports via `additionalContext`, not by blocking; read and act on it rather than ignoring the nudge.
- **`--current` mode confirms before writing.** Detected stack/conventions can be wrong (monorepos, vendored deps, abandoned configs); a wrong `02-architecture-and-tech-stack.md` misleads every later session.
- **Delete `.template.md` originals** after populating reference docs — leaving both breeds edits to the wrong file.
- **Windows:** hook commands use `python`, not `python3`.
- **Atomic tasks or bust:** a task that can't finish in one session ends as a `continuation` with degraded context — split at seeding time, wire with `--deps`.
- **Scope honesty pays later:** empty `--scope-dirs` means lock-time conflict detection has nothing to check — two parallel sessions can then collide on the same files with no warning.

## See Also

- `templates/prd.md`, `templates/adr-template.md`, `templates/task.md`, `templates/isa.md` (epic bodies come from `forge epic add`, not a template)
- `skills/reflect/SKILL.md` — resume/status/handoff on the seeded tasks
- `skills/run-epic/SKILL.md` — drain an epic autonomously
- `scripts/forge/forge.py` — task-state CLI (`task add|lock|complete|ls|show`, `specialist add`)
