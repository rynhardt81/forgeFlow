# code-map MCP server

Symbol-level navigation tools for Forge Flow projects, backed by `docs/code-map.json` (the structured companion to `docs/code-map.md`, both produced by the `/audit-code-map` skill).

The skill's SessionStart hook keeps both artifacts fresh. This server just queries the JSON — it never regenerates.

## Why this exists

Cole Medin's [demo](https://www.youtube.com/watch?v=efRIrLXoOVA) wraps `pyright`/`tsserver` LSPs behind an MCP server to give Claude symbol-level search. Forge Flow already extracts the same symbol data via `code_map.py` — wrapping that artifact in MCP is cheaper than running language servers per language per target project, and the data is the same shape Claude needs.

## Tools

| Tool | Purpose | Example call |
|---|---|---|
| `find_definition(symbol)` | Files where a class or top-level function is declared | `find_definition("AuthService")` |
| `find_references(symbol)` | Files that import a module declaring this symbol (coarse — module-level, not call-site) | `find_references("AuthService")` |
| `dependents_of(file)` | Files that import this file's module | `dependents_of("src/auth/service.py")` |
| `list_symbols_in_file(file)` | Classes + top-level functions declared in the file | `list_symbols_in_file("src/auth/service.py")` |
| `language_stats()` | File + LOC totals per language; cheap orientation call | `language_stats()` |

All tools are read-only. The server reloads `docs/code-map.json` automatically when its mtime changes — no daemon to restart, no stale-cache footgun.

## Installation in a target project

The server lives in this repo at `mcp-servers/code-map/`. After running `install.sh` in your target project, register it in `.claude/settings.json` (or `.mcp.json`, if you use a top-level config):

```jsonc
{
  "mcpServers": {
    "forge-code-map": {
      "command": "uv",
      "args": [
        "run",
        "--with",
        "mcp",
        "python",
        ".claude/mcp-servers/code-map/server.py"
      ]
    }
  }
}
```

The path is **project-root-relative on purpose** — do not prefix it with `${CLAUDE_PROJECT_DIR}`. Claude Code does **not** expand `${CLAUDE_PROJECT_DIR}` inside MCP `args` (it expands it in `hooks` command strings, not here — that asymmetry is the trap), so a literal `${CLAUDE_PROJECT_DIR}/…` is passed verbatim to python and fails with `No such file or directory` → JSON-RPC `-32000`. Claude Code launches MCP servers with the project root as cwd and the server's `_project_root()` falls back to cwd, so the relative path resolves correctly and stays portable.

`uv run --with mcp python …` pulls the `mcp` SDK into an ephemeral environment per launch — no global `pip install mcp` needed, and the config follows the repo for anyone who clones it. Bare `python3` fails on systems whose interpreter (e.g. Homebrew Python 3.14) has no `mcp` installed: the server prints the install hint to stderr and exits, and Claude Code surfaces JSON-RPC error `-32000`.

Then restart your Claude Code session. Verify with `/mcp` — you should see `forge-code-map` connected with five tools.

## Prerequisites

- `uv` (install via `brew install uv` on macOS, or see [astral.sh/uv](https://docs.astral.sh/uv/getting-started/installation/))
- Python 3.10+ (uses `dict | None` union syntax) — `uv` will fetch one if your system lacks it
- The `mcp` Python SDK — supplied automatically by `uv run --with mcp` (no separate install)
- `docs/code-map.json` present — produced by:
  ```bash
  python3 .claude/skills/audit-code-map/Tools/code_map.py --emit-json
  ```
  Once generated, the SessionStart hook (`hooks/session/session-context.py`) will keep it fresh via `--ensure-fresh` on every session start.

## Limitations

These are inherent to the code map's parsing model — not bugs in this server:

- **`find_references` is module-level, not call-site.** The code map records imports but not call-site usages. For exact call-site analysis, use ripgrep on the symbol name.
- **Methods are not indexed as top-level symbols.** Only class declarations and top-level functions appear. To find a method, look up its class first, then read the file.
- **TS/JS/Go/Rust parsing is regex-based.** Exotic syntax (computed class names, dynamically-named exports) may be missed. The Python AST path is exact.
- **DRY-hotspot detection isn't here.** Similarity scoring (Levenshtein/Jaccard) is a possible future extension; for now, `find_definition` returning multiple matches is your DRY signal (e.g., a function name defined in 12 files is a DRY hotspot — see the duplicated `get_project_root` in this repo).

## Environment overrides

| Variable | Default | Purpose |
|---|---|---|
| `CLAUDE_PROJECT_DIR` | _(none — falls back to `FORGE_PROJECT_ROOT`, then cwd)_ | Set by Claude Code harness; the server's project root |
| `FORGE_PROJECT_ROOT` | _(none)_ | Manual override when running outside Claude Code |
| `FORGE_CODE_MAP_JSON` | `<root>/docs/code-map.json` | Direct path to JSON artifact; useful for tests |

## Smoke test

```bash
# 1. Generate the JSON for the current repo
python3 skills/audit-code-map/Tools/code_map.py --emit-json

# 2. Run a one-shot tool invocation through stdio
# (or just use it via /mcp once the server is registered)
python3 -c "
import sys; sys.path.insert(0, 'mcp-servers/code-map')
import server
print(server.language_stats())
print(server.find_definition('YourClassName'))
"
```
