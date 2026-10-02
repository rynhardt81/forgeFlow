# New Project — Task Seeding Reference

Templates and CLI detail for Phase 6. The sequence, confirmation and rules are in SKILL.md.

## Contents

- Proposed-tasks table (CONFIRM #2)
- Registry skeleton
- Epic commands
- Task commands and flags
- Verification commands
- Category codes

## Proposed-tasks table (CONFIRM #2)

```markdown
## Proposed Tasks

| ID | Epic | Name | Deps | Scope |
|----|------|------|------|-------|
| T001 | E01 Auth | Set up auth scaffolding | — | src/auth/ |
| T002 | E01 Auth | Login + session flow | T001 | src/auth/, src/app/login/ |
| T003 | E02 Catalog | Product list + detail pages | — | src/app/products/ |
| ... |

[X] epics, [Y] tasks, [Z] immediately ready. Seed the registry?
```

## Registry skeleton

The one sanctioned hand-write — settings only:

```json
{
  "project": "[PROJECT_NAME]",
  "version": "1.0.0",
  "lastUpdated": "[UTC RFC3339]",
  "settings": {
    "lockTimeoutSeconds": 3600,
    "allowManualUnlock": true,
    "maxParallelAgents": 3,
    "autoAssignNext": true
  },
  "stats": {
    "epics": { "total": 0, "completed": 0, "in_progress": 0, "blocked": 0 },
    "tasks": { "total": 0, "completed": 0, "in_progress": 0, "continuation": 0, "ready": 0, "pending": 0 }
  },
  "epics": [],
  "tasks": []
}
```

(`stats` may be zeros — forge recomputes it on every mutation.)

## Epic commands

```bash
python3 .claude/scripts/forge/forge.py epic add E01 \
    --name "Authentication" --description "Login, session, RBAC" \
    --category A --priority 1
python3 .claude/scripts/forge/forge.py epic add E02 \
    --name "Catalog" --deps E01 --category B
```

One command creates the registry entry AND `docs/epics/E##-{slug}/` with its `tasks/` subdir and body file (`E##-{slug}.md`). Epic `--deps` express epic ordering (E02 depends on E01). After seeding, enrich each generated body — goal and in/out of scope under `## Summary`, the epic's task table under `## Tasks`. Edit body sections only; the frontmatter belongs to forge.

## Task commands and flags

```bash
python3 .claude/scripts/forge/forge.py task add T001 --epic E01 \
    --name "Set up auth scaffolding" --category A --priority 1 \
    --scope-dirs src/auth/
python3 .claude/scripts/forge/forge.py task add T002 --epic E01 \
    --name "Login + session flow" --deps T001 \
    --scope-dirs src/auth/,src/app/login/ --category A --isa
```

- `forge task add` creates the task body file from `templates/task.md` at `docs/epics/E##-{slug}/tasks/T###-{slug}.md` by default — do NOT pass `--no-file` during seeding.
- No `--deps` → task starts `ready`; with `--deps` → `pending` (auto-flips to `ready` as dependencies complete). Foundation and security tasks first; no circular dependencies — forge appends to the epic's `tasks[]` and recomputes stats for you.
- `--scope-dirs`/`--scope-files` power lock-time conflict detection between parallel sessions — fill them honestly.
- `--isa` scaffolds `docs/tasks/T###/ISA.md` — use it for E3+ tasks (multi-file, risk-bearing) where a verification trail earns its keep. Criterion count is judgment; there are no floors.
- `--preflight` defaults to `auto` (CI preflight required iff scope touches non-doc paths) — leave it alone unless the task is odd.

## Verification commands

```bash
python3 .claude/scripts/forge/forge.py task ls          # every task present
python3 .claude/scripts/forge/forge.py task ls --ready  # non-empty
```

Every registry `file` path must exist on disk (`forge task reconcile-files` with no flag dry-runs the check).

## Category codes

**Category codes** (`--category`, used for priority ordering — security/data first, polish last; no per-category quotas):

> A Security/Auth · B Navigation · C Data/CRUD · D Workflows · E Error handling · F Forms/Validation · G Search/Filter · H Responsive/X-browser · I Performance · J Integrations · K Notifications · L Preferences/Settings · M Help/Docs · N Analytics · O Accessibility/i18n · P Payments · Q Admin/Moderation · R Collaboration · S Export/Reporting · T UI Polish
