# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| v4.x (Forge Flow) | Yes |
| v3.x and earlier | End of life — upgrade via [MIGRATION-GUIDE.md](MIGRATION-GUIDE.md) |

Security fixes apply to the latest release on the `main` branch.

## Reporting a vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Instead:

1. Open a [GitHub private vulnerability report](https://github.com/rynhardt81/forgeFlow/security/advisories/new) on this repository, **or**
2. Contact the maintainers through GitHub's private reporting channel if advisory creation is unavailable.

Include:

- Description of the vulnerability and potential impact
- Steps to reproduce
- Affected files, hooks, or scripts (if known)
- Suggested fix (optional)

### Response timeline

- **Acknowledgment:** within 5 business days
- **Initial assessment:** within 10 business days
- **Fix or mitigation plan:** coordinated with the reporter; target disclosure window of **90 days** from report unless a shorter timeline is agreed

We will credit reporters in the release notes when they wish to be named.

## Scope

**In scope**

- The forge CLI (`scripts/forge/`) — command injection, path traversal, unsafe file writes
- Install scripts (`scripts/install/`) — destructive operations, privilege escalation
- Hooks and validators — bypass of security checks, secret exfiltration
- MCP servers shipped with the framework — unsafe defaults, credential handling
- `/damage-control` blocking hooks — bypasses of the opt-in defense-in-depth layer

**Out of scope**

- Vulnerabilities in [Claude Code](https://github.com/anthropics/claude-code/issues) itself — report to Anthropic
- Consumer-project application code installed alongside Forge Flow
- Social engineering or physical access attacks
- Denial-of-service against local-only tools (e.g. `forge dashboard` on localhost) unless exploitable remotely without user action

## Safe usage notes

- Framework-wired hooks are informational and never blocking, and no hook ever spawns an LLM subprocess. Blocking enforcement exists only as explicit opt-ins (`/damage-control` hooks, `consistency-banner --strict`) — none of it replaces OS-level access controls.
- Never commit `.env`, credentials, or secrets to projects using Forge Flow. Use `.gitignore` patterns shipped with the framework.
- `forge dashboard` binds to `127.0.0.1` by default — do not expose it to untrusted networks without additional authentication.

## Security updates

Security fixes are released through normal semver tags. Check [RELEASES.md](RELEASES.md) and [CHANGELOG.md](CHANGELOG.md) for advisories.

---

*Last updated: 2026-07-09*
