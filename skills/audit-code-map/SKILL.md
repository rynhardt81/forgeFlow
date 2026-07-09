---
name: audit-code-map
description: Generate or refresh `docs/code-map.md` — a structural map of the project's classes, top-level functions, and import graph across Python, TypeScript/JavaScript, Go, and Rust. Use when the user wants a code map, structure overview, dependency graph, module inventory, "show me how everything is wired", DRY hotspot scout, or a refreshable architecture summary. Trigger keywords — code map, structure map, module map, dependency graph, import graph, where is X defined, how are these wired, audit code structure, scan codebase, regenerate code map.
---

## Quick Scan

| | |
|---|---|
| **Purpose** | Generate `docs/code-map.md` — file inventory, per-file class/function lists, import graph. Optionally emit `docs/code-map.json` for MCP/programmatic consumers. |
| **Inputs** | None required (auto-detects stack); optional: project root, output path, flags |
| **Output** | `docs/code-map.md` (human-readable + Mermaid graph). With `--emit-json` also `docs/code-map.json` (structured artifact, consumed by the `forge-code-map` MCP server at `mcp-servers/code-map/`). |
| **Languages** | Python (full AST), TS/JS, Go, Rust (regex) |
| **Dependencies** | Python 3.8+ stdlib only — no external tools required |

---

# audit-code-map Workflow

## Invocation

User runs:

```
/audit-code-map                        # Generate or refresh docs/code-map.md
/audit-code-map --no-mermaid           # Skip the import-graph section
/audit-code-map --include-tests        # Include test files (excluded by default)
/audit-code-map --root path/to/sub     # Map a sub-tree only
/audit-code-map --output some/path.md  # Write to a different location
/audit-code-map --emit-json            # Also write docs/code-map.json (consumed by the code-map MCP server)
/audit-code-map --json-output PATH     # Custom JSON path (implies --emit-json)
```

---

## Step 1: Detect

Run the analyzer:

```bash
python3 .claude/skills/audit-code-map/Tools/code_map.py [args]
```

The script:

1. Walks the repo (uses `git ls-files` when available so `.gitignore` is honored; falls back to `Path.rglob` with a sensible exclude set).
2. Identifies language by extension. Languages NOT in `{python, ts, tsx, js, jsx, mjs, cjs, go, rs}` are skipped silently.
3. Detects stack manifests at the root (`package.json`, `pyproject.toml`, `requirements.txt`, `go.mod`, `Cargo.toml`, etc.).

## Step 2: Parse

Per file, extract top-level symbols:

| Language | Strategy | Extracts |
|----------|----------|----------|
| Python | stdlib `ast` (full parse) | classes, top-level functions, `import` + `from … import` |
| TypeScript / JavaScript | regex | `class X`, `function X`, `export const X = (` arrow functions, `import … from '…'` |
| Go | regex | `type X struct/interface`, `func X(` (incl. methods), `import "…"` (single + grouped) |
| Rust | regex | `pub struct/enum/trait`, `pub fn`/`async fn`, `use` |

Regex parsing is best-effort — multi-line declarations and unusual formatting may be missed. The Python AST path is exact.

## Step 3: Render

Produces `docs/code-map.md` with these sections:

1. **Generated metadata** — timestamp (UTC), root path, total files, total LOC.
2. **Stack** — detected manifests + per-language file/LOC table sorted by LOC.
3. **Largest files (top 20)** — file path, lang, LOC, class count, function count.
4. **DRY hotspots** — symbols declared in 3+ files of the same language (cheap duplication signal).
5. **Directories needing context files** — directories over ~20k estimated tokens (bytes ÷ 4, by immediate parent dir) that lack a nested `CLAUDE.md`/`AGENTS.md`. The "Intent Layer" heuristic — a context file here points the model at the right files instead of re-discovering structure each session. **Advisory only**: candidates, never auto-created.
6. **Module symbols** — per-file listing of top-level classes and functions, capped at `--max-symbols-per-file` (default 15) with `…` overflow indicator.
7. **Import graph** — directory-level (first-path-segment) Mermaid `flowchart LR`, edge labels = import frequency, capped at top-100 edges.

## Step 4: Commit (when running inside an Algorithm phase)

If the skill was fired by another skill or by the Algorithm BUILD phase, commit the regenerated map:

```bash
git add docs/code-map.md
git commit -m "docs(code-map): regenerate"
```

Standalone invocations leave the file unstaged so the user can review the diff.

---

## Flags

| Flag | Default | Effect |
|------|---------|--------|
| `--root PATH` | `cwd` | Project root to analyze |
| `--output PATH` | `<root>/docs/code-map.md` | Where to write the map |
| `--no-mermaid` | off | Skip the Mermaid import-graph section (faster, smaller file) |
| `--include-tests` | off | Include `tests/`, `*.test.*`, `*.spec.*`, `*_test.*` files |
| `--max-symbols-per-file N` | 15 | Cap per-file symbol listings |
| `--emit-json` | off | Also write `docs/code-map.json` — structured artifact for the `forge-code-map` MCP server |
| `--json-output PATH` | `<root>/docs/code-map.json` | Custom JSON output path. Implies `--emit-json`. |

### When does the SessionStart hook co-emit JSON?

The `--ensure-fresh` path used by `hooks/session/session-context.py` co-emits `docs/code-map.json` automatically **when the JSON already exists** alongside the markdown. The contract: if you've opted into the MCP server once (by running `/audit-code-map --emit-json`), every subsequent session keeps the JSON fresh without further intervention. If you don't want the JSON, don't generate it — the hook will only co-emit if it sees an existing JSON to refresh.

## When to use

- Onboarding into a new or unfamiliar codebase — quick structural overview
- Pre-refactor scout — identify largest files, complex modules, cross-cutting imports
- After a feature lands — regenerate the map so newcomers see the new shape
- Light DRY check — the largest-files table surfaces obvious extraction candidates
- Algorithm OBSERVE phase, when scoping a refactor or large change

## Integration with the framework

The map isn't a static artifact you generate and forget — it's wired into the runtime so agents and skills consult it without prompting:

| Integration | What it does |
|-------------|--------------|
| **SessionStart hook** (`hooks/session/session-context.py`) | Calls `code_map.py --ensure-fresh` on every session start. Regenerates `docs/code-map.md` if it's missing or older than the youngest source file, then injects a ~150-token summary block (file count, LOC, language mix, modules, top-10 largest files) into session context. |
| **Stale-on-load regen** (built into `--ensure-fresh`) | Compares map mtime to the youngest source file. If the map is behind, regenerates it before injecting. The map can never silently lie about the codebase. |
| **Framework agents** (`@architect`, `@project-manager`, `@quality-engineer`, `@security-boss`, `@devops`) | Every framework agent's `## Project conventions I respect` block includes "read `docs/code-map.md` before X". The map is part of their working context the moment they're invoked. |
| **Code-touching skills** (`/new-feature`, `/refactor`, `/fix-bug`) | Each skill has a "Step 0: Map the surface" that reads `docs/code-map.md` before classification or planning. Prevents proposals that duplicate existing capability. |
| **`forge-code-map` MCP server** (`mcp-servers/code-map/`) | Optional. Reads `docs/code-map.json` and exposes 5 tools (`find_definition`, `find_references`, `dependents_of`, `list_symbols_in_file`, `language_stats`). Opt in by running `/audit-code-map --emit-json` once and registering the server in `.claude/settings.json` — see `mcp-servers/code-map/README.md`. |

The result: agents and skills know what already exists before suggesting changes. No more "build feature X" recommendations when X mostly already lives at `src/lib/x.py`. No more "extract method Y" suggestions when Y already exists in a sibling module.

The summary block injected at SessionStart looks like this:

```
=== CODE MAP ===
Files: 42 | LOC: 10,418 | Langs: python:10,418
Modules: hooks, scripts, security, skills
Top 10 largest:
  skills/ui-ux-pro-max/scripts/design_system.py (1067 LOC)
  scripts/forge/check_consistency.py (745 LOC)
  ...
Full map: docs/code-map.md
===
```

When a deeper read is needed, the model uses `Read docs/code-map.md` to pull the full map (file inventory, per-file symbols, Mermaid import graph).

## Limitations (known)

- Polyglot regex parsers can miss exotic syntax (computed class names, dynamically-named functions, decorators-as-classes). The Python AST path is exact.
- The import graph collapses to first-path-segment nodes (`src/api/users.ts → src/api`); file-to-file edges would explode and become unreadable.
- DRY hotspot detection (cross-file duplicate code blocks) is not yet implemented in v1 — listed as a future extension. For now, large-file LOC is the proxy.
- C, C++, Java, Ruby, PHP, Swift, Kotlin, etc. — not yet supported. Files in these languages are silently skipped.

## Prerequisites

- Python 3.8+ (uses `Path` type hints, `dataclasses`, `subprocess.run(timeout=...)`)
- Git installed (optional — falls back to filesystem walk if absent)

## See also

- `skills/audit-code-map/PHASES.md` — phase walkthrough for skill maintainers
- `skills/audit-code-map/Tools/code_map.py` — the analyzer
- `agents/README.md` — `@architect` is the natural follow-up consumer of the map for ADR work
