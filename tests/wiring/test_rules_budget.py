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


def _is_scoped(f: Path) -> bool:
    return re.match(r"^---\n(.*\n)*?paths:", f.read_text()) is not None


def test_every_rule_states_how_it_loads():
    """The header is the only place an author sees what the file costs, so it
    must match the frontmatter: unscoped loads every session, scoped on Read."""
    wrong = []
    for f in RULES:
        text = f.read_text()
        says = ("Loaded when Claude reads a file matching" if _is_scoped(f)
                else "Loaded at every session start")
        if says not in text:
            wrong.append(f.name)
    assert not wrong, (
        f"header does not state how this rule actually loads: {wrong}"
    )


# Path-scoped rules are advisory, per-domain guidance. Each must name the files
# that make it relevant, or it silently never loads.
SCOPED = {
    "release-engineering.md", "testing.md", "hooks.md", "error-handling.md",
    "observability.md", "patterns.md", "coding-style.md",
}


def test_scoped_rules_carry_valid_paths_frontmatter():
    import yaml
    bad = []
    for f in RULES:
        if f.name not in SCOPED:
            continue
        text = f.read_text()
        m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
        paths = (yaml.safe_load(m.group(1)) or {}).get("paths") if m else None
        if not (isinstance(paths, list) and paths and all(isinstance(p, str) for p in paths)):
            bad.append(f.name)
    assert not bad, f"scoped rule without a parseable, non-empty paths list: {bad}"


ALWAYS_ON_BUDGET_BYTES = 32_000


def test_always_on_rules_stay_within_their_budget():
    """What every session pays before the first prompt, scoped rules excluded."""
    total = sum(f.stat().st_size for f in RULES if not _is_scoped(f))
    assert total <= ALWAYS_ON_BUDGET_BYTES, (
        f"always-on rules are {total} B against {ALWAYS_ON_BUDGET_BYTES} B. Scope "
        "advisory guidance with paths:, move depth to reference/, or raise this "
        "deliberately."
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
    HARD_FLOORS = {"migrations.md", "security.md", "privacy.md", "dependencies.md",
                   "agent-verification.md", "framework-vs-project-root.md", "git-workflow.md"}
    scoped = [
        f.name for f in RULES
        if f.name in HARD_FLOORS and re.match(r"^---\n(.*\n)*?paths:", f.read_text())
    ]
    assert not scoped, (
        f"these must load unconditionally; path-scoping would hide them: {scoped}"
    )
