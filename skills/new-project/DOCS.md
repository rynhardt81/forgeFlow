# New Project — Delegation Prompts and Reference-Doc Map

The Phase 2 question checklist, Task-tool prompts for Phases 3–4, the Phase 5 source map and the Phase 8 summary. When to delegate is in SKILL.md.

## Discovery checklist (Phase 2)

- **What** — the problem, the outcome, the smallest version worth shipping
- **Who** — users/personas, and who is explicitly NOT a user
- **Stack** — languages, frameworks, database, hosting (`--current`: detected, present for confirmation)
- **Constraints** — deadlines, integrations, compliance, team conventions, budget for external services
- **Data sensitivity** — what data flows through this system, where it's stored, who can see it

## PRD drafting (Phase 3)

Alternative headers the validator accepts for its four sections: Overview/Problem Statement; Objectives/Requirements; Users/Personas/Target Audience; Acceptance Criteria/Definition of Done/Metrics.

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

## ADR seeding (Phase 4)

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

## Reference docs 01–09 (Phase 5)

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

## Summary template (Phase 8)

```markdown
## Project Initialized

- PRD: docs/prd.md
- ADRs: .claude/reference/06-architecture-decisions.md ([N] seeded)
- Reference docs: 01-09 populated ([M] TODO(user) markers remain)
- Tasks: [Y] across [X] epics — [Z] ready

**Next:** /reflect resume T001
```
