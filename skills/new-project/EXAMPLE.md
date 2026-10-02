# New Project — Worked Example, Recovery and Gotchas

## Contents

- Worked Example (greenfield)
- Error Recovery
- Gotchas

## Worked Example (greenfield)

Illustrative only: question count, stack choices, epic and task counts all come from the project in hand, not from this run.

```
User: /new-project "Invoice tracker for a small workshop — customers, invoices, payment status"

Phase 2 Discovery (5 questions):
  what's the smallest shippable version? who uses it (owner only, or staff)?
  stack preference? any accounting-system integration? personal data → yes
  (customer names/contacts) → rules/privacy.md flagged, recorded in PRD.

Phase 3 PRD → docs/prd.md
  Vision / Goals (G1 track invoices, G2 payment status at a glance) /
  User Stories (owner persona, 8 stories) / Success Criteria /
  Non-Goals: no multi-tenant, no e-invoicing compliance in v1.
CONFIRM #1 → user approves.

Phase 4 ADRs → reference/06
  ADR-001 Next.js app router · ADR-002 SQLite via Drizzle ·
  ADR-003 single-user session auth · ADR-004 deploy on VPS.
  security-boss skipped: auth is single-user, no payments processed —
  privacy.md still active for the customer-data handling.

Phase 5 reference docs 01-09 populated; 07 carries
  TODO(user): expected invoice volume/year — affects pagination + backup cadence.

Phase 6 seeding: 3 epics, 14 tasks proposed.
CONFIRM #2 → user drops 1 task (CSV import → backlog note in PRD), approves 13.
  Registry authored (E01 Foundation, E02 Invoicing, E03 Reporting) →
  epic dirs/files created → 13 × forge task add (T004 --isa: money-path
  status transitions) → task ls --ready shows T001-T003.

Phase 8: summary + "Next: /reflect resume T001" → committed.
```

## Error Recovery

- **PRD drafting stalls** (agent can't converge): save whatever analysis exists to `docs/prd.md` as a partial with `TODO(user)` markers, ask the user to fill the gaps, resume at Phase 4 once the validator passes.
- **User cancels mid-flow:** append current state to `.claude/memories/progress-notes.md` (which phases completed, which artifacts exist). Re-invoking `/new-project` later detects existing artifacts (Phase 1 re-run check) and offers to resume from the first gap.
- **Registry half-seeded** (interrupted during Phase 6): `forge task ls` shows what landed; add the missing tasks — `forge task add` rejects duplicate IDs, so re-running the remaining commands is safe.

## Gotchas

- **Epics before tasks:** `forge epic add` creates the properly-slugged epic dir + body file atomically. Without it, `forge task add` fails with `EpicNotFound`; and if the registry entry exists but the dir was removed, task bodies get parked in an `E##-untitled/` fallback dir.
- **Never hand-set frontmatter `status:`** in task files — the consistency-banner hook treats the registry as truth and silently reverts frontmatter that disagrees with it.
- **Every registry task needs its file on disk** at the recorded `file` path — `/reflect resume E##` guards on this. `forge task add` creates it by default; if a gap sneaks in, `forge task reconcile-files --apply` creates stubs (works, but the user sees warning noise — do it right at seeding).
- **PRD validator fires on every Write** while this skill runs — it reports via `additionalContext`, not by blocking; read and act on it rather than ignoring the nudge.
- **`--current` mode confirms before writing.** Detected stack/conventions can be wrong (monorepos, vendored deps, abandoned configs); a wrong `02-architecture-and-tech-stack.md` misleads every later session.
- **Delete `.template.md` originals** after populating reference docs — leaving both breeds edits to the wrong file.
- **Windows:** hook commands use `python`, not `python3`.
- **Atomic tasks or bust:** a task that can't finish in one session ends as a `continuation` with degraded context — split at seeding time, wire with `--deps`.
- **Scope honesty pays later:** empty `--scope-dirs` means lock-time conflict detection has nothing to check — two parallel sessions can then collide on the same files with no warning.
