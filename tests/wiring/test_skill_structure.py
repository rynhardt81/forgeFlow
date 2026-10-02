"""Doctrine test: every framework skill follows `skills/_shared/skill-authoring.md`.

A skill's SKILL.md is a router: core steps and gates plus an `## Index` that
sends the reader to the one bundled file it needs. The layout is load-bearing
for two harness behaviours — after auto-compaction Claude Code keeps only the
first 5,000 tokens of an invoked skill, and Claude may read a long reference
file only partially. A skill that drifts back to one long file loses its tail
at compaction; a reference file without a contents list is read incompletely;
a reference chain two levels deep is followed by preview, not in full.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / "skills"
MANIFEST = SKILLS_DIR / "skills-manifest.json"

MAX_SKILL_LINES = 200
MAX_SKILL_BYTES = 10_240
MAX_DESCRIPTION_CHARS = 1024
INDEX_WITHIN_LINES = 40
TOC_THRESHOLD_LINES = 100
TOC_WITHIN_LINES = 15

# Bundled .md files that are fixtures or human docs, not reference reading.
NON_REFERENCE_PARTS = {"test-prompts", "evals"}
NON_REFERENCE_NAMES = {"SKILL.md", "SKILL.local.md", "README.md"}


def _skill_dirs() -> list[Path]:
    return sorted(p.parent for p in SKILLS_DIR.glob("*/SKILL.md"))


def _bundled_md(skill_dir: Path) -> list[Path]:
    out = []
    for p in sorted(skill_dir.rglob("*.md")):
        rel = p.relative_to(skill_dir)
        if p.name in NON_REFERENCE_NAMES or NON_REFERENCE_PARTS & set(rel.parts):
            continue
        out.append(p)
    return out


def _frontmatter_field(text: str, key: str) -> str | None:
    """Value of a top-level frontmatter key; folds `>`/`|` blocks and quotes."""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not m:
        return None
    lines = m.group(1).splitlines()
    for i, line in enumerate(lines):
        if not line.startswith(f"{key}:"):
            continue
        value = line[len(key) + 1:].strip()
        if value in (">", "|", ">-", "|-"):
            block = []
            for nxt in lines[i + 1:]:
                if nxt and not nxt[0].isspace():
                    break
                block.append(nxt.strip())
            value = " ".join(b for b in block if b)
        return value.strip().strip('"').strip("'")
    return None


SKILLS = _skill_dirs()
IDS = [d.name for d in SKILLS]


def test_skill_roster_is_nonempty():
    assert len(SKILLS) >= 20, f"expected >=20 skills, found {len(SKILLS)}"


@pytest.mark.parametrize("skill_dir", SKILLS, ids=IDS)
def test_skill_has_index_near_top(skill_dir: Path):
    head = (skill_dir / "SKILL.md").read_text().splitlines()[:INDEX_WITHIN_LINES]
    assert any(line.strip() == "## Index" for line in head), (
        f"{skill_dir.name}: SKILL.md needs an `## Index` heading in its first "
        f"{INDEX_WITHIN_LINES} lines (skills/_shared/skill-authoring.md)"
    )


@pytest.mark.parametrize("skill_dir", SKILLS, ids=IDS)
def test_skill_within_budget(skill_dir: Path):
    path = skill_dir / "SKILL.md"
    lines = len(path.read_text().splitlines())
    size = path.stat().st_size
    assert lines <= MAX_SKILL_LINES and size <= MAX_SKILL_BYTES, (
        f"{skill_dir.name}: SKILL.md is {lines} lines / {size} bytes; budget is "
        f"{MAX_SKILL_LINES} lines / {MAX_SKILL_BYTES} bytes — move reference "
        "material into a bundled file"
    )


@pytest.mark.parametrize("skill_dir", SKILLS, ids=IDS)
def test_description_says_when(skill_dir: Path):
    text = (skill_dir / "SKILL.md").read_text()
    desc = _frontmatter_field(text, "description") or ""
    when = _frontmatter_field(text, "when_to_use") or ""
    assert desc, f"{skill_dir.name}: missing description"
    assert len(desc) <= MAX_DESCRIPTION_CHARS, (
        f"{skill_dir.name}: description is {len(desc)} chars "
        f"(max {MAX_DESCRIPTION_CHARS})"
    )
    assert "use when" in desc.lower() or when, (
        f"{skill_dir.name}: description needs a `Use when …` clause "
        "(or a when_to_use field)"
    )


@pytest.mark.parametrize("skill_dir", SKILLS, ids=IDS)
def test_long_bundled_files_open_with_contents(skill_dir: Path):
    missing = []
    for p in _bundled_md(skill_dir):
        lines = p.read_text().splitlines()
        if len(lines) <= TOC_THRESHOLD_LINES:
            continue
        if not any(l.strip() == "## Contents" for l in lines[:TOC_WITHIN_LINES]):
            missing.append(str(p.relative_to(skill_dir)))
    assert not missing, (
        f"{skill_dir.name}: files over {TOC_THRESHOLD_LINES} lines need a "
        f"`## Contents` list in their first {TOC_WITHIN_LINES} lines: {missing}"
    )


@pytest.mark.parametrize("skill_dir", SKILLS, ids=IDS)
def test_index_covers_every_bundled_file(skill_dir: Path):
    skill_text = (skill_dir / "SKILL.md").read_text()
    orphans = [
        str(p.relative_to(skill_dir))
        for p in _bundled_md(skill_dir)
        if str(p.relative_to(skill_dir)) not in skill_text
    ]
    assert not orphans, (
        f"{skill_dir.name}: bundled files not named in SKILL.md: {orphans}"
    )


@pytest.mark.parametrize("skill_dir", SKILLS, ids=IDS)
def test_index_targets_exist(skill_dir: Path):
    skill_text = (skill_dir / "SKILL.md").read_text()
    m = re.search(r"^## Index\s*\n(.*?)(?=^## |\Z)", skill_text, re.DOTALL | re.MULTILINE)
    assert m, f"{skill_dir.name}: no Index section"
    dangling = []
    for target in re.findall(r"`([\w./-]+\.md)`|\]\(([\w./-]+\.md)\)", m.group(1)):
        rel = target[0] or target[1]
        if rel.startswith("_shared/") or rel.startswith("skills/_shared/"):
            path = SKILLS_DIR / rel.removeprefix("skills/")
        else:
            path = skill_dir / rel
        if not path.is_file():
            dangling.append(rel)
    assert not dangling, f"{skill_dir.name}: Index names missing files: {dangling}"


@pytest.mark.parametrize("skill_dir", SKILLS, ids=IDS)
def test_references_one_level_deep(skill_dir: Path):
    """A bundled file points back to SKILL.md only — never to a sibling."""
    bundled = _bundled_md(skill_dir)
    skill_text = (skill_dir / "SKILL.md").read_text()
    violations = []
    for p in bundled:
        text = p.read_text()
        for other in bundled:
            if other == p:
                continue
            if other.name in text:
                violations.append(f"{p.relative_to(skill_dir)} -> {other.name}")
        for shared in set(re.findall(r"_shared/([\w-]+\.md)", text)):
            if f"_shared/{shared}" not in skill_text:
                violations.append(
                    f"{p.relative_to(skill_dir)} -> _shared/{shared} "
                    "(not listed in SKILL.md)"
                )
    assert not violations, (
        f"{skill_dir.name}: references nested beyond one level: {violations}"
    )


@pytest.mark.parametrize("skill_dir", SKILLS, ids=IDS)
def test_no_reach_into_other_skills_files(skill_dir: Path):
    hits = []
    for p in [skill_dir / "SKILL.md", *_bundled_md(skill_dir)]:
        for other, rest in re.findall(r"skills/([\w-]+)/([\w/.-]+\.md)", p.read_text()):
            if other in (skill_dir.name, "_shared") or rest == "SKILL.md":
                continue
            hits.append(f"{p.relative_to(skill_dir)} -> skills/{other}/{rest}")
    assert not hits, f"{skill_dir.name}: points into another skill's files: {hits}"


def test_manifest_matches_skill_dirs():
    names = {s["name"] for s in json.loads(MANIFEST.read_text())["skills"]}
    assert names == set(IDS), (
        f"manifest-only: {sorted(names - set(IDS))}; "
        f"dir-only: {sorted(set(IDS) - names)}"
    )
