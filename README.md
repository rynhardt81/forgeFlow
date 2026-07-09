# Claude Forge — Forge Flow

[![tests](https://github.com/rynhardt81/forgeFlow/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/rynhardt81/forgeFlow/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Made for Claude Code](https://img.shields.io/badge/Made%20for-Claude%20Code-blueviolet)](https://claude.ai)

A project-portable framework for AI-assisted, full-cycle software development with Claude Code. Drops into any project via `git clone .claude` and works identically on personal and work machines — no dependency on globally-installed plugins, no personal-data wiring. It is the deterministic spine of structured AI development: task state that can't drift, done-criteria that can't be faked, and CI feedback that doesn't burn money.

**v4 design principle: the model is smart; the framework is a harness, not a script.** Everything here either enforces verification, manages state deterministically, or encodes a learned incident. Process narration, output ceremony, and numeric quotas were removed — they measurably made output worse.

---

## What Forge Flow gives you

| Primitive | What it does |
|-----------|--------------|
| **Forge CLI** | Atomic task-state operations — add, lock, pr, complete, reconcile — with file-scope conflict detection at lock time and a consistency hook that auto-fixes registry drift on every write |
| **ISA (Ideal State Articulation)** | A per-task/per-project verification trail: testable criteria (each with a nameable tool probe), required `Anti:` criteria, and a hard rule that `[x]` needs tool evidence — never "tests pass" |
| **Algorithm** | Phase discipline for genuinely complex work — OBSERVE → THINK → PLAN → BUILD → EXECUTE → VERIFY → LEARN — with reproduce-first gates for bugs, schema gates for migrations, and checkpoint discipline for background agents |
| **CI economics** | `/preflight-ci` mirrors your GitHub Actions locally before push; `/diagnose-ci` root-causes failed runs locally instead of retry-pushing; `/create-pr` gates pushes on a pre-flight review |
| **Full-cycle coverage** | Idea (`/vet-idea`) → project (`/new-project`) → feature/bug/refactor → PR → release (`/release`, rollback-verified) → production (`/triage-incident`, postmortems) |
| **Production rules** | On-demand directives for the risky parts: database migrations (expand/contract, backup-verified), release engineering (feature flags, staged rollout), data privacy (POPIA/GDPR, children's data), dependency hygiene + CVE surveillance |
| **5 framework agents** | architect, project-manager, quality-engineer, security-boss, devops — with bound validators whose advice actually reaches the model |
| **Project memory** | `/remember` writes committed knowledge to `docs/project-memory/`; the SessionStart hook loads it back. Manual and intentional — no silent transcript capture, no hook ever spawns an LLM |
| **Forge Dashboard** | `forge dashboard` (`forge` = `python3 .claude/scripts/forge/forge.py`; alias it) — local cockpit at `http://127.0.0.1:4847/` with live-reloading tabs for tasks, code map, ISAs, memory, registry, burndown. Zero external dependencies |
| **Code map + MCP** | `/audit-code-map` generates a queryable inventory (`find_definition`, `dependents_of`, …) served by a framework-shipped MCP server |

## Quick Start

> **New here?** See [docs/USER-GUIDE.md](docs/USER-GUIDE.md) for a full walkthrough.

### New project

```bash
mkdir my-project && cd my-project
git clone https://github.com/rynhardt81/forgeFlow.git .claude
rm -rf .claude/.git
claude
```

In Claude Code:
```
/new-project "My awesome app"
```

### Existing project

```bash
cd /path/to/existing-project
git clone https://github.com/rynhardt81/forgeFlow.git .claude
rm -rf .claude/.git
claude
```

```
/new-project --current
```

### Resume work

```
/reflect status        # See available tasks
/reflect resume T001   # Start a task
```

## Core commands

| Command | Purpose |
|---------|---------|
| `/new-project` | Initialize — PRD, ADRs, tasks, populated source-of-truth docs |
| `/reflect resume` / `status` / `handoff` | Session continuity across days and machines |
| `/new-feature` | Scoped feature workflow, verification trail at E3+ |
| `/fix-bug` | Reproduce → root-cause → fix → regression test |
| `/run-epic E##` | Autonomously drain an epic — hard caps, 3-failure halt, PR per task |
| `/create-pr` | PR with pre-flight review gate, review-feedback triage loop, merge-order for multi-PR days |
| `/preflight-ci` / `/diagnose-ci` | Local CI mirror + local failure diagnosis — protect your Actions minutes |
| `/release` | Version + changelog + tag + release-safety checklist (rollback verified before deploy) |
| `/triage-incident` | Production incident → stabilize → fix → verify in prod → postmortem |
| `/vet-idea` | Adversarial GO / NO-GO / RECONSIDER verdict before you build |
| `/security-review` | Business-logic security pass + secrets scan before shipping |
| `/remember` | Capture a bug/decision/pattern/fact into committed project memory |
| `python3 .claude/scripts/forge/forge.py dashboard` | One-URL local cockpit for every artifact (alias `forge` for daily use) |

Full roster: [skills/README.md](skills/README.md) · machine-readable: `skills/skills-manifest.json`.

## Project structure

```
your-project/
├── .claude/                  # The framework (this repo)
│   ├── CLAUDE.md             # Entry point — modes, tiers, roster
│   ├── ALGORITHM/v1.2.0.md   # Phase doctrine (LATEST)
│   ├── agents/               # 5 framework agents + specialists/ (yours, never touched)
│   ├── skills/               # Workflow skills + skills-manifest.json
│   ├── hooks/                # Session context + consistency + validators (wired hooks never block or spawn LLMs)
│   ├── reference/            # 4-tier documentation governance (00-10, 13-14)
│   ├── rules/                # On-demand directives incl. migrations, release-engineering, privacy
│   ├── templates/            # PRD, ADR, ISA, session, renovate.json, dependency-scan.yml
│   ├── scripts/forge/        # Task-state CLI + dashboard
│   ├── scripts/install/      # install.sh / install.ps1 / verify.sh
│   ├── mcp-servers/          # code-map MCP server
│   └── tests/                # Framework test harness (pytest)
├── docs/
│   ├── tasks/registry.json   # Task state (forge CLI only)
│   ├── tasks/<id>/ISA.md     # Per-task verification trails
│   └── project-memory/       # Committed knowledge
├── daily/                    # Per-user, gitignored
└── ISA.md                    # Project verification trail
```

## Installing / upgrading

```bash
# Interactive (detects fresh vs existing)
./scripts/install/install.sh /path/to/your-project

# Refresh an existing install to the current framework
./scripts/install/install.sh --mode refresh-v3 /path/to/existing-project
```

The installer backs up before overwriting and never touches user content (`agents/specialists/`, `docs/tasks/registry.json`, `docs/project-memory/`, `daily/`, `rules/*.local.md`). Windows: `install.ps1`.

## Documentation

| Topic | Path |
|-------|------|
| User guide | [docs/USER-GUIDE.md](docs/USER-GUIDE.md) |
| Framework entry point | [CLAUDE.md](CLAUDE.md) |
| Algorithm doctrine | `.claude/ALGORITHM/v1.2.0.md` |
| ISA spec | `.claude/skills/ISA/SKILL.md` |
| Memory schema | [MEMORY-SCHEMA.md](MEMORY-SCHEMA.md) |
| Migration guide | [MIGRATION-GUIDE.md](MIGRATION-GUIDE.md) |
| Dashboard | `scripts/forge/dashboard/README.md` |

## Versioning

**Current:** v4.1.0 (Forge Flow) — see [RELEASES.md](RELEASES.md) for the full release history.

## Contributing & security

See [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Report vulnerabilities per [SECURITY.md](SECURITY.md) — not via public issues.

## License

MIT — see [LICENSE](LICENSE).

---

*Forge Flow: the deterministic spine of AI-assisted development — verification you can't fake, state that can't drift, and a lifecycle that doesn't end at the merge.*
