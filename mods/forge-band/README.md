# forge-band

A Claude Code mod (a plugin of function hooks, Claude Code v2.1.287+) that draws a
bordered band above the prompt:

```
╭──────────────────────────────────────────────────────────────────────────────────────────╮
│ ◆ forge   ● 42m cache · 180k ctx   ▸ T313 · E16 · 7 ready   ✓ in sync   [Status] [Resume] [Handoff] [Run E16] × │
╰──────────────────────────────────────────────────────────────────────────────────────────╯
```

- **Cache** — minutes left before the prompt cache lapses, counted 60 minutes from the
  last main-thread reply (an estimate: the mod cannot read the real TTL, which drops to
  5 minutes under usage overage). Green > 15m, yellow ≤ 15m, red ≤ 5m; one toast at 5m.
- **Next task** — first entry of `forge task ls --ready --json`.
- **Drift** — finding count from `consistency-banner.py --json` (check only, no `--fix`).
- **Buttons** — `/reflect status|resume|handoff` and `/run-epic <epic of next task>`.
  Run needs a second press within 10s. A button whose skill is not installed is hidden.
- `/forge-band` prints the same line as text; `/forge-band show` unhides the band.

The mod only reads. Python settings hooks stay the floor: mods can be switched off
(`disableAllHooks`, `--safe-mode`, an organisation's `allowManagedModsOnly`).

## Load

Refresh copies this folder to `<project>/.claude/mods/forge-band/`. Load it per session:

```bash
claude --plugin-dir .claude/mods/forge-band
```

## Develop

```bash
claude plugin validate mods/forge-band
cd mods/forge-band && claude plugin test
```
