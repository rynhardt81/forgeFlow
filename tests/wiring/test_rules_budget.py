"""T920: `rules/` is always-on context, so its size and honesty are testable.

Claude Code loads every `.claude/rules/*.md` at launch — "Rules without `paths`
frontmatter are loaded at launch with the same priority as `.claude/CLAUDE.md`".
Fourteen framework rules used to claim the opposite in their own header, and that
claim is why nobody treated the directory as a budget: one consumer reached 133 KB,
68% of its startup context.

These tests pin the two failure modes that let it grow: a header that tells authors
the file is opt-in, and boilerplate repeated once per file inside a single context
window.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES = sorted((REPO_ROOT / "rules").glob("*.md"))

# The shipped baseline is charged to every session of every consuming project.
# Raising this is a decision to spend more of everyone's context, so it should
# require deliberately editing this number.
BASELINE_BUDGET_BYTES = 52_000


def test_no_rule_claims_to_be_loaded_on_demand():
    liars = [f.name for f in RULES if re.search(r"on.?demand", f.read_text(), re.I)]
    assert not liars, (
        "these rules tell the reader they are opt-in, which is false and is how the "
        f"directory grew unchecked: {liars}"
    )


def test_every_rule_states_that_it_is_always_loaded():
    silent = [
        f.name for f in RULES
        if "Loaded at every session start" not in f.read_text()
    ]
    assert not silent, (
        f"a rule whose header omits its own cost invites reference-length prose: {silent}"
    )


def test_shipped_rules_stay_within_the_always_on_budget():
    total = sum(f.stat().st_size for f in RULES)
    assert total <= BASELINE_BUDGET_BYTES, (
        f"shipped rules/ is {total} B against a {BASELINE_BUDGET_BYTES} B budget "
        f"(~{total // 4000}k tokens charged to every session in every consuming "
        "project). Move opt-in depth into a skill or reference/, or change the "
        "budget deliberately."
    )


def test_sidecar_paragraph_is_one_line_not_a_repeated_essay():
    """The same explanation in 14 files is 14 copies in one context window."""
    bloated = []
    for f in RULES:
        m = re.search(r"## Project-specific extensions\n\n(.*?)(?=\n## |\Z)",
                      f.read_text(), re.S)
        if m and len(m.group(1).strip()) > 200:
            bloated.append((f.name, len(m.group(1).strip())))
    assert not bloated, (
        f"sidecar boilerplate has regrown; say it once in CONTRIBUTING.md: {bloated}"
    )


def test_hard_floor_rules_are_not_path_scoped():
    """Scoped rules load on Read, and auto mode prefers Bash — so a scoped
    hard-floor rule is dark in exactly the sessions that touch its domain."""
    HARD_FLOORS = {"migrations.md", "security.md", "privacy.md", "dependencies.md"}
    scoped = [
        f.name for f in RULES
        if f.name in HARD_FLOORS and re.match(r"^---\n(.*\n)*?paths:", f.read_text())
    ]
    assert not scoped, (
        f"these must load unconditionally; path-scoping would hide them: {scoped}"
    )
