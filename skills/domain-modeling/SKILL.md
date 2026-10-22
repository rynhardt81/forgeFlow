---
name: domain-modeling
description: Builds and sharpens a project's domain model while designing — challenges terms against GLOSSARY.md, sharpens fuzzy language, stress-tests boundaries with invented scenarios, checks claims against the code, writes resolved terms into GLOSSARY.md inline, and offers an ADR in reference/06 only when a decision is hard to reverse, surprising, and a real trade-off. Use when discussing codebase terminology, writing or editing GLOSSARY.md, recording or editing an ADR, or running /grilling --docs. NOT FOR merely reading the glossary for vocabulary (every skill does that via _shared/domain-docs.md).
metadata:
  credits:
    skill: domain-modeling
    author: Matt Pocock
    url: "https://github.com/mattpocock/skills"
    license: MIT
---

# Domain Modeling

Actively build and sharpen the project's domain model as you design. This is the *active* discipline: challenging terms, inventing edge-case scenarios, and writing the glossary and decisions down the moment they crystallise. (Merely *reading* `GLOSSARY.md` for vocabulary is not this skill: that's a one-line habit any skill can do, defined in `_shared/domain-docs.md`. This skill is for when you're changing the model, not just consuming it.)

## Index

| File or section | Read when… |
|---|---|
| File structure | Finding or creating the glossary |
| During the session | Every invocation — the five moves |
| `GLOSSARY-FORMAT.md` | Writing or editing a glossary entry, or a multi-context glossary map |
| reference/06 → *When a decision earns an ADR* | Before offering an ADR, and for the ADR format |
| `_shared/domain-docs.md` | The consumer rules other skills follow (what this skill keeps current) |

## File structure

The glossary lives at the **project root** (`project_root`, never under `.claude/`). It is a Tier 2 source-of-truth document (`reference/00`). Most repos have a single context:

```
/
├── GLOSSARY.md
├── .claude/reference/06-architecture-decisions.md   ← ADRs
└── src/
```

If a `GLOSSARY-MAP.md` exists at the root, the repo has multiple contexts. The map points to where each one lives:

```
/
├── GLOSSARY-MAP.md
├── src/
│   ├── ordering/
│   │   └── GLOSSARY.md
│   └── billing/
│       └── GLOSSARY.md
```

Create files lazily: only when you have something to write. If no `GLOSSARY.md` exists, create one when the first term is resolved. ADRs are entries in `reference/06`; never create a `docs/adr/` directory.

## During the session

### Challenge against the glossary

When the user uses a term that conflicts with the existing language in `GLOSSARY.md`, call it out immediately. "Your glossary defines 'cancellation' as X, but you seem to mean Y. Which is it?"

### Sharpen fuzzy language

When the user uses vague or overloaded terms, propose a precise canonical term. "You're saying 'account': do you mean the Customer or the User? Those are different things."

### Discuss concrete scenarios

When domain relationships are being discussed, stress-test them with specific scenarios. Invent scenarios that probe edge cases and force the user to be precise about the boundaries between concepts.

### Cross-reference with code

When the user states how something works, check whether the code agrees. If you find a contradiction, surface it: "Your code cancels entire Orders, but you just said partial cancellation is possible. Which is right?"

### Update GLOSSARY.md inline

When a term is resolved, update `GLOSSARY.md` right there. Don't batch these up: capture them as they happen. Use the format in `GLOSSARY-FORMAT.md`.

`GLOSSARY.md` should be totally devoid of implementation details. Do not treat `GLOSSARY.md` as a spec, a scratch pad, or a repository for implementation decisions. It is a glossary and nothing else.

### Offer ADRs sparingly

Only offer to create an ADR when all three are true:

1. **Hard to reverse**: the cost of changing your mind later is meaningful
2. **Surprising without context**: a future reader will wonder "why did they do it this way?"
3. **The result of a real trade-off**: there were genuine alternatives and you picked one for specific reasons

If any of the three is missing, skip the ADR. An accepted ADR is a new entry in `reference/06` (index row + record, next free `ADR-NNN`), following that file's *When a decision earns an ADR* section. Because 06 is Tier 2, the user confirms the entry before it is written.

---

**Project-specific overrides:** if `SKILL.local.md` exists in this directory, read it — it is consumer-owned, survives framework refresh, and **wins on conflict**. A sidecar that relaxes a gate defined above must state how to prove the gate is wrong in that case. Doctrine: `rules/framework-vs-project-root.md`.
