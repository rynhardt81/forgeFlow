# Skill Authoring

> How a framework skill is laid out, and how any document an agent reads — a skill, `CLAUDE.md`, a rule, a doc reached by a pointer — is written. Layout is enforced by `tests/wiring/test_skill_structure.py`; the writing sections are adapted from mattpocock/skills `writing-for-agents` (MIT, see `THIRD-PARTY-NOTICES.md`). Sources: Anthropic's [skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) and the [Claude Code skills reference](https://code.claude.com/docs/en/skills).

## Contents

- Why the layout matters · The two loads · Context pointers
- SKILL.md layout, in order · Budgets · What stays in SKILL.md and what moves out
- References stay one level deep · Description (invocation choice)
- Steps and completion criteria · When to split · Leading words · Pruning
- File naming

## Why the layout matters

A skill loads in three levels:
1. **Description** (frontmatter): always in context, in every session.
2. **SKILL.md body**: loaded when the skill is invoked. It then stays in context for the rest of the session.
3. **Bundled files**: cost nothing until read.

Two harness facts make the body's size and order load-bearing:
- **Compaction:** after auto-compaction, Claude Code keeps only the **first 5,000 tokens** of each invoked skill. Anything below that is gone for the rest of the session.
- **Partial reads:** Claude may read a long reference file only partly (`head -100`) and act on what it saw. A file whose scope isn't visible at the top gets used incompletely.

So SKILL.md is a router: the core that must always apply, plus an index that sends the reader to the one file it needs now.

## The two loads

Every document and pointer you add spends one of two budgets:

- **Context load** is the cost of always-loaded material on the agent's window: a `CLAUDE.md` line, a skill description, an always-on rule — anything sitting in context every turn, spending tokens and attention whether or not it fires.
- **Cognitive load** is the cost on the human: which documents exist and when to reach for each. The human is the index. Not a cost to minimise: it is the price of human agency; spend it where human judgement matters, remove it where it does not.

Material reached only through a pointer escapes context load at the price of the pointer's own line; material with no pointer at all rides entirely on cognitive load.

## Context pointers

A **context pointer** is a reference held in the agent's context that names some out-of-context material and encodes the condition for reaching it. A skill's description is one; an `## Index` row is one; a line in `CLAUDE.md` naming a doc is the same object. The pointer's _wording_, not its target, decides when the agent reaches the material, and how reliably. A must-have target behind a weakly worded pointer is a variance bug: sharpen the wording first, and inline the material only if sharpening fails.

A pointer does two jobs: state what the material is, and list the **branches** that should trigger reaching it (a branch is a distinct case the document handles, so different runs take different paths through it). Every word of an always-loaded pointer costs on every turn, so it earns even harder pruning than the body:

- **Front-load the leading word**: the pointer is where it does its triggering work.
- **One trigger per branch.** Synonyms that rename a single branch are one branch written twice; collapse them and keep only genuinely distinct branches.
- **Cut identity the body already carries.**

## SKILL.md layout, in order

1. **Frontmatter:** `name`, `description`, plus any Claude Code fields the skill needs (`allowed-tools`, `hooks`, `model`, `effort`, `when_to_use`, …).
2. **Title and a short purpose:** one paragraph at most.
3. **`## Index`:** a table of `File or section | Read when…`. List every bundled `.md` file **and** every `skills/_shared/*.md` file the skill uses. If a skill has nothing to route to, the index lists its own sections.
4. **The core:** invocation, steps, gates, key rules.
5. **The sidecar pointer line:** stays the last line of the file (`test_skill_sidecar_pointer.py`).

## Budgets

- **SKILL.md: ≤ 200 lines and ≤ 10 KB.** This is stricter than Anthropic's 500-line ceiling on purpose, so the compaction-kept first 5,000 tokens hold the whole core.
- **Any bundled `.md` over 100 lines** opens with a `## Contents` list within its first 15 lines.

## What stays in SKILL.md and what moves out

A document is built from two content types: **steps** (the ordered actions the agent performs) and **reference** (definitions, rules, facts consulted on demand). The core decision is where each piece sits on the **information hierarchy**, ranked by how immediately the agent needs it: (1) in-file step, (2) in-file reference, (3) disclosed reference — a separate file reached by a pointer, loaded only when the pointer fires. Push too little down and the top bloats; push too much and you hide material the agent actually needs.

**Progressive disclosure** is the move down that ladder, so the top stays legible. Branching is the cleanest test: inline what every branch needs, and push behind a pointer what only some branches reach. In-file reference that should be disclosed buries the steps and turns attending to them into a coin-flip. **Co-location** is the within-file companion: keep a concept's definition, rules and caveats under one heading rather than scattered, so reading one part brings its neighbours with it. **Sprawl** — a document simply too long, even when every line is live — thins attention; the cure is the ladder, not deletion of live material.

Rule of thumb: a partial read of the skill must never skip a gate.

**Stays:**
- Every gate, hard floor and blocking check, stated as a rule with its trigger.
- Verification requirements.
- The step sequence.
- Exit codes and statuses a caller depends on.
- Key rules.

**Moves to a bundled file:**
- Templates and output skeletons.
- Worked examples.
- Long sub-flows behind a subcommand or flag.
- Config and lookup tables.
- Version quirks and rationale ("why this exists").
- Gotchas lists longer than a handful of lines.

When a gate moves its *mechanics* out, the SKILL.md step keeps the gate itself in one or two lines: what blocks, and when. It then points to the file that holds the commands.

## References stay one level deep

- SKILL.md is the only file that points at other files.
- A bundled file may point back to SKILL.md, and to nothing else. If a sub-flow needs `_shared/task-triage.md`, list it in the SKILL.md index against that step instead.
- Pointing into **another skill's** files is not allowed. Name the other skill (`/new-feature`) or the shared file instead.

## Description

The description is the skill's top-level context pointer (the rules above apply in full). Choose the invocation first:

- **Model-invoked** (no `disable-model-invocation`): the description stays loaded, so the agent can fire the skill autonomously and other skills can reach it; you can still type its name. Permanent context load in exchange for discoverability. A model-invoked skill whose content is all reference is also a home for reference several skills share.
- **User-invoked** (`disable-model-invocation: true`): only the human typing its name can invoke it, and no other skill can. Zero context load, but cognitive load: you are the index. The description becomes a human-facing one-line summary.

Pick model-invocation only when the agent must reach the skill on its own, or another skill must. Reference two user-invoked skills both need can live in neither — push it to a `_shared/` file. When user-invoked skills multiply past what anyone remembers, a **router skill** (one user-invoked skill naming the others and when to reach for each) cures the cognitive load; it can only hint, never fire them.

- Third person. It says what the skill does **and** when to use it, with an explicit `Use when …` clause (or a `when_to_use` field).
- At most 1,024 characters. Claude Code truncates `description` + `when_to_use` at 1,536 in the listing, and under a full skill listing drops the descriptions of the least-used skills first.
- Add a `NOT FOR …` clause when a neighbouring skill is easy to confuse with this one.

## Steps and completion criteria

Every step ends on a **completion criterion**, the condition that tells the agent the work is done. Two properties make it a lever:

- **Clarity**: can the agent tell done from not-done? A vague bound ("understanding reached") invites **premature completion**: ending the step before it is genuinely done, attention slipping to _being done_. Sharpen the bound first (local and cheap); only if it is irreducibly fuzzy _and_ you observe the rush, hide the later steps by splitting the sequence — which only works across a real context boundary (a hand-off or a subagent dispatch).
- **Demand**: how much it requires. "Every modified model accounted for" forces thorough work where "produce a change list" does not. Demand drives legwork, and it binds flat reference too: "every rule applied" is an exhaustiveness bar.

The strongest criteria are both checkable and exhaustive.

## When to split

Splitting one document into two spends one of the two loads, so split only when the cut earns it:

- **By sequence**: split a run of steps where the later steps tempt the agent to rush the one in front of it. Beware the reverse: merging sequences exposes each step's later steps, inviting premature completion.
- **By invocation**: split off a model-invoked skill when a distinct leading word should trigger it on its own, or another skill must reach it. The new always-loaded description has to be worth its context load.

## Leading words

A **leading word** is a compact concept already living in the model's pretraining that the agent thinks with while running the document (_frontier_, _tracer bullet_, _red_ loop, _seam_). Repeated as a token, never as a sentence, it accumulates a distributed definition and anchors a whole region of behaviour in the fewest tokens. Reach for an existing word before coining one: a made-up word recruits no priors, and you pay in definition tokens what a pretrained word gives free. Hunt for passages that collapse into one: "fast, deterministic, low-overhead" → _tight_; "a loop you believe in" → _red_.

**Negation** is the failure mode beside this lever: steering by prohibition drags the forbidden behaviour into context and makes it _more_ available. Prompt the **positive** — state the target behaviour so the banned one is never spoken. A prohibition earns its place only as a hard guardrail you cannot phrase positively (Forge's gates and hard floors are these); even then, pair it with the positive target.

## Pruning

- Keep each meaning in a **single source of truth**, so changing the behaviour is a one-place edit. **Duplication** costs maintenance and tokens and inflates a meaning's prominence. (Deliberate duplicates exist and are test-pinned — `tests/wiring/test_duplicated_doctrine_blocks.py`.)
- The **environment** is a source of truth too (`package.json` scripts, config, directory layout, `--help` output). A document that restates it is a **cache**, earning its load only when the lookup is expensive. Cache what the agent cannot find by looking: the unwritten convention, the reason behind a choice, the gotcha no config confesses.
- Check every line for **relevance**. Without a pruning discipline the default fate is **sediment**: stale layers that settle because adding feels safe and removing feels risky.
- Hunt **no-ops** sentence by sentence: an instruction the model already obeys by default pays load to say nothing. The test (does it change behaviour versus the default?) is model-relative; settle disagreements by running the document, not by debate. When a sentence fails, delete the whole sentence. A word too weak to beat the default (_be thorough_) is a no-op too; the fix is a stronger word (_relentless_). **Exception:** the no-claim-without-a-probe rule in `CLAUDE.md` is load-bearing and never cut on the grounds that a newer model "does it natively".

## File naming

- Bundled files are uppercase topic names (`PHASES.md`, `TEMPLATES.md`, `GATES.md`) or a lowercase folder for a family (`flows/`, `cookbook/`, `Workflows/`).
- Use forward-slash relative paths in the index.
- Say whether a bundled script is to be **run** or **read**.

---

**Project-specific overrides:** if `skill-authoring.local.md` exists in this directory, read it — it is consumer-owned, survives framework refresh, and **wins on conflict**.
