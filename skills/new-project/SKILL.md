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

# New Project Skill

Take a project from idea (or existing code) to a working Forge state: PRD, ADRs, populated 4-tier reference docs, and the PRD's work seeded into the forge task registry (`docs/tasks/registry.json`, the **one task system**, drained by `/run-epic`) so `/reflect resume T001` can start immediately.

Flow: Setup → Discovery → PRD → **CONFIRM #1** → ADRs → reference docs → **CONFIRM #2** → task seeding → summary.

## Index

| File or section | Read when… |
|-----------------|------------|
| `DOCS.md` | Phases 2–5, 8 — discovery checklist, PRD/ADR Task-tool prompts, reference-doc source map, summary template |
| `SEEDING.md` | Phase 6 — proposed-tasks table, registry skeleton JSON, `epic add` / `task add` examples, category codes |
| `EXAMPLE.md` | Worked greenfield run; recovery (stalled PRD, cancel, half-seeded registry); gotchas |
| See Also (bottom) | Templates and neighbouring skills this one hands off to |

## Modes

```
/new-project "project description"    # Greenfield — interview the user, then build docs
/new-project --current                # Existing codebase — read the code FIRST, confirm findings, then build docs
```

**`--current` rule:** discovery starts by reading the codebase (dependency files, structure, commands, docs, CI config) and presents detected stack, name, conventions and entry points **for user confirmation before writing anything**. The PRD reflects current state + planned enhancements; reference docs describe what the code actually is.

## Confirmation Points (exactly two)

1. **After Discovery + PRD** — user reviews the PRD before architecture work builds on it.
2. **Before task seeding** — user reviews the proposed epic/task breakdown before the registry is written.

No other ceremony or checkpoint banners.

## Phase 1 — Setup (quick, mostly idempotent)

1. Verify the framework is installed (`.claude/` with `scripts/forge/forge.py` present). If not, stop and point at `install.sh` — installation is not this skill's job.
2. Placeholder `CLAUDE.md` → populate from `templates/CLAUDE.template.md`. Fill **Verifying your work** from commands the repo actually runs, each run once to record its healthy output line (quiet reporters). A command you could not run stays a bracketed placeholder, never guessed.
3. Ensure `.claude/memories/{sessions/active,sessions/completed}`, `progress-notes.md`, `general.md` and `docs/project-memory/` exist.
4. `git init` + initial commit if not already a repo.

Existing `docs/prd.md` or populated registry → re-run: report what exists, offer to resume from the first gap.

## Phase 2 — Discovery

Ask targeted questions. Greenfield: interview the user. `--current`: confirm what the code says; ask only what it can't answer.

Cover what, who (and who is NOT a user), stack, constraints and data sensitivity (checklist: DOCS.md), plus:

- **Privacy** — ask verbatim: *"Does this handle personal data, children's data, or health data?"* → if yes, flag `rules/privacy.md` as an active directive for all subsequent work on this project and record the answer in the PRD's constraints.

Capture explicit **non-goals** — Out of Scope keeps task seeding honest. 4-8 questions is normal; don't re-ask what's answered.

## Phase 3 — PRD

Generate `docs/prd.md` from `templates/prd.md`.

- Keep the four `##` sections the validator requires: **Vision, Goals, User Stories, Success Criteria** (alternative headers accepted — see `hooks/validators/skills/new_project_prd.py`). The validator fires on every Write while this skill is active and reports missing sections as `additionalContext`, not by blocking; read it and act on it.
- Fill Non-Goals / Out of Scope from Discovery. Record the privacy answer under constraints.
- `docs/prd.md` is a **Tier 2 master document** — downstream docs defer to it.

For substantial projects, delegate drafting to `project-manager` via the Task tool (prompt: DOCS.md); write it inline for small ones.

**CONFIRM #1:** present the PRD summary (goals, personas, story count, non-goals); user approves or amends before anything builds on it.

## Phase 4 — ADR Seeds

For each real stack/architecture choice the PRD implies, seed an ADR from `templates/adr-template.md` into `.claude/reference/06-architecture-decisions.md` (Nygard shape: Status / Context / Decision / Consequences / Alternatives). Seed only decisions actually being made (frontend, API style, database, auth, deploy target).

An ADR with an empty Context is worse than no ADR — if the choice is genuinely open, record it as a `TODO(user)` in `reference/02` instead of fabricating a decision. For multi-service or unfamiliar-stack projects, delegate to `architect` (prompt: DOCS.md).

**Security review (conditional):** if the project involves auth, payments, sensitive/personal data, or compliance requirements, have `@security-boss` review the auth/data ADRs — validate token/session strategy, define the threat model (assets / actors / vectors / mitigations) in `reference/08-security-model.md`, and update `reference/03-security-auth-and-access.md`. Unmitigated concerns get flagged to the user, not buried.

## Phase 5 — Populate Reference Docs (4-tier)

For each `reference/0N-*.template.md` (01-09):

1. Copy to the active name (drop `.template`), **then delete the `.template.md` original** — only active documents remain, so templates and content never get confused.
2. Populate from the PRD, ADRs, and (in `--current` mode) the codebase — per-doc sources in DOCS.md.
3. **Honest TODO markers** where the user must decide: write `TODO(user): <the specific open question>` — never invent content to make a doc look finished. A visible gap is recoverable; fabricated "truth" in a Tier 2 doc poisons every later session, because Tier 2 wins conflicts.

## Phase 6 — Task Seeding

Break the PRD into epics (typically 2-5) and atomic tasks. **Seed the tasks the PRD actually implies — typically 10-30 for a real MVP; no count floors.** Each task must fit one session; split anything bigger and wire the pieces with `--deps`.

**CONFIRM #2:** present the proposed breakdown (ID / Epic / Name / Deps / Scope table — SEEDING.md) BEFORE writing anything. User approves or edits. Then, in this order:

1. **Create the registry skeleton** — the forge CLI errors if `docs/tasks/registry.json` doesn't exist. Authoring the empty skeleton (settings only, JSON in SEEDING.md) is the one sanctioned hand-write.
2. **Create each epic via `forge epic add`** — before its tasks; `forge task add` raises `EpicNotFound` for an epic that isn't in the registry. Then enrich each generated body (`## Summary`, `## Tasks`); edit body sections only — the frontmatter belongs to forge.
3. **Add each task via `forge task add`** — never hand-edit the registry for tasks. Do NOT pass `--no-file`. Fill `--scope-dirs`/`--scope-files` honestly (they power lock-time conflict detection); `--isa` for E3+ tasks; no circular dependencies. Examples and flag notes: SEEDING.md.
4. **Fill in task bodies** — objective, requirements, acceptance criteria from the PRD breakdown. Edit the body only; never hand-set frontmatter `status:` (the consistency-banner hook reverts it to the registry).
5. **Verify before declaring done:** `forge task ls` shows every task, `forge task ls --ready` is non-empty, and every registry `file` path exists on disk (`forge task reconcile-files` with no flag dry-runs the check).

Use `--category` (codes in SEEDING.md) for priority ordering — security/data first, polish last; no per-category quotas.

## Phase 7 — Optional Specialist Scaffold

If the project has a deep recurring domain (a specific WMS, a proprietary API, a design system), offer `python3 .claude/scripts/forge/forge.py specialist add <name> --domain "..."`. Skip silently if no domain warrants one.

## Phase 8 — Summary + Next Step

Present a compact summary (template: DOCS.md) ending **Next:** `/reflect resume T001`. Commit everything (`docs/`, `.claude/reference/`, registry, epic/task files) with a clear message, e.g. `chore: initialize project — PRD, ADRs, reference docs, task registry`.

## Key Rules

- **One task system.** The forge registry is the only tracker — no feature database, no parallel lists, no per-task TodoWrite mandates.
- **Two confirmations only:** after Discovery/PRD, and before task seeding.
- **Registry skeleton → epics → tasks, in that order.** The empty skeleton is the one sanctioned hand-write; every epic and task goes through the forge CLI.
- **Seed what the PRD implies** — no numeric floors, no padding.
- **Honest TODOs:** `TODO(user): ...` where the user must decide; never fabricate Tier 2 content.
- **PRD keeps its four validator sections** (Vision, Goals, User Stories, Success Criteria).
- **Tier 2 wins:** once populated, reference docs 01-09 are source-of-truth; later conflicts get reconciled via ADR.
- **`--current` mode confirms before writing.**

## See Also

- `templates/prd.md`, `templates/adr-template.md`, `templates/task.md`, `templates/isa.md` (epic bodies come from `forge epic add`, not a template)
- `/reflect` (resume seeded tasks), `/run-epic` (drain an epic), `scripts/forge/forge.py` (task-state CLI)

---

**Project-specific overrides:** if `SKILL.local.md` exists in this directory, read it — it is consumer-owned, survives framework refresh, and **wins on conflict**. A sidecar that relaxes a gate defined above must state how to prove the gate is wrong in that case. Doctrine: `rules/framework-vs-project-root.md`.
