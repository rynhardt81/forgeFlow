#!/usr/bin/env python3
"""
code_map.py — Generate docs/code-map.md from the current project.

Pure-Python stdlib analyzer. No mandatory external tools.

Output sections:
  1. Generated metadata
  2. Stack summary (languages + file/LOC counts)
  3. Largest files (top 20 by LOC)
  4. Module symbols (per-file classes + top-level functions)
  5. Import graph (Mermaid)

Languages supported v1:
  - Python    (stdlib ast — full)
  - TypeScript / JavaScript   (regex — classes, functions, imports)
  - Go                        (regex — types, funcs, package, imports)
  - Rust                      (regex — pub fn, pub struct, mod, use)

Usage:
  python3 code_map.py [--root PATH] [--output PATH] [--no-mermaid]
                     [--include-tests] [--max-symbols-per-file N]
"""

from __future__ import annotations

import argparse
import ast
import datetime as dt
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

LANG_BY_EXT = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".go": "go",
    ".rs": "rust",
}

DEFAULT_EXCLUDES = {
    ".git", "node_modules", "dist", "build", "target", "venv",
    ".venv", "__pycache__", ".next", ".nuxt", "out", "coverage",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".turbo",
    ".cache", "vendor", ".terraform",
}

TEST_PATTERNS = re.compile(r"(/tests?/|\.test\.|\.spec\.|_test\.)", re.IGNORECASE)

# Intent-layer context-file heuristic. A directory whose source weighs more than
# CONTEXT_FILE_TOKEN_THRESHOLD estimated tokens and has no nested context file is
# a candidate for one — re-discovering its structure every session is the input-
# token waste a nested CLAUDE.md/AGENTS.md eliminates. ~20k matches the common
# "Intent Layer" convention. Token estimate is bytes/CHARS_PER_TOKEN (≈4 chars
# per token for code) — steadier across languages than a per-line estimate.
CONTEXT_FILE_TOKEN_THRESHOLD = 20_000
CHARS_PER_TOKEN = 4
CONTEXT_FILENAMES = ("CLAUDE.md", "AGENTS.md")


@dataclass
class FileInfo:
    path: Path
    lang: str
    loc: int
    size: int = 0  # bytes on disk — drives the token estimate for context-file flagging
    classes: list[str] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)


def list_repo_files(root: Path) -> list[Path]:
    """Use git ls-files when available — respects .gitignore. Fallback to rglob."""
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "ls-files"],
            capture_output=True, text=True, check=True, timeout=10,
        )
        return [root / line for line in out.stdout.splitlines() if line]
    except (subprocess.SubprocessError, FileNotFoundError):
        files = []
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if any(part in DEFAULT_EXCLUDES for part in p.parts):
                continue
            files.append(p)
        return files


def loc_of(path: Path) -> int:
    try:
        return sum(1 for _ in path.open("r", encoding="utf-8", errors="ignore"))
    except OSError:
        return 0


def parse_python(path: Path) -> tuple[list[str], list[str], list[str]]:
    """Return (classes, top-level functions, imports) using stdlib ast."""
    try:
        source = path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source, filename=str(path))
    except (SyntaxError, ValueError, OSError):
        return [], [], []

    classes, funcs, imports = [], [], []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs.append(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return classes, funcs, imports


_TS_CLASS = re.compile(r"^\s*(?:export\s+)?(?:abstract\s+)?class\s+([A-Z][\w$]*)", re.MULTILINE)
_TS_FUNC = re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)", re.MULTILINE)
_TS_ARROW = re.compile(r"^\s*(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?\(", re.MULTILINE)
_TS_IMPORT = re.compile(r"""^\s*import[^'"]*['"]([^'"]+)['"]""", re.MULTILINE)


def parse_ts_js(path: Path) -> tuple[list[str], list[str], list[str]]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return [], [], []
    classes = _TS_CLASS.findall(text)
    funcs = _TS_FUNC.findall(text) + _TS_ARROW.findall(text)
    imports = _TS_IMPORT.findall(text)
    return classes, funcs, imports


_GO_TYPE = re.compile(r"^\s*type\s+([A-Z]\w*)\s+(?:struct|interface)\b", re.MULTILINE)
_GO_FUNC = re.compile(r"^func\s+(?:\([^)]+\)\s+)?([A-Za-z_]\w*)\s*\(", re.MULTILINE)
_GO_IMPORT = re.compile(r"""import\s*(?:\(\s*([^)]+)\)|"([^"]+)")""", re.MULTILINE)
_GO_IMPORT_LINE = re.compile(r"""^\s*"([^"]+)"\s*$""", re.MULTILINE)


def parse_go(path: Path) -> tuple[list[str], list[str], list[str]]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return [], [], []
    classes = _GO_TYPE.findall(text)
    funcs = _GO_FUNC.findall(text)
    imports = []
    for block, single in _GO_IMPORT.findall(text):
        if single:
            imports.append(single)
        if block:
            imports.extend(_GO_IMPORT_LINE.findall(block))
    return classes, funcs, imports


_RS_STRUCT = re.compile(r"^\s*(?:pub\s+)?(?:struct|enum|trait)\s+([A-Z]\w*)", re.MULTILINE)
_RS_FN = re.compile(r"^\s*(?:pub\s+)?(?:async\s+)?fn\s+(\w+)", re.MULTILINE)
_RS_USE = re.compile(r"^\s*(?:pub\s+)?use\s+([\w:]+)", re.MULTILINE)


def parse_rust(path: Path) -> tuple[list[str], list[str], list[str]]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return [], [], []
    classes = _RS_STRUCT.findall(text)
    funcs = _RS_FN.findall(text)
    imports = _RS_USE.findall(text)
    return classes, funcs, imports


PARSERS = {
    "python": parse_python,
    "typescript": parse_ts_js,
    "javascript": parse_ts_js,
    "go": parse_go,
    "rust": parse_rust,
}


def detect_stack(root: Path) -> list[str]:
    """Return list of detected stack manifests."""
    manifests = {
        "package.json": "Node / TS / JS",
        "pyproject.toml": "Python (PEP 621)",
        "requirements.txt": "Python",
        "go.mod": "Go",
        "Cargo.toml": "Rust",
        "Gemfile": "Ruby",
        "pom.xml": "Java (Maven)",
        "build.gradle": "Java (Gradle)",
        "composer.json": "PHP",
    }
    return [label for f, label in manifests.items() if (root / f).exists()]


def build_file_infos(root: Path, files: list[Path], include_tests: bool) -> list[FileInfo]:
    infos: list[FileInfo] = []
    for path in files:
        ext = path.suffix.lower()
        lang = LANG_BY_EXT.get(ext)
        if not lang:
            continue
        rel = path.relative_to(root).as_posix()
        if not include_tests and TEST_PATTERNS.search("/" + rel):
            continue
        loc = loc_of(path)
        if loc == 0:
            continue
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        classes, funcs, imports = PARSERS[lang](path)
        infos.append(FileInfo(
            path=Path(rel), lang=lang, loc=loc, size=size,
            classes=classes, functions=funcs, imports=imports,
        ))
    return infos


def render_stack_summary(infos: list[FileInfo], stack: list[str]) -> str:
    lang_counts = Counter(f.lang for f in infos)
    lang_loc = defaultdict(int)
    for f in infos:
        lang_loc[f.lang] += f.loc

    lines = ["## Stack", ""]
    if stack:
        lines.append("**Detected manifests:** " + ", ".join(f"`{s}`" for s in stack))
        lines.append("")
    lines.append("| Language | Files | LOC |")
    lines.append("|----------|------:|----:|")
    for lang in sorted(lang_counts, key=lambda l: -lang_loc[l]):
        lines.append(f"| {lang} | {lang_counts[lang]} | {lang_loc[lang]:,} |")
    return "\n".join(lines)


def render_largest_files(infos: list[FileInfo], top: int = 20) -> str:
    sorted_infos = sorted(infos, key=lambda f: -f.loc)[:top]
    lines = [f"## Largest files (top {top})", ""]
    lines.append("| File | Lang | LOC | Classes | Functions |")
    lines.append("|------|------|----:|--------:|----------:|")
    for f in sorted_infos:
        lines.append(
            f"| `{f.path.as_posix()}` | {f.lang} | {f.loc:,} | "
            f"{len(f.classes)} | {len(f.functions)} |"
        )
    return "\n".join(lines)


def render_module_symbols(infos: list[FileInfo], max_per_file: int) -> str:
    files_with_symbols = [f for f in infos if f.classes or f.functions]
    files_with_symbols.sort(key=lambda f: f.path.as_posix())
    lines = ["## Module symbols", ""]
    lines.append(
        f"_Each entry shows top-level classes and functions per file. "
        f"Truncated at {max_per_file} symbols per file; `…` indicates more present._"
    )
    lines.append("")
    for f in files_with_symbols:
        lines.append(f"### `{f.path.as_posix()}` _{f.lang}, {f.loc} LOC_")
        if f.classes:
            shown = f.classes[:max_per_file]
            suffix = " …" if len(f.classes) > max_per_file else ""
            lines.append("**Classes:** " + ", ".join(f"`{c}`" for c in shown) + suffix)
        if f.functions:
            shown = f.functions[:max_per_file]
            suffix = " …" if len(f.functions) > max_per_file else ""
            lines.append("**Functions:** " + ", ".join(f"`{fn}`" for fn in shown) + suffix)
        lines.append("")
    return "\n".join(lines)


def render_import_graph(infos: list[FileInfo], root: Path, max_edges: int = 100) -> str:
    """Render a Mermaid graph of directory-level imports.

    File-level edges explode quickly; we collapse to first-segment-of-path nodes
    (e.g. `src/api/users.ts -> src/db/conn.ts` becomes `src/api -> src/db`).
    """
    edges: Counter[tuple[str, str]] = Counter()
    own_modules = {f.path.parts[0] for f in infos if f.path.parts}

    def node_for(path_str: str) -> str | None:
        head = path_str.split("/", 1)[0].split(".", 1)[0]
        if head in own_modules:
            return head
        return None

    for f in infos:
        if not f.path.parts:
            continue
        src_node = f.path.parts[0]
        for imp in f.imports:
            tgt_node = node_for(imp.replace(".", "/"))
            if tgt_node and tgt_node != src_node:
                edges[(src_node, tgt_node)] += 1

    if not edges:
        return "## Import graph\n\n_No cross-module imports detected (or all imports are external packages)._"

    top_edges = edges.most_common(max_edges)
    lines = ["## Import graph", "", "```mermaid", "flowchart LR"]
    nodes_seen = set()
    for (src, tgt), weight in top_edges:
        if src not in nodes_seen:
            lines.append(f"    {src}([{src}])")
            nodes_seen.add(src)
        if tgt not in nodes_seen:
            lines.append(f"    {tgt}([{tgt}])")
            nodes_seen.add(tgt)
        lines.append(f"    {src} -->|{weight}| {tgt}")
    lines.append("```")
    if len(edges) > max_edges:
        lines.append("")
        lines.append(f"_Showing top {max_edges} edges by frequency; {len(edges) - max_edges} more elided._")
    return "\n".join(lines)


def compute_dry_hotspots(infos: list[FileInfo], min_occurrences: int = 3) -> list[dict]:
    """Identify symbols (class or top-level function) declared in N+ files.

    Cheap DRY signal — the spec's full Levenshtein/Jaccard version is a future
    extension. For now: any same-named symbol appearing in `min_occurrences`+
    files of the same language is a candidate hotspot.

    Returns list ordered by occurrence count descending, then symbol name.
    Each entry: {symbol, kind, lang, count, files: [paths]}.
    """
    # (symbol, lang, kind) -> list of file paths
    occurrences: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for f in infos:
        for cls in f.classes:
            occurrences[(cls, f.lang, "class")].append(f.path.as_posix())
        for fn in f.functions:
            occurrences[(fn, f.lang, "function")].append(f.path.as_posix())

    hotspots = [
        {
            "symbol": symbol,
            "kind": kind,
            "lang": lang,
            "count": len(files),
            "files": sorted(set(files)),
        }
        for (symbol, lang, kind), files in occurrences.items()
        if len(set(files)) >= min_occurrences
    ]
    hotspots.sort(key=lambda h: (-h["count"], h["symbol"]))
    return hotspots


def render_dry_hotspots(hotspots: list[dict], top: int = 20) -> str:
    if not hotspots:
        return (
            "## DRY hotspots\n\n"
            "_No symbols declared in 3+ files. Either the codebase is well-factored "
            "or it's small enough that duplication hasn't surfaced yet._"
        )
    lines = [
        f"## DRY hotspots (top {min(top, len(hotspots))})",
        "",
        "_Symbols declared in 3+ files of the same language. Often legitimate "
        "(e.g. `main`, `__init__`), often not. Inspect before refactoring._",
        "",
        "| Symbol | Kind | Lang | Count | Files |",
        "|--------|------|------|------:|-------|",
    ]
    for h in hotspots[:top]:
        files_str = ", ".join(f"`{p}`" for p in h["files"][:5])
        if len(h["files"]) > 5:
            files_str += f" _(+{len(h['files']) - 5} more)_"
        lines.append(
            f"| `{h['symbol']}` | {h['kind']} | {h['lang']} | {h['count']} | {files_str} |"
        )
    if len(hotspots) > top:
        lines.extend(["", f"_Showing top {top} of {len(hotspots)} hotspots._"])
    return "\n".join(lines)


def compute_context_file_candidates(
    infos: list[FileInfo],
    root: Path,
    token_threshold: int = CONTEXT_FILE_TOKEN_THRESHOLD,
) -> list[dict]:
    """Directories heavy enough to warrant a nested context file but lacking one.

    The "Intent Layer" heuristic: a directory whose source weighs more than
    ~token_threshold tokens is one the model would otherwise re-discover from
    scratch each session. A nested CLAUDE.md/AGENTS.md in that directory points
    it straight at the right files instead. We flag such directories that don't
    already have one.

    Aggregation is by IMMEDIATE PARENT DIRECTORY (the dir each source file lives
    in) — simple and double-count-free. A heavy subtree split across many small
    leaf dirs may slip under the bar; that's the conservative trade (we under-
    flag rather than over-flag). The repo root itself is excluded — the root
    CLAUDE.md already covers it.

    Token estimate = bytes / CHARS_PER_TOKEN. Returns dirs over threshold without
    a context file, ordered by estimated tokens descending.
    """
    dir_bytes: dict[str, int] = defaultdict(int)
    dir_files: dict[str, int] = defaultdict(int)
    for f in infos:
        parent = f.path.parent.as_posix()
        if parent in (".", ""):
            continue  # repo root — covered by the root CLAUDE.md
        dir_bytes[parent] += f.size
        dir_files[parent] += 1

    candidates: list[dict] = []
    for d, total_bytes in dir_bytes.items():
        est_tokens = total_bytes // CHARS_PER_TOKEN
        if est_tokens < token_threshold:
            continue
        has_context = any(
            (root / d / name).is_file() for name in CONTEXT_FILENAMES
        )
        if has_context:
            continue
        candidates.append({
            "directory": d,
            "est_tokens": est_tokens,
            "files": dir_files[d],
        })
    candidates.sort(key=lambda c: (-c["est_tokens"], c["directory"]))
    return candidates


def render_context_file_candidates(
    candidates: list[dict],
    token_threshold: int = CONTEXT_FILE_TOKEN_THRESHOLD,
) -> str:
    threshold_k = token_threshold // 1000
    if not candidates:
        return (
            "## Directories needing context files\n\n"
            f"_No directory exceeds ~{threshold_k}k estimated tokens without a "
            "nested `CLAUDE.md`/`AGENTS.md`. Either the tree is well-covered or "
            "no single directory is heavy enough to warrant one._"
        )
    lines = [
        "## Directories needing context files",
        "",
        f"_Directories over ~{threshold_k}k estimated tokens with no nested "
        "`CLAUDE.md`/`AGENTS.md`. A context file here points the model straight "
        "at the right files instead of re-discovering structure each session "
        "(the \"Intent Layer\" pattern). **Advisory only** — candidates, not "
        "auto-created. Estimate = bytes ÷ 4; aggregated by immediate parent "
        "directory._",
        "",
        "| Directory | Est. tokens | Files |",
        "|-----------|------------:|------:|",
    ]
    for c in candidates:
        lines.append(
            f"| `{c['directory']}/` | {c['est_tokens']:,} | {c['files']} |"
        )
    return "\n".join(lines)


def render(infos: list[FileInfo], root: Path, stack: list[str],
           include_mermaid: bool, max_symbols_per_file: int) -> str:
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    total_loc = sum(f.loc for f in infos)
    hotspots = compute_dry_hotspots(infos)
    sections = [
        "# Code Map\n",
        "> Auto-generated by `audit-code-map` skill. Do not edit manually.",
        f"> Generated: {ts} | Root: `{root.name}` | Files: {len(infos)} | LOC: {total_loc:,}",
        "",
        render_stack_summary(infos, stack),
        "",
        render_largest_files(infos),
        "",
        render_dry_hotspots(hotspots),
        "",
        render_context_file_candidates(compute_context_file_candidates(infos, root)),
        "",
        render_module_symbols(infos, max_symbols_per_file),
    ]
    if include_mermaid:
        sections.extend(["", render_import_graph(infos, root)])
    sections.append("")
    return "\n".join(sections)


def render_summary(infos: list[FileInfo], root: Path, stack: list[str],
                   map_path: Path, top_files: int = 10) -> str:
    """Compact ~150-token summary. Used by SessionStart hook."""
    if not infos:
        return "=== CODE MAP ===\nNo source files mapped. Run `/audit-code-map` to scaffold.\n==="

    total_loc = sum(f.loc for f in infos)
    lang_loc = defaultdict(int)
    for f in infos:
        lang_loc[f.lang] += f.loc
    lang_str = ", ".join(
        f"{l}:{loc:,}" for l, loc in sorted(lang_loc.items(), key=lambda x: -x[1])
    )

    largest = sorted(infos, key=lambda f: -f.loc)[:top_files]
    largest_lines = [f"  {f.path.as_posix()} ({f.loc} LOC)" for f in largest]

    own_modules = sorted({f.path.parts[0] for f in infos if f.path.parts})

    rel_map = map_path.relative_to(root).as_posix() if map_path.is_relative_to(root) else str(map_path)

    return "\n".join([
        "=== CODE MAP ===",
        f"Files: {len(infos)} | LOC: {total_loc:,} | Langs: {lang_str}",
        f"Modules: {', '.join(own_modules)}",
        f"Top {top_files} largest:",
        *largest_lines,
        f"Full map: {rel_map}",
        "===",
    ])


def resolve_file_edges(infos: list[FileInfo]) -> list[dict]:
    """Resolve each import to a target file within the project, when possible.

    Returns a list of {"source": <path>, "target": <path>, "import": <raw>}
    dicts. Imports that resolve to external packages (or can't be resolved)
    are dropped — they appear in the per-file `imports` array unchanged for
    consumers that want the raw view.

    Resolution strategy per language:
      - Python: `pkg.mod` → `pkg/mod.py` or `pkg/mod/__init__.py` (treats
        the import as project-rooted; relative imports starting with `.` are
        not currently emitted by the parser so we don't handle them).
      - TS / JS: `'./foo'` or `'../foo/bar'` → resolve relative to source
        file, try `.ts .tsx .js .jsx .mjs .cjs` and `/index.*`. Bare imports
        (`'react'`, `'@scope/pkg'`) are skipped.
      - Go / Rust: skipped (import strings are package paths, not file paths).
        Module-level grouping in the existing Mermaid graph covers them.

    Output is consumed by the Forge Dashboard code-map generator's Layer 3
    (per-file mini-graph). External or unresolvable imports drop out — they
    remain visible in the per-file `imports` array.
    """
    by_path: dict[str, FileInfo] = {f.path.as_posix(): f for f in infos}

    TS_EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")

    def resolve_python(imp: str) -> str | None:
        if not imp or imp.startswith("."):
            return None
        parts = imp.split(".")
        candidates = [
            "/".join(parts) + ".py",
            "/".join(parts) + "/__init__.py",
        ]
        for c in candidates:
            if c in by_path:
                return c
        return None

    def resolve_ts(source_path: str, imp: str) -> str | None:
        if not imp or not (imp.startswith("./") or imp.startswith("../")):
            return None
        source_dir = "/".join(source_path.split("/")[:-1])
        parts = (source_dir + "/" + imp).split("/") if source_dir else imp.split("/")
        normalized: list[str] = []
        for p in parts:
            if p == "" or p == ".":
                continue
            if p == "..":
                if normalized:
                    normalized.pop()
                continue
            normalized.append(p)
        base = "/".join(normalized)
        if not base:
            return None
        if base in by_path:
            return base
        for ext in TS_EXTS:
            if base + ext in by_path:
                return base + ext
            if base + "/index" + ext in by_path:
                return base + "/index" + ext
        return None

    edges: list[dict] = []
    for f in infos:
        src = f.path.as_posix()
        for imp in f.imports:
            target: str | None = None
            if f.lang == "python":
                target = resolve_python(imp)
            elif f.lang in ("typescript", "javascript"):
                target = resolve_ts(src, imp)
            if target and target != src:
                edges.append({"source": src, "target": target, "import": imp})
    return edges


def emit_json(infos: list[FileInfo], root: Path, stack: list[str]) -> dict:
    """Build the structured artifact consumed by the code-map MCP server.

    Schema is intentionally flat and append-safe:
      - version: bump on breaking changes; consumers should accept >= their floor
      - generated: ISO-8601 UTC
      - root: absolute project root (for cross-checking)
      - stack: detected manifest labels (informational)
      - totals: files + LOC by language
      - files: per-file records with classes/functions/imports

    The MCP server treats `files` as the index — it builds in-memory lookups
    (symbol -> file, file -> imports, file -> imported-by) at startup.
    """
    lang_counts: Counter[str] = Counter()
    lang_loc: dict[str, int] = defaultdict(int)
    for f in infos:
        lang_counts[f.lang] += 1
        lang_loc[f.lang] += f.loc

    file_records = [
        {
            "path": f.path.as_posix(),
            "lang": f.lang,
            "loc": f.loc,
            "classes": list(f.classes),
            "functions": list(f.functions),
            "imports": list(f.imports),
        }
        for f in infos
    ]

    return {
        "version": 3,
        "generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "root": str(root),
        "stack": list(stack),
        "totals": {
            "files": len(infos),
            "loc": sum(f.loc for f in infos),
            "by_language": {
                lang: {"files": lang_counts[lang], "loc": lang_loc[lang]}
                for lang in sorted(lang_counts, key=lambda l: -lang_loc[l])
            },
        },
        "files": file_records,
        "dry_hotspots": compute_dry_hotspots(infos),
        "context_file_candidates": compute_context_file_candidates(infos, root),
        "file_edges": resolve_file_edges(infos),
    }


def write_json(payload: dict, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def is_stale(map_path: Path, files: list[Path]) -> bool:
    """Map is stale if missing or older than the youngest source file."""
    if not map_path.exists():
        return True
    map_mtime = map_path.stat().st_mtime
    for f in files:
        try:
            if f.stat().st_mtime > map_mtime:
                return True
        except OSError:
            continue
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate docs/code-map.md for the current project.")
    ap.add_argument("--root", type=Path, default=Path.cwd(),
                    help="Project root (default: cwd)")
    ap.add_argument("--output", type=Path, default=None,
                    help="Output path (default: <root>/docs/code-map.md)")
    ap.add_argument("--no-mermaid", action="store_true",
                    help="Skip the Mermaid import-graph section")
    ap.add_argument("--include-tests", action="store_true",
                    help="Include test files (default: excluded)")
    ap.add_argument("--max-symbols-per-file", type=int, default=15,
                    help="Cap symbols listed per file (default: 15)")
    ap.add_argument("--summary", action="store_true",
                    help="Print compact summary block to stdout (no file write)")
    ap.add_argument("--ensure-fresh", action="store_true",
                    help="Hook entry: regen if missing/stale, then print summary. Always exits 0.")
    ap.add_argument("--emit-json", action="store_true",
                    help="Also write docs/code-map.json (structured artifact for the code-map MCP server)")
    ap.add_argument("--json-output", type=Path, default=None,
                    help="JSON output path (default: <root>/docs/code-map.json). Implies --emit-json.")
    args = ap.parse_args()

    root = args.root.resolve()
    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        return 1

    output = args.output or (root / "docs" / "code-map.md")
    emit_json_flag = args.emit_json or (args.json_output is not None)
    json_output = args.json_output or (root / "docs" / "code-map.json")

    files = list_repo_files(root)

    # --ensure-fresh: hook-friendly mode — never blocks the session.
    # Co-emit JSON when emit-json is requested OR a code-map.json already exists
    # next to the markdown — the MCP server may depend on it staying fresh.
    if args.ensure_fresh:
        try:
            stale = is_stale(output, files)
            json_exists = json_output.exists()
            want_json = emit_json_flag or json_exists
            if stale:
                output.parent.mkdir(parents=True, exist_ok=True)
                infos = build_file_infos(root, files, include_tests=args.include_tests)
                stack = detect_stack(root)
                body = render(infos, root, stack,
                              include_mermaid=not args.no_mermaid,
                              max_symbols_per_file=args.max_symbols_per_file)
                output.write_text(body, encoding="utf-8")
                if want_json:
                    write_json(emit_json(infos, root, stack), json_output)
            else:
                infos = build_file_infos(root, files, include_tests=args.include_tests)
                stack = detect_stack(root)
                # Map fresh, but JSON may still be missing or stale relative to source.
                if want_json and is_stale(json_output, files):
                    write_json(emit_json(infos, root, stack), json_output)
            print(render_summary(infos, root, stack, output))
        except Exception as exc:
            # Never block SessionStart on a bad map
            print(f"=== CODE MAP ===\n(skipped: {exc})\n===", file=sys.stderr)
        return 0

    infos = build_file_infos(root, files, include_tests=args.include_tests)
    stack = detect_stack(root)

    if args.summary:
        print(render_summary(infos, root, stack, output))
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    body = render(
        infos, root, stack,
        include_mermaid=not args.no_mermaid,
        max_symbols_per_file=args.max_symbols_per_file,
    )
    output.write_text(body, encoding="utf-8")

    if emit_json_flag:
        write_json(emit_json(infos, root, stack), json_output)
        print(
            f"wrote {output} and {json_output} "
            f"({len(infos)} files, {sum(f.loc for f in infos):,} LOC)"
        )
    else:
        print(f"wrote {output} ({len(infos)} files, {sum(f.loc for f in infos):,} LOC)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
