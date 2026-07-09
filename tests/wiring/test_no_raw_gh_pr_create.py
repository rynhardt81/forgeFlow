"""Doctrine test: no Forge Flow skill invokes `gh pr create` directly.

Only `skills/create-pr/SKILL.md` is allowed to mention `gh pr create` — it's
the canonical skill that wraps the raw command with DRY check, pr-review-toolkit
specialist pre-flight (Step 3.7), and the mandatory `@codex` mention.

Every other skill that ships code must route the PR through `Skill("create-pr")`.
Raw `gh pr create` anywhere else bypasses every one of those gates.

This is a grep-based assertion, not a runtime check. It runs in CI (and can be
invoked locally via `pytest tests/wiring/`). Failure surfaces the offending
file:line so the skill author sees exactly where the doctrine break landed.

Background: a consumer project on 2026-05-12 had two PRs opened via raw
`gh pr create` from a `/reflect resume` driver. The 5 GAP-implicit findings
from the create-pr-audit were patched in v3.1.1; this test prevents
regression.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / "skills"

# Only this exact file:pattern is allowed to mention `gh pr create`.
# create-pr/SKILL.md documents its own implementation; that's the canonical
# raw-command site. Anywhere else is a doctrine break.
ALLOWED_FILES = {SKILLS_DIR / "create-pr" / "SKILL.md"}

# Pattern: literal `gh pr create` invocation. Matches the bare command and
# common variants (with flags, in code fences, in inline backticks).
PATTERN = re.compile(r"\bgh\s+pr\s+create\b")


def _all_skill_markdowns() -> list[Path]:
    """Every .md file under skills/, excluding archive."""
    return [
        p for p in SKILLS_DIR.rglob("*.md")
        if "_archive" not in p.parts and "node_modules" not in p.parts
    ]


def test_only_create_pr_skill_uses_raw_gh_pr_create():
    """No skill markdown except create-pr/SKILL.md may contain `gh pr create`.

    If this fails, the offending file:line is reported. The fix is to replace
    the raw command with `Skill("create-pr")` in the skill's workflow.
    """
    violations: list[tuple[Path, int, str]] = []

    for md in _all_skill_markdowns():
        if md in ALLOWED_FILES:
            continue
        text = md.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if not PATTERN.search(line):
                continue
            # Doctrine-prose whitelist: any line that mentions `gh pr create`
            # AND signals it's prose ABOUT the command (never / not / bypass /
            # raw-as-adjective / Skill("create-pr") / /create-pr) is allowed.
            # This catches "never use raw `gh pr create`", "improvised via raw
            # `gh pr create`", "do NOT use `gh pr create`", etc. — doctrine
            # text discussing the rule, not invoking the command.
            stripped = line.lower()
            doctrine_markers = (
                "never",
                "do not",
                "do **not**",
                "don't",
                "bypass",
                "instead of",
                "rather than",
                "raw `gh pr create`",
                "raw gh pr create",
                "improvis",
                "anti:",
                "skill(\"create-pr\")",
                "/create-pr",
                "via create-pr",
                "always route",
                "must route",
                "must invoke",
                "wraps the raw",
                "wraps `gh pr create`",
                "the raw command",
                "the canonical",
            )
            if any(marker in stripped for marker in doctrine_markers):
                continue
            violations.append((md.relative_to(REPO_ROOT), lineno, line.rstrip()))

    if violations:
        msg_lines = [
            "Doctrine violation: `gh pr create` found in skill markdown outside",
            "`skills/create-pr/SKILL.md`. Route PRs through `Skill(\"create-pr\")`",
            "to keep the DRY check, pr-review-toolkit pre-flight, and `@codex`",
            "mention intact. Offending lines:",
            "",
        ]
        for path, lineno, line in violations:
            msg_lines.append(f"  {path}:{lineno}: {line}")
        msg_lines.append("")
        msg_lines.append(
            "If a skill must document why NOT to use raw `gh pr create`, "
            "rewrite the line to start with 'Never use', 'Do NOT use', "
            "'bypasses', etc. — those phrases are whitelisted."
        )
        pytest.fail("\n".join(msg_lines))


def test_create_pr_skill_remains_the_canonical_site():
    """Belt-and-suspenders: the allowed file still exists and still mentions
    the command. Catches accidental rename / deletion of the canonical skill.
    """
    canonical = SKILLS_DIR / "create-pr" / "SKILL.md"
    assert canonical.exists(), (
        f"canonical PR skill missing: {canonical} — "
        "this means the audit's reference point is gone"
    )
    text = canonical.read_text(encoding="utf-8", errors="replace")
    assert PATTERN.search(text), (
        f"canonical PR skill {canonical} no longer documents `gh pr create` — "
        "either it moved or the skill was rewritten; update ALLOWED_FILES"
    )


if __name__ == "__main__":
    # Allow direct invocation: `python3 tests/wiring/test_no_raw_gh_pr_create.py`
    import sys

    rc = pytest.main([__file__, "-v"])
    sys.exit(rc)
