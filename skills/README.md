# Claude Forge Skills

One directory per skill; each skill's `SKILL.md` is its complete definition (frontmatter description drives triggering). **`skills-manifest.json` is the canonical machine-readable roster** — this README is a human index only. If they disagree, fix the manifest first, then this table.

## Daily spine

| Skill | Purpose |
|-------|---------|
| `/reflect` | Session continuity — resume, status, handoff, unlock |
| `/create-pr` | PR creation with pre-flight review gate + review-feedback loop |
| `/run-epic` | Autonomously drain one epic with guardrails (caps, 3-failure halt) |
| `/fix-bug` | Reproduce → root-cause → fix → verify |
| `/new-feature` | Scoped feature workflow, ISA at E3+, ships via `/create-pr` |

## Project lifecycle

| Skill | Purpose |
|-------|---------|
| `/new-project` | Initialize a project — PRD, ADRs, tasks, populated reference docs |
| `/migrate` | Onboard an existing project / upgrade framework versions |
| `/refactor` | Risk-scaled refactoring with behavior verification |
| `/release` | Version + changelog + tag, with release-safety checklist |
| `/build` | Stack-aware production build routing |
| `/triage-incident` | Production incident → reproduce → fix → postmortem |

## CI economics

| Skill | Purpose |
|-------|---------|
| `/preflight-ci` | Mirror GitHub Actions locally before push; pre-push hook |
| `/diagnose-ci` | Diagnose a failed Actions run locally instead of retry-pushing |

## Quality & judgment

| Skill | Purpose |
|-------|---------|
| `/vet-idea` | GO / NO-GO / RECONSIDER council verdict BEFORE building |
| ISA (skill) | Ideal-state criteria + verification trail (Scaffold, CheckCompleteness, Interview) |
| `/security-review` | Business-logic security pass (IDOR, race, state bypass) + secrets scan |
| `/audit-rules` | Advisory audit of CLAUDE.md + rules for staleness/contradiction |
| `/audit-task-status` | Reconcile task/epic statuses against the registry |
| `/audit-code-map` | (Re)generate `docs/code-map.md` + JSON for the MCP server |

## Knowledge & context

| Skill | Purpose |
|-------|---------|
| `/remember` | Manual knowledge capture → `docs/project-memory/` |
| `/refresh-project-context` | Sync CLAUDE.md + project docs with reality |

## Design

| Skill | Purpose |
|-------|---------|
| `/frontend-design` | Design direction (defers to native plugin when present) |
| `/ui-ux-pro-max` | Searchable local design DB — styles, palettes, font pairings |

## Security hardening

| Skill | Purpose |
|-------|---------|
| `/damage-control` | Install defense-in-depth blocking hooks (the framework's one blocking security layer) |

## Shared infrastructure

- `_shared/ci-failure-classifier.md` — single source of CI-failure routing, used by `/preflight-ci`, `/diagnose-ci`, and `/create-pr`
- `visualize/Tools/` — dashboard rendering engine (not a skill; `forge dashboard` serves it)

## Removed in v4

`implement-features` (duplicate task system — use the forge registry + `/run-epic`), `pdf` (native Read handles PDFs), `permissions` (native `/permissions`), `post-implementation-check` (folded into `/create-pr` Step 3.7), `/visualize` slash-skill (use `forge dashboard`). Vendored `frontend-design` course replaced by a routing card.
