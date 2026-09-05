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
