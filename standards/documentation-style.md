# Documentation Style Standards

**Purpose:** Define how all documentation should be written across projects.
**Authority:** Referenced by governance; applies to all tiers of documentation.
**Audience:** Claude Code, technical writers, developers, agents.

---

## Rule 1: No Time Estimates

NEVER document time estimates, durations, or completion times for any workflow, task, or activity. This includes workflow execution time, task duration estimates, reading time estimates, and implementation time ranges.

**Why:** Time varies dramatically based on project complexity, team experience, tooling, and unforeseen blockers.

**Instead:** Focus on steps, dependencies, and outputs. Let users determine their own timelines.

## Rule 2: Task-Oriented Writing

Write for user GOALS, not feature lists:

- Start with WHY, then HOW
- Every doc answers: "What can I accomplish?"
- Structure around tasks users want to complete
- One idea per sentence, one topic per paragraph; examples follow explanations

## Rule 3: Style Hierarchy

Apply style guidance in this order:

1. **Project-specific guide** (if one exists in project docs)
2. **This document**
3. **Google Developer Docs style**, then the CommonMark spec, for anything not covered here

---

## Mermaid Diagram Gotchas

Hard-won one-off fixes — these produce broken renders when missed:

| Mistake | Correct |
|---------|---------|
| No diagram type on first line | Start with `flowchart TD` (or `sequenceDiagram`, `erDiagram`, …) |
| Unquoted special chars in labels | Quote them: `A["Label: with colon"]` |
| `->` arrows in flowcharts | Use `-->` |
| Connecting undefined nodes | Define all nodes before connecting |
| Sprawling diagrams | 5–10 nodes ideal, 15 maximum — split beyond that |

Use valid Mermaid v10+ syntax and validate mentally before outputting.

---

## Quality Checklist

Before finalizing ANY documentation:

- [ ] NO time estimates anywhere
- [ ] Task-oriented (answers "how do I…")
- [ ] Examples are concrete and working (realistic values, not `"string"` placeholders)
- [ ] Mermaid diagrams pass the gotcha table above
- [ ] Links have descriptive text (never "click here"); images have alt text; tables have headers
