---
name: grilling
description: Grills the user relentlessly about a plan, decision, or idea — a design-tree interview asked in rounds, each round the whole frontier of answerable questions with a recommended answer. Works at any effort tier, with or without an ISA. Use when the user wants to stress-test their thinking, says "grill me" / "grill with docs" / any 'grill' phrase, or a skill needs a plan sharpened before acting. NOT FOR deciding whether to build at all (/vet-idea) or deepening an existing E3+ ISA (the ISA Interview workflow, which runs this same round format).
metadata:
  credits:
    skill: grilling, grill-me, grill-with-docs
    author: Matt Pocock
    url: "https://github.com/mattpocock/skills"
    license: MIT
---

# Grilling

Interview the user relentlessly until you reach a shared understanding. The interview primitive other skills run: the architecture survey, `/domain-modeling` sessions, and the ISA Interview workflow all use its round format.

## Index

| File or section | Read when… |
|---|---|
| Modes | Choosing plain grilling or grilling with docs |
| The interview | Every invocation — the design tree, rounds, frontier, done condition |
| Where this sits | Routing between `/grilling`, `/vet-idea` and the ISA Interview |
| `_shared/model-routing.md` | Dispatching a subagent to find a fact |

## Modes

- **Plain** (`/grilling`, "grill me"): the interview alone. Stateless: it writes nothing.
- **With docs** (`/grilling --docs`, "grill with docs"): the same interview, plus the `/domain-modeling` discipline running alongside it, so resolved terms land in `GLOSSARY.md` and hard-to-reverse decisions are offered as ADRs in `reference/06` as they crystallise. Default to this mode whenever there is a project under the working directory: it leaves a paper trail.

## The interview

Map the plan as a **design tree**: every decision branches into the decisions that hang off it.

Work the tree in **rounds**. The **frontier** is every decision whose prerequisites are already settled: the questions you can ask _now_ without guessing at answers you haven't heard yet. Ask the whole frontier in one round: number each question and give your recommended answer. Then wait for the user's answers before the next round.

Format a round like so:

```
❓ **Q1** - **<question title>**: <question body, might be multiple paragraphs, including multiple choices>

➡️ <your recommended answer>

---

❓ **Q2** - **<question title>**: <question body, might be multiple paragraphs, including multiple choices>

➡️ <your recommended answer>
```

Word each question so "yes" accepts your recommended answer.

Each round the user answers reshapes the tree: settled decisions push the frontier outward and unblock questions that depended on them. Recompute the frontier and ask the next round. A question whose answer depends on another question still open in this round belongs to a _later_ round, not this one.

Finding _facts_ is your job, never the user's. When a frontier question needs a fact from the environment (filesystem, tools, etc.), dispatch a sub-agent to find it; don't ask the user for anything you could look up yourself. A lookup is E1 work under `_shared/model-routing.md`: the read-only `Explore` agent or `worker-e1`. Don't block on it: a running exploration is an unsettled prerequisite, so only the questions downstream of it wait for the sub-agent to report; ask the rest of the frontier now. The _decisions_ are the user's: put each to them and wait.

The session is done when the frontier is empty: every branch of the design tree visited, nothing left silently assumed. Do not act on it until the user confirms you have reached a shared understanding.

## Where this sits

| Question on the table | Run |
|---|---|
| *Whether* to build it at all | `/vet-idea` |
| *How* to shape a plan, any size, no ISA needed | `/grilling` |
| *How* to shape an E3+ task that already has an ISA, writing decisions back into it | the ISA Interview workflow (`/ISA interview`) |

What a finished grilling session feeds: `/intent` for work someone else must accept, `/new-feature` for a small clear change, or `/prototype` when a question can only be settled by something runnable.

---

**Project-specific overrides:** if `SKILL.local.md` exists in this directory, read it — it is consumer-owned, survives framework refresh, and **wins on conflict**. A sidecar that relaxes a gate defined above must state how to prove the gate is wrong in that case. Doctrine: `rules/framework-vs-project-root.md`.
