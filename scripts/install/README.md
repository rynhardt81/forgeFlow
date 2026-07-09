# `scripts/install/` — Forge Flow installer

Three scripts plus the cut-paths manifest:

| File | Purpose |
|------|---------|
| `install.sh` | POSIX installer (macOS / Linux) |
| `install.ps1` | PowerShell installer (Windows) |
| `verify.sh`  | Post-install structural drift checker |
| `cut-paths.txt` | Declared cut-paths manifest (permanent retired-paths ledger; read on every refresh) |

## Cut-paths mechanism

Forge Flow deploys framework files via additive `rsync`. When a path is **removed** from the framework source (e.g. a skill is consolidated, an agent is retired, a hook is replaced), the new structure lands in consumers on refresh, but the old path **persists** — `rsync` has no delete-on-source-missing semantics in our deploy mode.

The cut-paths manifest at `cut-paths.txt` declares those removals so the installer can clean them up.

### How it works

1. `install.sh --mode refresh-framework`, `install.sh --mode refresh-v3` (and their `install.ps1` equivalents) all read `cut-paths.txt`
2. Each non-comment path is interpreted relative to the consumer's `.claude/` directory
3. If the path exists in the consumer, it is removed (with backup if `--backup` is in effect; outright if `--no-backup`)
4. Anti-clobber guard: hard-coded denylist refuses to touch `agents/specialists/`, `docs/tasks/`, `docs/project-memory/`, `daily/` even if the manifest mistakenly lists them
5. Absolute paths and `..` traversals are rejected at install-time

### Adding a cut-path entry (maintainer workflow)

When you `git rm` a framework path that was previously shipped to consumers, add an entry to `cut-paths.txt`:

```text
# YYYY-MM-DD — commit <short-sha> <one-line reason for the cut>
relative/path/under/dot-claude/
```

Rules:

- **Relative paths only** — interpreted against `<project>/.claude/`. No leading `/`, no `..`.
- **Trailing slash optional** — directories and files both supported. Use a trailing slash for directories as a readability hint.
- **One path per line.**
- **Always include a comment line above** with the date, commit short-SHA that did the cut, and a one-line reason. This is the audit trail.
- **Do NOT list user-owned paths** — `agents/specialists/`, `docs/tasks/`, `docs/project-memory/`, `daily/` are refused by the denylist even if you add them. The denylist is defense-in-depth, not your authority — never try to bypass it.

Once added, the next consumer refresh will pick it up automatically. No code changes needed.

### What the installer prints

```text
▸ Removing framework-cut paths (cut-paths.txt)
  cut: skills/design (backed up to .claude/backups/<ts>/cut-paths/skills/design)
✓ Removed 1 cut path(s); backups at .claude/backups/<ts>/cut-paths
```

With `--no-backup`:

```text
▸ Removing framework-cut paths (cut-paths.txt)
  cut: skills/design (removed)
✓ Removed 1 cut path(s)
```

### Why a flat-text manifest?

The format is intentionally minimal so both bash and PowerShell can parse it with stdlib primitives — no jq, no YAML parser, no new dependencies. Comments live next to entries so an auditor can answer "why was this cut?" without spelunking through git log.

### Scope boundary

This manifest is the **permanent, version-agnostic ledger of framework-retired paths**, applied on every routine refresh (`refresh-framework`) as well as the one-time `refresh-v3` upgrade path. The one-time v2 → v3 migration cleanup is handled separately by `install_v3_cut_v2_cleanup` (install.sh) / `Install-V3CutV2Cleanup` (install.ps1) and is not parameterised through this manifest.
