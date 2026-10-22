# Security Guidelines

> **Loaded at every session start.** Binding.

## When to invoke @security-boss

- **Authentication** (who you are) — verified once at the entry point: login, token issuance, session establishment.
- **Authorization** (what you may do) — a *distinct* concern, verified **on every resource access, server-side**. Authentication passing does not imply authorization; check ownership/role at each protected operation, and never trust a client-supplied role or object ID.
- Passwords / Tokens (JWT, sessions)
- Payment processing
- PII / Sensitive data
- API keys / Encryption

## Path warnings (advisory, never blocks)

The `validation/validate-edit.py` PreToolUse hook warns on edits to `.env*`, `.git/`, lockfiles, `node_modules/`, and similar. Defaults to advisory — confirm intent and proceed.

## See also

- `rules/dependencies.md` — supply-chain hygiene rules
- `.claude/reference/03-security-auth-and-access.md` — project auth model + secrets handling
- `.claude/reference/08-security-model.md` — threat model + security architecture
