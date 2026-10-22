"""Every SKILL.md frontmatter must parse as YAML.

An unquoted description containing ": " (e.g. `phase: complete`) is invalid
YAML — "mapping values are not allowed here". Three skills shipped that way
(ISA, improve-codebase-architecture, prototype); a consumer had to hand-quote
ISA's, and a refresh would have overwritten the fix. Quote such a description.
"""
import re
from pathlib import Path

import pytest
import yaml

SKILLS = sorted((Path(__file__).resolve().parents[2] / "skills").glob("*/SKILL.md"))


@pytest.mark.parametrize("path", SKILLS, ids=[p.parent.name for p in SKILLS])
def test_frontmatter_is_valid_yaml(path: Path):
    m = re.match(r"^---\n(.*?)\n---\n", path.read_text(), re.S)
    assert m, f"{path.parent.name}: no frontmatter block"
    data = yaml.safe_load(m.group(1))
    assert isinstance(data, dict) and data.get("description"), (
        f"{path.parent.name}: frontmatter parsed but has no description"
    )
