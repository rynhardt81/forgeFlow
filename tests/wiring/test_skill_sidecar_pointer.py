"""Doctrine test: every framework skill advertises its `SKILL.local.md` sidecar.

Skills are invoked individually — nothing globs skill files the way readers glob
`rules/*.md`. So for skills the pointer line at the end of each `SKILL.md` IS the
discovery mechanism: an agent following the skill reads that line and loads the
sidecar. A skill missing the line silently loses sidecar support, and the next
consumer with project-specific guidance for it goes back to editing the
framework file — which refresh then eats. That is the exact failure this
convention exists to stop.

See `rules/framework-vs-project-root.md` for the doctrine and precedence rule.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / "skills"
INSTALL_SH = REPO_ROOT / "scripts" / "install" / "install.sh"


def _skill_files() -> list[Path]:
    return sorted(SKILLS_DIR.glob("*/SKILL.md"))


def test_every_framework_skill_points_at_its_sidecar():
    skills = _skill_files()
    assert len(skills) >= 20, (
        f"expected >=20 framework skills, found {len(skills)} — did the skills "
        "layout change shape?"
    )

    missing = [s.parent.name for s in skills if "SKILL.local.md" not in s.read_text()]
    assert not missing, (
        "these skills do not advertise their SKILL.local.md sidecar, so a "
        f"consumer's overrides for them would never be read: {sorted(missing)}"
    )


def test_pointer_states_precedence_and_the_gate_obligation():
    """The line must carry both halves of the rule, not just the filename.

    'Read the sidecar' without 'it wins' leaves precedence ambiguous; 'it wins'
    without the proof obligation makes a silent gate opt-out look sanctioned.
    """
    for skill in _skill_files():
        text = skill.read_text()
        assert "wins on conflict" in text, (
            f"{skill.parent.name}: pointer must state the sidecar wins on conflict"
        )
        assert "prove the gate is wrong" in text, (
            f"{skill.parent.name}: pointer must state the gate-relaxation "
            "proof obligation"
        )


def test_refresh_excludes_the_sidecar():
    """Framework refresh must never overwrite a consumer's sidecar.

    Mirrors the `rules/*.local.md` exclude, and on the same two refresh paths —
    a fresh install has no pre-existing sidecar to protect.
    """
    text = INSTALL_SH.read_text()
    rules_excludes = text.count("--exclude='rules/*.local.md'")
    skill_excludes = text.count("--exclude='skills/*/SKILL.local.md'")
    assert rules_excludes >= 2, (
        f"expected >=2 rules sidecar excludes, found {rules_excludes}"
    )
    assert skill_excludes >= rules_excludes, (
        f"install.sh excludes rules sidecars in {rules_excludes} places but "
        f"skill sidecars in only {skill_excludes} — both survive the same paths"
    )
