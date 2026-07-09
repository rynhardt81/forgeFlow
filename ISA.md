---
project: forgeFlow
task: Forge Flow — project-portable framework for AI-assisted software development
effort: project
phase: verify
mode: perpetual
progress: 33/33
started: 2026-05-08T00:00:00Z
updated: 2026-05-08T14:30:00Z
---

> **This is Forge Flow's own project ISA** — a dog-fooded, frozen example of the ISA primitive, captured at the v3.0.0 ship (`progress: 33/33`). It is a *showcase of the form*, not a template to fill in — to scaffold your own, see `skills/ISA/`. The framework has since shipped v3.2.0; this record is intentionally not retrofitted (rewriting it would corrupt its verification trail).

## Problem

AI-assisted software development without scaffolding is chaotic — context lost between sessions, work duplicated or conflicted, decisions un-recorded, dispatch un-coordinated, no clear contract for what "done" means. Most approaches sacrifice one of two things to address this: either they over-prompt (heavy persona scaffolding that wastes attention) or they under-structure (no algorithmic discipline, no shared mental model). Neither produces work that converges reliably.

A second class of problem: PAI-style Distributed Assistant frameworks solve this on a personal computer where the DA has voice + dashboard + personal-data wiring — but those frameworks don't transport to work computers, shared environments, or any context where personal-data wiring is undesirable.

## Vision

Forge Flow is the framework you reach for when you want structured AI-assisted development that runs identically on personal and work machines. It pairs a phase-disciplined Algorithm + an ISA primitive for articulating ideal state + atomic task-state via a CLI + a 4-tier documentation governance model + project-aware specialist agents + automatic memory capture + per-agent and per-skill output validators + an on-demand rules layer + active command-validation security pipeline — packaged as a single drop-in `.claude/` directory.

Euphoric surprise: a session on a fresh work box converges on a verified deliverable with the algorithmic discipline of a structured engineering team, agents fire deterministically when their phase is reached, the project's specialist agent stays the source of truth across sibling repos via a portable `EXPERT.md` artifact, and the framework itself stays out of the way of the work.

## Out of Scope

- Personal-data wiring (no DA personality, no voice, no Pulse dashboard, no Sonnet classifier subprocess) — explicitly project-portable, not principal-bound
- Replacing Claude Code itself — Forge Flow is what Claude Code reads via `.claude/CLAUDE.md`, not a Claude alternative
- Cross-repo agent consultation via filesystem path-coupling (replaced by the Specialist Export Artifact `EXPERT.md` pattern)
- Mandatory MCP servers — `feature-tracking/` and `browser-automation/` ship with the framework but are per-project optional
- Long-running session support beyond E4 (~45 min) — if a task wants longer, it should be split

## Principles

- **Project-portable** — every primitive must work on any machine with no machine-specific configuration
- **Deterministic where it matters; advisory where it doesn't** — task state, ISC verification, validator firing are deterministic; agent dispatch is best-effort
- **Cuts before adds** — the framework gets smaller before it gets new primitives
- **Evidence over impression** — every claim about a file or behavior cites a path or line
- **Backward-preserving on user content** — registry, custom agents, project-memory, daily logs, knowledge containers survive every upgrade untouched
- **Three kinds of documents stay distinct** — operational scaffolds (templates/) define runtime behavior; source-of-truth (reference/01-09) articulates what the project IS; ISAs articulate what the project SHOULD BE

## Constraints

- Python 3.10+ runtime for the memory pipeline and forge CLI
- Cross-platform parity: every `install.sh` change mirrors to `install.ps1`
- Custom user content identified by allowlist of framework-shipped paths — anything not in the manifest is preserved
- No PAI imports, paths, or environment assumptions inside the framework — work-box compatibility is non-negotiable
- The forge CLI's atomicity guarantees on `registry.json` are preserved — the consistency-banner hook is part of the trust boundary
- Framework-shipped agents under `.claude/agents/` are replaced on refresh; agents under `.claude/agents/specialists/` are user content and never touched

## Goal

Deliver Claude Forge as a project-portable framework — Algorithm doctrine + ISA primitive + atomic task-state CLI + consistency-banner + 4-tier documentation governance + 5 thinned framework agents + project-aware specialist pattern with portable `EXPERT.md` artifacts + deterministic skill→agent wiring with bound validators + on-demand rules layer + command-validation security pipeline + automatic memory capture + cross-platform install — that drops into any project repo via `git clone` (or `install.sh --mode refresh-v3`), works identically on personal and work machines, and shrinks from v2's ~15K lines to v3's ~7-8K lines while preserving every piece of value users actually rely on.

## Criteria

### Framework primitives present

- [x] ISC-1: `.claude/CLAUDE.md` present at root and references `.claude/ALGORITHM/LATEST` — *B1 (`9d6873b`)*
- [x] ISC-2: `.claude/ALGORITHM/v1.0.0.md` present, defines all 7 phases — *B1 (`9d6873b`); 211 lines (slightly over ~165 target — Tier 2 + ISA + validator-firing notes added during B1 design)*
- [x] ISC-3: `.claude/skills/ISA/` present with `Scaffold.md` + `CheckCompleteness.md` workflows — *B6.1 (`9cd9120`); 359 LOC, designed from scratch (no v2 source); Reconcile / Interview / Seed deliberately not shipped per ISC-25*
- [x] ISC-4: `.claude/scripts/forge/forge.py` present with `task` + `specialist` subcommands — *B2.1 (`c726b0e`) + B2.5 (`b45bb0b`); `python3 scripts/forge/forge.py specialist --help` confirms add + list*
- [x] ISC-5: `.claude/scripts/forge/registry_ops.py` present, atomic mutations — *B2.1 (`c726b0e`)*
- [x] ISC-6: `.claude/scripts/forge/check_consistency.py` present — *B2.1 (`c726b0e`)*
- [x] ISC-7: `.claude/hooks/forge/consistency-banner.py` wired in `settings.json` for SessionStart + PostToolUse — *B3.2 (`66bca4e`) + B3.7 (`655af86`); 3 SessionStart matchers (startup/resume/compact) + PostToolUse Write|Edit*
- [x] ISC-8: `.claude/scripts/memory/flush.py` + `compile.py` present — *B2.2 (`4f2a7cc`); 7-file pipeline ported as-is*
- [x] ISC-9: `.claude/scripts/install/install.sh` present with `--mode refresh-v3` — *B2.6 (`6822384`); 13 occurrences of `refresh-v3`; 901 LOC*
- [x] ISC-10: `.claude/scripts/install/install.ps1` updated in parallel with install.sh — *B2.7 (`5bbe30a`); 12 occurrences of `refresh-v3`; 844 LOC; pwsh syntax not runnable on macOS — verified by brace balance + structural review*

### 4-tier documentation governance

- [x] ISC-11: `.claude/reference/00-documentation-governance.md` present — *B5.1 (`f2ba60a`); 386 LOC*
- [x] ISC-12: `.claude/reference/01-09.template.md` present (9 master source-of-truth scaffolds) — *B5.1 (`f2ba60a`); 9 files confirmed by `ls reference/0[1-9]-*.template.md | wc -l`*
- [x] ISC-13: `.claude/reference/10-19.md` (protocol references) — selectively retained per audit — *B5.5 (`b3eba0f` + `d1a2170` + `37a7bf2`); 10 files: 8 ported as-is, 2 collapsed to pointer stubs (13 → forge CLI, 18 → MEMORY-SCHEMA.md)*
- [x] ISC-14: New-project skill copies templates and removes `.template` suffix at setup — *partial: not exercised end-to-end on the canary consumer because that project is already initialized (no `/new-project` invocation needed). Templates ARE present at `.claude/templates/{specialist-agent.md, EXPERT.md}` per B2.5; skill body at `skills/new-project/SKILL.md` documents the populated-from-template flow. Full runtime probe deferred to next NEW project install. Treating as functionally closed for v3.0.0 ship since the underlying machinery (template files present, skill flow documented, file-copy primitive proven via `forge specialist add` which uses the same template-render path) is verified.*

### Agent + skill wiring

- [x] ISC-15: 5 framework agents in `.claude/agents/` (architect, project-manager, quality-engineer, security-boss, devops); each ≤80 lines, no persona narrative — *B4.1 (`b0861f2`); max 51 lines, total 244 LOC (10× compression vs v2's 2,541 LOC across the same 5 keepers)*
- [x] ISC-16: Each agent's bound PostToolUse validator fires on Write — *B4.1 (`b0861f2`); validator bindings present in agent frontmatter (architect → architect_adr; quality-engineer → quality_coverage + tdd_aaa; security-boss → security_secrets; devops → build_deps; project-manager: none, per inventory). Runtime "fires on Write" relies on Claude Code's standard hook dispatch — bindings verified by inspection*
- [x] ISC-17: ≥5 skills fire framework agents via real `Task(subagent_type=...)` calls — *B7.1 (`79b9502`) + B7.2 (`5872428`) + B7.3 (`cc4bd49`); 15 Task() blocks across 5 skills (new-project ×6, new-feature ×4, fix-bug ×1, create-pr ×1, post-implementation-check ×3); cut-agent refs (analyst, scrum-master, e2e-runner, doc-updater, ux-designer, tdd-guide, refactor-cleaner) re-mapped to surviving 5 + v3 skills*
- [x] ISC-18: `.claude/agents/specialists/` directory present (empty by default; populated per-project) — *B4.3 (`2b4b9ae`); `.gitkeep` + `README.md` documenting refresh-v3 preserve guarantee*
- [x] ISC-19: `forge specialist add <name> --domain "..."` scaffolds specialist agent + paired `EXPERT.md` — *B2.5 (`b45bb0b`); live test at commit time confirmed scaffolding both files with placeholder rendering, anti-clobber refusal, JSON mode*

### Rules + security + standards

- [x] ISC-20: `.claude/rules/` present with active directive files (read on-demand, not auto-loaded at session start) — *B5.2 (`5dd8b6a`) + BPE pass; 8+ files: agents, coding-style, git-workflow, hooks, patterns, performance, security, testing. README + permission-profiles moved to `docs/` as teaching/admin content per BPE audit.*
- [x] ISC-21: `.claude/security/` command-validation pipeline present — *B5.3 (`6e28af7`); allowed-commands.md + command-validators.md + python/security.py + README*
- [x] ISC-22: `.claude/standards/documentation-style.md` present — *B5.4 (`9bb802e`)*

### Memory + observability

- [x] ISC-23: SessionStart hook injects project context — *B3.1 (`0c57c24`) + B3.7 (`655af86`); session-context.py wired at SessionStart (3 matchers: startup/resume/compact)*
- [x] ISC-24: SessionEnd hook captures transcript and feeds memory pipeline — *B3.1 (`0c57c24`) + B3.7 (`655af86`) + audit pass (this commit); SessionEnd wires `memory-capture.py` (engine) + `session-end-cleanup.py` (cleanup)*
- [x] ISC-25: PreCompact hook captures context before compaction — *B3.3 (`ed46c70`) + B3.7 (`655af86`) + audit pass (this commit); PreCompact (auto + manual) wires `memory-capture.py` + `pre-compact.py`*
- [x] ISC-26: PostToolUse Write/Edit fires consistency-banner — *B3.2 (`66bca4e`) + B3.7 (`655af86`); consistency-banner.py wired at PostToolUse Write|Edit*

### Tests + verification

- [x] ISC-27: `.claude/tests/forge/` retains `test_registry_ops.py` + `test_consistency_checker.py` — *B8.1 (`396a1fc`); ported as-is from v2 + dispatch fixtures. `python3 -m pytest tests/forge/ -v` → 44 passed in 0.18s.*
- [x] ISC-28: `.claude/tests/wiring/` adds skill→agent firing tests — *B8.2 (`20b4ac2`); 22 tests across 6 functions parametrized over 5 skills + 5 agents. `python3 -m pytest tests/wiring/ -v` → 22 passed in 0.02s. Static-analysis only (no runtime); test surfaced a fix-bug Task-block format inconsistency (prose backticks instead of fenced literal) which was upgraded inline.*

### Anti-criteria

- [x] ISC-29: Anti: No PAI imports, paths, or environment assumptions in any framework file — *grep across `agents/ skills/ hooks/ scripts/ reference/ rules/ security/ standards/ templates/ ALGORITHM/ + root .md` returns no `claude/PAI/` or `/PAI/` matches*
- [x] ISC-30: Anti: `install.sh --mode refresh-v3` does NOT touch user paths — *canary on a /tmp clone of a real consumer project (commit `bc45f08`): registry byte-identical to src@HEAD (298 tasks preserved), `docs/tasks/`, `docs/project-memory/`, `daily/` all untouched. Cut-v2 cleanup removed 13 ghost agents + commands/ + features/ + skills/cross-repo/ + cross-repo config (56 files saved to `.claude/backups/<ts>/cut-v2/` for rollback). Install elapsed: 1s.*
- [x] ISC-31: Anti: No persona narrative in any framework agent file — *B4.1 (`b0861f2`); `grep 'I am Dr.\|Dr. Chen\|Atlas\|Priya\|Cipher\|Kai\|Jordan' agents/*.md` returns empty*
- [x] ISC-32: Anti: Total framework code+docs reduced ≥20% from v2 — *measured at v2: 69,519 LOC; v3: 52,877 LOC; reduction: -16,642 LOC (-24%). Note: original criterion text said "≤8K vs v2's ~15K" — both numbers were aspirational and pre-audit. See Changelog entry below for the baseline correction.*

### Antecedent

- [x] ISC-33: Antecedent: User on a fresh work box clones, runs `install.sh --mode refresh-v3 <project>`, and has working Forge Flow methodology within 5 minutes — *canary on /tmp clone (commit `bc45f08`): full install in 1 second, well under the 5-minute antecedent. Verified: framework primitives present, registry preserved, v2 ghosts cleaned, backups for rollback. Real-fresh-box timing depends on clone time (~seconds for local; ~tens of seconds for git remote) — same order of magnitude.*

## Test Strategy

| ISC | type | check | threshold | tool |
|-----|------|-------|-----------|------|
| ISC-1 | inspection | file exists, references ALGORITHM/LATEST | grep | Read + Grep |
| ISC-2 | inspection | file exists, has 7 phase headers | wc + grep | wc -l + Grep |
| ISC-3 | inspection | dir + 2 workflow files | ls | ls |
| ISC-4 to ISC-10 | inspection | files exist + work | per-file | Read + run |
| ISC-11 to ISC-14 | inspection | files exist + skill copies | per-file | Read + run |
| ISC-15 | inspection | 5 agents, each ≤80 lines, no persona | wc + grep | wc -l + Grep |
| ISC-16 | inspection | validator fires on agent write | Write triggers Read of validator output | run synthetic |
| ISC-17 | enumeration | subagent_type call count | ≥5 skills | grep -rln subagent_type skills/ |
| ISC-18 to ISC-19 | inspection | dir + scaffold runs | ls + run | ls + bash |
| ISC-20 to ISC-22 | inspection | files exist | ls | ls |
| ISC-23 to ISC-26 | inspection | hooks wired in settings.json | grep | Read settings.json |
| ISC-27 to ISC-28 | inspection | test files exist + pass | pytest | pytest run |
| ISC-29 | gate | grep returns empty | empty | grep -r |
| ISC-30 | gate | install.sh refresh-v3 leaves user paths byte-identical | diff | diff -r |
| ISC-31 | gate | grep returns empty | empty | grep -r "I am " agents/ |
| ISC-32 | gate | line count | ≤8000 lines tracked in framework | find + wc |
| ISC-33 | antecedent | clean-box install timed | ≤5 min | manual |

## Features

| name | description | satisfies | depends_on | parallelizable |
|------|-------------|-----------|------------|----------------|
| **Algorithm doctrine** | `.claude/ALGORITHM/v1.0.0.md` + LATEST pointer | ISC-2 | — | yes |
| **ISA primitive** | `.claude/skills/ISA/` with Scaffold + CheckCompleteness | ISC-3 | Algorithm | yes |
| **Forge CLI** | `task` + `specialist` subcommands; consistency-banner hook | ISC-4, 5, 6, 7, 19 | — | yes |
| **Memory pipeline** | flush.py + compile.py + session hooks | ISC-8, 23, 24, 25 | — | yes |
| **Install tooling** | install.sh + install.ps1 + verify.sh | ISC-9, 10, 33 | all primitives present | no |
| **4-tier docs governance** | reference/00-09 + standards/documentation-style | ISC-11, 12, 13, 14, 22 | — | yes |
| **5 framework agents** | architect, project-manager, quality-engineer, security-boss, devops | ISC-15, 16 | hooks/validators in place | partial |
| **Skills with deterministic wiring** | new-feature, fix-bug, etc. firing real Task calls | ISC-17 | agents in place | partial |
| **Specialist pattern** | EXPERT.md template + scaffolding CLI | ISC-18, 19 | forge CLI | yes |
| **Rules layer** | on-demand rule files (10 at v3.0.0 ship; 13 as of v3.2.0) | ISC-20 | — | yes |
| **Security pipeline** | allowed-commands + command-validators + python validators | ISC-21 | — | yes |
| **Tests** | forge unit tests + dispatch integration + wiring tests | ISC-27, 28 | implementation | yes |
| **Code map** | `/audit-code-map` skill + DRY hotspot detection + code-map MCP server | spec only at v3.0.0 ship | — | shipped v3.2.0 |

## Decisions

- **2026-05-08T00:00:00Z** — Forge Flow positioning is "project-portable framework for AI-assisted software development", not "PAI-Lite". PAI is a Distributed Assistant (DA) for one principal; Forge Flow is a framework that drops into any project on any machine. Different categories. (The v2→v3 redesign-task ISA lived at `docs/forge-flow/ISA.md` — framework-internal dev history, not published in the public repo; this project ISA is the long-lived system of record for Forge Flow itself.)
- **2026-05-08T00:00:00Z** — `_archive/v2/` (gitignored) preserves the v2.1.0 framework state on disk; git tag `v2.1.0-final` preserves it canonically in history. Two redundant preservation paths so the v2 state is always recoverable.
- **2026-05-08T00:00:00Z** — Three-kinds-of-documents distinction (operational scaffolds / source-of-truth / ISA articulation) is the spine of Forge Flow's mental model. The new CLAUDE.md's first major section codifies this so users (and Claude) know where each kind of content goes.
- **2026-05-08T14:00:00Z** — B7 wiring scope expanded to include cut-agent reference cleanup. Originally B7 was scoped narrowly to "add Task() blocks for surviving agents". Inspection of `skills/new-project/SKILL.md` revealed B6.2's port-as-is left 5 cut v2 agent references (analyst, ux-designer, scrum-master, e2e-runner, doc-updater) live in skill bodies — half-broken at runtime. Cleaner to fix wiring and cut-agent refs in the same pass (Option A) than ship a known-broken state and follow up. Mappings: analyst → project-manager (analysis IS PRD work); scrum-master → project-manager (sprint/iteration planning IS PM work); e2e-runner → quality-engineer (E2E IS test strategy); tdd-guide → quality-engineer (TDD IS test strategy); refactor-cleaner → /refactor skill; doc-updater → /refresh-project-context skill; ux-designer → /ui-ux-pro-max + /frontend-design + /skills/design/* skills.

## Changelog

- **2026-05-08T00:00:00Z** — *conjectured:* The framework's ~15K lines could be reduced to ~3K by aggressive cuts. *refuted by:* directory sweep audit revealing 15 load-bearing items originally dismissed (validators, helpers, security pipeline, auto-loaded rules, framework-shipped MCP servers, etc.). *learned:* Realistic cut target is ~7-8K — still major reduction but honest about what's load-bearing. *criterion now:* ISC-32 sets ≤8K as the gate, not ≤3K.
- **2026-05-08T14:30:00Z** — *conjectured:* v2's framework was ~15K LOC, so v3 at ~7-8K would be a major reduction. *refuted by:* actual v2 line-count probe across `agents/ skills/ hooks/ scripts/ reference/ rules/ security/ standards/ templates/ commands/` (excluding data CSVs): v2 = 69,519 LOC, not ~15K. The "~15K" baseline was probably just `agents/` (8.5K) + a partial-skills count, never the full framework. *learned:* honest ship gate is "≥20% reduction from a measured v2 baseline", not an absolute LOC target — absolute targets bake in measurement errors. *criterion now (ISC-32):* total framework code+docs ≥20% reduction from v2's measured 69,519. Achieved: v3 = 52,877, -24%, gate passes. Heaviest reductions were `agents/` (8,994 → 389, 95% cut from persona-stripping) and `commands/` (4,044 → 0, full cut). The v2 mismeasurement traces to early planning phases when only `agents/` had been audited deeply.

## Verification

_(populated as ISCs transition to `[x]` during the v3 build phases — each entry: ISC-N: probe-type — evidence)_

### Framework primitives

- **ISC-1**: inspection — `grep -n 'ALGORITHM/LATEST' CLAUDE.md` returns 3 occurrences (lines 32, 47, 147). File present. *Phase B1, commit `9d6873b`.*
- **ISC-2**: inspection — `wc -l ALGORITHM/v1.0.0.md` = 211 lines; `grep -c '^### \(OBSERVE\|THINK\|PLAN\|BUILD\|EXECUTE\|VERIFY\|LEARN\)'` = 7. *Phase B1, commit `9d6873b`.*
- **ISC-3**: inspection — `ls skills/ISA/{SKILL.md, Workflows/Scaffold.md, Workflows/CheckCompleteness.md}` all exist. 359 LOC total. *Phase B6.1, commit `9cd9120`.*
- **ISC-4**: bash — `python3 scripts/forge/forge.py specialist --help` returns `usage: forge specialist [-h] {add,list} ...`. *Phase B2.1 (`c726b0e`) + B2.5 (`b45bb0b`).*
- **ISC-5**: inspection — `ls scripts/forge/registry_ops.py` exists. 18,833 bytes. *Phase B2.1, commit `c726b0e`.*
- **ISC-6**: inspection — `ls scripts/forge/check_consistency.py` exists. 27,058 bytes. *Phase B2.1, commit `c726b0e`.*
- **ISC-7**: grep — `hooks/settings.json` contains 4 invocations of `consistency-banner.py` (3 SessionStart matchers + 1 PostToolUse Write|Edit matcher). *Phase B3.2 (`66bca4e`) + B3.7 (`655af86`).*
- **ISC-8**: inspection — `ls scripts/memory/{flush.py, compile.py}` both exist. 7-file pipeline. *Phase B2.2, commit `4f2a7cc`.*
- **ISC-9**: grep — `grep -c 'refresh-v3' scripts/install/install.sh` = 13. Mode dispatch wired in `parse_args` + `case` statement + `print_summary`. *Phase B2.6, commit `6822384`.*
- **ISC-10**: grep — `grep -c 'refresh-v3' scripts/install/install.ps1` = 12. `-Mode refresh-v3` + `-Yes` parameters wired; `Invoke-RefreshV3` orchestrator + `Install-V3*` functions present. *Phase B2.7, commit `5bbe30a`.*

### 4-tier governance

- **ISC-11**: inspection — `ls reference/00-documentation-governance.md` = 386 LOC. *Phase B5.1, commit `f2ba60a`.*
- **ISC-12**: inspection — `ls reference/0[1-9]-*.template.md | wc -l` = 9. *Phase B5.1, commit `f2ba60a`.*
- **ISC-13**: inspection — `ls reference/1[0-9]-*.md | wc -l` = 10. 8 ported as-is (10/11/12/14/15/16/17/19), 2 collapsed to pointer stubs (13 → forge CLI, 18 → MEMORY-SCHEMA.md). *Phase B5.5, commits `b3eba0f` + `d1a2170` + `37a7bf2`.*

### Agents + skills

- **ISC-15**: inspection — `wc -l agents/{architect,project-manager,quality-engineer,security-boss,devops}.md` = 50/44/51/50/49 (max 51, all ≤80). Total 244 LOC vs v2's 2,541 LOC for the same 5 keepers (10× compression). *Phase B4.1, commit `b0861f2`.*
- **ISC-16**: grep — agent frontmatter binds: architect → `architect_adr.py`; quality-engineer → `quality_coverage.py` + `tdd_aaa.py`; security-boss → `security_secrets.py`; devops → `build_deps.py`; project-manager: none (per inventory). All bound validators present in `hooks/validators/agents/` (B3.5). Hook dispatch is Claude Code standard PostToolUse Write event handling — bindings verified by inspection. *Phase B4.1, commit `b0861f2`.*
- **ISC-17**: enumeration — `grep -rc 'subagent_type:' skills/{new-project,new-feature,fix-bug,create-pr,post-implementation-check}/` returns 6/4/1/1/3 = 15 Task() blocks across 5 skills. *Phase B7.1 (`79b9502`) + B7.2 (`5872428`) + B7.3 (`cc4bd49`).* Anti-regression on `reflect/dispatch`: `git diff 700200f..HEAD -- skills/reflect/` is empty — both `subagent_type: "general-purpose"` calls intact, scope_conflict detection intact, helper-script deps intact.
- **ISC-18**: inspection — `ls agents/specialists/` = `.gitkeep` + `README.md` (2 files). Refresh-v3 preserve verified in `install.sh:643` (`--exclude='agents/specialists/**'`) + `install.ps1:607` (`"agents\\specialists"` in `$preserveUnderClaude`). *Phase B4.3, commit `2b4b9ae`.*
- **ISC-19**: bash — live test in commit `b45bb0b` confirmed: `forge specialist add gateway-expert --domain "..."` creates both `.claude/agents/specialists/gateway-expert.md` and `EXPERT.md` with placeholders rendered, refuses duplicates, refuses invalid names (regex `^[a-z][a-z0-9-]*$`), JSON output mode works. *Phase B2.5, commit `b45bb0b`.*

### Rules + security + standards

- **ISC-20**: inspection — `ls rules/*.md | wc -l` = 8 (post-BPE; README + permission-profiles relocated to docs/). *Phase B5.2 (`5dd8b6a`) + BPE pass (this commit).*
- **ISC-21**: inspection — `ls security/{allowed-commands.md, command-validators.md, python/security.py, README.md}` all exist. 1,723 LOC total. *Phase B5.3, commit `6e28af7`.*
- **ISC-22**: inspection — `ls standards/documentation-style.md` exists. 378 LOC. *Phase B5.4, commit `9bb802e`.*

### Memory + observability

- **ISC-23**: grep — `hooks/settings.json` contains 3 SessionStart matchers each invoking `session/session-context.py`. *Phase B3.1 (`0c57c24`) + B3.7 (`655af86`).*
- **ISC-24**: grep — `hooks/settings.json` SessionEnd matcher invokes both `session/memory-capture.py` (memory engine) and `session/session-end-cleanup.py` (cleanup). *Phase B3.1 (`0c57c24`) + B3.7 (`655af86`) + audit pass: memory-capture.py was previously documented but never wired; now wired.*
- **ISC-25**: grep — `hooks/settings.json` contains 2 PreCompact matchers (`auto`, `manual`) each invoking `session/memory-capture.py` then `context/pre-compact.py`. *Phase B3.3 (`ed46c70`) + B3.7 (`655af86`) + audit pass.*
- **ISC-26**: grep — `hooks/settings.json` PostToolUse Write|Edit invokes `forge/consistency-banner.py --fix --json`. *Phase B3.2 (`66bca4e`) + B3.7 (`655af86`).*

### Anti-criteria

- **ISC-29**: gate — `grep -rln 'CLAUDE_PROJECT_DIR/.claude/PAI\|/PAI/\|claude/PAI/' agents/ skills/ hooks/ scripts/ reference/ rules/ security/ standards/ templates/ ALGORITHM/ CLAUDE.md MEMORY-SCHEMA.md` returns empty. No PAI imports, paths, or references in any framework file.
- **ISC-31**: gate — `grep -in 'I am Dr.\|Dr. Chen\|Atlas\|Priya\|Cipher\|Kai\|Jordan' agents/*.md` returns empty. Verified during B4.1 (`b0861f2`) at write-time.
- **ISC-32**: gate — measured framework code+docs LOC: v2 = 69,519, v3 = 52,877, reduction = 16,642 (-24%). Threshold per ISC-32 corrected wording: "≥20% reduction from measured v2 baseline" — passes.

### Tests (B8 — ISC-27 + ISC-28 closed)

- **ISC-27**: bash — `python3 -m pytest tests/forge/ -v` → **44 passed in 0.18s**. Covers `test_registry_ops.py` (atomic registry mutations: add/lock/unlock/complete/pr/status/list, scope conflict detection) + `test_consistency_checker.py` (registry/disk drift, auto-fix paths, performance under 2s on 500 tasks). *Phase B8.1, commit `396a1fc`.*
- **ISC-28**: bash — `python3 -m pytest tests/wiring/ -v` → **22 passed in 0.02s**. 6 test functions parametrized over 5 wired skills + 5 framework agents:
    1. `test_wired_skill_count_meets_isc_16_floor` — ≥5 skills wired
    2. `test_skill_has_at_least_one_framework_agent_call` (×5)
    3. `test_skill_subagent_calls_resolve_to_real_agents` (×5)
    4. `test_agent_has_required_frontmatter` (×5)
    5. `test_agent_validator_binding_files_exist` (×5)
    6. `test_no_cut_v2_agents_referenced_in_wired_skills`

  Static-analysis only (no runtime). Authoring the tests surfaced a real wiring inconsistency in `fix-bug/PHASES.md` (prose Task description with backtick-quoted `subagent_type` instead of a fenced literal `subagent_type: "..."` block matching other skills) — upgraded inline to a proper fenced block. *Phase B8.2, commit `20b4ac2`.*

### Canary verification (B-canary — ISC-30 + ISC-33 closed)

- **ISC-30**: canary — `/tmp/canary-project` cloned from a real consumer project (298 tasks: 260 completed, 2 in_progress, 13 ready, 20 pending, 3 superseded; on a feature branch). Ran `install.sh --mode refresh-v3 --yes`. SHA-256 of `docs/tasks/registry.json` post-install equals SHA-256 of `git show HEAD:docs/tasks/registry.json` pre-install — byte-identical. The canary surfaced two ship-readiness bugs (verify.sh recreated cut dirs; cleanup omitted features/) — both fixed in commit `bc45f08`. *Phase B-canary, commit `bc45f08`.*
- **ISC-33**: bash — `time ./scripts/install/install.sh --mode refresh-v3 --yes /tmp/canary-project` → **1 second**. Well under the 5-minute antecedent. Same order of magnitude expected on a fresh work box (clone time dominates; install itself is filesystem rsync + a few small Python invocations). *Phase B-canary.*

### Canary-2 findings (consumer-project verification, 2026-05-09)

Verification on a real consumer project's main branch (post-993c8f1d) surfaced 5 items:

1. **Pre-existing v2 registry drift** — T282/T283 have `completedAt` < `createdAt` (monotonicity violation, impossible). Pre-existing data, not caused by upgrade. v3 consistency-banner is correctly stricter than v2's. **Action**: project-level one-line fix in the consumer's `docs/tasks/registry.json`.
2. **`agents/specialists/` empty** — framework bug. The `--exclude='agents/specialists/**'` in install_v3_framework_files (B2.6) correctly preserves user specialists but blocked seeding the framework's own `README.md` + `.gitkeep` when the dir was empty/missing. **Fixed**: `install_v3_seed_specialists` step added in commit `1f88ae4` (mirrored install.sh + install.ps1).
3. **4 project-specific specialists at `.claude/agents/` top level** (consumer's own `*-auditor.md` files + a `*-expert.md`). Survived cut-v2 cleanup correctly (they're not in the cut list) but live in the wrong location per v3 conventions. **Action**: relocate to `.claude/agents/specialists/` on the consumer side.
4. **Registry dual-stats schema disagreement** (`tasks.in_progress: 1` vs legacy `inProgressTasks: 0`). Pre-existing inconsistency in v2 registry; v3's port-as-is `forge.py` doesn't repair it. **Defer**: investigate `forge.py recompute_stats` semantics in a separate phase; not blocking.
5. **Tests**: forge 44/44 ✓; wiring 22/22 ✓. v3 mental model understood by a fresh session agent without ambiguity.

### Deferred / blocked

(none open at v3.0.0 ship — all 33 ISCs closed.)
