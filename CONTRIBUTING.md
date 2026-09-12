# Contributing to Forge Flow

Thanks for considering a contribution. Forge Flow is a deterministic spine for AI-assisted software development, and the bar for changes is correctness, clarity, and respect for the framework's primitives (phase-disciplined Algorithm, ISA articulation, atomic task-state CLI, 4-tier documentation governance).

## Getting started

1. Read [README.md](README.md) for what the framework is and how it's structured.
2. Run the test suite: `python3 -m pytest tests/` (suites: `forge/`, `wiring/`, `dashboard/`, `preflight/`).
3. Make a scoped change, add/update tests, and open a PR.

> **A note on paths.** This is the framework *source* repo, so the framework lives at the repo root: `reference/`, `agents/`, `skills/`, `rules/`, etc. When the framework is *installed* into a consumer project it lives under `.claude/` — so docs that reference `.claude/reference/…` or `.claude/agents/…` describe the **installed** layout. In this source checkout, drop the `.claude/` prefix.

## How to contribute

- **Issues** — open one before non-trivial PRs so design intent gets discussed before code lands.
- **PRs** — keep them scoped; one logical change per PR. Reference any related task IDs and ADRs.
- **Tests** — changes touching framework behavior (skills, hooks, the forge CLI, Algorithm doctrine) must include or update tests under `tests/`.
- **Docs** — if a change alters runtime behavior, update the relevant Tier 2 source-of-truth file under `.claude/reference/` in the same PR. Operational scaffolds (`templates/`, `CLAUDE.md`) and source-of-truth docs are different categories — see `CLAUDE.md` "Three kinds of documents".
- **Specialist agents** — user-owned specialists live in `.claude/agents/specialists/` and are never modified by framework refresh; framework agents under `.claude/agents/` are.

## What ships into a consumer's `.claude/`

These are decisions made while authoring the framework, not while using it. They lived in `rules/framework-vs-project-root.md` until 2026-09-12, where every consumer session loaded ~5 KB of installer doctrine at startup to answer a question only a framework developer asks. The consumer-facing half of that rule — path resolution and the sidecar mechanism — stayed behind.

`.claude/` is framework_root — CODE only. The strict test for whether a path in the framework dev repo should rsync into a consumer's `.claude/`:

> Is this path **required by framework runtime functionality** in the target project? Required means: read by a Python script, loaded by Claude Code at session start (via `settings.json` or `CLAUDE.md` `@`-import), referenced by a template at project init, or otherwise needed for the framework to *function* — not just to be *documented*.

If the answer isn't a clear yes, exclude it. The default is **exclude**, not include — every file that ships into a consumer's `.claude/` is one the consumer's dev team has to either accept as opaque framework infrastructure or read to understand. Both are costs. Charge them only when there's runtime value.

**`docs/` in particular** — the framework dev repo's `docs/` tree is framework self-documentation (code-map describing the framework, planning history, debug audits, the framework's own task ISAs). None of it is referenced by framework runtime. **None of it ships.** Consumer projects own their own `docs/` at project_root for their own data.

Top-level files like `CHANGELOG.md`, `CHEATSHEET.md`, `README.md`, `LICENSE`, `MEMORY-SCHEMA.md` DO ship — they're referenced by verify, by templates, and by hooks that read them into session context. That's the discriminator: real runtime reference vs. authored-only documentation.

## Rsync excludes — the other half of this rule

Anything that is BOTH (a) generated/derived at framework dev time, AND (b) gitignored — must be rsync-excluded in `install.sh`. Otherwise the framework dev repo's copy bleeds into `<project>/.claude/` and the walk-up resolvers grab it as a marker.

Cross-check `.gitignore` against `install.sh` rsync `--exclude` lines for every framework refresh. Add a one-shot `rm -rf` on the post-rsync step for paths that previous installs leaked, so refresh actively heals past damage.

## And the public-repo discriminator

When the framework repo itself goes public, an additional filter applies to what's tracked in git:

> Would an outside contributor browsing this file find user-facing value, or is this internal dev history?

Framework dev planning history (v2→v3 migration notes, dated audits, dev plans), the framework's own task ISAs, and orphan reference docs that don't have a home in the canonical 4-tier structure (`reference/`) should not be in public-facing git history. Keep them on disk (gitignored) for the framework dev's own use; don't expose them.

## Tests guard this

`tests/dashboard/test_root_resolution.py` synthesizes a vendored install on disk and asserts each false-positive marker is ignored. Add a new test there whenever you introduce a new resolver — synthetic vendored install + assert it resolves to the project root, not `.claude/`.

## The rules budget

Claude Code loads **every** `.claude/rules/*.md` at launch. The documentation is explicit — "Rules without `paths` frontmatter are loaded at launch with the same priority as `.claude/CLAUDE.md`" — so a rule file is not a reference shelf you consult, it is context charged to every session in every consuming project, whether or not the work touches that domain.

Until 2026-09-12 fourteen of these files claimed the opposite in their own header ("discovered on-demand via the `rules/*.md` glob"). That header is why the directory was never treated as a budget: authors wrote at reference length because "on-demand" implies the reader opted in. One consumer reached 133 KB of always-on rules, 68% of its startup context. Full account: `docs/debug/2026-09-12-always-on-rules.md`.

**Writing a rule, therefore:**

- State the floor and stop. If a reader would only want the detail when actually doing the thing, it belongs in a skill (loads on invocation) or `reference/` (never auto-loaded).
- Don't explain the framework to itself. Disambiguation between framework features is a question only a framework developer asks, and every consumer pays for the answer.
- Don't point at another rule that is also always-on — both are already in context, so the pointer costs and buys nothing.
- Don't repeat a convention across files. Fourteen copies of the same sidecar paragraph is fourteen copies in one context window; say it once here.
- `forge doctor` reports the directory's always-on total. Treat a warning as a prompt to move material out, not to raise the threshold.

**`paths:` frontmatter scopes a rule to matching files — but do not reach for it on a hard floor.** Scoped rules load when Claude *reads* a matching file, and under auto mode the model prefers Bash `cat`/`sed` over Read, so a scoped rule can stay dark in exactly the sessions that touch its domain. Never scope schema, auth, money-path or security rules. Scoping a framework rule also has to be authored upstream: the refresh rsync overwrites `rules/*.md`, and only `*.local.md` sidecars survive.

A consumer that wants a specific framework rule gone can drop it durably with a `claudeMdExcludes` glob in `.claude/settings.local.json`, which the refresh rsync excludes.

## Don't duplicate the harness

Claude Code injects a substantial system prompt of its own before any framework file is read. Re-stating an instruction it already gives makes behaviour **worse**, not better: both current prompting guides name compounding as a real cost, and the Claude Opus 5 guide is explicit that such instructions "compound with the model's own behavior and add cost without improving results."

So a framework file's job is what the harness does *not* say — the forge CLI's mutation discipline, the ISA verification trail, the gate domains, the task-triage defaults. Not a second copy of general good behaviour.

**Already injected by the harness — do not add these to framework files:**

| Already there | Don't re-add |
|---|---|
| A "Delivering work" block: the request sets the scope, don't quietly narrow or widen it, make routine judgment calls yourself, finish the whole task, stop short of what's clearly beyond the ask | A framework restatement of scope discipline |
| A corrections limiter: only correct an earlier statement when the error changes the user's code, conclusions, or decisions | "Don't over-apologise", "don't narrate mistakes" |
| Deterministic subagent caps as environment variables — always. Plus a delegation instruction, but only on Claude Opus 5 **and** only when the harness uses its `claude_code` system-prompt preset; a custom or omitted system prompt gets no such line | A framework rule telling the model when to delegate in general (per-tier *routing* in `skills/_shared/model-routing.md` is different — it says which model and effort, not whether to delegate at all) |
| A parallel-tool-call nudge: make independent calls in the same block | "Batch your tool calls" |
| Context-management guidance for long sessions | "Wrap up early", "hand off before you run out" |

**Named as harmful by the guides — do not add, and remove on sight:**

- **Anti-formatting rules** — "no bullets", "avoid bold", "minimal formatting". Current models already under-format rather than over-format; Claude Fable 5.1's guide: *"If your prompt contains anti-formatting language, remove it or replace it with a rule that says when specific formatting is appropriate."*
- **"Hold all findings for the final response"** — written for models that over-narrated. It now suppresses the progress updates users need during long tool chains.
- **Self-re-verification scaffolding** — "double-check your answer", "re-verify before responding", "include a final verification step for any non-trivial task", "use a subagent to verify your own work". Claude Opus 5's guide: *"Avoid instructing re-checks it already performs ... these compound with the model's own behavior and add cost without improving results."*

### The one boundary this section must not be used to cross

**"No claim without a probe" is not self-re-verification, and it stays.** The distinction is exact and worth stating because the two look alike:

- What the guides tell you to delete is an instruction to *do the work again* — a second pass, an extra verification step, a subagent whose job is to re-check the first one. That is redundant, because the model already does it.
- What this framework requires is that a claim *cite what established it*. That is a rule about evidence, not about extra passes. It costs one sentence, it does not re-run anything, and nothing in the harness supplies it.

`CLAUDE.md`'s Operational rules mark that rule load-bearing and say never to relax it on the grounds that a newer model does it natively. This section does not license doing so, and a PR that cites "don't duplicate the harness" while deleting an evidence requirement is out of scope for it.

### Audit an incoming framework, plugin, or skill pack

Run this before enabling anything written for an older model, and read every hit — some are legitimate (a re-check after a repair action is not self-re-verification):

```bash
rg -il "no bullet|avoid bullet|minimal formatting|no bold|hold all findings|double.?check|re-?verify|subagent.{0,40}verif" <dir> --glob '*.md'
```

A hit is a question, not a verdict. Check what the line is actually doing before removing it.

## Style

- Read the existing code before adding more. Forge Flow prefers fewer, sharper primitives over feature accretion.
- No emojis in framework files unless an existing file already uses them.
- Markdown for content; HTML only where markdown can't express the structure.
- Never hand-edit `docs/tasks/registry.json` — use the `forge` CLI.

## Acknowledgments

**[Daniel Miessler](https://github.com/danielmiessler)** — creator of the [Personal AI Infrastructure (PAI)](https://github.com/danielmiessler/PAI) system.

Forge Flow was already designed when PAI entered the picture, but PAI's primitives — its Algorithm doctrine, ISA articulation, skill model, and bias toward deterministic scaffolding over model improvisation — directly inspired the fine-tuning that shaped Forge Flow's current form: more structured, more direct in its functionality, and more disciplined in how it separates source-of-truth docs from operational scaffolds. The conceptual debt is real and worth naming.

If you build on Forge Flow, consider looking at PAI as well — much of what makes Forge Flow opinionated about *how* AI-assisted development should be scaffolded traces back to ideas Daniel articulated first.
