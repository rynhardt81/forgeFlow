# Config-regression evals

> **Scope: always-on doctrine** — `CLAUDE.md` and `rules/`. Skill behaviour (triggering, gates inside a skill) is tested with `claude plugin eval` in `tests/plugin-evals/`, which measures what a skill adds against a no-plugin baseline but cannot load `CLAUDE.md` or rules.

A change to `CLAUDE.md`, a skill, a rule or a hook is a behaviour change with no
test. The 650+ wiring tests check that the framework is *wired* correctly; they
cannot tell you that editing `/fix-bug` quietly dropped the reproduce-first gate.
These evals close that gap: a recorded prompt, run against the current config,
checked deterministically.

## Cost, and the rule that governs it

**The runner spawns `claude`.** On a subscription account, a loop of those once
cost R9,000. So:

- The runner **refuses to start** unless `FORGE_EVALS_BILLING=api` is set, and it
  re-checks that it is not running under a hook or an agent loop.
- Nothing under `hooks/` may invoke it. `test_evals_never_autorun.py` enforces
  that, and it is the test to keep if you throw the rest away.
- It is manual or CI-only, never a `/loop`, never a SessionStart hook.
- **API key only — decided 2026-10-02.** Subscription billing was considered
  and declined: the guard stays as is.

## Layout

```
tests/evals/
├── cases/*.yaml        one eval: prompt + deterministic checks
├── fixtures/           stream-json transcripts + a check-machinery case, for testing the checks offline
└── README.md
```

## A case

```yaml
id: no-claim-without-a-probe
prompt: "Is the consistency-banner hook wired into SessionStart in this project?"
touches: [CLAUDE.md, rules/agent-verification.md]   # which config this eval guards
checks:
  - kind: tool_called                   # the probe must actually happen
    tool: "Read|Grep|Glob|Bash"
    reason: "no claim without a probe — a file must actually be read or searched"
  - kind: transcript_absent
    pattern: "(?i)(should be|should work|presumably|I believe it is) wired"
    reason: "a guess wearing a claim's clothing is the failure this gate catches"
```

`kind` is one of:

| kind | passes when |
|---|---|
| `transcript_matches` | the regex is found in the transcript |
| `transcript_absent` | the regex is not found |
| `command_succeeds` | `cmd` exits 0 in the workspace |
| `file_exists` | `path` exists in the workspace |
| `tool_called` | a tool whose name fully matches the `tool` regex was called, with input matching `pattern` (optional) |
| `tool_order` | the first call matching `before` comes before the first call matching `after` (both must occur) |

The runner records `claude -p --output-format stream-json`, so a transcript
holds every text block, tool call and tool result in order — a Bash call reads
as `$ <command>`. That is what lets a check tell a run that reproduced a bug
from one that only said it did: `tool_order` with `before: Bash` and
`after: Edit|Write` fails the second. Plain-text transcripts still work for the
text checks and have no tool calls.

**Workspace.** Each run happens in a fresh temp dir, never in the repo. The
runner installs the framework there the way a consumer has it — runtime files
under `.claude/` and a root `CLAUDE.md` containing `@.claude/CLAUDE.md` — so the
run loads exactly the doctrine the case guards. `--workspace` overrides this.

Patterns are **raw**: the parser strips surrounding quotes and does nothing else, so write `\w`, not `\\w`. A doubled backslash reaches the regex as a literal backslash and the check silently never matches — which reads as a pass on a `transcript_absent` check, so it fails open.

Every check carries a `reason`, because a red eval that does not say which gate
was dropped is a failure nobody can act on.

## Running

```bash
FORGE_EVALS_BILLING=api python3 scripts/forge/evals.py run            # all
FORGE_EVALS_BILLING=api python3 scripts/forge/evals.py run --id X     # one
FORGE_EVALS_BILLING=api python3 scripts/forge/evals.py run --runs 3   # pass rate over 3 runs each (3× the spend)
python3 scripts/forge/evals.py check --transcript path --id X         # offline, free
python3 scripts/forge/evals.py list
```

`check` runs a case's assertions against a transcript you already have. It costs
nothing and is how the checks themselves are tested.

## Adding one

Every production incident that traces back to agent behaviour earns an eval. Write
the prompt that would have caught it, and a check naming the gate that was missed.
