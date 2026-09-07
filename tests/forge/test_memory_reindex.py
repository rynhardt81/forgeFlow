"""`forge memory reindex` regenerates index.md from the entry files.

Reproduced 2026-09-05 in two consumers: a v2-format index (Summary table,
counts 0) sitting beside 56 and 4 real entries. v4 removed the v2 compiler
and never replaced it, and the installer only created a MISSING index, so a
fossil survived every refresh and every session started blind.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import memory_index

FORGE = Path(__file__).resolve().parents[2] / "scripts" / "forge" / "forge.py"

V2_INDEX = """# Project Memory Index

> Auto-generated catalog of all project knowledge.

## Summary

| Category | Count | Last Updated |
|----------|-------|--------------|
| Bugs | 0 | — |

## Recent Entries

_No entries yet._
"""

V2_BUGS = """# Bug Patterns & Fixes

## Table of Contents
<!-- Auto-generated: Do not edit manually -->
| ID | Title | Tags | Date |
|----|-------|------|------|
| BUG-001 | Registry drift | registry | 2026-02-07 |

---

## BUG-001: Registry drift

**Date:** 2026-02-07
**Tags:** registry

### Problem
words
"""

V4_DECISIONS = """# Decisions

## Chose SQLite over Postgres for the cache
- **Date:** 2026-08-30
- **Context:** CLI cache
- Zero-config wins.

## Undated decision
- No date line here.
"""


def _memory(tmp_path):
    d = tmp_path / "docs" / "project-memory"
    d.mkdir(parents=True)
    (d / "index.md").write_text(V2_INDEX)
    (d / "bugs.md").write_text(V2_BUGS)
    (d / "decisions.md").write_text(V4_DECISIONS)
    (d / "patterns.md").write_text("# Patterns\n")
    (d / "key-facts.md").write_text("# Key facts\n- port 8000\n")
    return d


def test_reindex_lists_every_entry_newest_first_and_skips_v2_toc(tmp_path):
    d = _memory(tmp_path)
    counts = memory_index.reindex(tmp_path)
    assert counts == {"bug": 1, "decision": 2, "pattern": 0}
    text = (d / "index.md").read_text()
    pointers = [line for line in text.splitlines() if line.startswith("- ")]
    assert pointers == [
        "- 2026-08-30 [decision] Chose SQLite over Postgres for the cache",
        "- 2026-02-07 [bug] BUG-001: Registry drift",
        "- ---- [decision] Undated decision",
    ]
    assert "Table of Contents" not in text
    assert "_No entries yet._" not in text  # hook no longer treats it as a skeleton


def test_reindex_is_idempotent(tmp_path):
    d = _memory(tmp_path)
    memory_index.reindex(tmp_path)
    first = (d / "index.md").read_text()
    memory_index.reindex(tmp_path)
    assert (d / "index.md").read_text() == first


def test_cli_memory_reindex_reports_counts(tmp_path):
    _memory(tmp_path)
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(tmp_path)}
    r = subprocess.run([sys.executable, str(FORGE), "memory", "reindex"],
                       cwd=tmp_path, capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    assert "index.md rebuilt: 3 entries" in r.stdout


def test_cli_memory_reindex_fails_loudly_without_memory_dir(tmp_path):
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(tmp_path)}
    r = subprocess.run([sys.executable, str(FORGE), "memory", "reindex"],
                       cwd=tmp_path, capture_output=True, text=True, env=env)
    assert r.returncode == 1
    assert "does not exist" in r.stderr


# --- Shape tolerance -------------------------------------------------------
# Reported 2026-09-07 from a consumer (fic) via /intent, then measured across
# two consumers. `parse_entries` treated every `## ` heading as an entry and
# read the date only from a `**Date:**` line, which produced two failures:
#
#   1. The SHIPPED template's example lives in an HTML comment, and the parser
#      does not strip comments -- so every project on the current template
#      indexes `## <one-line symptom>` as a real entry. Measured: 3 phantoms in
#      one consumer, whose decisions.md was 1 parsed entry and 0 real ones.
#   2. A consumer stamping dates in the heading (`## [2026-06-23] Title`) with
#      no `**Date:**` field at all landed every entry in the undated bucket, so
#      "newest first" degraded silently to file order: 12 parsed, 0 dated,
#      9 of them scaffolding headings.

TEMPLATE_BUGS = """# Bugs

> Root-caused bugs worth remembering.

<!-- Entry format:
## <one-line symptom>
- **Date:** YYYY-MM-DD
- **Root cause:** <the actual cause, not the symptom>
-->

## Real bug that actually happened
- **Date:** 2026-07-16
- **Root cause:** words
"""

HEADING_DATED_PATTERNS = """# Patterns

## Format

## [YYYY-MM-DD] Pattern name

## Entries

## [2026-06-23] Migration: ADD column + CHECK in one batch
- **Context:** words

## [2026-06-18] Enum schema missing the hyphen
- **Context:** words
"""

FENCED = """# Decisions

## A real decision
- **Date:** 2026-08-30

```markdown
## Not an entry -- this is a fenced example
```
"""


def _write(tmp_path, **files):
    d = tmp_path / "docs" / "project-memory"
    d.mkdir(parents=True)
    for name in ("bugs.md", "decisions.md", "patterns.md"):
        (d / name).write_text(files.get(name, "# Empty\n"))
    return d


def test_template_example_in_html_comment_is_not_an_entry(tmp_path):
    d = _write(tmp_path, **{"bugs.md": TEMPLATE_BUGS})
    counts = memory_index.reindex(tmp_path)
    assert counts["bug"] == 1
    pointers = [l for l in (d / "index.md").read_text().splitlines() if l.startswith("- ")]
    assert pointers == ["- 2026-07-16 [bug] Real bug that actually happened"]


def test_date_in_heading_is_parsed_and_scaffolding_is_skipped(tmp_path):
    d = _write(tmp_path, **{"patterns.md": HEADING_DATED_PATTERNS})
    counts = memory_index.reindex(tmp_path)
    assert counts["pattern"] == 2, "Format/Entries/placeholder headings are not entries"
    pointers = [l for l in (d / "index.md").read_text().splitlines() if l.startswith("- ")]
    assert pointers == [
        "- 2026-06-23 [pattern] Migration: ADD column + CHECK in one batch",
        "- 2026-06-18 [pattern] Enum schema missing the hyphen",
    ]


def test_fenced_code_block_headings_are_not_entries(tmp_path):
    _write(tmp_path, **{"decisions.md": FENCED})
    assert memory_index.reindex(tmp_path)["decision"] == 1
