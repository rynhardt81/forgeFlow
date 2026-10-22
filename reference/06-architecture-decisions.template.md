# 06-architecture-decisions.md

**Architecture Decision Records (ADRs)**

> **Audience:** Engineers, architects, Claude Code
> **Authority:** Master Source-of-Truth (Tier 2)
> **Persona:** Architecture Review Board
> **Purpose:** Document WHY architectural decisions were made

---

## 1. Purpose of This Document

This document contains **Architecture Decision Records (ADRs)** that explain the reasoning behind key technical decisions.

### When a decision earns an ADR

Record one only when all three of these are true:

1. **Hard to reverse**: the cost of changing your mind later is meaningful
2. **Surprising without context**: a future reader will look at the code and wonder "why on earth did they do it this way?"
3. **The result of a real trade-off**: there were genuine alternatives and you picked one for specific reasons

If a decision is easy to reverse, skip it: you'll just reverse it. If it's not surprising, nobody will wonder why. If there was no real alternative, there's nothing to record beyond "we did the obvious thing."

What qualifies:

- **Architectural shape.** "We're using a monorepo." "The write model is event-sourced, the read model is projected into Postgres."
- **Integration patterns between contexts.** "Ordering and Billing communicate via domain events, not synchronous HTTP."
- **Technology choices that carry lock-in.** Database, message bus, auth provider, deployment target. Not every library: just the ones that would take a quarter to swap out.
- **Boundary and scope decisions.** "Customer data is owned by the Customer context; other contexts reference it by ID only." The explicit no-s are as valuable as the yes-s.
- **Deliberate deviations from the obvious path.** "We're using manual SQL instead of an ORM because X." Anything where a reasonable reader would assume the opposite. These stop the next engineer from "fixing" something that was deliberate.
- **Constraints not visible in the code.** "We can't use AWS because of compliance requirements." "Response times must be under 200ms because of the partner API contract."
- **Rejected alternatives when the rejection is non-obvious.** If you considered GraphQL and picked REST for subtle reasons, record it; otherwise someone will suggest GraphQL again in six months.

A **rejected proposal** earns an ADR the same way: when a refactor or design is turned down for a lasting reason that a future reviewer would need, record it so it isn't proposed again. Skip ephemeral reasons ("not worth it right now") and self-evident ones.

An ADR can be a single paragraph. The value is in recording *that* a decision was made and *why*, not in filling out sections: Context and Decision are the core, and Consequences and Alternatives Considered earn their place only when they carry non-obvious information.

<!-- Adapted from mattpocock/skills domain-modeling/ADR-FORMAT.md (MIT) — see THIRD-PARTY-NOTICES.md -->

---

## 2. ADR Index

<!-- CUSTOMIZE: Add your ADRs as they're created -->

| ID | Title | Status | Date |
|----|-------|--------|------|
| ADR-001 | [Example: Use PostgreSQL for primary database] | Accepted | YYYY-MM-DD |
| ADR-002 | [Example: Adopt microservices architecture] | Accepted | YYYY-MM-DD |

---

## 3. ADR Template

Use this template for new ADRs. Also available at `.claude/templates/adr-template.md`.

```markdown
## ADR-XXX: [Title]

**Status:** [Proposed | Accepted | Deprecated | Superseded]
**Date:** YYYY-MM-DD
**Deciders:** [List of people involved]

### Context
What is the issue that we're seeing that motivates this decision?

### Decision
What is the change that we're proposing and/or doing?

### Consequences
What becomes easier or more difficult because of this change?

### Alternatives Considered
What other options were evaluated?

| Option | Pros | Cons |
|--------|------|------|
| Option A | | |
| Option B | | |
```

---

## 4. Architecture Decision Records

<!-- CUSTOMIZE: Add your actual ADRs below -->

### ADR-001: [Title]

**Status:** Accepted
**Date:** YYYY-MM-DD
**Deciders:** [Names]

#### Context
[Describe the situation and problem]

#### Decision
[Describe what was decided]

#### Consequences
[Describe the outcomes]

#### Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| [Chosen option] | [Benefits] | [Drawbacks] |
| [Alternative] | [Benefits] | [Drawbacks] |

---

### ADR-002: [Title]

**Status:** Accepted
**Date:** YYYY-MM-DD
**Deciders:** [Names]

#### Context
[Describe the situation and problem]

#### Decision
[Describe what was decided]

#### Consequences
[Describe the outcomes]

---

## Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | YYYY-MM-DD | [Author] | Initial version |
