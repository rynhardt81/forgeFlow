# Security Guidelines

> Active directive. Discovered on-demand via the `rules/*.md` glob — read by `/audit-rules` and any agent reasoning about security. Treat as binding when encountered.

## When to invoke @security-boss

- **Authentication** (who you are) — verified once at the entry point: login, token issuance, session establishment.
- **Authorization** (what you may do) — a *distinct* concern, verified **on every resource access, server-side**. Authentication passing does not imply authorization; check ownership/role at each protected operation, and never trust a client-supplied role or object ID.
- Passwords / Tokens (JWT, sessions)
- Payment processing
- PII / Sensitive data
- API keys / Encryption

## Path warnings (advisory, never blocks)

The `validation/validate-edit.py` PreToolUse hook warns on edits to `.env*`, `.git/`, lockfiles, `node_modules/`, and similar. Defaults to advisory — confirm intent and proceed.

## Supply chain

Dependency hygiene (pin exact, publish cool-down, lockfile-strict CI, agent must ask before adding) is its own active directive — see `rules/dependencies.md`. Applies to every project that consumes Forge Flow.

## Project-specific extensions

Add project-specific examples, exceptions, and conventions to `rules/security.local.md` alongside this file. Sidecar `*.local.md` files are excluded from framework refresh — they survive `install.sh --mode refresh-v3`. Readers (skills, agents, `/audit-rules`) pick up both via the `rules/*.md` glob.

## See also

- `rules/dependencies.md` — supply-chain hygiene rules
- `.claude/reference/03-security-auth-and-access.md` — project auth model + secrets handling
- `.claude/reference/08-security-model.md` — threat model + security architecture
