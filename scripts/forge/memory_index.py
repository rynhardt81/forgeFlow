"""Regenerate docs/project-memory/index.md from the entry files.

The index is a catalog derived from bugs.md / decisions.md / patterns.md, so it
is a pure function of those files and safe to regenerate on every run. v2
shipped a compiler that did this automatically; v4 removed the pipeline and
left consumers with a fossil index whose counts read zero while entries
existed. Every session then started blind. This is the deterministic
replacement -- no LLM, no transcript capture, idempotent.

Entry = a `## ` heading in one of the three files, ignoring headings that are
not entries: v2's "Table of Contents", the `Format`/`Entries` section headings
some consumers carry, and placeholders (a `<bracketed>` title, or one still
carrying the literal `YYYY-MM-DD`). Headings inside HTML comments or fenced
code are not entries either -- the shipped template's own example lives in a
comment, so a parser that misses this indexes the template in every project.

Date = a leading `[YYYY-MM-DD]` in the heading, else the first
`**Date:** YYYY-MM-DD` line after it (both v2 `**Date:**` and v4 `- **Date:**`
shapes match). Both date shapes are supported because consumers carry both;
the heading shape is drift from the template, not a second blessed convention,
but it is drift the index has to survive rather than silently mis-order.

Output lines follow the v4 template's comment: `- YYYY-MM-DD [type] title`,
newest first.
"""
from __future__ import annotations

import re
from pathlib import Path

ENTRY_FILES = (("bugs.md", "bug"), ("decisions.md", "decision"), ("patterns.md", "pattern"))
_DATE_RE = re.compile(r"\*\*Date:\*\*\s*(\d{4}-\d{2}-\d{2})")
_HEADING_DATE_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2})\]\s*(.+)$")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_SKIP_HEADINGS = {"table of contents", "format", "entries"}
_PLACEHOLDER_DATE = "YYYY-MM-DD"

HEADER = """# Project Memory — Index

> Master catalog of this project's committed knowledge. Loaded at every SessionStart. One line per notable entry — content lives in the files below. Regenerate with `forge memory reindex`; never hand-edit.

| File | Holds | Load |
|------|-------|------|
| [key-facts.md](key-facts.md) | Always-relevant facts (URLs, accounts, magic values) | Always (SessionStart) |
| [decisions.md](decisions.md) | Architectural + product decisions with their why | On-demand |
| [bugs.md](bugs.md) | Root-caused bugs worth remembering | On-demand |
| [patterns.md](patterns.md) | Codebase patterns and conventions | On-demand |

## Recent entries

<!-- /remember appends a one-line pointer here per capture: - YYYY-MM-DD [type] title -->
"""


def _strip_noise(lines: list[str]) -> list[str]:
    """Blank HTML comments and fenced code, keeping one output line per input.

    Line positions are preserved so the date lookahead still reads the lines
    that actually follow the heading.
    """
    out: list[str] = []
    in_comment = False
    fence: str | None = None
    for line in lines:
        if in_comment:
            out.append("")
            if "-->" in line:
                in_comment = False
            continue
        if fence is not None:
            out.append("")
            if line.strip().startswith(fence):
                fence = None
            continue
        m = _FENCE_RE.match(line)
        if m:
            fence = m.group(1)
            out.append("")
            continue
        if "<!--" in line:
            before, rest = line.split("<!--", 1)
            if "-->" in rest:
                out.append(before + rest.split("-->", 1)[1])
            else:
                in_comment = True
                out.append(before)
            continue
        out.append(line)
    return out


def _is_placeholder(title: str) -> bool:
    """A template example, not a memory: `<bracketed>` or still saying YYYY-MM-DD."""
    return (title.startswith("<") and title.endswith(">")) or _PLACEHOLDER_DATE in title


def parse_entries(text: str, kind: str) -> list[tuple[str, str, str]]:
    """(date, kind, title) per entry `## ` heading; date is '----' when absent."""
    out: list[tuple[str, str, str]] = []
    lines = _strip_noise(text.splitlines())
    for i, line in enumerate(lines):
        if not line.startswith("## "):
            continue
        title = line[3:].strip()
        if not title or title.lower() in _SKIP_HEADINGS or _is_placeholder(title):
            continue
        date = "----"
        heading_date = _HEADING_DATE_RE.match(title)
        if heading_date:
            date, title = heading_date.group(1), heading_date.group(2).strip()
        else:
            for nxt in lines[i + 1:]:
                if nxt.startswith("## "):
                    break
                m = _DATE_RE.search(nxt)
                if m:
                    date = m.group(1)
                    break
        out.append((date, kind, title))
    return out


def build_index(memory_dir: Path) -> tuple[str, dict[str, int]]:
    entries: list[tuple[str, str, str]] = []
    counts: dict[str, int] = {}
    for name, kind in ENTRY_FILES:
        path = memory_dir / name
        found = parse_entries(path.read_text(encoding="utf-8"), kind) if path.exists() else []
        counts[kind] = len(found)
        entries.extend(found)
    dated = sorted((e for e in entries if e[0] != "----"), key=lambda e: e[0], reverse=True)
    undated = [e for e in entries if e[0] == "----"]
    body = "".join(f"- {d} [{k}] {t}\n" for d, k, t in dated + undated)
    return HEADER + body, counts


def reindex(project_root: Path) -> dict[str, int]:
    memory_dir = project_root / "docs" / "project-memory"
    if not memory_dir.is_dir():
        raise FileNotFoundError(f"{memory_dir} does not exist")
    text, counts = build_index(memory_dir)
    (memory_dir / "index.md").write_text(text, encoding="utf-8")
    return counts
