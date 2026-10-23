"""/create-pr scales review depth by door and blast radius (T970).

Before, door and radius were only words in the PR body; review was picked by
file pattern alone, so a one-line migration got the same reviewers as a typo.
"""

from __future__ import annotations

from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2] / "skills" / "create-pr"
GATES = (SKILL_DIR / "GATES.md").read_text(encoding="utf-8")
SKILL = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
TIERS = GATES[GATES.index("**Review tier**"):GATES.index("**Agent selection**")]


def test_step_37_sets_the_tier_before_selecting_agents():
    step = SKILL[SKILL.index("## Step 3.7"):SKILL.index("## Step 3.8")]
    assert step.index("review tier") < step.index("Select specialists")


def test_three_tiers_keyed_on_door_and_radius():
    for row in ("two-way + narrow", "two-way + wide", "one-way, any radius"):
        assert row in TIERS, row


def test_hard_floors_are_always_one_way():
    assert "schema, auth, money paths, security" in TIERS
    assert "always one-way" in TIERS


def test_one_way_adds_security_review_and_a_second_full_pass():
    tier3 = TIERS[TIERS.index("| **3**"):]
    assert "`security-boss`" in tier3
    assert "second full tier-3 pass over the whole diff" in tier3


def test_tier_is_recorded_and_ties_go_up():
    assert "Pre-flight notes" in TIERS
    assert "take the higher one" in TIERS
