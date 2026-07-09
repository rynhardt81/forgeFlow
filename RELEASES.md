# Releases

> Release history for Claude Forge. v4.0.0 is the subtractive release; v3.0.0 introduced the Forge Flow rebrand and architecture rebuild; v2.x predates the rebuild and its release notes are not part of this repo.

---

## v4.1.0 — Skills catch up to `epic add` + model-routed dispatch

**Status:** released 2026-07-07 (tag `v4.1.0`).

v4.0.1 shipped `forge epic add`, but every skill still described the pre-`epic-add` process — `/new-project` hand-wrote epic registry entries and hand-created epic dirs from a template, `/run-epic`'s auto-file command used a `--type` flag the CLI has never had, and `/reflect resume` offered `task add` in the exact scenario where the epic couldn't exist. v4.1.0 catches the whole skill layer up: the empty registry skeleton is now the only sanctioned hand-write, epics go through `forge epic add` (registry entry + `docs/epics/<id>-<slug>/` dir + `tasks/` subdir + body file, atomically), and the divergent `templates/epic-minimal.md` is gone — the CLI owns the epic-body format.

It also adds **model-routed subagent dispatch**: `skills/_shared/model-routing.md` maps task effort tiers to subagent models (E1 → `haiku`, E2 → `sonnet`, E3 → inherit, E4 → main loop only) with hard floors for gate domains (schema/auth/money paths never down-route) and a single-escalation-on-failure rule, wired into `/run-epic --parallel`. All mechanisms are generally-available Claude Code features — the framework gains cheap parallel execution on any session model. Full list: [CHANGELOG.md](CHANGELOG.md#v410--2026-07-07).

---

## v4.0.1 — Task-registry integrity + lifecycle fixes

**Status:** released 2026-07-07 (tag `v4.0.1`).

A patch release driven by running v4 through real consumer projects. The headline fix closes a task-registry integrity gap: the forge CLI had **no way to create an epic**, yet `task add` *required* the epic to exist — and silently accepted a task under a non-existent epic, orphaning it from `registry.epics` with no back-reference (a blocking, non-auto-fixable consistency finding surfaced only later). The only workaround was hand-editing `registry.json`, the one mutation the framework forbids. v4.0.1 adds **`forge epic add`** (atomic registry entry + on-disk dir/body file, mirroring `task add`) and makes `task add` raise `EpicNotFound` for an unknown epic, with `--allow-missing-epic` as the deliberate escape hatch.

Alongside it: `install.sh` non-interactive runs no longer die silently under `set -e` (three `read` prompts hit EOF on `--yes`/non-tty and skipped the settings/MCP/root-import steps); the dependency-hygiene rule is now reachable from the always-loaded `CLAUDE.md` domain gates; and the `tests.yml` `pip` cache — which required a root manifest this repo intentionally lacks — was dropped. Interfaces of the daily-spine tools are unchanged. Full list: [CHANGELOG.md](CHANGELOG.md#v401--2026-07-07).

---

## v4.0.0 — The subtractive release

**Status:** released 2026-07-03 (tag `v4.0.0`).

A four-pass audit of the whole framework (skills, deterministic spine, governance docs, adversarial gap review — plus field inspection of three consumer installs) drove one conclusion: the spine is real and the wrapping was hurting. The task CLI, ISA verification trail, and CI-preflight economics survived scrutiny; the ceremony layer around them was found to *aggravate* the exact failure modes it claimed to prevent, the automatic memory pipeline had never captured a session in the field, and the security pipeline discarded its own verdicts.

v4 therefore: **removes** ~2/3 of the instruction surface (duplicate task system, dead pipelines, vendored plugin copies, orphaned protocol docs, all numeric floors and output ceremony); **fixes** the wiring that was aspirational (validator advice now reaches the model; installers stop shipping caches; the mode classifier no longer escalates everything); and **adds** the production half of the lifecycle the audit found missing — migration discipline (Gate E), release safety with verified rollback, POPIA/GDPR privacy rules, `/triage-incident` with postmortems, and dependency-CVE surveillance templates.

Interfaces of the daily-spine tools are unchanged; upgrade is a normal framework refresh. Full itemized list: [CHANGELOG.md](CHANGELOG.md#v400--2026-07-03); upgrade notes: [MIGRATION-GUIDE.md](MIGRATION-GUIDE.md).

---

## v3.2.0 — Cockpit + visualisation + code-map intelligence

**Status:** committed to `main`; tagged `v3.2.0`. Public-release docs (USER-GUIDE, MIGRATION-GUIDE, community scaffolding) added 2026-06-21; public-readiness pass 2026-06-30.

### What's new

#### Forge Dashboard — `forge dashboard`

A read-only local HTTP cockpit at `http://127.0.0.1:4847/` serving every Forge Flow artifact under one URL with SSE live-reload. Seven tabs:

- **Tasks** — kanban: epics → tasks by status (`docs/tasks/registry.json`)
- **Code Map** — module / file / symbol graph with DRY-hotspot highlights (`docs/code-map.json`)
- **ISAs** — feature ideal-state articulations with verification trails (`docs/tasks/F-*/ISA.md`)
- **Memory** — bugs, decisions, patterns, facts (`docs/project-memory/`)
- **Daily** — recent daily-log entries (`daily/`)
- **Registry** — raw `registry.json` as a collapsible tree (debug view)
- **Burndown** — tasks completed per day, derived from git history of registry.json

`ThreadingHTTPServer` + stdlib-only architecture (no `watchdog` / `pyinotify` / fsevents). Singleton mtime-poll watcher subscribes per-connection via SSE; broadcasts changed paths to all subscribers every 2 s; drop-oldest on `Queue.Full` so a stuck subscriber never wedges the broadcaster. Friendly EADDRINUSE / EACCES error pages with `--port <n>` hint. Read-only by design — every mutation flows through `forge task ...` per CLAUDE.md.

`scripts/forge/dashboard/` (server, watcher, per-tab renderers, vendored CSS), `docs/tasks/F-DASHBOARD/ISA.md` (12 ISCs verified).

#### `/visualize` skill — standalone HTML renders

For sharing, offline review, or single-file artifacts. Generators discovered by scanning `Tools/generators/*.py` for a module-level `register()` — adding a generator is one file, no dispatcher edit:

- **`code-map`** — three-layer drill-down (modules → files → symbols) over `docs/code-map.json`. Cytoscape.js + dagre vendored inline. Symbol-level "lineage mode" showing import linkage. Role filter sidebar.
- **`tasks`** — two-layer kanban (epic board → per-epic task board with detail drawer). Viewport-height fixed columns with internal scrolling. State-color coding for 7 status values.
- **`isa <id>`**, **`ci-report <run-id>`** — additional generators registered in the manifest.

Output lands at `<project>/docs/visualizations/<name>.html` (gitignored). Single-file HTML, works offline.

`skills/visualize/SKILL.md` + `Tools/`, `docs/tasks/F-VISUALIZE/ISA.md`.

#### Code Map JSON v3 + `forge-code-map` MCP server

`/audit-code-map` now emits both `docs/code-map.md` (human-readable) and `docs/code-map.json` (machine-readable). JSON schema bumped `v2 → v3`:

- **`file_edges`** — every import resolved to a target file path within the project. Python `pkg.mod` → `pkg/mod.py` (or `__init__.py`); TS `./foo` → `foo.ts` / `foo.tsx` / `foo/index.ts`. External or unresolvable imports drop out cleanly. Powers per-file mini-graphs in `/visualize`.
- **`dry_hotspots`** — symbols (classes or top-level functions) declared in 3+ files across the codebase. Top 20 also rendered in `docs/code-map.md`. Threshold tunable.

`mcp-servers/code-map/server.py` exposes the JSON to Claude as a queryable index for fast symbol → file resolution without re-reading large files. Registered in `.mcp.json` at install time (`install.sh` adds the entry, gitignores `docs/code-map.json`). Code-touching skills (`/fix-bug`, `/refactor`, `/new-feature`, `/implement-features`) carry a baked-in "consult the forge-code-map MCP before reading source" instruction.

Auto-runs on `SessionStart` via the audit-code-map skill's `--ensure-fresh` path — fresh data without manual maintenance.

#### Dashboard root-resolution fix (architectural, applies to every vendored install)

Closed a class of bug where `server.py:project_root()` and `_shared.py:project_root()` used markers (`CLAUDE.md`, `docs/code-map.json`) that false-positive'd on files inside `.claude/` itself, causing the dashboard to resolve its data root to `.claude/` instead of the parent project. Result before fix: Tasks tab showed fixture data ("E01 Authentication") instead of real registry; other tabs read empty data from `.claude/docs/`. The framework dev repo's testing didn't catch this because in self-hosting mode the two roots coincide.

**Fix:** `framework_root` (where CODE lives — `.claude/` in vendored installs, repo root in self-hosting) and `project_root` (where DATA lives — parent of `.claude/`) are now distinct resolvers, derived structurally from `__file__` instead of marker walks. The whole framework now consistently writes project artifacts (visualizations, generated maps, task state) to project root, never under `.claude/`. Doctrine: `rules/framework-vs-project-root.md` (auto-loads every session). Tests: 7 regression tests at `tests/dashboard/` synthesize a vendored install and assert resolvers ignore both false-positive markers + assert no fixture leak in rendered HTML.

#### Framework scope tightening — `docs/` no longer ships into consumers

The framework dev repo's `docs/` tree is dev-repo state only (self-documentation, planning notes, the framework's own task ISAs, orphan reference docs that aren't referenced by any framework runtime). Previously it was rsyncing into every consumer's `.claude/docs/`, polluting consumer projects with framework internals (code-map of the framework, debug audits, dashboard spec drafts, etc.).

All three install modes (`fresh`, `refresh`, `refresh-v3`) now exclude `docs/` entirely via `--exclude='docs'` + `--exclude='docs/**'`, plus a post-rsync `rm -rf <project>/.claude/docs/` to heal past leaks. Framework-internal docs (`docs/forge-flow/`, `docs/debug/`, `docs/permission-profiles.md`, `docs/rules-system.md`, framework's own task ISAs) also git-rm'd from framework tracking in prep for public release — kept on disk for framework dev's own use, gitignored to prevent re-tracking. Only `docs/code-map.md` remains tracked under `docs/` in the public framework repo.

#### `/audit-rules` skill — quarterly governance audit

Audits `CLAUDE.md` + every file in `.claude/rules/*.md` for stale, contradictory, or over-prompting rules. Outputs a review report (advisory, never modifies governance files). Designed to be run on a cadence — quarterly — as the rules layer accumulates corrections over time.

#### `/preflight-ci` skill — local CI mirror

Mirrors GitHub Actions locally before push. Derives gating jobs from `.github/workflows/*.yml`, generates committed `.forge/preflight/*.sh` scripts, runs them, routes failures via the same classifier as `/diagnose-ci`. Installs by default as a pre-push hook that only fires when locked in-progress tasks have `preflight_required: true`. Subshell-isolated steps so `cd` in one step doesn't leak to the next; GHA `${{ ... }}` template syntax rewritten to env vars in the generated scripts so they run outside Actions; `preflight.py` runs as a script (not a module) so the pre-push hook path resolves.

#### `/run-epic` skill — autonomous single-epic drain

Autonomously drains every open task in a single epic — inline work (no skill-fork to `/fix-bug` etc., which loses epic context), auto-files discovered follow-ups back into the same epic, opens a PR per task. Guardrails halt on `--max-iter` cap, three consecutive failures, or escalation gates. Add `--parallel` to spawn background sub-agents (reuses `/reflect dispatch` infra) for non-conflicting ready tasks.

#### Path-scoped skills

Skills can declare a `paths:` field in their manifest entry; `SessionStart` surfaces only the skills relevant to the directory you started in (e.g. frontend skills in frontend dirs, infra skills under `infrastructure/`). Reduces noise in the skill catalog presented at session start.

#### Self-improving CLAUDE.md hook

A `Stop` hook now reflects on the session and proposes CLAUDE.md edits when it spots recurring friction. Captures lessons without manual remembering.

#### ISA auto-emit reflection skeleton

When an ISA transitions to `phase: complete`, a hook emits a reflection skeleton — prompts the agent to record what was learned, what changed about the approach, and what should propagate back to the relevant skill or rule.

#### Monorepo CLAUDE.md scaffolding

`install.sh` can now scaffold workspace-local `CLAUDE.md` stubs (frontend / backend / infra / etc.) under a monorepo root. Each workspace gets a minimal `CLAUDE.md` that inherits from the root one but can be specialised.

#### `.claudeignore` default scaffolded at install time

Per-project `.claudeignore` seeded with sensible defaults (build artifacts, lock files, large generated data) so Claude Code's file-listing isn't overwhelmed on first session.

#### `/create-pr` invocation doctrine across code-shipping skills

`/new-feature`, `/fix-bug`, `/refactor`, `/implement-features`, `/release` now route their wrap-up step through `/create-pr` rather than letting the agent improvise the PR ceremony. Closes the gap that produced the original raw-`gh pr create` slip observed in a consumer project. (Shipped as v3.1.1 in mid-May, folded into the v3.2.0 milestone here for narrative coherence.)

#### Background-agent checkpoint discipline (algorithm v1.1.0)

Algorithm doctrine extended: long-running background agents now emit periodic checkpoints (progress + remaining work) at well-defined transition points so a session resuming from a compact doesn't lose state. `algorithm/v1.1.0.md` is the active version (pointer at `ALGORITHM/LATEST` advanced).

#### `forge task set-file T### <path>`

New CLI subcommand for explicit registry → file linkage when a task's file path doesn't follow the canonical `docs/epics/E##-*/tasks/T###-*.md` shape (legacy projects, custom layouts). Atomic-write contract identical to the other forge mutations.

#### `pr-skill-reminder` hook

PostToolUse hook detects raw `gh pr create` / `gh pr edit` invocations and reminds the agent to route through `/create-pr` for the DRY check + pr-review-toolkit specialist pre-flight + mandatory `@codex` mention.

### Test counts

| Surface | v3.1.0 | v3.2.0 | Δ |
|---------|--------|--------|---|
| `tests/forge/` | 59 | 71 | +12 (set-file, code-map JSON shape, drift fixes) |
| `tests/wiring/` | 22 | 28 | +6 (skill→agent wiring for new skills) |
| `tests/dashboard/` | 0 | 7 | +7 (root-resolution + fixture-leak guards) |
| **Total** | **81** | **106** | **+25** |

All run in <1s.

### ISAs added

- `docs/tasks/F-DASHBOARD/ISA.md` — local cockpit (12 ISCs verified)
- `docs/tasks/F-VISUALIZE/ISA.md` — standalone HTML renders (with DAG→kanban design pivot documented)
- `docs/tasks/F-PREFLIGHT-CI/ISA.md` — local CI mirror

### Doctrine added

- `rules/framework-vs-project-root.md` — the framework_root vs project_root distinction; codifies "what ships into consumer `.claude/`" and the public-repo discriminator

### Notable commits

- `dc767db` — fix(install,scope): exclude all of docs/ from rsync + untrack framework-internal docs
- `114009c` — fix(dashboard): resolve framework_root vs project_root correctly in vendored installs
- `66f3520` — feat(audit-code-map): emit file_edges + register /visualize skill
- `0d3e781` — feat: /visualize skill + forge dashboard local cockpit
- `c783929` — feat(skills): add /audit-rules — quarterly governance audit
- `04e684a` — feat(preflight): add /preflight-ci skill + workflow-derived local CI mirror
- `c6a89c6` — feat(skills): add /run-epic for autonomous single-epic drain
- `3283139` — feat(code-map): emit JSON artifact + MCP server for symbol-level navigation
- `215f77a` — feat(code-map): DRY hotspot detection — symbols declared in 3+ files
- `4cda7d1` — feat(skills): path-scoped skills via 'paths' field + SessionStart surfacing
- `960eae2` — feat(hooks): self-improving CLAUDE.md reflection on Stop event
- `b67f743` — feat(hooks): auto-emit reflection skeleton on ISA phase: complete
- `9daa2b9` — feat(install): scaffold layered CLAUDE.md stubs for monorepo workspaces
- `b308d61` — feat(algorithm,forge,hooks,agents): background-agent checkpoint discipline (v1.1.0)

---

## v3.1.2 — Session Protocol First (enforced)

**Status:** landed on `main` 2026-05-12; no standalone tag — folded into the `v3.2.0` milestone. (Tagged release lineage: `v2.1.0-final`, `v3.0.0`, `v3.0.1`, `v3.2.0`.)

### Fixed

Previously, `skills/reflect/SKILL.md` carried a "Session Protocol First — always start with the session protocol" rule that was aspirational only. Nothing in the framework created a session file at SessionStart; the rule only fired when the user explicitly invoked `/reflect`. A long Forge Flow session could run end-to-end with an empty `active/` directory and the rule never tripped.

**Behavior change:** `hooks/session/session-context.py` now auto-creates a minimal session file when `active/` is empty, at every SessionStart (startup / resume / compact matchers). The session ID format and storage path match the doctrine in `reference/12-session-protocol.md`. Race-safe (re-checks inside the create path) and never blocks SessionStart on filesystem errors — falls back silently to the pre-auto-create `S:NONE` behavior.

`skills/reflect/SKILL.md` updated to reflect that Steps 1–2 are now framework-owned. The rule rephrased: "A session file always exists — the SessionStart hook auto-creates one if `active/` is empty."

### Commit

- `385b446` — fix(hooks,reflect): enforce Session Protocol First by auto-creating session file at SessionStart

---

## v3.1.1 — `/create-pr` invocation doctrine

**Status:** landed on `main` 2026-05-11; no standalone tag — folded into the `v3.2.0` milestone.

### Added

Code-shipping skills (`/new-feature`, `/fix-bug`, `/refactor`, `/implement-features`, `/release`) now route their wrap-up step through `/create-pr` rather than letting the agent improvise the PR ceremony. Closes the gap that produced the original raw-`gh pr create` slip observed in a consumer project. Net effect: no skill ships code without the DRY hotspot check, the `pr-review-toolkit` specialist pre-flight (Step 3.7), and the mandatory `@codex` review mention.

Wiring tests added to `tests/wiring/` asserting every code-shipping skill cites `/create-pr` in its wrap-up step.

### Commit

- `687cfac` — feat(skills,reflect,tests): /create-pr invocation doctrine across code-shipping skills

---

## v3.1.0 — pr-review-toolkit + slicing-bug gate + forge rename (post-canary)

**Status:** committed to `main` (no tag yet). Three additive features built on top of the v3.0.0 spine. Existing skills, hooks, and tests preserved unchanged; this release only *adds*.

### What's new

- **`/create-pr` Step 3.7 — `pr-review-toolkit` specialist pre-flight.** When the `pr-review-toolkit` plugin is installed at user scope, `/create-pr` fans out the matched specialists (`code-reviewer`, `pr-test-analyzer`, `type-design-analyzer`, `silent-failure-hunter`, `comment-analyzer`, `code-simplifier`) in parallel against the diff *before* the push. Findings are bucketed `MUST-FIX` / `NICE-TO-HAVE` / `NO-ACTION` (matching the existing codex review vocabulary); `MUST-FIX` gates push until resolved or explicitly overridden via `--proceed-anyway`. CI remains the gate of record. Plugin-absence is graceful: a one-line skip note, then the original flow.

- **`/diagnose-ci` (new skill).** Companion to Step 3.7 for the post-CI-failure path. Reads `gh run view --log-failed`, classifies by failure pattern, routes to the matching `pr-review-toolkit` specialist, outputs a proposed fix plan. **Diagnosis only** — no `git commit`, `git push`, `gh pr edit`, or `gh run rerun` (enforced by `hooks/validators/skills/diagnose_ci_format.py` on the Stop hook). Avoids re-burning Actions minutes on blind retry-pushes.

- **`/refactor` Step 5 slicing-bug gate (Python projects).** New `skills/refactor/Tools/check_undefined_names.py` wraps `pyflakes` and filters to F821-class (`undefined name`) findings — the slicing-bug class produced when a Structural refactor splits a module along section boundaries and orphans a module-local helper into one new file while another still calls it. Three-tier `pyflakes` invocation: host → `python -m pyflakes` → opt-in `docker exec $REFACTOR_CHECK_CONTAINER`. Exit codes: 0 clean, 1 slicing bug, 2 pyflakes unavailable (warn, don't block). TypeScript/JS projects no-op (covered by their type-checker).

- **`forge task rename T### "new name"`.** Atomic update of registry name + task-file frontmatter `name:`. YAML-quotes values containing `:`, `#`, etc. Same atomic-write contract as every other forge mutation. Closes the gap that previously forced hand-edits of `registry.json`.

- **`forge task reconcile-from-files`.** Opt-in CLI that seeds registry entries from orphan task files on disk. Reads each file's frontmatter `name` + `status`; defaults to `"<id> (reconciled)"` / `pending` when missing. Idempotent. Preserves existing registry entries even when file name disagrees. Designed to recover from v2 → v3 migrations where task files predate the v3 registry schema (the case a consumer project hit on its v3 refresh).

- **Drift #8 — `file-vs-registry-name`** in the consistency banner. Detects and auto-fixes frontmatter `name:` skew in registry-as-truth direction, mirroring drift #6 (`status:`) mechanics. Auto-fix severity (not blocking), preserving the existing commit-gate contract. `gather_task_files` now returns 4-tuples `(file, id, status, name)`; all four callers updated in the same change.

### Test counts

| Surface | v3.0.0 | v3.1.0 | Δ |
|---------|--------|--------|---|
| `tests/forge/` | 44 | 59 | +15 (rename × 6, reconcile × 4, drift #8 × 5) |
| `tests/wiring/` | 22 | 22 | 0 |
| **Total** | **66** | **81** | **+15** |

All run in <1s. The 7 existing drift classes + 8 existing forge subcommands are untouched and pass identically (anti-criteria ISC-A1 / ISC-A2 from `docs/tasks/F-FORGE-RENAME/ISA.md`).

### ISAs

- `docs/tasks/F-PR-REVIEW-TOOLKIT/ISA.md` — pr-review-toolkit integration (23 ISCs verified)
- `docs/tasks/F-FORGE-RENAME/ISA.md` — rename + reconcile + drift #8 (31 ISCs verified)

### Commits

- `8eb99bc` — feat(skills): pr-review-toolkit pre-flight + /diagnose-ci skill
- `a6c8d9a` — feat(skills/refactor): add check_undefined_names.py slicing-bug catcher
- `034ac6a` — feat(forge): task rename + name-drift reconciliation + orphan-file recovery

---

## v3.0.0 — Forge Flow

**Codename:** Forge Flow
**Status:** shipped. **33/33 ISCs verified `[x]`** in root `ISA.md` (canary closed ISC-14, ISC-30, ISC-33). Framework code complete on `main`.
**Branch:** merged to `main`
**Build phases shipped:** B1–B8.

### Headline

Rebrand + architecture rebuild. Claude Forge is now a project-portable framework for AI-assisted software development with a phase-disciplined Algorithm, ISA primitive, atomic task-state CLI, 4-tier documentation governance, project-aware specialist agents with portable `EXPERT.md` artifacts, and deterministic skill→agent wiring with bound output validators.

### What's new

- **Algorithm doctrine** — `.claude/ALGORITHM/v1.0.0.md` with 7 fixed phases (OBSERVE → THINK → PLAN → BUILD → EXECUTE → VERIFY → LEARN), atomic ISC quality system, anti-criteria, antecedents, splitting test, verification doctrine, learning router
- **ISA primitive** — single document per task / per project that is the test harness; ships at `<project>/ISA.md` (long-lived) or `docs/tasks/<id>/ISA.md` (ad-hoc); `.claude/skills/ISA/` provides Scaffold + CheckCompleteness workflows
- **`forge specialist add`** — CLI subcommand that scaffolds a project specialist agent + paired `EXPERT.md` knowledge artifact for vendoring into sibling projects (replaces v2's path-coupled `cross-repo` skill)
- **Three-kinds-of-documents distinction** — operational scaffolds (`templates/`) vs. source-of-truth docs (`reference/01-09`) vs. ideal-state articulation (ISAs); makes the framework's mental model explicit
- **5 framework agents, persona-stripped** — architect, project-manager, quality-engineer, security-boss, devops; each ≤80 lines (10× compression vs v2's 470-LOC personas), validator-bound (architect → architect_adr; quality-engineer → quality_coverage + tdd_aaa; security-boss → security_secrets; devops → build_deps)
- **Real `Task(subagent_type=...)` wiring** — 5 skills (new-project, new-feature, fix-bug, create-pr, post-implementation-check) fire framework agents via 15 concrete Task() blocks; markdown agent-routing tables updated to v3 5-agent roster with v2-mapping column for historical reference
- **`install.sh --mode refresh-v3`** — leverages existing `verify.sh --fix` for drift detection; preserves all user content (specialists, registry, daily, project-memory, knowledge, worktrees, mcp-servers, settings.json); mirrored to `install.ps1 -Mode refresh-v3 -Yes` for Windows parity
- **17 design micro-skills** — flattened from v2's nested `commands/commands/` to first-class `skills/design/<name>.md`
- **Test suite** — 66 tests total: 44 in `tests/forge/` (atomic registry mutations + drift detection, ported from v2) and 22 in `tests/wiring/` (static analysis verifying every `Task(subagent_type=...)` cites a real agent, every agent has parseable frontmatter, every validator binding resolves to a real file). Both suites run in <1s.

### Cuts

- **18 framework agents → 5**. 13 cut. Cut-agent work folded into surviving 5 + v3 skills:
  - `@analyst` + `@scrum-master` → `@project-manager`
  - `@e2e-runner` + `@tdd-guide` → `@quality-engineer`
  - `@doc-updater` → `/refresh-project-context` skill
  - `@refactor-cleaner` → `/refactor` skill
  - `@ux-designer` → `/ui-ux-pro-max` + `/frontend-design` + `/skills/design/*`
- **`commands/` directory entirely** — all 4 v2 ops commands removed; skills cover them. ISC-12 spirit: exactly-one-home for every concept.
- **`commands/commands/` 17 design commands** — moved to `skills/design/<name>.md` as first-class skills.
- **`skills/cross-repo/` and `add-cross-repo.sh`** — replaced by Specialist Export Artifact (`EXPERT.md`) pattern.
- **`features/` and `framework-docs/plans/`** — empty placeholders; deleted.
- **`reference/13-task-management.md` and `reference/18-project-memory.md`** — collapsed to thin pointer stubs (399 LOC → 29; 248 → 27). Content moved to `forge.py` self-documentation and root `MEMORY-SCHEMA.md` respectively.
- **PAI-Lite positioning** — Forge Flow is its own framework with its own identity, not "PAI but lighter".

### Net change (measured)

| Surface | v2 | v3 | Δ |
|---------|-----|-----|---|
| `agents/` | 8,994 | 389 | **-95%** |
| `commands/` (incl. nested) | 4,044 | 0 | **-100%** |
| `templates/` | 3,705 | 76 | **-98%** |
| `skills/` | 35,528 | 32,164 | -9% |
| `scripts/` | 8,718 | 8,292 | -5% |
| `reference/` | 6,553 | 5,961 | -9% |
| `hooks/` | 3,351 | 3,114 | -7% |
| `security/`, `rules/`, `standards/` | 2,670 | 2,670 | 0 |
| **Total framework code+docs** | **69,519** | **52,877** | **-24%** |

The original ISA stated "v2 ~15K → v3 ≤8K". That baseline was probably just `agents/` (8.5K) plus a partial-skills count, never the full framework. Honest measure now lives in `ISA.md`'s ISC-32 (corrected wording: "≥20% reduction from measured v2 baseline"). Heaviest reductions came from persona-stripping (`agents/`) and removing the duplicate `commands/` surface.

### Open at ship

All 33 ISCs in root `ISA.md` are verified `[x]` as of the canary pass (ISC-14, ISC-30, ISC-33 closed). See the Canary verification section in `ISA.md`.

### Deferred to v3.1

- **`forge code-map`** — auto-generated symbol-structure document with DRY hotspot detection. Spec captured at `docs/forge-flow/06-code-map-spec.md`. Tree-sitter Python + TypeScript extraction, 4-trigger cadence (manual skill / session-start-warn / PostToolUse-incremental / PR-creation-full), 0.85 DRY threshold.

### Migration from v2

`install.sh --mode refresh-v3 /path/to/project`:
- Backs up existing `.claude/` framework files to `.claude/backups/<timestamp>/`
- Replaces framework-shipped files with v3 versions
- **Preserves**: `.claude/agents/specialists/*`, `docs/tasks/registry.json`, `docs/tasks/epics/*`, `docs/project-memory/*`, `daily/*`, `.claude/knowledge/*`, `.claude/worktrees/*`, `.claude/mcp-servers/*` (project-specific)
- **Removes**: existing `.claude/cross-repo/` config (with one-time notice listing external projects so the user can re-vendor as `EXPERT.md` artifacts)
- See [MIGRATION-GUIDE.md](MIGRATION-GUIDE.md) for full walkthrough

### Architecture changes

- v2.1.0 framework files moved to `_archive/v2/` (gitignored, local only); canonical v2 state preserved at git tag `v2.1.0-final`
- Repo root rebuilt fresh per `docs/forge-flow/` planning artifacts (six review files: ISA, inventory, CLAUDE.md draft, agent roster, Algorithm draft, specialist pattern, code-map spec)

### Phases

- **Phase A** (2026-05-08): archive v2 to `_archive/v2/`, tag `v2.1.0-final`, clean root ✅
- **Phase B1** (current): Root + spine — CLAUDE.md, ALGORITHM/v1.0.0.md, ALGORITHM/LATEST, ISA.md, README.md, CHEATSHEET.md, MEMORY-SCHEMA.md, RELEASES.md ✅
- **Phase B2** (next): Forge CLI + scripts — port `scripts/forge/`, `scripts/memory/`, redesign `scripts/install/` for v3, port `scripts/helpers/` + `scripts/lib/`
- **Phase B3**: Hooks subsystem — port `hooks/` with consistency-banner + per-agent and per-skill validators bound to surviving 5
- **Phase B4**: Agents (5 thinned) + skills with deterministic wiring + specialist scaffolding + skills/design/ + skills/ISA/
- **Phase B5**: Reference (4-tier) + rules + security + standards + templates
- **Phase B6**: MCP servers + tests + MIGRATION-GUIDE.md
- **Phase B7**: Canary on a real consumer project, then ship

---

## v2.x — historical

Full v2 release notes preserved at `_archive/v2/RELEASES.md` (gitignored locally) and at git tag `v2.1.0-final`.

To browse v2 history:
```bash
git checkout v2.1.0-final
# explore the v2 tree
git checkout forge-flow
# back to current
```

Or read the archived `RELEASES.md` directly:
```bash
cat _archive/v2/RELEASES.md  # local archive (after Phase A)
```

---

*Forge Flow is iterated on the `forge-flow` branch; merges to `main` happen at v3.0.0 ship.*
