---
name: new-feature
description: Orchestrates full feature development workflow from discovery through commit. Infers scope (small/medium/large) from the feature description and adapts phases accordingly. Auto-invokes ISA at E3+ and hands off to /create-pr for shipping (its Step 3.7 pre-flight reviews the diff before push). Use when the user wants to add any new feature, capability, or functionality — regardless of size. Triggers on phrases like "add feature", "new feature", "implement X", "build X", "create X functionality". NOT FOR draining a forge-registry epic (use /run-epic).
---

## Quick Scan

| | |
|---|---|
| **Purpose** | Full feature development from discovery to commit |
| **Inputs** | Feature description |
| **Output** | Implemented feature, tests, documentation, commit |
| **Flow** | Discover → Design → Plan → Implement → Verify → Commit |

---

# New Feature Workflow

## Invocation

User runs: `/new-feature <description>`

Example: `/new-feature add user preference settings to the portal`

## Step 0: Map the surface

Read `docs/code-map.md` (auto-regenerated each SessionStart). Knowing which modules and classes already exist prevents proposing a feature that mostly already exists, and surfaces the right insertion points so new code doesn't duplicate existing capability. If the map is missing, run `/audit-code-map`.

**Before proposing new code with a specific class or function name**, check the `forge-code-map` MCP tools so the feature doesn't collide with something already shipping:

- `find_definition("ProposedClassName")` → if a class with that name exists, surface it in the proposal: extend or rename rather than duplicate.
- `language_stats()` → confirms the language mix and scale of the codebase you're adding to (cheap orientation in fresh sessions).
- `dry_hotspots()` → if the feature touches a domain that already has DRY duplication, flag it in the proposal — the feature is a chance to consolidate.

If the MCP server isn't registered, run `/audit-code-map --emit-json` and follow `mcp-servers/code-map/README.md`. Fall back to Grep + the markdown map otherwise.

## Step 1: Analyze and Propose

1. Analyze the feature description
2. Infer scope — **small**: one domain, 1-3 files, no schema/API surface change; **medium**: crosses one boundary (UI↔API or API↔data) or adds API surface; **large**: crosses two or more boundaries, touches schema, or changes auth/money paths. When in doubt, pick the larger scope.
3. Present to user:
   - "**Feature:** [restate clearly]"
   - "**Inferred scope:** [small/medium/large]"
   - "**Recommended phases:** [list]"
   - "Proceed with this plan?"

## Step 2: Execute Phases

Run each phase sequentially. See [PHASES.md](PHASES.md) for detailed instructions.

| Scope | Phases |
|-------|--------|
| Small | Discovery → Planning → Implementation → Verification → Commit → **PR (`/create-pr`)** |
| Medium | Discovery → Design → Planning → Implementation → Verification → Review → Doc Update → Commit → **PR (`/create-pr`)** |
| Large | All phases with deeper analysis, ending in **PR (`/create-pr`)** |

### Agent + Skill Routing Reference (v3)

| Phase | Invocation | Condition | Purpose | v2 mapping |
|-------|-----------|-----------|---------|-----------|
| Design | `@architect` (Task) | Medium/Large | Architecture decisions, ADRs | unchanged |
| Implementation | `@quality-engineer` (Task) | Always | TDD workflow guidance + AAA structure | `@tdd-guide` → quality-engineer |
| Implementation | `@security-boss` (Task) | Security features | Threat-model + security review | unchanged |
| Verification | `@quality-engineer` (Task) | UI/user flows | E2E test execution | `@e2e-runner` → quality-engineer |
| Review | `@quality-engineer` (Task) | Medium/Large | Code review (correctness, coverage) | unchanged |
| Review | `/refactor` (Skill) | Significant refactor surfaces | Risk-scaled refactor | `@refactor-cleaner` → /refactor |
| Doc Update | `/refresh-project-context` (Skill) | Medium/Large or public API | Documentation sync | `@doc-updater` → skill |

Concrete `Task(subagent_type=…)` blocks with full prompts live in [PHASES.md](PHASES.md) at each invocation point.

## Step 3: Checkpoint Protocol

Confirm with the user at two points only: after the proposal (Step 1) and before opening the PR. Mid-phase progress is reported inline, not gated — large-scope design decisions that change the proposal get surfaced when they happen, not batched into ceremony.

## Step 4: Open PR via `/create-pr`

After the Commit phase, invoke the canonical PR skill:

```
Skill("create-pr")
```

`/create-pr` runs the DRY hotspot check, the `pr-review-toolkit` specialist pre-flight (Step 3.7), and ensures the mandatory `@codex` mention is in the PR body. Do **not** use raw `gh pr create` — it bypasses every one of those gates.

If the user has explicitly asked for no PR (rare; usually a local-only experiment), say so and stop. Otherwise, `/create-pr` is the default wrap-up.

## Skills I invoke

- `/create-pr` — mandatory at the wrap-up of every feature flow that ships code
- `/refactor` — invoked from the Review phase on Medium/Large scopes when significant refactor surfaces emerge
- `/refresh-project-context` — invoked from the Doc Update phase on Medium/Large scopes or public-API changes

## Key Rules

- Always use TodoWrite to track progress through phases
- Always invoke skills via Skill tool, not by memory
- Always check for project-level agents before falling back to built-in
- Never skip verification phase
- Never use raw `gh pr create` — always route the PR through `/create-pr`
