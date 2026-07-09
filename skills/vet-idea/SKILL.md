---
name: vet-idea
description: Vet an idea, decision, or plan BEFORE building it. Runs a single model through five fixed adversarial advisor roles, a peer-review pass, and a chairman synthesis that emits a halt-capable GO / NO-GO / RECONSIDER verdict. Advisory and non-mutating — outputs a report, never writes task state. Trigger keywords — vet idea, should I build this, is this worth it, go no-go, council, advisors, worth the effort, before I start.
allowed-tools: Read, Glob, Grep, Bash, Write, TodoWrite
---

## Quick Scan

| | |
|---|---|
| **Purpose** | Decide *whether* an idea is worth building, before any time/money/effort is spent. |
| **Inputs** | An idea / decision / plan statement (and optionally a path to its ISA or design doc). |
| **Output** | A council report ending in a categorical **GO / NO-GO / RECONSIDER** verdict + minority report. |
| **Mutates** | Nothing. Advisory only — the user (or the Algorithm) acts on the verdict. |
| **Flow** | Independent analysis (5 roles) → peer review → chairman synthesis |

---

# vet-idea Workflow

This is the **WHETHER** gate. It is deliberately distinct from two things it is often confused with:

- **NOT the ISA Interview** (`skills/ISA/Workflows/Interview.md`) — that resolves *how* to shape the work (design-decision dependencies). `/vet-idea` asks *whether* to do the work at all.
- **NOT Algorithm THINK premortem** (`ALGORITHM/v1.2.0.md` PREMORTEM) — that enumerates failure modes the work must withstand *after* the decision to build is made. `/vet-idea` runs before that decision.

It runs entirely on the single harness model — **no `Task`/subagent fan-out**. A bare clone of the framework has no multi-agent swarm (that is a PAI-layer capability, absent here), so this skill must self-contain all role prompts and run sequentially in one transcript. Never instruct it to call `RedTeam`, `FirstPrinciples`, `Council`, or any capability that is not a file in this repo.

## When to use

- **A new product, feature, or project of uncertain worth** — before scaffolding the ISA, when the cost of building the wrong thing is high.
- **A costly or hard-to-reverse decision** — architecture bets, a dependency you can't easily drop, a direction that commits weeks.
- **When you catch yourself rationalizing** — the idea feels exciting but you haven't said out loud what would make it a bad call.

**Do NOT use it** for routine execution where the decision to build is already settled — bug fixes, refactors, a feature already approved. Vetting settled work is friction.

## Invocation

```
/vet-idea "<the idea or decision, stated plainly>"
/vet-idea "<idea>" --isa <path>     # ground the council in an existing ISA / design doc
/vet-idea "<idea>" --roles 7        # add the 3 optional roles (default 5)
/vet-idea "<idea>" --output PATH    # custom report path (default: memories/vet-idea-{slug}-{date}.md)
```

**Manual-invoke only.** This skill never auto-fires. The Algorithm may *mention* it as available at OBSERVE for an idea of uncertain worth, but firing it is always the user's call — auto-running it on every task would tax the E1 fast path and turn routine work into debate.

---

## Step 1: Frame the idea

Restate the idea in one concrete sentence the council can attack. Vague ideas produce vague verdicts. If the input is "build a dashboard", sharpen it: "build a read-only HTTP dashboard for the task registry, served locally, for solo use." Capture the stakes in one line: what does building the wrong thing cost (time / money / reversibility)?

If `--isa` is given, read it for the real Goal, Constraints, and Out-of-Scope — the council reasons against the actual articulation, not a guess.

## Step 2: Independent analysis — five fixed roles

Play each role **in sequence, in one transcript**, each producing a short independent take. The point is genuine disagreement, so each role has a **forbidden move** — a thing it is not allowed to do — that stops all five from collapsing into one agreeable voice.

| Role | Mandate | Forbidden move |
|------|---------|----------------|
| **Contrarian** | Make the strongest case *against* building this. | Forbidden from validating any part of the idea — no "but it could work if…". |
| **First-Principles** | Strip the idea to its base premise and rebuild; may conclude "you're solving the wrong problem." | Forbidden from accepting the idea's original framing. |
| **Outsider** | Ask the naive questions an outsider would; surface what's obvious to you but opaque to everyone else. | Forbidden from assuming any insider context or jargon. |
| **Executor** | Map the concrete first steps and real costs — "what do you do Monday morning?" | Forbidden from staying abstract; must name a real first action and a real cost. |
| **Expansionist** | Find the upside everyone else is missing — adjacent wins, bigger version. | Forbidden from cataloguing risks (that's the Contrarian's job). |

**Optional 3 roles** (`--roles 7`): **Strategist** (market/ROI/timing), **Scientist** (base rates, evidence), **Humanist** (the people and second-order effects). Same forbidden-move discipline — give each one a single concrete prohibition.

Write each role's take as 2-4 sharp sentences. No hedging, no role echoing another.

## Step 3: Peer review

Now each role reads the *others'* takes and responds — citing a specific point it agrees kills/saves the idea, or a specific point it thinks is wrong. This is where dissent gets tested. Keep it to one short reaction per role. Do not let the roles converge politely; if they still disagree after review, that disagreement is signal for the chairman.

## Step 4: Chairman synthesis

The chairman reads all takes and the peer review, then emits a **single decisive verdict**. No averaging into mush.

```markdown
## Verdict: GO | NO-GO | RECONSIDER   (confidence: <low | medium | high, or one coarse %>)

**Strongest case for:** <one paragraph — the best reason to build it>
**Primary objection:** <the single most serious reason not to>
**Named risks:**
1. <risk> — <why it matters>
2. <risk>
3. <risk>
**Next steps (if GO or RECONSIDER):**
1. <concrete first action>
2. ...
**Minority report:** <the strongest dissenting view, stated in full — never averaged away. If the dissent is strong enough, the chairman may side with it.>
```

Verdict meanings:
- **GO** — worth building; proceed to scaffold the ISA / start the work.
- **NO-GO** — not worth it as framed; **halt**. Do not proceed to build.
- **RECONSIDER** — the idea has merit but a load-bearing assumption is unresolved; reframe or validate first, then re-vet.

Keep the verdict **categorical**. A single coarse confidence band (low/medium/high or a round %) is fine; do not invent a multi-axis numeric score — false precision reads as rigor it doesn't have.

## Step 5: Write the report and surface

Write the full council report to `memories/vet-idea-{slug}-{date}.md` (or `--output`). Print a one-paragraph summary to the session: the verdict, the primary objection, and the recommended next step. Then stop.

**When run inside an Algorithm flow:** record the verdict in the ISA `## Decisions` section, and seed the chairman's named risks as candidate `Anti:` ISCs. A **NO-GO halts the run** — reuse the same human-stop discipline as "plan means stop" (`ALGORITHM/v1.2.0.md`): present the verdict and do not proceed to build without the user overriding.

## When NOT to use

- The decision to build is already made (approved feature, scheduled refactor, bug fix). Vetting settled work is friction.
- Trivial / reversible work (E1). The fast path exists for a reason.
- As a design interview — use the ISA `Interview` workflow for *how* to shape the work.
- As a premortem — use Algorithm THINK for failure modes once you've decided to build.

## Anti-criteria for this skill

- **Anti:** Does NOT call `RedTeam`, `FirstPrinciples`, `Council`, or any non-repo capability — it self-contains all role prompts and runs single-model so it works on a bare clone.
- **Anti:** Does NOT auto-fire — manual-invoke only; the Algorithm may mention it but never runs it unprompted.
- **Anti:** Does NOT mutate task state, the registry, or governance files — advisory only, like `/audit-rules`.
- **Anti:** Does NOT emit a design plan or a premortem — it emits a WHETHER verdict and stops.
- **Anti:** Does NOT average dissent away — the minority report preserves the strongest opposing view verbatim.

## See also

- `skills/ISA/Workflows/Interview.md` — the *HOW* gate (design-decision dependency resolution). Run this AFTER a GO verdict.
- `skills/audit-rules/SKILL.md` — the other advisory, non-mutating, report-only skill; `/vet-idea` mirrors its shape.
- `ALGORITHM/v1.2.0.md` — OBSERVE mentions `/vet-idea` as optional; THINK owns premortem (a different concern).
