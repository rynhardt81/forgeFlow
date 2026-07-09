# Specialist Agents — User-Owned

> Specialist agents live here. **This directory is never touched by `install.sh --mode refresh-v3` or any framework refresh.** Add as many specialists as your project needs; they survive every upgrade.

## What goes here

One markdown file per specialist agent: `<name>.md`. Each file is the live specialist for one domain in your project — API gateway, database schema, billing, etc.

Specialists know:

- The architecture and how the pieces fit together
- The integration contracts other systems depend on
- The critical invariants that must hold
- The known gotchas and past incidents
- The version history of significant changes

Each specialist also maintains a paired `EXPERT.md` knowledge artifact (default location: project root) — that's the *exportable* version that sibling projects can vendor.

## How to add a specialist

```bash
python3 .claude/scripts/forge/forge.py specialist add gateway-expert \
    --domain "API gateway — routing, auth, rate limiting"
```

This scaffolds two files:

- `.claude/agents/specialists/gateway-expert.md` — the live specialist agent (lives here)
- `EXPERT.md` (project root, by default) — the knowledge artifact (vendorable by consumers)

Re-run with a different `--export-path` to put `EXPERT.md` elsewhere (e.g. `--export-path .claude/specialists/gateway-expert.knowledge.md` for a scoped location).

## How to invoke a specialist

Any of:

- A skill calls `Task(subagent_type="<name>", ...)`
- The user types `@<name>: <question>` in chat
- Another agent (framework or specialist) consults this one for domain knowledge

## Why two layers (agent + EXPERT.md)

- **Live agent** (in this directory): not portable across repos — has the project's full filesystem in scope, can run commands and audit code.
- **Knowledge artifact** (`EXPERT.md`): portable — consumer projects vendor it via git submodule, copy-with-sync, or symlink.

The agent is the source of truth; the artifact is the export. The agent's job includes keeping `EXPERT.md` current as architecture and contracts shift.

## Refresh-v3 guarantee

`install.sh --mode refresh-v3` (and `install.ps1 -Mode refresh-v3`) never reads from, writes to, or removes anything under this directory. Custom specialists are part of your project's accumulated knowledge — they belong to you, not to the framework.

## See also

- `.claude/templates/specialist-agent.md` — the template the scaffolder renders
- `.claude/templates/EXPERT.md` — the knowledge-artifact template
