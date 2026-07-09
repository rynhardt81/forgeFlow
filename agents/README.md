# Agents

Forge Flow ships **5 framework agents** (`architect`, `project-manager`, `quality-engineer`, `security-boss`, `devops`). User-owned project specialists live in `specialists/`. Nothing here is auto-loaded at session start — this roster, like the rules, is discovered on-demand.

## Layout

```
agents/
├── architect.md              # Tech stack + ADRs + system architecture
├── project-manager.md        # PRDs + scope + prioritization + task breakdown
├── quality-engineer.md       # Test plans + code reviews + verification
├── security-boss.md          # Threat modeling + auth + OWASP + secrets
├── devops.md                 # CI/CD + deployment + infra + runbooks
├── specialists/              # User-owned project agents (refresh-v3 never touches)
│   └── README.md             # Scaffold + EXPERT.md vendoring contract
    └── <agent-name>.md       # One per framework agent
```

Each framework agent file is ≤80 lines, no persona narrative, defers to Tier 2 reference docs (`.claude/reference/0X-*.md`) for project-canonical facts. Every framework agent also consults `docs/code-map.md` (auto-regenerated each SessionStart by the `audit-code-map` skill) before recommending structural changes — this is what prevents agents from proposing capability that already exists somewhere in the repo.

## Invocation

| Path | How |
|------|-----|
| Skill auto-fires the agent | A skill calls `Task(subagent_type="<name>", ...)` at the right phase. Happens in `new-project`, `new-feature`, `fix-bug`, `create-pr`. |
| Direct invocation | `@<agent>: <ask>` in chat — the agent runs in an isolated context with the full repo in scope. |

The Task-tool wiring shape and multi-agent flow patterns live in `reference/14-agent-delegation.md` — this README owns the roster and validator bindings.

**Model routing:** every agent file accepts `model:` frontmatter (`haiku` | `sonnet` | `opus` | full model ID | `inherit`) — framework agents ship with `inherit`; specialists doing bounded mechanical work can pin a smaller model. Per-task routing for autonomous dispatch lives in `skills/_shared/model-routing.md`.

## Roster — when to delegate

| Agent | Delegate when | Produces | Defers to |
|-------|---------------|----------|-----------|
| `@architect` | Tech-stack choice, ADRs, system architecture, API contracts, DB schemas, NFR review, **performance work** | ADRs → `reference/06` (Nygard format); tech-stack updates → `reference/02`; boundary/schema notes → task ISA `## Constraints` | `reference/02`, `06` (supersede explicitly), `07` |
| `@project-manager` | PRDs, MVP scope, prioritization (MoSCoW, RICE), epic-to-task breakdown, acceptance-criteria refinement | PRDs at `docs/tasks/<feature>/PRD.md`; epic/task entries via `forge task add`; scope ADRs (handed to `@architect` if architectural) | `reference/01`, `07` |
| `@quality-engineer` | Test plans, code reviews, coverage gaps, E2E, TDD/AAA structure, bug reproduction, VERIFY-phase ISC probes | Test plans → task ISA `## Test Strategy`; bug reports as new tasks; review notes on the PR/task | `reference/04`, `07` |
| `@security-boss` | Threat modeling (OWASP Top 10), auth/authz review, payments, security-sensitive dependency changes, secrets/session handling. Zero-trust posture. | Threat models → `reference/08` (extend, don't rewrite); findings as tasks with severity; auth-review notes → task ISA `## Verification` | `reference/03`, `08` |
| `@devops` | CI/CD pipelines, deployment configs (Docker, K8s, Terraform, GH Actions), runbooks, monitoring strategy, dependency-change CI implications. Rollback path is part of the design. | Runbook updates → `reference/05`; CI/CD configs in canonical locations; deploy notes → task ISA `## Verification` | `reference/02`, `05` |

**Performance routing:** performance work routes to `@architect` — perf is architectural in v3; there is no separate performance agent.

## Validator bindings

Each agent's frontmatter `hooks:` block binds PostToolUse-Write validators. All are **advisory** — they surface findings, never block.

| Agent | Validator(s) | What the code checks |
|-------|--------------|----------------------|
| `@architect` | `architect_adr.py` | ADR shape (Status / Context / Decision / Consequences / Alternatives) on ADR-like writes |
| `@project-manager` | (none) | — |
| `@quality-engineer` | `quality_coverage.py` + `tdd_aaa.py` | Coverage-gap detection; AAA (Arrange / Act / Assert) structure on test-file writes |
| `@security-boss` | `security_secrets.py` | Committed secrets (API keys, tokens, private keys) |
| `@devops` | `build_deps.py` | Package-manifest writes: warns on unpinned/wildcard versions (`*`, `latest`, bare requirement lines — pin them), git-URL dependencies, dangerous install scripts (`rm -rf`, `sudo`) |

Implementations: `hooks/validators/agents/*.py`.

## Checkpoint discipline

**Background worktree work:** every framework agent and specialist follows the Checkpoint Discipline in `ALGORITHM/v1.2.0.md` — wip: commits every ~5 min / 10 tool actions, checkpoint before long operations, final commit before completion.

## Specialists (user-owned)

`specialists/<name>.md` — project-specific agents (e.g. `payments-backend-auditor`, `inventory-expert`). Scaffold via:

```bash
python3 .claude/scripts/forge/forge.py specialist add <name> --domain "..."
```

This creates the live agent + a paired `EXPERT.md` knowledge artifact (the *exportable* version sibling projects can vendor). The `specialists/` directory is never touched by `install.sh --mode refresh-v3`.

See `specialists/README.md` for the full contract.

## Summaries


## External plugin agents (pr-review-toolkit)

Some skills invoke specialist agents shipped by external Claude Code plugins, not by Forge Flow itself. The framework does not vendor these — it references them by their plugin-namespaced `subagent_type`.

### `pr-review-toolkit:*`

**Skills that fan them out:** `/create-pr` (Step 3.7 pre-flight) and `/diagnose-ci` (CI-failure routing).

| Specialist | `subagent_type` | When invoked |
|------------|-----------------|--------------|
| code-reviewer | `pr-review-toolkit:code-reviewer` | Always (general quality); CI lint failure |
| pr-test-analyzer | `pr-review-toolkit:pr-test-analyzer` | Test files in diff; CI test failure |
| type-design-analyzer | `pr-review-toolkit:type-design-analyzer` | New types in diff; CI type-check failure |
| silent-failure-hunter | `pr-review-toolkit:silent-failure-hunter` | Error-handling changes in diff; uncaught/swallowed errors in CI |
| comment-analyzer | `pr-review-toolkit:comment-analyzer` | Comments / docstrings touched |
| code-simplifier | `pr-review-toolkit:code-simplifier` | Final pass after MUST-FIX cleared |

**Install** the plugin into Claude Code at user scope; it then surfaces in every project automatically. Forge Flow detects its presence via `~/.claude/plugins/installed_plugins.json` and skips the fan-out gracefully when absent — `/create-pr` continues with the original flow plus a one-line note.

**Anti-criterion:** the framework does NOT fork these into `agents/` or `agents/specialists/`. Forking would create a maintenance liability against an externally-maintained source.

## See also

- `reference/14-agent-delegation.md` — how skills delegate (Task-tool wiring, multi-agent flows, v2-to-v3 routing for legacy agent references)
- `hooks/validators/agents/*.py` — the validators bound to each framework agent
- `skills/<name>/SKILL.md` — skills that auto-fire framework agents
- `skills/create-pr/CHECKS.md` → "Specialist Review" — the diff-pattern → agent matrix used by `/create-pr` Step 3.7
