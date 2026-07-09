# {{PROJECT}} Expert Knowledge

> Exported from `.claude/agents/specialists/{{NAME}}.md`. Maintained by the specialist agent.
> Vendor this file into sibling projects that depend on {{PROJECT}}.

**Domain**: {{DOMAIN}}
**Version**: 0.1.0
**Last updated**: {{TIMESTAMP}}
**Specialist**: `{{NAME}}` in the `{{PROJECT}}` repo

## Architecture overview

_2-5 paragraph summary of the system architecture — the major pieces, the data flows, the boundaries. Aim for the level of detail a competent engineer needs to integrate without reading the source._

## Key contracts

_API endpoints, message formats, schemas, integration points consumers need. Versioned where relevant. Code blocks for request/response shapes._

## Critical invariants

_Things that MUST be true for this system to function correctly — security boundaries, data integrity rules, ordering constraints, idempotency guarantees. Violating any of these is a defect, not a tradeoff._

## Known gotchas

_Past incidents, surprising behaviors, "if you do X, you must Y". Each entry: short description + when it bit + how to avoid._

## Version history

_Significant changes with dates, semver bumps, breaking-change notices. Keep the most recent at the top._

- {{TIMESTAMP}} — Initial export, knowledge skeleton scaffolded by `forge specialist add`

## How consumers should use this

_Specific guidance for sibling projects — what to call, what to avoid, how to authenticate, how to handle errors. The "if you're vendoring this, here's what you need to know" section._
