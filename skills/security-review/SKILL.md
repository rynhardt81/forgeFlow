---
name: security-review
description: Portable security review for a feature, endpoint, or change before it ships. Orchestrates the existing OWASP review (@security-boss) and secrets scan (security_secrets validator), then adds the pass they miss — an explicit business-logic-flaw walkthrough (IDOR, race/TOCTOU, state-machine bypass, privilege escalation, price/quantity tampering). Advisory and non-mutating — produces a findings report; real findings are filed as tasks. Trigger keywords — security review, review for vulnerabilities, business logic flaws, IDOR, before shipping check security, threat review.
allowed-tools: Read, Glob, Grep, Bash, Write, TodoWrite, Task
---

## Quick Scan

| | |
|---|---|
| **Purpose** | Review a feature/change for security flaws before it ships — including the business-logic flaws generic OWASP red-flags miss. |
| **Inputs** | The change under review (a diff, a feature's files, or a task ID). |
| **Output** | A findings report; real findings filed as tasks via the `@security-boss` convention. |
| **Mutates** | Nothing. Advisory — findings become tasks, never a hard gate. |
| **Flow** | OWASP pass (@security-boss) → secrets scan → business-logic walkthrough → report |

---

# security-review Workflow

This skill **orchestrates** Forge's existing security pieces and adds the one missing pass. It does **not** re-implement OWASP or secret detection — those already exist:

- **OWASP Top 10 review** → `@security-boss` (injection, broken auth, broken access control, XSS, SSRF, etc.). It already carries the authn-vs-authz distinction and access-control red-flags.
- **Secrets scan** → the `security_secrets.py` validator (hardcoded keys/tokens, `.env` writes), with patterns from `hooks/config/secret-patterns.yaml`.

What neither covers — and what this skill adds — is **business-logic flaws**: vulnerabilities where every individual call is "authenticated and well-formed," but the *sequence* or *values* break an invariant. A generic OWASP red-flag list provably doesn't force this; it takes a deliberate walkthrough. The skill self-contains that walkthrough so it runs on a bare clone with no PAI/external plugins.

## When to use

- **Before shipping a feature that touches money, access, or state** — checkout, balance, role changes, multi-step workflows.
- **At `/new-feature` security review** and in the `/create-pr` Step 3.7 pre-flight for any security-relevant change.
- When a reviewer says "the auth looks fine" but the *flow* could be abused.

**Do NOT use it** as a SAST engine or dependency-CVE scanner — those are the consumer project's CI/runtime job, not this portable framework's. This skill is review *judgment*, not tooling.

## Invocation

```
/security-review                      # review the current diff (git diff)
/security-review T###                 # review the change for a task
/security-review --files <glob>       # review specific files
/security-review --output PATH        # custom report path (default: memories/security-review-{date}.md)
```

---

## Step 1: Scope the surface

Identify what's under review (diff, feature files, or a task's scope). Read `docs/code-map.md` if present to locate the relevant surfaces (auth handlers, input parsers, money/state mutations, external-call sites). Note which surfaces touch **money, access control, or multi-step state** — those are where business-logic flaws live.

## Step 2: OWASP + secrets (orchestrate existing)

- Invoke `@security-boss` (via the Task tool) for the OWASP Top 10 review of the scoped surface. Do not restate the OWASP list here — `@security-boss` owns it.
- Confirm the secrets scan is clean (the `security_secrets.py` validator fires on writes; for a review pass, grep the diff for the same pattern classes — hardcoded keys, tokens, `.env` content).

## Step 3: Business-logic-flaw walkthrough (the missing pass)

For each money/access/state surface, walk these explicitly — each is a flaw where the individual request is valid but the *logic* is exploitable:

- **IDOR / object-level:** can a user act on another user's object by changing an ID? (`/orders/{id}` returning any order.)
- **Race / TOCTOU:** can two concurrent requests both pass a check that should only pass once? (double-spend, coupon reuse, balance going negative.)
- **State-machine / workflow bypass:** can a step be skipped or replayed out of order? (reaching "shipped" without "paid"; re-submitting a one-time action.)
- **Privilege escalation:** horizontal (peer's data) or vertical (higher role's capability) — by manipulating a role/tenant/flag the server trusts without re-checking.
- **Price / quantity tampering:** is an amount, price, discount, or quantity taken from the client and trusted? (negative quantity, client-set price, stacked discounts.)
- **Invariant breaks:** what business rule must *always* hold (balance ≥ 0, one vote per user, total = sum of line items) — and can a sequence of valid calls violate it?

For each surface, record: the invariant, the abuse it could allow, and whether the code enforces it **server-side on every relevant operation** (not just the happy path, not client-trusted).

## Step 4: Report and file findings

Write the findings to `memories/security-review-{date}.md` (or `--output`). For each real finding: severity, the surface, the abuse, and the fix direction. **File genuine findings as tasks** via the `@security-boss` convention (`forge task add` with severity in `--category`) — so they enter the work queue rather than evaporate. Print a one-paragraph summary and stop. **Advisory only** — never blocks a ship; the findings are the deliverable.

## When NOT to use

- As SAST / dependency-CVE tooling — that's consumer CI (Trail of Bits skills, Semgrep, CodeQL, `npm audit` live there, not here).
- For pure secrets scanning with no logic surface — the `security_secrets.py` validator already fires on writes.
- On a change with no money/access/state surface — the business-logic pass has nothing to bite on; a normal `@security-boss` review suffices.

## Anti-criteria for this skill

- **Anti:** Does NOT re-implement the OWASP Top 10 inline — it invokes `@security-boss`, which owns that list.
- **Anti:** Does NOT block a ship — advisory only; findings become tasks, not gates (informational-hooks doctrine).
- **Anti:** Does NOT ship SAST/CVE tooling — review judgment only; scanning tools are the consumer's CI job.
- **Anti:** Does NOT depend on a PAI/external plugin — the business-logic walkthrough is self-contained, bare-clone runnable.

## See also

- `agents/security-boss.md` — the OWASP + authn/authz reviewer this skill orchestrates
- `hooks/validators/agents/security_secrets.py` + `hooks/config/secret-patterns.yaml` — the secrets scan + its (now live) pattern config
- `rules/security.md` — the authn-vs-authz distinction + when to invoke `@security-boss`
- `skills/audit-rules/SKILL.md` / `skills/vet-idea/SKILL.md` — sibling advisory, non-mutating, report-only skills this mirrors
