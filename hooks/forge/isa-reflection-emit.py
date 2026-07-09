#!/usr/bin/env python3
"""
isa-reflection-emit.py — Auto-emit reflection skeleton on ISA phase: complete.

Fires on PostToolUse Write|Edit. When the edited file is an ISA.md whose
frontmatter `phase` is `complete` and `effort` is E2/E3/E4, appends a skeleton
reflection entry to `daily/algorithm-reflections.jsonl`. Idempotent — keyed on
ISA `updated` timestamp to skip duplicates on re-edits of the same complete state.

The skeleton captures everything extractable from the ISA itself (effort, slug,
criteria counts, project). The model still fills reflection_q1/q2/q3 at LEARN
per ALGORITHM/v1.2.0.md doctrine; those land in the same JSONL via the model's
own append (or stay null in the skeleton if it skips).

Claude Forge philosophy: informational only — never blocks. sys.exit(0) always.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REFLECTION_TIERS = {"E2", "E3", "E4"}
PROJECT_ROOT_ENV = "CLAUDE_PROJECT_DIR"


def _read_stdin_json() -> dict | None:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return None
        return json.loads(raw)
    except Exception:
        return None


def _parse_frontmatter(text: str) -> dict | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end < 0:
        return None
    block = text[4:end]
    fm: dict = {}
    for line in block.splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm


def _count_criteria(text: str) -> tuple[int, int, int]:
    match = re.search(r"^## Criteria\s*\n(.*?)(?=\n## |\Z)", text, re.DOTALL | re.MULTILINE)
    if not match:
        return 0, 0, 0
    body = match.group(1)
    total = len(re.findall(r"^\s*- \[[ x]\] ISC-", body, re.MULTILINE))
    passed = len(re.findall(r"^\s*- \[x\] ISC-", body, re.MULTILINE))
    return total, passed, max(0, total - passed)


def _project_root() -> Path:
    import os
    return Path(os.environ.get(PROJECT_ROOT_ENV, "")).resolve() if os.environ.get(PROJECT_ROOT_ENV) else Path.cwd()


def _already_emitted(log_path: Path, slug: str, updated: str) -> bool:
    """Scan tail of JSONL for a matching slug + updated; skip if found."""
    if not log_path.exists():
        return False
    try:
        with log_path.open() as f:
            for line in f:
                try:
                    entry = json.loads(line)
                except Exception:
                    continue
                if entry.get("prd_id") == slug and entry.get("_isa_updated") == updated:
                    return True
    except Exception:
        return False
    return False


def main() -> int:
    payload = _read_stdin_json()
    if not payload:
        return 0

    tool_input = payload.get("tool_input") or {}
    file_path_str = tool_input.get("file_path") or ""
    if not file_path_str.endswith("ISA.md"):
        return 0

    isa_path = Path(file_path_str)
    if not isa_path.exists():
        return 0

    try:
        content = isa_path.read_text()
    except Exception:
        return 0

    fm = _parse_frontmatter(content)
    if not fm:
        return 0

    phase = (fm.get("phase") or "").lower()
    effort = (fm.get("effort") or "").upper()
    if phase != "complete" or effort not in REFLECTION_TIERS:
        return 0

    slug = fm.get("slug") or fm.get("project") or isa_path.parent.name
    updated = fm.get("updated") or ""

    project_root = _project_root()
    log_dir = project_root / "daily"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "algorithm-reflections.jsonl"

    if _already_emitted(log_path, slug, updated):
        return 0

    total, passed, failed = _count_criteria(content)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "effort_level": effort,
        "effort_source": "auto",
        "task_description": fm.get("task", ""),
        "criteria_count": total,
        "criteria_passed": passed,
        "criteria_failed": failed,
        "prd_id": slug,
        "project": fm.get("project", ""),
        "implied_sentiment": None,
        "satisfaction_prediction": None,
        "reflection_q1": None,
        "reflection_q2": None,
        "reflection_q3": None,
        "within_budget": None,
        "_source": "isa-reflection-emit",
        "_isa_path": str(isa_path),
        "_isa_updated": updated,
    }
    try:
        with log_path.open("a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
