# Config-regression evals

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

## Layout

```
tests/evals/
├── cases/*.yaml        one eval: prompt + deterministic checks
├── fixtures/*.txt      recorded transcripts, for testing the checks offline
└── README.md
```

## A case

```yaml
id: fix-bug-reproduces-first
prompt: "There's a bug: login returns 500 for users with an apostrophe in their surname. Fix it."
touches: [skills/fix-bug/SKILL.md]      # which config this eval guards
checks:
  - kind: transcript_matches            # the gate must be visible in the work
    pattern: "(?i)reproduc"
    reason: "fix-bug must reproduce before fixing (Gate A)"
  - kind: transcript_absent
    pattern: "(?i)the fix is straightforward, skipping"
    reason: "must not skip the reproduction"
```

`kind` is one of:

| kind | passes when |
|---|---|
| `transcript_matches` | the regex is found in the transcript |
| `transcript_absent` | the regex is not found |
| `command_succeeds` | `cmd` exits 0 in the workspace |
| `file_exists` | `path` exists in the workspace |

Patterns are **raw**: the parser strips surrounding quotes and does nothing else, so write `\w`, not `\\w`. A doubled backslash reaches the regex as a literal backslash and the check silently never matches — which reads as a pass on a `transcript_absent` check, so it fails open.

Every check carries a `reason`, because a red eval that does not say which gate
was dropped is a failure nobody can act on.

## Running

```bash
FORGE_EVALS_BILLING=api python3 scripts/forge/evals.py run            # all
FORGE_EVALS_BILLING=api python3 scripts/forge/evals.py run --id X     # one
python3 scripts/forge/evals.py check --transcript path --id X         # offline, free
python3 scripts/forge/evals.py list
```

`check` runs a case's assertions against a transcript you already have. It costs
nothing and is how the checks themselves are tested.

## Adding one

Every production incident that traces back to agent behaviour earns an eval. Write
the prompt that would have caught it, and a check naming the gate that was missed.
