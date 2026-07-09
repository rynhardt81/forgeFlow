#!/usr/bin/env python3
"""
code-map MCP server — symbol-level navigation tools backed by docs/code-map.json.

The companion artifact is produced by:
    python3 .claude/skills/audit-code-map/Tools/code_map.py --emit-json

The SessionStart hook keeps both docs/code-map.md and docs/code-map.json fresh
via --ensure-fresh; this server just queries the JSON.

Tools exposed:
  - find_definition(symbol)        -> files where the symbol is defined
  - find_references(symbol)        -> files that import a module exporting the symbol
  - dependents_of(file)            -> files that import the given file's module
  - list_symbols_in_file(file)     -> classes + functions declared in the file
  - language_stats()               -> file + LOC totals per language

Design notes:
  - Read-only. Never mutates docs/code-map.json. Regeneration is the skill's job.
  - Reloads JSON on every call when the file mtime has changed (cheap; the JSON
    is small — ~25KB for a 50-file repo). No long-lived stale cache.
  - Gracefully degrades when the JSON is missing — returns an actionable error
    suggesting /audit-code-map rather than crashing the session.
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print(
        "error: mcp Python SDK not installed.\n"
        "Install with: pip install mcp  (or: uv pip install mcp)",
        file=sys.stderr,
    )
    sys.exit(1)


# --- Configuration ----------------------------------------------------------

def _project_root() -> Path:
    """Resolve the project root.

    Priority: $CLAUDE_PROJECT_DIR (set by the Claude Code harness) →
    $FORGE_PROJECT_ROOT (manual override) → cwd. Matches the convention used
    by every other Forge Flow hook/script.
    """
    for env_var in ("CLAUDE_PROJECT_DIR", "FORGE_PROJECT_ROOT"):
        val = os.environ.get(env_var)
        if val:
            return Path(val)
    return Path.cwd()


def _json_path() -> Path:
    """Path to the code-map JSON artifact.

    Override with $FORGE_CODE_MAP_JSON when running the server against a
    non-standard location (e.g. tests).
    """
    override = os.environ.get("FORGE_CODE_MAP_JSON")
    if override:
        return Path(override)
    return _project_root() / "docs" / "code-map.json"


# --- Cache ------------------------------------------------------------------

class _Cache:
    """Reload the JSON when its mtime changes — never older than the source."""

    def __init__(self) -> None:
        self._mtime: float | None = None
        self._payload: dict | None = None
        self._indices: dict[str, Any] | None = None

    def load(self) -> tuple[dict | None, dict[str, Any] | None, str | None]:
        path = _json_path()
        if not path.exists():
            return None, None, (
                f"code-map JSON not found at {path}. Generate it with: "
                f"python3 .claude/skills/audit-code-map/Tools/code_map.py --emit-json"
            )
        try:
            mtime = path.stat().st_mtime
        except OSError as exc:
            return None, None, f"cannot stat {path}: {exc}"

        if self._payload is not None and self._mtime == mtime:
            return self._payload, self._indices, None

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return None, None, f"cannot read {path}: {exc}"

        self._payload = payload
        self._mtime = mtime
        self._indices = _build_indices(payload)
        return self._payload, self._indices, None


def _build_indices(payload: dict) -> dict[str, Any]:
    """Build in-memory lookups for fast symbol/import queries.

    - symbol_to_files: {symbol_name: [{file, kind}]}
    - module_to_file: {module_path_stem: file_record}  (e.g. "foo.bar" -> file)
    - imported_by: {target_file_path: [importer_file_path]}
    """
    symbol_to_files: dict[str, list[dict]] = defaultdict(list)
    module_to_file: dict[str, dict] = {}
    imported_by: dict[str, list[str]] = defaultdict(list)

    files = payload.get("files", [])

    # First pass: index symbols + module-name lookups.
    for record in files:
        path = record.get("path", "")
        for cls in record.get("classes", []):
            symbol_to_files[cls].append({"file": path, "kind": "class"})
        for fn in record.get("functions", []):
            symbol_to_files[fn].append({"file": path, "kind": "function"})

        # Module-name keys for import resolution. For Python files we strip the
        # extension and convert path separators to dots: src/foo/bar.py -> src.foo.bar.
        # We also index just the stem (bar) so partial-name imports can resolve.
        stem = Path(path).with_suffix("").as_posix()
        dotted = stem.replace("/", ".")
        module_to_file[dotted] = record
        module_to_file[stem] = record
        # Bare filename without directory (for from-X-import style on flat layouts)
        bare = Path(path).stem
        module_to_file.setdefault(bare, record)

    # Second pass: who imports whom.
    for record in files:
        importer = record.get("path", "")
        for imp in record.get("imports", []):
            # Try exact dotted match, then progressively trim segments — handles
            # "from foo.bar import baz" hitting both foo/bar.py and foo/bar/baz.py.
            candidates = [imp, imp.replace(".", "/")]
            stem = imp.split(".")[0]
            candidates.append(stem)
            for cand in candidates:
                if cand in module_to_file:
                    target = module_to_file[cand].get("path", "")
                    if target and target != importer:
                        imported_by[target].append(importer)
                    break

    return {
        "symbol_to_files": dict(symbol_to_files),
        "module_to_file": module_to_file,
        "imported_by": {k: sorted(set(v)) for k, v in imported_by.items()},
    }


_CACHE = _Cache()


# --- MCP server -------------------------------------------------------------

mcp = FastMCP("forge-code-map")


@mcp.tool()
def find_definition(symbol: str) -> dict:
    """Return files where the given symbol (class or top-level function) is defined.

    Args:
        symbol: Symbol name (case-sensitive). Examples: "AuthService", "format_date".

    Returns a dict with `symbol`, `matches` (list of {file, kind}), and `count`.
    Empty `matches` means the symbol is not declared at module top-level anywhere
    in the mapped languages — it may exist as a method, nested function, or in
    an unmapped language.
    """
    payload, indices, err = _CACHE.load()
    if err:
        return {"error": err}
    matches = indices["symbol_to_files"].get(symbol, [])
    return {"symbol": symbol, "matches": matches, "count": len(matches)}


@mcp.tool()
def find_references(symbol: str) -> dict:
    """Return files that import a module declaring this symbol.

    This is a *coarse* reference search: the code map only records imports at the
    module level, not per-symbol usage. If `symbol` is declared in `foo/bar.py`,
    this returns every file that imports `foo.bar` (or `bar`). For exact
    per-symbol call-site analysis, use ripgrep on the symbol name directly.

    Args:
        symbol: Symbol name.

    Returns a dict with `symbol`, `defined_in` (files containing the definition),
    `referenced_in` (files importing those modules), and `count`.
    """
    payload, indices, err = _CACHE.load()
    if err:
        return {"error": err}
    definitions = indices["symbol_to_files"].get(symbol, [])
    referrers: set[str] = set()
    for d in definitions:
        for ref in indices["imported_by"].get(d["file"], []):
            referrers.add(ref)
    return {
        "symbol": symbol,
        "defined_in": [d["file"] for d in definitions],
        "referenced_in": sorted(referrers),
        "count": len(referrers),
    }


@mcp.tool()
def dependents_of(file: str) -> dict:
    """Return files that import the given file's module.

    Args:
        file: Project-relative path. Example: "src/auth/service.py".

    Returns a dict with `file`, `dependents` (list of importer paths), and `count`.
    """
    payload, indices, err = _CACHE.load()
    if err:
        return {"error": err}
    dependents = indices["imported_by"].get(file, [])
    return {"file": file, "dependents": dependents, "count": len(dependents)}


@mcp.tool()
def list_symbols_in_file(file: str) -> dict:
    """Return classes + top-level functions declared in the given file.

    Args:
        file: Project-relative path. Example: "src/auth/service.py".

    Returns a dict with `file`, `lang`, `loc`, `classes`, `functions`, `imports`.
    Returns an error key if the file is not in the code map (e.g. unmapped
    language, generated file, or excluded by .gitignore).
    """
    payload, indices, err = _CACHE.load()
    if err:
        return {"error": err}
    for record in payload.get("files", []):
        if record.get("path") == file:
            return {
                "file": file,
                "lang": record.get("lang"),
                "loc": record.get("loc"),
                "classes": record.get("classes", []),
                "functions": record.get("functions", []),
                "imports": record.get("imports", []),
            }
    return {"error": f"file not in code map: {file}"}


@mcp.tool()
def dry_hotspots(min_count: int = 3, top: int = 20) -> dict:
    """Return symbols declared in N+ files of the same language — DRY candidates.

    Cheap multi-definition detector. A function name appearing in 12 files is
    usually copy-paste; a name appearing in 3 may be legitimate (`main`,
    `__init__`, `setUp`). Inspect before refactoring.

    Args:
        min_count: Minimum files a symbol must appear in to be flagged.
            Default 3. Raise to 5+ on big codebases to cut noise.
        top: Maximum hotspots to return, ordered by count descending.

    Returns a dict with `hotspots` (list) and `total_found` (int before truncation).
    """
    payload, indices, err = _CACHE.load()
    if err:
        return {"error": err}
    all_hotspots = payload.get("dry_hotspots", [])
    filtered = [h for h in all_hotspots if h.get("count", 0) >= min_count]
    return {
        "min_count": min_count,
        "total_found": len(filtered),
        "hotspots": filtered[:top],
    }


@mcp.tool()
def language_stats() -> dict:
    """Return file + LOC totals per language, plus overall totals.

    Cheap orientation call for fresh sessions — answers "what kind of repo is this?"
    in a single tool round-trip rather than reading the full markdown.
    """
    payload, indices, err = _CACHE.load()
    if err:
        return {"error": err}
    totals = payload.get("totals", {})
    return {
        "generated": payload.get("generated"),
        "files": totals.get("files", 0),
        "loc": totals.get("loc", 0),
        "by_language": totals.get("by_language", {}),
        "stack": payload.get("stack", []),
    }


# --- Entry point ------------------------------------------------------------

def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
