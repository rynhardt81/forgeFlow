---
id: {{TASK_ID}}
kind: task-isa
name: {{TASK_NAME}}
phase: observe
createdAt: {{CREATED_AT}}
---

# ISA — {{TASK_ID}} — {{TASK_NAME}}

> Per-task ideal-state articulation. Read `.claude/skills/ISA/SKILL.md` for the full doctrine. Phase vocabulary: `observe` → `think` → `plan` → `build` → `execute` → `verify` → `complete`. Sections below follow the locked 12-section order — some may start empty, none may be reordered or removed.

## Problem

<!-- What's broken / missing / wanted? Concrete, evidence-backed. -->

## Vision

<!-- What the world looks like once this is done. Includes the "euphoric surprise". -->

## Out of Scope

<!-- Explicit cuts — what we are NOT doing this run. Work that matches an entry here gets filed as a separate task, not absorbed. -->

-

## Principles

<!-- Inviolable rules that frame every decision on this task. -->

-

## Constraints

<!-- Inherited boundaries: relevant ADRs (.claude/reference/06-architecture-decisions.md#ADR-NNN), NFRs (07-non-functional-requirements.md), threat model (08-security-model.md), tech stack (02). What MUST hold regardless of how the task is solved. Tier 2 docs win on conflict. -->

-

## Goal

<!-- One paragraph: the deliverable in concrete terms, stated as a present-tense observable outcome, not a list of TODOs. -->

## Criteria

> Atomic ISCs. Each is a single verifiable end-state with one nameable tool probe — one command, one pass/fail outcome. No "and/or", no compound clauses; if you can't probe it from the command line or a single test, split it. Use the `Anti:` prefix for criteria stating what must NOT happen. IDs are stable — never renumber; splits become `ISC-N.M`, drops become tombstones.

| ID | Statement | Probe |
|----|-----------|-------|
| ISC-1 | | |
| ISC-2 | | |

## Test Strategy

<!-- Per-ISC: type / check / threshold / tool. Name the surface (unit / integration / e2e / manual probe), not the framework. Reference test files when they exist. -->

## Features

<!-- Phased breakdown linking ISCs to delivery units. -->

## Decisions

<!-- Timestamped — what was chosen, why, what was rejected. -->

## Changelog

<!-- Conjecture / refutation pairs — how understanding evolved during the task. -->

## Verification

> Tool-probe evidence per `[x]` ISC — never just "tests pass" or "looks fine". This is what closes the loop and gates `phase: complete`.

| ISC | Status | Probe result | Date |
|-----|--------|--------------|------|
| ISC-1 | `[ ]` | | |
| ISC-2 | `[ ]` | | |
