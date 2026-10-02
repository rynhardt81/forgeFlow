# Plugin evals — skill behaviour under `claude plugin eval`

Anthropic's `claude plugin eval` (Claude Code ≥ v2.1.269) runs each case in an isolated session with only a plugin loaded, three times by default, and again **without** the plugin, reporting `Δ` — what the skill actually adds. The repo root carries `.claude-plugin/plugin.json` purely so this works; consumers never install Forge Flow as a plugin, and every installer copy excludes `.claude-plugin`. Docs: <https://code.claude.com/docs/en/plugin-evals>.

## What lives where

| Guards | Harness | Why |
|---|---|---|
| Skills (does it trigger, does it keep its gate) | this suite | Loads `skills/` and `agents/` as a plugin; measures `Δ` against no plugin |
| Always-on doctrine (`CLAUDE.md`, `rules/`) | `scripts/forge/evals.py` + `tests/evals/cases/` | Plugin eval loads no `CLAUDE.md`, `.claude/` or rules — by design |

## Cases

| Case | Checks |
|---|---|
| `fix-bug-reproduces-first` | `/fix-bug` fires; a command runs **before** the first Edit (Gate A); a test file is written; `app.py` ends parameterised. Workspace seeded by `scaffold.sh` (needs `--scaffold`) |
| `triggers-create-pr` | `/create-pr` fires on "open a pull request" |
| `triggers-vet-idea` | `/vet-idea` fires on "is that worth doing at all?" |
| `question-triggers-no-skill` | a plain question fires **no** skill (over-triggering) |

All graders are free (`tool_used`, `tool_order`, `regex`); none calls a judge model.

## Running — this spends plan usage

Runs use your normal Claude Code login and count against your plan (or API bill). Always pass a cost ceiling and run it by hand — never from a hook, a `/loop`, or a scheduled job.

```bash
# cheapest smoke test: one case, one run, no baseline
claude plugin eval . --case triggers-create-pr --runs 1 --ablation none --max-cost-usd 1

# the full pilot: 4 cases × 3 runs × 2 arms, capped
claude plugin eval . --scaffold --allow-tools Bash Edit Write --max-cost-usd 5 --threshold 0.67
```

The first run asks `Trust this plugin directory?` — answer `y` (or pass `--trust-plugin`). `--scaffold` runs `fix-bug-reproduces-first/scaffold.sh` as you; it only writes `app.py` and a git commit into the run's temp workspace. `Bash`, `Edit` and `Write` are granted only inside Claude Code's OS sandbox, confined to that workspace. Results land in `tests/plugin-evals/results/` (git-ignored).

Reading a result: `Δ` near zero with the `skill-fired` grader failing means the skill's `description` does not trigger on that phrasing — fix the description, re-run.
