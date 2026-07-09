# Error Handling Rules

> Active directive. Discovered on-demand via the `rules/*.md` glob — read by `/audit-rules` and any agent reasoning about error handling. Treat as binding when encountered.
>
> The always-present error-handling floor. Detection of swallowed errors is review-time and plugin-optional (`pr-review-toolkit:silent-failure-hunter` when installed); this rule is the standing floor that fires even on a bare clone with no plugins. Canonical home for error-handling discipline — `rules/coding-style.md` defers here.

## Core rules

- **Specific error types, not generic.** *DO:* `throw new ValidationError(...)` / `raise ValidationError(...)`. *DON'T:* `throw new Error("validation failed")`.
- **Handle at boundaries.** Catch where you can do something meaningful (API edge, job boundary, UI boundary) — not at every call site. Let errors propagate to the boundary that owns the response.
- **Never swallow silently.** *DON'T:* bare `except:`, `except Exception: pass`, empty `catch {}`, or `.catch(() => {})`. If you catch, you must either handle, re-throw, or log-with-context-and-rethrow. A caught-and-dropped error is a silent failure.
- **Surface, don't hide.** An error the caller needs to know about must reach them — as a thrown error, a rejected promise, or a structured error result. Returning `null`/`undefined`/`-1` to mean "it failed" hides the cause; prefer an explicit error.
- **Structured responses at API edges.** HTTP/RPC boundaries return a structured error body + the correct status code (4xx for client errors, 5xx for server). *DON'T:* 200-with-error-in-body; *DON'T:* leak stack traces or internal messages to clients.
- **User-facing vs internal.** Log the full internal detail (with a correlation/request ID); show the user a safe, actionable message. Never the raw exception.
- **Retries are deliberate.** Retry only idempotent operations, with backoff and a cap. *DON'T:* retry a non-idempotent write blindly. Make the operation idempotent first (idempotency key) if it must be retried.
- **Fail fast on programmer errors.** Bad config, missing required env, broken invariants → crash loud at startup, don't degrade silently into a half-working state.

## What this is NOT

This rule is **review-time discipline**, not a hardcoded scanner. Forge deliberately does **not** ship a regex PostToolUse validator for swallowed errors — a pattern-match on `except: pass` produces false positives (legitimate suppressions exist) and duplicates the judgment the LLM review (`silent-failure-hunter` when present, or a careful read) already does better. The floor lives in this rule + verification doctrine, not in a brittle hook.

## Verification tie-in

The Algorithm's VERIFY phase already forbids claiming success without evidence ("no errors" without the actual log is forbidden language). This rule is the *authoring* counterpart: write code whose errors are surfaced, so that verification has something truthful to read.

## Project-specific extensions

Add project-specific error types, framework conventions (e.g. your API error envelope shape), and exceptions to `rules/error-handling.local.md` alongside this file. Sidecar `*.local.md` files are excluded from framework refresh — they survive `install.sh --mode refresh-v3`. Readers (skills, agents, `/audit-rules`) pick up both via the `rules/*.md` glob.

## See also

- `rules/coding-style.md` — defers here for the error-handling floor
- `rules/testing.md` — error-path and edge-case coverage expectations
- `skills/fix-bug/SKILL.md` — reproduce → root-cause → fix → verify; surfaces swallowed errors during diagnosis
- `ALGORITHM/v1.2.0.md` — VERIFY phase forbidden-language doctrine ("no errors" without the log)
