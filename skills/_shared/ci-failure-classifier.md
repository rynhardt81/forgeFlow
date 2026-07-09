# Shared CI Failure Classifier

> Single source of truth for the failure-pattern → `pr-review-toolkit` specialist routing used by `/diagnose-ci` (remote CI failure) and `/preflight-ci` (local mirror failure). Update this file; both skills inherit.

## Routing table

Match the failed-log output (or local-script stderr) against the table top-to-bottom. Use the first rule that matches; multiple distinct matches → fan out to all matched specialists in parallel.

| Failure pattern (regex-friendly substrings) | Specialist | `subagent_type` |
|---------------------------------------------|------------|-----------------|
| `eslint`, `ruff`, `flake8`, `golangci-lint`, lint exit code | code-reviewer | `pr-review-toolkit:code-reviewer` |
| `FAIL `, `pytest`, `vitest`, `jest`, `cargo test`, test runner exit code | pr-test-analyzer | `pr-review-toolkit:pr-test-analyzer` |
| `error TS`, `mypy:`, `tsc` exit code, type checker exit code | type-design-analyzer | `pr-review-toolkit:type-design-analyzer` |
| Uncaught exception, swallowed error, `try/except: pass` flagged | silent-failure-hunter | `pr-review-toolkit:silent-failure-hunter` |
| `pip install`, `npm install`, `pnpm install`, dependency resolution fail | code-reviewer (general) | `pr-review-toolkit:code-reviewer` |
| Unmatched / ambiguous | code-reviewer (general triage) | `pr-review-toolkit:code-reviewer` |

## Graceful degradation

If `pr-review-toolkit` plugin is not installed, the consuming skill must:

1. Emit `Specialist routing unavailable (pr-review-toolkit not installed) — falling back to log summary` (or the local-execution equivalent).
2. Print the first 80 lines of the failing log/stderr block.
3. Exit non-zero so the caller knows preflight/diagnosis is degraded.

## Dispatch prompt template

When dispatching a matched specialist via the Task tool, both skills use this prompt shape:

```
Failure source: <local-preflight | remote-ci-run-<id>>
Branch: <branch>
Failure class: <classification from the table above>

Failed log excerpt (first 200 lines):
<log excerpt>

Diff context:
<git diff or gh pr diff>

Identify:
  1. Root cause of the failure (one sentence).
  2. The minimal change that fixes it (file:line).
  3. Whether this points to a wider issue in the diff (yes/no + one sentence).

Do not propose pushes or commits — output is advisory only.
```

## Where this is referenced

- `skills/diagnose-ci/SKILL.md` — Step 3 routing
- `skills/preflight-ci/SKILL.md` — Step 5 failure routing

Both skills `@see` this file rather than embedding their own copy. Anti-duplication is enforced by the F-PREFLIGHT-CI ISC-10 probe (`grep` shows zero embedded copies in either skill).
