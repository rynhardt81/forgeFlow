# Database Migration Rules

> Active directive. Discovered on-demand via the `rules/*.md` glob — read by `/audit-rules`, ALGORITHM Gate E, and any agent touching schema. Treat as binding when encountered. A bad production migration is the single worst unrecoverable failure available to a small team — these rules exist to make that failure structurally hard.

## Gate E (from ALGORITHM): fires when migration files, DDL, or model/schema definitions are in scope

Before any schema change is applied anywhere:

1. **Backup verified, not assumed.** A restorable backup of the target database exists and you have CONFIRMED it (list the backup, check its timestamp — for Supabase: dashboard backup list or `pg_dump` artifact; for anything else: the platform's equivalent). "The platform auto-backs-up" without checking is forbidden language.
2. **Every migration is paired with its rollback** — a down-migration, or for destructive steps an explicit written recovery note ("restore column from backup table `_backup_users_20260703`"). No rollback story → the migration does not ship.
3. **The migration has an `Anti:` ISC** on the task: "Anti: existing rows unreadable / data loss / app version N-1 breaks against new schema."

## Expand / contract — the only safe shape for live systems

Never make a change that breaks the currently-deployed app version. Split into phases across releases:

| Phase | What | Example |
|-------|------|---------|
| **Expand** | Add the new column/table/index NULLABLE or with defaults; deploy app code that writes BOTH old and new | add `display_name`, keep writing `name` |
| **Migrate** | Backfill data in batches (bounded, resumable — never one giant UPDATE on a hot table) | `UPDATE ... WHERE id BETWEEN ...` loop |
| **Contract** | Only after the old path has zero readers (verify with logs/queries, not assumption): drop the old column in a LATER release | drop `name` next release |

Renames are always expand+contract (new column, dual-write, backfill, drop) — never `ALTER ... RENAME` on a live table with a deployed app reading the old name.

## DO / DON'T

- **DO** run every migration against a local/branch database first (Supabase: branch or local stack; verify with a `SELECT` probing the new shape + one probing old data survived).
- **DO** make backfills idempotent — re-running must be safe.
- **DO** add indexes `CONCURRENTLY` (Postgres) on non-trivial tables; a blocking index build is an outage.
- **DO** keep migrations in versioned files under the project's migration dir (`supabase/migrations/`, `prisma/migrations/`, `drizzle/`) — never apply ad-hoc SQL to prod that isn't captured as a migration file.
- **DON'T** edit an already-applied migration file — write a new one (checksum drift breaks every environment that already ran it).
- **DON'T** mix schema change and data backfill in one migration on large tables — separate steps, separate failure domains.
- **DON'T** drop or narrow a column in the same release that stops writing it.
- **DON'T** trust ORM-generated destructive diffs (column type changes that recreate tables) without reading the generated SQL.

## RLS / policies (Supabase-specific)

A new table without RLS enabled and policies written is a data leak, not a migration. The migration that creates a table containing user data MUST enable RLS and create its policies in the same file — probe with a `SELECT` as an unauthorized role (expect zero rows / permission error).

## Verification probes (ISA `## Verification` entries for schema ISCs)

- `SELECT` confirming new shape + one legacy row still reads correctly
- App smoke: the previous app version's critical query still succeeds against the new schema (expand phase)
- RLS probe for any new user-data table
- Rollback rehearsed on the branch/local DB (actually run the down path once)
