# [Project Name] — Product Requirements Document

> Operational scaffold read by `/new-project` (Phase 1) to produce `docs/prd.md`. Replace bracketed placeholders with gathered requirements. `docs/prd.md` is a Tier 2 master source-of-truth document. The `new_project_prd.py` validator requires the four `##` sections below (Vision, Goals, User Stories, Success Criteria) — keep their headers intact.

## Vision

> The problem being solved and the world once it's solved. One or two paragraphs.

[What is broken / missing / wanted today? Who feels the pain, and why does it matter? What does success look like at a high level — the "euphoric surprise" when this lands?]

## Goals

> What we are trying to achieve. Concrete, ideally measurable.

- **G1:** [primary goal]
- **G2:** [secondary goal]
- **G3:** [stretch / later goal]

### Non-Goals

- [Explicit cut — what this product is deliberately NOT doing]

## User Stories

> Who the users are and what they need. One persona block per distinct user type.

### [Persona name — e.g. "Operations lead"]

- As a [persona], I want to [action] so that [outcome].
- As a [persona], I want to [action] so that [outcome].

### [Second persona, if any]

- As a [persona], I want to [action] so that [outcome].

## Success Criteria

> How we know it's done and working. Each criterion should be observable or testable.

- [ ] [Criterion 1 — a concrete, checkable end-state]
- [ ] [Criterion 2]
- [ ] [Criterion 3]

## Functional Requirements

> What the system must do. Group by capability.

- **FR1:** [capability]
- **FR2:** [capability]

## Non-Functional Requirements

> Constraints on how the system performs. References Tier 2 `07-non-functional-requirements.md` once populated.

- **Performance:** [e.g. p95 latency target]
- **Scale:** [e.g. expected load]
- **Security:** [e.g. auth model, data sensitivity]
- **Availability:** [e.g. uptime target]

## Constraints & Assumptions

- **Constraints:** [tech stack, budget, timeline, regulatory]
- **Assumptions:** [what we're taking as given — flag the risky ones]
