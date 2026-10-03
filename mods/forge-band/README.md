# forge-band

A Claude Code mod (a plugin of function hooks, Claude Code v2.1.287+) that draws a
bordered band above the prompt:

```
╭──────────────────────────────────────────────────────────────────────────────────────────╮
│ ◆ forge v4.8.0   ● 42m cache · 180k ctx   ▸ T313 · E16 · 7 ready   ✓ in sync   [Status] [Resume] [Handoff] [Review PR] [Run E16] × │
╰──────────────────────────────────────────────────────────────────────────────────────────╯
```

- **Cache** — minutes left before the prompt cache lapses, counted 60 minutes from the
  last main-thread reply (an estimate: the mod cannot read the real TTL, which drops to
  5 minutes under usage overage). Green > 15m, yellow ≤ 15m, red ≤ 5m; one toast at 5m.
- **Version** — installed Forge Flow version from `forge version` (hidden on pre-4.2
  installs that have no `VERSION` file).
- **Next task** — first entry of `forge task ls --ready --json`.
- **Drift** — finding count from `consistency-banner.py --json` (check only, no `--fix`).
- **Buttons** — `/reflect status|resume|handoff`, `/pr-review-toolkit:review-pr` and
  `/run-epic <epic of next task>`.
  Run needs a second press within 10s. A button whose skill is not installed is hidden.
- `/forge-band` prints the same line as text; `/forge-band show` unhides the band.

The band's own refresh only reads: it never writes a file or task state. Its buttons are
different — a press runs that skill, and `/run-epic` or `/reflect handoff` can change files,
task state and git history, which is why Run needs a confirming second press.

Python settings hooks stay the floor: mods can be switched off
(`disableAllHooks`, `--safe-mode`, an organisation's `allowManagedModsOnly`).

## Load

Refresh copies this folder to `<project>/.claude/mods/forge-band/`; in the framework repo
it lives at `mods/forge-band/`. Claude Code does not load it on its own.

**Every session** — add the folder to the `env` block of `~/.claude/settings.json`
(a project's settings are not read for this), then restart Claude:

```json
"env": { "CLAUDE_CODE_PLUGIN_DIRS": "/absolute/path/to/forge-band" }
```

The path must be absolute (`~` allowed); separate several with `:`. One copy serves
every project: the band finds Forge Flow under `.claude/` or at the repo root, and outside
a Forge Flow project it shows the cache alone.

**One session only** — the flag lasts until you exit:

```bash
claude --plugin-dir .claude/mods/forge-band   # mods/forge-band in the framework repo
```

## Develop

```bash
claude plugin validate mods/forge-band
cd mods/forge-band && claude plugin test
```
