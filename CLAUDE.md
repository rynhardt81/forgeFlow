# Forge Flow

> Claude Forge v4 — project-portable framework for AI-assisted software development. Deterministic primitives (task-state CLI, ISA verification trail, CI preflight) + documentation governance + focused agents. Installs into any project; works identically on personal and work machines, with no dependency on globally-installed plugins.

## Three kinds of documents

| Kind | Where | Time horizon | Purpose |
|------|-------|--------------|---------|
| **Operational scaffolds** | `templates/` (session.md, task.md, CLAUDE.template.md) | Per-session / per-task | Define runtime behavior of the project's Claude integration |
| **Source-of-truth docs** | `.claude/reference/01-09.md` (populated at setup) + Tier 1 governance at `00` | Per-project, long-lived | What the project IS — architecture, security, NFRs, ADRs |
| **Ideal-state articulation** | `<project>/ISA.md` + `docs/tasks/<id>/ISA.md` | Per-project / per-task | What the project SHOULD BE — testable criteria + verification trail |

Decision rule: architecture decision → `reference/06`; tech-stack constraint → `reference/02`; test strategy for a feature → ISA Test Strategy; acceptance criteria → ISA Criteria; "when skill X runs do Y" → operational scaffold.

## Modes

**Native is the default.** Reply directly, use tools, keep the loop tight: intent → change → verify. Most work — questions, single-domain edits, routine task execution — lives here.

**Algorithm mode** (read `.claude/ALGORITHM/LATEST` and follow it through all phases) fires on explicit signals only:

- Debugging with a nontrivial reproduction (Gate A work)
- Multi-file feature or refactor where planning has real value
- Schema, auth, or money-path changes (Gates apply)
- Architectural/doctrine work
- The user asks for rigor or sets `/e3`–`/e4`

When in doubt, stay Native and escalate the moment the work reveals multi-file/multi-risk shape — escalation mid-task is cheap; ceremony on a simple task is pure cost.

**Effort tiers** (user-overridable with `/e1`–`/e4`):

| Tier | Scope | ISA |
|------|-------|-----|
| E1 | Trivial | none |
| E2 | Single-domain substantial | inline criteria checklist |
| E3 | Multi-file, planned | ISA document |
| E4 | Architectural, cross-cutting | ISA document |

**Feedback level** (user-overridable with `/fb low|medium|high`, default `medium`; a project `CLAUDE.md` may set its own default): how much prose a *finished-work report* carries — subagent return, skill completion, task done. Four fields, always: Problem/Task · Action · Result + evidence pointer · Recommends (omitted when empty). The level caps prose, never evidence. Spec: `skills/_shared/report-format.md`. Questions, discussion, and mid-work narration are not reports and stay plain prose.

## ISA — Ideal State Articulation

The verification trail. Project ISA at `<project>/ISA.md`; task ISA at `docs/tasks/<id>/ISA.md` (created by `forge task add --isa`). ISCs are atomic (one nameable tool probe each), ≥1 `Anti:` criterion required, `[x]` requires evidence in `## Verification` — never "tests pass". Workflows: Scaffold, CheckCompleteness, Interview (`.claude/skills/ISA/`). Criterion count is judgment — there are no floors.

## Skills

Invoke via `/<skill-name>`. Canonical roster: `skills/skills-manifest.json`; human index: `skills/README.md`.

Each skill's own one-line purpose is already in the session's skill listing, so it is not repeated here.

`forge dashboard` is not a skill: it serves a local cockpit at `http://127.0.0.1:4847/` — tasks, code map, ISAs, memory, registry, burndown (read-only, SSE live-reload). `forge` = `python3 .claude/scripts/forge/forge.py`; alias it once per machine.

## Agents

Framework agents in `.claude/agents/` (replaced on refresh); specialists in `.claude/agents/specialists/` (user-owned, never touched). Each agent's frontmatter binds a PostToolUse validator whose advice arrives as `additionalContext` — read it. Agents accept `model:` frontmatter; per-task model routing for subagent dispatch (used by `/run-epic --parallel`) is defined in `skills/_shared/model-routing.md`.

Each agent's specialization and its bound validator are in its own frontmatter — read the file rather than a copy of it here.

Scaffold specialists: `python3 .claude/scripts/forge/forge.py specialist add <name> --domain "..."` (paired `EXPERT.md` for vendoring into sibling projects).

## Project memory

Manual and intentional: `/remember bug|decision|pattern|fact "..."` writes to `docs/project-memory/`; the SessionStart hook injects `index.md` + `key-facts.md` back. Schema: `MEMORY-SCHEMA.md`. There is no automatic transcript capture, and **no hook ever spawns an LLM subprocess**.

**Three stores, three jobs — don't cross-file.** `docs/project-memory/` is the project's durable record: committed, team-shared, cross-machine. The harness's own auto-memory (`~/.claude/projects/<slug>/memory/`) is per-machine and uncommitted — working context, not the record; a fact the team needs goes in the former. `memories/` and `daily/` are **continuity, not memory** — resume state and reflection logs that `/reflect resume|handoff` reads. `/reflect` learnings go to a skill's `SKILL.local.md`; never a framework `SKILL.md`, which refresh overwrites.

## Task lifecycle

Atomic state via `python3 .claude/scripts/forge/forge.py`:

- `epic add E0X --name "..."` (+`--description`, `--deps`, `--priority`, `--category`, `--status`) — create the epic (registry entry + `docs/epics/<id>-<slug>/` dir + body file) **before** filing tasks under it
- `task add T### --epic E0X --name "..."` (+`--isa`, `--deps`, `--scope-dirs`, `--scope-files`, `--priority`, `--preflight`) — the epic must already exist, else it raises `EpicNotFound` (override with `--allow-missing-epic` only for staged imports / fixtures)
- `task lock T### --session <id>` — file-scope conflicts fail here
- `task move T### --epic E0X` — reassign a task's epic (registry + body file + frontmatter); refuses a locked task
- `epic status E0X pending|in_progress|backlog` — park or promote a whole epic (`epic complete` still owns `completed`)
- `task pr T###` / `task complete T###` / `task ls --ready` / `task show T###`
- `task reconcile-files [--apply]`

**Derived work defers by default.** When executing a task surfaces a bug, review finding, or hardening gap, `skills/_shared/task-triage.md` is binding: answer *"what breaks if this ships later?"* — Blocker (fold in, or `--deps`), Next (active epic), or **Deferred** (`--epic E99`, the default). Tasks in a `backlog` epic are excluded from `task ls --ready` and from `/run-epic`'s selection; `task ls` reports how many are parked and how old. Promote a batch with `epic status E99 in_progress`. Hard floors — schema, auth, money paths, security — are never deferred by default.

States: `pending → ready → in_progress → pr_pending → completed`. Never hand-edit `docs/tasks/registry.json` — create epics with `epic add` and tasks with `task add`; the consistency-banner hook auto-fixes drift on every write and at SessionStart.

## Documentation governance (4-tier)

| Tier | Files | Role |
|------|-------|------|
| 1 — Governance | `reference/00` | Rules for how docs work |
| 2 — Source-of-truth | `reference/01-09` | What the system IS (populated at setup) |
| 3 — Processed | `docs/processed/` | Background/evidence, referenced by Tier 2 |
| 4 — Execution | `CLAUDE.md`, `.claude/*` | Guides execution; does not define truth |

**Tier 2 wins** conflicts with ISA constraints until reconciled via ADR.

## Operational rules

- **No claim without a probe.** Every factual statement about this system — what a file contains, what a test returned, whether something works, whether a fix is complete — is made only after a tool call that establishes it, and says what established it. Binds in every mode, at every effort tier, ISA or not: Native replies, mid-work narration, and finished-work reports alike. "Should work", "that's already handled", "tests pass" are guesses wearing a claim's clothing. The scoped doctrine elaborates it — `rules/agent-verification.md` for delegated claims, ALGORITHM VERIFY for ISC evidence and the live-probe rule, `skills/_shared/report-format.md` for the Result pointer — but this holds where none of them apply. **Load-bearing: never cut or relax on the grounds that a newer model "does it natively" — confidence under load is the failure it exists to catch.**
- The forge CLI is the only sanctioned mutation path for task state.
- **Every subagent dispatch routes by effort tier** — `skills/_shared/model-routing.md` is binding on all of them, not just `/run-epic --parallel`. Name the tier and model at dispatch (E1 → `haiku`, E2 → `sonnet`, E3 → inherit, E4 → main loop only); never route up by default. Hard floors (schema, auth, money paths, security review) never scale down.
- Custom specialists live in `.claude/agents/specialists/` to survive refresh.
- Framework-wired hooks are informational and never blocking, and no hook ever spawns an LLM subprocess. Blocking layers exist only as explicit opt-ins: `/damage-control` hooks and `consistency-banner --strict`.
- For UI/web verification use a real browser probe — never theorize from code.
- **Delegated output and green focus-tests are inputs to verification, not proof.** Ground-truth a subagent's claim before acting on or relaying it (a NO-ACTION verdict gets *more* scrutiny — check the real cost of it being wrong); trace every caller/script/test on the same path before declaring a fix done. Doctrine: `rules/agent-verification.md`.
- Rules in `.claude/rules/` are active directives read on-demand; treat as binding when encountered. Domain gates pull them in: schema work → `migrations.md`, shipping → `release-engineering.md`, personal data → `privacy.md`, **adding or updating any dependency → `dependencies.md`** (exact pins; refuse versions published in the last 7 days — supply-chain compromises are usually caught within that window; new dependencies require explicit justification before install).
- **Project-specific rule content goes in sidecar files** `rules/<name>.local.md` — refresh overwrites framework rules, never sidecars. Applies to: patterns, coding-style, dependencies, git-workflow, security, testing, error-handling, observability, migrations, release-engineering, privacy, agent-verification.
- **Project-specific skill content goes in `skills/<name>/SKILL.local.md`** — same deal for skills, and the sidecar **wins on conflict**. Nothing globs skill files, so the pointer line at the end of each `SKILL.md` is what loads it; keep that line when editing a skill. A sidecar that relaxes a gate the skill defines must state how to prove the gate is wrong. Never put project-specific content in a framework `SKILL.md` — refresh will eat it.
- `.claude/` is `framework_root` (CODE); the parent is `project_root` (DATA: docs/tasks, docs/epics, docs/project-memory, daily/, ISA.md). Never write project data under `.claude/`. Doctrine: `rules/framework-vs-project-root.md`.
- Framework rules load via a root `CLAUDE.md` containing `@.claude/CLAUDE.md` — `install.sh` creates or amends this import on every install/refresh.

## See also

- `.claude/ALGORITHM/v1.2.0.md` — full Algorithm doctrine (LATEST)
- `.claude/skills/ISA/SKILL.md` — ISA workflows
- `.claude/skills/_shared/report-format.md` — finished-work report contract + feedback levels
- `MEMORY-SCHEMA.md` — project-memory spec
- `MIGRATION-GUIDE.md` — version upgrade walkthrough
