# audit-code-map — Phase walkthrough

For skill maintainers extending the analyzer. The skill itself runs in a single shot — there are no checkpoints.

## Phase 0 — Discover

Inputs: parsed CLI args (`--root`, `--output`, `--no-mermaid`, `--include-tests`, `--max-symbols-per-file`).

Steps:

1. Resolve `root` (must be a directory).
2. Compute output path (`<root>/docs/code-map.md` if not overridden); create parent dir.
3. Enumerate candidate files via `list_repo_files(root)` — prefers `git ls-files`; falls back to `Path.rglob` with `DEFAULT_EXCLUDES`.

## Phase 1 — Filter and parse

For each candidate file:

1. Skip if extension not in `LANG_BY_EXT`.
2. Skip if `--include-tests` is off and the path matches `TEST_PATTERNS` (`/tests?/`, `.test.`, `.spec.`, `_test.`).
3. Skip if LOC == 0 (empty or unreadable).
4. Dispatch to the language parser (`PARSERS[lang]`) → `(classes, functions, imports)`.
5. Build a `FileInfo` and append.

## Phase 2 — Detect stack

`detect_stack(root)` checks for known manifests at the root:

```
package.json     → Node / TS / JS
pyproject.toml   → Python (PEP 621)
requirements.txt → Python
go.mod           → Go
Cargo.toml       → Rust
Gemfile          → Ruby
pom.xml          → Java (Maven)
build.gradle     → Java (Gradle)
composer.json    → PHP
```

Returned as a list of human labels.

## Phase 3 — Render

Five rendered sections, in order, joined by blank lines:

1. `render_stack_summary(infos, stack)` — "Detected manifests" line + per-language LOC/file table sorted by LOC.
2. `render_largest_files(infos, top=20)` — Top-N table.
3. `render_module_symbols(infos, max_per_file)` — Per-file class + function listings.
4. `render_import_graph(infos, root)` — Mermaid `flowchart LR` (only when `--no-mermaid` is NOT set).
   - Collapses file paths to first-segment directory nodes.
   - Resolves import strings against `own_modules = {first-segment of every analyzed file}` — keeps own-repo edges, drops external packages.
   - Caps at top-100 edges by frequency; labels each edge with the count.
5. Final newline.

## Phase 4 — Write

Output written via `Path.write_text()` with UTF-8. Status line printed to stdout.

## Extending

### Adding a new language

1. Add the extension(s) to `LANG_BY_EXT`.
2. Implement a parser `parse_<lang>(path) -> (classes, functions, imports)`.
3. Register it in `PARSERS`.
4. Update the language table in `SKILL.md`.

If the language has a stdlib AST module (Python's `ast`, JavaScript's `acorn`-style), prefer that path over regex.

### Adding DRY hotspot detection

A natural v2 extension. Reasonable approaches:

- **Cheap heuristic**: hash 20-line sliding windows per file; report any hash with ≥2 occurrences across different files.
- **External tool**: shell out to `jscpd` if installed (`npx jscpd --silent --reporters json …`), parse JSON, render a `## DRY hotspots` section.

Either approach should be off by default and gated behind `--hotspots` to keep the default run fast.

### Output format extensions

The five render functions are pure — they take `list[FileInfo]` and return a string. New sections compose by appending another render call in `render(...)`. Keep section order stable so cross-version diffs stay reviewable.

## Failure modes (debugging the analyzer)

| Symptom | Likely cause |
|---------|--------------|
| Empty / tiny output | `git ls-files` returned nothing AND fallback rglob hit DEFAULT_EXCLUDES; check `--root` and exclude set |
| Missing classes/functions in TS file | Multi-line declaration that the regex misses; consider switching to `ts-morph` for TS-heavy projects |
| Import graph empty | All imports resolve to non-own-repo modules (i.e. external packages) — common in Python projects with mostly stdlib usage |
| Mermaid graph too dense | Reduce `max_edges` in `render_import_graph` or run with `--no-mermaid` |
