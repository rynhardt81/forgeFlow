# Agent Delegation (Forge Flow v3)

> Authoritative spec for **how** skills delegate work to framework agents and how users invoke agents directly. The agent roster and validator bindings live in `agents/README.md` (read on-demand, like all rules and reference docs — nothing here is auto-loaded at session start); this document owns the delegation patterns.

---

## Core principle

**Specialized work benefits from specialized agents — but in v3, implementation runs through skill workflows, not through a generic implementer agent.** Framework agents are consulted for design (architecture, threat modeling) or review (test coverage, code quality) at specific phases. Claude itself executes the implementation as it follows the active skill's workflow.

This is a deliberate v2 → v3 shift: v2 had a `@developer` agent that "did the implementation" and a router that dispatched between specialists; v3 collapses the router into the skill bodies and removes the `@developer` middleman. The five framework agents (`@architect`, `@project-manager`, `@quality-engineer`, `@security-boss`, `@devops` — full roster + validator bindings in `agents/README.md`) are domain experts, not implementers.

---

## How agents are invoked

Two paths:

**1. Auto-fired by a skill.** Skills like `/new-project`, `/new-feature`, `/fix-bug`, `/create-pr` fire framework agents at specific phases via real `Task(subagent_type=…)` calls. The skill provides a fully-prompted context block with the project's Tier 2 references; the agent runs in an isolated context and produces its specialized output.

**2. Direct user invocation.** For a focused review or design pass without the full skill workflow:

```
@architect: Review the proposed split of routes/auth into a routes/ package and surface any boundary concerns

@security-boss: Threat-model the new payment-webhook endpoint against OWASP A01–A10

@quality-engineer: Audit the new tests for AAA structure and coverage gaps

@devops: Review the proposed GitHub Actions workflow for the multi-environment deploy

@project-manager: Re-baseline the T210 epic — which sub-tasks are still in-scope after T210b/c/d landed?
```

Behind the scenes Claude Code invokes the Task tool with `subagent_type=<name>` and the prompt built from your message.

---

## Wiring shape (when a skill fires an agent)

Concrete fenced block in the skill body:

```
Use the Task tool:
- subagent_type: "<agent-name>"
- description: "<short — what the agent will produce>"
- prompt: |
    <full prompt with project context, deliverables, output paths, and
    which Tier 2 reference docs the agent must defer to>
```

Examples in `skills/{new-project, new-feature, fix-bug, create-pr}/**/*.md`. Static-analysis tests at `tests/wiring/test_skill_agent_wiring.py` verify every `subagent_type:` reference resolves to a real framework agent.

Each agent's frontmatter binds an advisory PostToolUse validator that fires on its writes — see `agents/README.md` for the bindings.

---

## v2 → v3 mapping

13 v2 personas were cut. Their work folded into the surviving 5 plus skill-based flows:

| v2 agent (cut) | v3 home |
|----------------|---------|
| `@analyst` | `@project-manager` (analysis IS PRD work) |
| `@scrum-master` | `@project-manager` (sprint / iteration planning IS PM work) |
| `@e2e-runner` | `@quality-engineer` (E2E IS test strategy) |
| `@tdd-guide` | `@quality-engineer` (TDD IS test strategy — `tdd_aaa.py` validator enforces AAA) |
| `@api-tester` | `@quality-engineer` (API contract testing) |
| `@performance-enhancer` | `@architect` (perf is architectural) |
| `@build-resolver` | `@devops` (build / CI failures are CI / infra) |
| `@refactor-cleaner` | `/refactor` skill (risk-scaled refactor IS a workflow) |
| `@doc-updater` | `/refresh-project-context` skill (doc refresh IS a workflow) |
| `@ux-designer` | `/ui-ux-pro-max` + `/frontend-design` |
| `@visual-mistro` | `/frontend-design` (its `interventions/*` reference library) |
| `@whimsy` | `/frontend-design` (reads `interventions/delight.md`) |
| `@orchestrator` | The Algorithm itself + skill orchestration |
| `@developer` | No equivalent — implementation runs through the active skill's workflow |

If legacy code, prose, or memory references a cut agent, route to the v3 home above.

---

## Multi-agent flows (typical sequences)

The user-facing skills already wire these explicitly. For ad-hoc work:

| Flow | Sequence |
|------|----------|
| **Auth / payments feature** | `@project-manager` (PRD) → `@architect` (ADRs) → `@security-boss` (threat model) → Claude implements via `/new-feature` → `@quality-engineer` (test plan + AAA review) |
| **Standard feature** | `@project-manager` (PRD + breakdown) → `@architect` (only if architectural) → Claude implements via `/new-feature` → `@quality-engineer` (review) |
| **Bug fix** | Claude reproduces + fixes via `/fix-bug` → `@quality-engineer` (E2E regression if UI touched) → `@security-boss` (only if security-related) |
| **Refactor** | Claude designs + executes via `/refactor` → `@quality-engineer` (correctness + coverage review) |
| **Architecture change** | `@architect` (ADR + design) → Claude implements via `/refactor` or `/new-feature` → `@quality-engineer` (review) |
| **Release** | Claude runs `/release` → on build failure: `@devops`; doc audit: `/refresh-project-context` → tag + push |

The skill is the orchestrator (replaces v2's `@orchestrator`); framework agents are domain experts consulted at phases; Claude resumes the skill workflow using agent output as input.

---

## Project specialists (user-owned)

Beyond the framework agents, projects add specialist agents in `.claude/agents/specialists/<name>.md`:

```bash
python3 .claude/scripts/forge/forge.py specialist add <name> --domain "..."
```

This generates the specialist agent (never replaced on `install.sh --mode refresh-v3`) plus a paired `EXPERT.md` knowledge artifact at the project root (vendorable into sibling projects). Specialists are invoked the same way — `@<name>: <ask>` or `Task(subagent_type="<name>", ...)`.

---

## See also

- `.claude/agents/README.md` — roster, delegation table, validator bindings
- `.claude/agents/<name>.md` — individual framework agent definitions
- `.claude/agents/specialists/README.md` — project specialist scaffold + refresh-v3 preserve guarantee
- `.claude/skills/<name>/SKILL.md` — skills that auto-fire agents
