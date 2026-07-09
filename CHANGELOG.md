# Changelog

All notable changes to Claude Forge are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/); the project follows semantic versioning where the major version tracks framework epochs (v2 → v3 → v4) and minor versions track feature additions.

## [v4.1.0] — 2026-07-07

> Minor release: the skills catch up to the v4.0.1 `epic add` CLI (they still described the pre-`epic add` process), and autonomous runs gain model-routed subagent dispatch. Docs/skills only — no CLI or interface changes.

### Added

- **Model-routed subagent dispatch** — `skills/_shared/model-routing.md`: the shared policy mapping task effort tiers to subagent models (E1 → `haiku`, E2 → `sonnet`, E3 → inherit, E4 → main loop only), hard floors for gate domains (schema/auth/money paths never down-route), a single-escalation-on-failure rule, and guidance on Workflow ("ultracode") fan-out and opt-in external executors. Wired into `/run-epic --parallel` dispatch, `agents/README.md` (`model:` frontmatter knob), and the CLAUDE.md agents section. All mechanisms are generally-available Claude Code features — works with any session model.

### Fixed

- **Skills caught up to `forge epic add`** (v4.0.1 shipped the CLI; the skills still described the pre-`epic add` process): `/new-project` now seeds epics via `epic add` — the empty registry skeleton is the only remaining sanctioned hand-write, and `templates/epic-minimal.md` is deleted (the CLI owns the epic-body format); `/run-epic`'s auto-file command dropped the nonexistent `--type` flag (classification lives in the name prefix); `/reflect resume` creates the epic before offering `task add` (was guaranteed `EpicNotFound` in its own empty-registry scenario); `/audit-task-status` no longer attributes task body files to `--isa`.
- `.gitignore` now excludes `.superpowers/` — plugin session ledgers, not framework content.

## [v4.0.1] — 2026-07-07

> Patch release: closes a task-registry integrity gap (epics had no creation path and `task add` silently orphaned tasks under unknown epics) plus install/CI/rules fixes surfaced while driving v4 through real consumer projects. No interface removals; daily-spine tools unchanged.

### Added

- **`forge epic add`** — the sanctioned atomic path to create an epic (registry entry + `docs/epics/<id>-<slug>/` dir + body file), mirroring `task add`. Previously the CLI had no way to create an epic, so callers had to hand-edit `registry.json` — the one mutation the framework otherwise forbids. `add_epic()` / `create_epic_dir()` in `registry_ops.py`; `create_epic_dir` reuses an existing `-untitled` fallback dir rather than duplicating.

### Fixed

- **`task add` no longer silently orphans a task under a non-existent epic.** It raised no error and appended the task with no back-reference in `registry.epics`, leaving the epic unrepresented — a *blocking, non-auto-fixable* consistency finding surfaced only later. It now raises `EpicNotFound` with an actionable message; `--allow-missing-epic` is the deliberate escape hatch for staged imports / test fixtures. New `EpicNotFound` / `EpicAlreadyExists` exceptions. (8 tests in `tests/forge/test_registry_ops.py`; full forge suite green.)
- **`install.sh` non-interactive runs survive prompts under `set -e`.** Three `read` prompts (project-memory overwrite, backup collision, verify) hit EOF on `--yes`/non-tty runs and killed the installer silently mid-run, skipping the settings/MCP/root-import steps. Non-interactive defaults now: keep existing memory, rotate (never destroy) existing backups, always verify. Found upgrading a v1.8.6 consumer.
- **Dependency-hygiene rule is now reachable.** The 7-day cool-down + pin-exact + earn-its-place discipline in `rules/dependencies.md` existed but had no trigger in the always-loaded `CLAUDE.md` domain gates — a rule nobody is told to read. Adding/updating a dependency now routes to it.
- **CI: dropped the `pip` cache** in `tests.yml` — it required a root `requirements`/`pyproject` this repo intentionally lacks, breaking the workflow. Diagnosed from the run log, not retry-pushed (per `/diagnose-ci` doctrine).

### Changed

- `.gitignore` now excludes the root `memories/` tree — advisory `/vet-idea` reports written there can carry personal context and should not enter the public repo.

## [v4.0.0] — 2026-07-03

> The subtractive release. A full-framework audit (four independent deep-audit passes + field inspection of consumer installs) found ~70% of the skills prose was restating the base model, native Claude Code features, or other parts of the framework — and that output ceremony measurably aggravated the failure modes the framework exists to prevent. v4 cuts to the load-bearing spine and fills the production-lifecycle gaps. Interfaces of the daily-spine tools (forge CLI, /reflect, /create-pr, /run-epic, preflight-ci, ISA) are unchanged.

### Removed

- **`/implement-features`** — an entire second task system (SQLite features.db, own locks/parallel-groups/resume) duplicating the forge registry. The registry + `/run-epic` is the one task system.
- **Automatic memory pipeline** (`memory-capture.py`, `flush.py`, `compile.py`, FTS5 archive) — broken at capture stage in every field install, and its design spawned LLM subprocesses from hooks (now categorically forbidden). `/remember` is the capture path.
- **`security/` command-validation pipeline + `security-check.py`** — evaluated commands, then discarded its own verdict into a channel nothing read. `/damage-control` hooks are the one blocking security layer.
- **`claude-md-reflect.py`** Stop hook (spawned headless `claude`); rule reflection is `/audit-rules`, run by a human.
- **`/pdf`**, **`/permissions`** — native Claude Code covers both.
- **`/post-implementation-check`** — third copy of the review pass; `/create-pr` Step 3.7 gates every PR already.
- **`/visualize` slash-skill** — `forge dashboard` serves the same renderers (Tools/ retained as the dashboard engine).
- **Vendored `frontend-design` course** (~3,900 lines) — replaced by a native-plugin-aware routing card with a self-contained fallback.
- **All numeric floors** — ISC floors (E2=8/E3=16/E4=32), thinking floors, feature-count floors ("simple project: 50-100 features"), the ≥5-wired-skills test floor. Floors manufacture padding; the splitting test and quality gates are the real mechanism.
- **All output ceremony** — emoji phase banners, the mandatory `━━━ 📃 SUMMARY` final format, fixed-word-count scaffolds, English response-parser tables ("Yes/Proceed → next phase"), checkpoint banners.
- **Orphaned governance** — `reference/11` (1,175-line spec the code never read), `15`–`19`, `protocols/`, `pipelines.yaml`, `release_changelog.py`, the reference/00 §9 "machine-enforceable JSON" parsed by nothing, ALGORITHM v1.0.0/v1.1.0 (archived).
- Rules merged/cut: `performance.md` (hollow), `agents.md` (→ agents/README), `phased-hardening.md` (→ ALGORITHM Anti-criteria).

### Added

- **`/triage-incident`** — production incident → stabilize → reproduce → fix → verify-in-prod → postmortem + prevention tasks. The lifecycle no longer ends at the merge.
- **`rules/migrations.md`** — expand/contract, rollback pairing, backup-verified-before-apply, RLS-with-table, batch backfills; wired as Algorithm **Gate E** (fires on schema-in-scope).
- **`rules/release-engineering.md`** — rollback verified before deploy, staged rollout defaults, feature-flag inventory ("what dormant thing could this release wake"), named post-release health signal.
- **`rules/privacy.md`** — POPIA-first data inventory (special categories: children's, health), retention defaults, real deletion, subject access, breach basics; `/new-project` discovery asks the privacy question.
- **`templates/renovate.json` + `templates/dependency-scan.yml`** — dependency surveillance (grouped updates + weekly OSV/bun-audit scan), aligned with `rules/dependencies.md` cool-down policy.
- **Validator advice now reaches the model** — `BaseValidator` emits PostToolUse `hookSpecificOutput.additionalContext` instead of stderr that the harness discards.

### Changed

- **Mode default inverted** — Native by default; Algorithm on explicit signals (multi-file, debugging, schema/auth/money, `/e3`+). The old "bias toward Algorithm, anything-else escalates" classifier put 41/41 real sessions into full ceremony.
- **ALGORITHM v1.2.0** — the verification harness (reproduce-first, probe tables, forbidden language, re-read gate, checkpoint discipline) kept in full; 497 lines → 175.
- **`/create-pr`** — review-bot coupling is config-aware (`git config forge.reviewBot`) instead of hardcoding `@codex`; contradictory CHECKPOINTS.md deleted.
- **`/fix-bug`** self-contained for bare installs (superpowers plugin used when present, not required).
- **`/release`** gained the release-safety checklist; gates 6 → 2.
- **Installers** — memory-only mode removed; rsync excludes fixed (no more `.venv`/cache junk shipped to consumers).
- **`/build`** — 3,904-line deploy wizard → 41-line stack-routing card (EAS/Vercel/Supabase first; Docker when the target needs it).
- ISA at E2 is an inline criteria checklist; the ISA document is required at E3+.

> Cockpit + visualisation + code-map intelligence. See `RELEASES.md` for the full release narrative; this entry captures the `/preflight-ci` fixes (T494–T498) that shipped in the same cycle.

### Fixed — `/preflight-ci` Compose-stack hardening (T494–T504)

A series of fixes made the `/preflight-ci` local mirror match a dev's actual Compose stack instead of CI's service-container assumptions: Compose host-port introspection, password env-ref substitution, layered `.env` sourcing, `pyproject.toml` overrides, and protocol-suffix (`/tcp`) port parsing. The original symptom was DB/Redis auth failures because generated scripts used CI ports/credentials rather than the local stack's. Net: `scripts/preflight/compose_introspector.py` (new) + `script_generator.py`/`preflight.py` wire-through, covered by 103 preflight unit tests. (Full per-task detail lived in the development PRs; collapsed here for the public changelog.)

### Added — Framework-shipped `permissions.deny` rules for build + cache paths

Per the [claude.com large-codebases guidance](https://code.claude.com/docs/en/large-codebases), `Read` deny rules block explicit file opens (Read tool, `cat`/`head`/`grep` with a denied path) on paths that waste context. `.gitignored` paths are already excluded by Claude's built-in search, but build outputs and caches that get committed (or that show up in greps anyway) leak into the model's read budget. Framework template now ships 22 deny entries covering the common surfaces:

- Build outputs: `dist`, `build`, `.next`, `.nuxt`, `.turbo`, `.parcel-cache`, `.vite`, `.svelte-kit`, `.angular`
- Python caches: `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `.tox`, `.venv`, `venv`
- Coverage: `htmlcov`, `coverage`
- Generated / minified: `*.generated.*`, `*.min.js`, `*.min.css`, `*.map`

- **`hooks/settings.json`** — new `permissions.deny` block + `_deny_note` explaining the recursive-search caveat (deny only blocks explicit opens; `grep -r` still matches inside denied paths).
- **`scripts/install/install.sh`** — `install_settings` merge logic now unions `permissions.deny` (not just `permissions.allow`), so deny rules added to the framework template reach existing consumers via `refresh-v3`, not only fresh installs.

Verified against a consumer project: refresh merged 22 deny rules into the consumer's `.claude/settings.json` correctly.

### Fixed — Dashboard misread its root in vendored installs (architectural)

The dashboard's `project_root()` walker used `CLAUDE.md` as a marker file, which false-positive'd on `.claude/CLAUDE.md` (every vendored install has one). The `/visualize` generator's `_shared.py:project_root()` had the same shape with `docs/code-map.json` as the marker, false-positive'ing whenever `install.sh` had leaked the framework dev repo's own code-map into `.claude/docs/`. Result: dashboard read `.claude/docs/tasks/registry.json` (missing or empty) instead of `<project>/docs/tasks/registry.json`. Tasks tab returned 404 in clean installs, or — when a stale `tasks.html` from the framework dev repo had been rsynced in — silently served fixture data ("E01 Authentication / E02 Dashboard") to consumer dashboards. Framework dev-repo testing didn't catch this because in self-hosting mode `framework_root` and `project_root` coincide.

**Fix:** introduce `framework_root()` derived structurally from `__file__` (`Path(__file__).resolve().parents[N]`), and derive `project_root()` from it (if `framework_root.name == ".claude"`, project_root is `framework_root.parent`; else walk up for `.git` only — `CLAUDE.md` and `docs/code-map.json` are NEVER markers). Applied to both `scripts/forge/dashboard/server.py` and `skills/visualize/Tools/_shared.py`. `_render_via_generator` now writes to `project_root/docs/visualizations/`, not `framework_root` — visualizations are project artifacts. Confirmed end-to-end against a consumer project: all 8 dashboard routes HTTP 200, real 513-task registry rendering, zero fixture-string leaks.

- **`scripts/forge/dashboard/server.py`** — `framework_root()` + reworked `project_root()` + output landing fix.
- **`skills/visualize/Tools/_shared.py`** — same pattern, no marker-file walk.
- **`tests/dashboard/test_root_resolution.py`** — 6 tests synthesizing vendored installs and asserting both false-positive markers are ignored, including self-hosting case where the two roots legitimately coincide.
- **`tests/dashboard/test_tasks_smoke.py`** — end-to-end assertion that rendered HTML contains the project's real epic IDs and does NOT contain the fixture marker string `User authentication system`.

All 106 framework tests pass.

### Fixed — `install.sh` rsync was leaking framework `docs/` into consumer `.claude/`

The framework dev repo's `docs/` tree (self-documentation: code-map of the framework, planning history, debug audits, the framework's own task ISAs, orphan reference docs) was rsyncing into every consumer's `.claude/docs/`. None of it is referenced by framework runtime code, settings.json, templates, or `@`-imports. Pure pollution of consumer projects.

**Fix:** all three install modes (`fresh`, `refresh-framework`, `refresh-v3`) now exclude `docs/` entirely via `--exclude='docs'` + `--exclude='docs/**'`. Post-rsync cleanup adds `rm -rf <project>/.claude/docs/` + `<project>/.claude/daily/` + `<project>/.claude/scripts/memory/` to heal past leaks (these are all project_root data, never framework_root code).

### Removed — Framework-internal docs untracked from framework git

Prep for framework repo going public. Pure framework dev artifacts removed from git tracking (kept on disk for framework dev's own use, gitignored to prevent re-tracking):

- `docs/forge-flow/` (7 files: v2→v3 migration planning history)
- `docs/debug/create-pr-audit-2026-05-12.md` (dated dev audit)
- `docs/permission-profiles.md`, `docs/rules-system.md` (orphan reference docs)
- `docs/tasks/F-*/ISA.md` (5 files) and `docs/tasks/T001-heartbeat-commits/ISA.md` (framework's own task ISAs)

Only `docs/code-map.md` remains tracked under `docs/` in the framework's public face. 16 files git-rm'd, ~2,800 lines removed from public-facing history.

### Added — Doctrine: `rules/framework-vs-project-root.md`

Codifies the resolver distinction and the inclusion rule. Auto-loaded at every Forge Flow session start. Three sections: (1) two roots, two artifact classes — `.claude/` is framework_root (CODE), parent is project_root (DATA); (2) what ships into consumer `.claude/` — inclusion test is "required by framework runtime functionality," default is exclude; (3) public-repo discriminator for what stays tracked in framework git when the repo goes public.

### Added — `/visualize` skill (F-VISUALIZE)

Render structured Forge Flow artifacts as standalone interactive HTML in `docs/visualizations/`. Generators, not replacements — markdown and JSON remain source of truth.

- **`skills/visualize/SKILL.md`** — skill definition with invocation, design principles, dispatcher.
- **`skills/visualize/Tools/visualize.py`** — generator dispatcher; discovers generators by scanning `Tools/generators/*.py` for a module-level `register()` function. Adding a generator = one file, no dispatcher edit.
- **`skills/visualize/Tools/generators/code_map.py`** + **`templates/code-map.html`** — three-layer drill-down (modules → files → symbols) over `docs/code-map.json`. Cytoscape.js + dagre vendored inline (~654 KB). Symbol-level "lineage mode" showing which files import each class/function via import-linkage. Role filter sidebar with counts; meta-line summary; small-node label fix (labels outside circles).
- **`skills/visualize/Tools/generators/tasks.py`** + **`templates/tasks.html`** — two-layer kanban: epic-level board → per-epic task-level board with detail drawer. Columns are viewport-height fixed (`flex: 1 1 0; min-width: 0`), with internal lane scrolling for overflow. State-color coding (pending / ready / in_progress / continuation / pr_pending / completed / blocked). Replaced the original force-directed DAG view, which was rejected during VERIFY for being chaotic and non-stable under drag (D-V8 in F-VISUALIZE ISA).
- **`docs/tasks/F-VISUALIZE/ISA.md`** — feature ISA with the design pivot from DAG → kanban documented.

### Added — `forge dashboard` (F-DASHBOARD)

A local read-only HTTP cockpit serving every Forge Flow artifact under one URL with SSE live-reload. Read-only by design — mutation continues to flow through the forge CLI per CLAUDE.md.

- **`scripts/forge/forge.py`** — new `dashboard` subcommand parser with `--host`, `--port`, `--no-open`, `--once` flags. Lazy-imports the dashboard module so `forge --help` doesn't pull it in.
- **`scripts/forge/dashboard/__init__.py`** — `DEFAULT_PORT = 4847`, `DEFAULT_HOST = "127.0.0.1"`.
- **`scripts/forge/dashboard/server.py`** — `ThreadingHTTPServer` + handler with routes `/`, `/tasks`, `/code-map`, `/isas`, `/isa/<feature>`, `/memory`, `/daily`, `/registry`, `/burndown`, `/events` (SSE), `/static/<file>`. Friendly EADDRINUSE / EACCES error pages with `forge dashboard --port <n>` hint and exit code 2 (no Python traceback). Generator routes lazy-load via `importlib.util.spec_from_file_location` so adding a new generator under `skills/visualize/Tools/generators/` exposes it automatically.
- **`scripts/forge/dashboard/watcher.py`** — singleton mtime-poll watcher with subscribe / unsubscribe / start / stop API. Background daemon thread polls `DEFAULT_WATCH` every 2 s, broadcasts changed paths to all subscriber queues. Drop-oldest on `Queue.Full` so a stuck subscriber never wedges the broadcaster. Stdlib-only (`threading + queue`); no `watchdog` / `pyinotify` / fsevents.
- **`scripts/forge/dashboard/render/`** — per-tab renderers: `index.py` (tab bar shell + inline SSE client + RELOAD_MAP), `isas.py`, `memory.py`, `daily.py`, `registry_view.py` (collapsible JSON tree), `burndown.py` (git-derived SVG chart with `.forge/cache/burndown.json` cache), `markdown.py` (stdlib Markdown → HTML mini-renderer with YAML-frontmatter stripping — fixes infinite-loop bug on `---` separators inside docs).
- **`scripts/forge/dashboard/static/`** — `dashboard.css` (chrome + live-indicator with color states + pulse animation), `content.css` (typography for ISA list, memory feeds, daily timeline, empty-state cards), `registry.css` (JSON tree + summary chips), `burndown.css` (chart panel + SVG element styles + delta color coding).
- **`scripts/forge/dashboard/README.md`** — dedicated reference doc covering invocation, all seven tabs, the SSE / watcher architecture, route table, file map, troubleshooting, and how to add a tab.
- **`docs/tasks/F-DASHBOARD/ISA.md`** — feature ISA with 12 ISCs all verified ✅ (probe results + dates filled in the Verification table). Phase set to `verified`.

### Updated — documentation

- **`CLAUDE.md`** (top-level + as-installed) — new row in the skills/CLI table for `forge dashboard` describing the seven tabs, default URL, SSE live-reload, read-only semantics, and flag set.
- **`README.md`** — `/visualize` and `forge dashboard` added to the "What Forge Flow gives you" primitives table and to Core Commands; `scripts/forge/` line updated to mention the dashboard server; Documentation table cross-references both new feature READMEs and ISAs.
- **`CHEATSHEET.md`** — `/visualize` added to v3.1+ deferred commands table; new Dashboard section with tab-by-tab source map; full CLI invocation block for `python3 .claude/scripts/forge/forge.py dashboard …`.
- **`skills/visualize/SKILL.md`** — Invocation section now cross-references `forge dashboard` as the unified single-URL entry point.

### Verified

All 13 ISCs across F-VISUALIZE (1) and F-DASHBOARD (12) pass under curl + Playwright probes. SSE end-to-end verified (`event: file-changed\ndata: docs/tasks/registry.json` emitted within 2–3 s of `touch`). Read-only invariant verified by mtime probe before/after an 8-route tab tour: no source files modified. Zero external Python deps verified by clean stdlib-only import.

## [v3.1.2] — 2026-05-12

### Fixed — Session Protocol First rule is now actually enforced

Previously, `skills/reflect/SKILL.md` carried a "Session Protocol First — always start with the session protocol" rule that was aspirational only. Nothing in the framework created a session file at SessionStart; the rule only fired when the user explicitly invoked `/reflect`. A long Forge Flow session could run end-to-end with an empty `active/` directory and the rule never tripped.

**Behavior change:** `hooks/session/session-context.py` now auto-creates a minimal session file when `active/` is empty, at every SessionStart (startup / resume / compact matchers). The session ID format and storage path match the doctrine in `reference/12-session-protocol.md`.

- **`hooks/session/session-context.py`** — new `_auto_create_session_file()` runs before `find_active_session()`. Creates `active/session-{YYYYMMDD-HHMMSS}-{4-random}.md` with scope intentionally empty (filled in by the agent or `/reflect resume` when work begins), Conflict Check deferred, Active Skill / Active Agent tables set to `none`/`-`. Race-safe (re-checks inside the create path) and never blocks SessionStart on filesystem errors — falls back silently to the pre-auto-create `S:NONE` behavior.
- **`skills/reflect/SKILL.md`** — Session Start Protocol section rewritten to reflect that Steps 1–2 are now framework-owned. "Session Protocol First" key rule rephrased: "A session file always exists — the SessionStart hook auto-creates one if `active/` is empty."
- **`reference/12-session-protocol.md`** — Steps 1 and 2 marked *(auto)* with a callout explaining that the framework now owns file existence at the hook layer; the remaining steps describe enrichment when real work begins.
- **`tests/wiring/test_session_auto_create.py`** (new) — 5 pytest cases: auto-create on empty active/, file shape (required scaffolding sections + downstream-parsable tables), idempotency on re-run, `S:<id>` in stdout, and active-dir creation when missing. All 5 pass.

### Migration notes

Existing consumer projects already have populated `active/` directories. The change is a no-op for them: if a session file is present, the hook leaves it alone (existing find-active-session logic still wins). Refreshing via `install.sh --mode refresh-v3` picks up the new hook on the next SessionStart and the next empty-active/ event auto-creates.

### Verified

- 5/5 new tests pass; 29/29 wiring tests pass (no regression).
- Manual smoke tested against fresh tmp project (consumer layout): hook creates `session-{id}.md`, reports `S:<id>` instead of `S:NONE`, re-run is idempotent.
- The doctrine line in `skills/reflect/SKILL.md` now describes real behavior rather than aspirational behavior.

## [v3.1.1] — 2026-05-12

### Added — `/create-pr` invocation doctrine across code-shipping skills

Audit + patch of every Forge Flow skill that ships code, ensuring each one explicitly routes its PR wrap-up through `Skill("create-pr")` instead of leaving the agent to improvise (which historically led to raw `gh pr create` slips observed in a consumer project on 2026-05-12). The doctrine guard is a grep-based pytest that fails loud if any new skill is added with raw `gh pr create`.

**Patched skills** (GAP-implicit → explicit `/create-pr` handoff):

- `skills/new-feature/SKILL.md` — phases now end in `Commit → PR (/create-pr)`; new Step 4 invokes `Skill("create-pr")`; "Skills I invoke" list added.
- `skills/fix-bug/SKILL.md` — new Step 5 invokes `Skill("create-pr")` after Step 4 Commit; calls out `silent-failure-hunter` pre-flight; "Skills I invoke" list added.
- `skills/refactor/SKILL.md` — new Step 7 invokes `Skill("create-pr")` after Step 6 Commit; calls out `code-reviewer` and `type-design-analyzer` pre-flight; "Skills I invoke" list added; Principles get a `never raw gh pr create` rule.
- `skills/implement-features/SKILL.md` — Phase 3 (Checkpoint) now offers batched PR via `Skill("create-pr")`; Phase 4 (Session End) mandates the final PR; PR-granularity note explains per-checkpoint cadence is the default; "Skills I invoke" + See Also updated.
- `skills/release/SKILL.md` — new "PR-first option" section invokes `Skill("create-pr")` BEFORE tag for projects that review release-prep commits; non-breaking (default behavior unchanged); honors `.release-config.json` `prFirst` flag when present.

**Doctrine handoff** (`/reflect` is N-A but needed clarification):

- `skills/reflect/flows/resume.md` — new "Wrap-up Handoff to `/create-pr`" section explicitly tells the resuming agent that when the resumed task ships code, `Skill("create-pr")` is mandatory at Step 7.5 (between Commit and Verification). The mandatory checklist includes the PR-via-create-pr check for code-shipping tasks. `/reflect` itself still does NOT invoke `/create-pr` (category error).

**Doctrine guard test** (new):

- `tests/wiring/test_no_raw_gh_pr_create.py` — pytest that greps every skill markdown for `gh pr create` and fails if anything outside `skills/create-pr/SKILL.md` invokes it. Doctrine-prose whitelist allows lines that DISCUSS the command (e.g. "never use raw `gh pr create`") via co-occurrence with `Skill("create-pr")`, `/create-pr`, `never`, `bypass`, etc. Negative-tested by inserting a fake violation and confirming the test catches it.

### Migration notes

Running `install.sh --mode refresh-v3` in any Forge-installed project picks up the patched skill workflow files and the doctrine guard test. The change is non-breaking: skills that haven't refreshed continue to work, just without the explicit `/create-pr` handoff in their workflow text. After refresh, the agent driving each skill sees the explicit `Skill("create-pr")` call at the wrap-up phase.

**Project-level overrides:** if a project ships its own override of any patched skill (e.g. a project-specific `/new-feature` at `.claude/skills/new-feature/SKILL.md` that supersedes the framework version), the override is preserved — `install.sh` only replaces framework-shipped skill files, not project-specific overrides. Whether the override carries the `/create-pr` handoff is the project's call.

### Not changed

- `/create-pr` itself — only callers were updated.
- `pr-review-toolkit` specialist agents — out of scope.
- Codex-exec integration — out of scope.
- No "dog-food PR" on the Forge framework repo — framework changes ship via direct push to main per `feedback_claude_forge_no_prs`.

### Verified

- All 5 GAP-implicit findings patched. `Read`/`grep` confirms each skill SKILL.md now contains `Skill("create-pr")` or the equivalent invocation at the wrap-up phase.
- `/reflect`'s `resume.md` contains the "Wrap-up Handoff to `/create-pr`" section and the Step 7.5 PR step.
- `tests/wiring/test_no_raw_gh_pr_create.py` — 2/2 tests pass against current tree; negative test (synthetic violation inserted under `skills/fix-bug/_test_violation.md`) caught the violation correctly; removed.

## [v3.1.0] — 2026-05-12

### Added — Background Agent Checkpoint Discipline

A heartbeat-commits / progress-checkpoint contract for background agents working in git worktrees. Motivated by a real consumer-project incident (2026-05-12) where a 14-minute background `Engineer` run produced two novel triage findings that never landed in git because the worktree was reaped mid-`vitest`.

- **Algorithm doctrine v1.1.0** (`ALGORITHM/v1.1.0.md`): new "Background Agent Checkpoint Discipline" section covering periodic checkpoint commits (~5 min / ~10 actions), `checkpoint-before-stuck-operation`, parent-side heartbeat reads, and no-commit-no-reap safety. New OBSERVE Gate D fires on background-agent context. `ALGORITHM/LATEST` bumped from `1.0.0` → `1.1.0`.
- **Framework-agent contract** (`agents/architect.md`, `agents/devops.md`, `agents/project-manager.md`, `agents/quality-engineer.md`, `agents/security-boss.md`): each agent now ships a "Checkpoint Discipline" section binding it to the contract when run as a background agent. `agents/README.md` documents the inherited contract for specialists.
- **`forge agent heartbeat <branch>`** (`scripts/forge/forge.py`): new CLI subcommand that returns the freshest commit + age + STALE flag + freshest `wip:`/`checkpoint:` commit for a given branch. JSON via `--json`. Replaces transcript-tailing as the canonical way to read background-agent progress.
- **`scripts/forge/worktree_safe_cleanup.py`**: new helper that refuses to delete a worktree with uncommitted changes; with `--force-promote`, commits the dirty state as `wip(reaped): final state at cleanup` and prints the SHA. For Forge-owned cleanup paths only.
- **`hooks/forge/checkpoint-nudge.py`** (PostToolUse advisory): emits a non-blocking advisory after N tool actions (default 10) without a new commit, only when running in background-agent context (`WORKTREE_AGENT_ID` env set OR branch starts with `wip-`). Wired into `hooks/settings.json` PostToolUse with `matcher: ""` so it fires on every tool action. Tunable via `CHECKPOINT_NUDGE_THRESHOLD` env; silenceable via `CHECKPOINT_NUDGE_DISABLED=1`.
- **Protocol doc** (`reference/protocols/background-agent-checkpoints.md`): worked-example version of the contract with end-to-end recovery walkthrough from the consumer-project incident.

### Migration notes

Running `install.sh --mode refresh-v3` in any Forge-installed project picks up:
- The new doctrine file and the bumped `ALGORITHM/LATEST` pointer
- The new `agents/*.md` Checkpoint Discipline sections
- The new `scripts/forge/worktree_safe_cleanup.py` + `forge agent heartbeat` subcommand
- The new `hooks/forge/checkpoint-nudge.py` + the `hooks/settings.json` PostToolUse entry
- The new protocol doc

**PAI-side follow-up (out of scope for this release):** the PAI-shipped `Engineer`, `Forge`, and `Anvil` agents live at `~/.claude/agents/` (not in this repo) and require a parallel update with the same Checkpoint Discipline section. That work must be done from a PAI session — this Forge release does NOT touch sibling projects.

### Not changed

- The Claude Code `Agent` tool itself (out of scope per upstream / harness ownership)
- No new long-running daemon process; the nudge rides on the existing PostToolUse hook surface
- No nested watchdog inside agents — agents are responsible for their own checkpoint cadence
- Existing tasks, registry, custom specialist agents, project-memory all unchanged

### Verified

- Doctrine + `LATEST` pointer present (`Read`, `cat`).
- Each framework agent contains "Checkpoint Discipline" section (`Grep`).
- `worktree_safe_cleanup.py`: refuses on dirty worktree (positive test); promotes + deletes with `--force-promote` (`git log` confirms `wip(reaped):` commit).
- `forge agent heartbeat`: returns expected JSON shape; STALE flag correct under `--stale-threshold 1`; surfaces `latest_checkpoint` separately from head on a multi-commit branch.
- `checkpoint-nudge.py`: silent outside background context; fires at threshold inside; state file persists per-branch; counter resets when head SHA changes.
- `hooks/settings.json` PostToolUse contains the new hook entry.
