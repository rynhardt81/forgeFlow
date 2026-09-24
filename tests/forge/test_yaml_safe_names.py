"""Task/ISA names must survive the frontmatter round-trip for every YAML reader.

Found in a consumer: `name: {{TASK_NAME}}` wrote the raw name into frontmatter,
so a colon or `#` made the file unparseable to any YAML reader. Forge's own
regex reader coped, which is why nothing noticed. A raw newline was worse — it
split the line and the regex reader silently kept the first half. Names YAML
types implicitly (`true`, `123`, dates) came back as bools, ints and dates.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

import registry_ops as ops
from conftest import base_registry, make_repo
from dashboard.render import markdown

NAMES = [
    "Fix: login 500",
    "fix #3 regression",
    "line one\nline two",
    "tab\there",
    "carriage\rreturn",
    "bell\x07byte",
    "nel\x85split",
    "ls split",
    "true",
    "No",
    "123 things",
    "2026-09-24 note",
    ".5 ratio",
    "<<",
    "=",
    "literal \\n not a newline",
    'mixed \\ and " quote',
]


def _frontmatter(text: str) -> dict:
    head = text.split("---\n", 2)[1]
    return yaml.safe_load(head)


@pytest.mark.parametrize("name", NAMES)
def test_quoted_scalar_parses_as_yaml_to_the_same_string(name):
    doc = yaml.safe_load(f"name: {ops._yaml_quote_if_needed(name)}\n")
    assert doc["name"] == name


@pytest.mark.parametrize("name", NAMES)
def test_forge_reader_reverses_the_encoder(name):
    assert ops._yaml_unquote_scalar(ops._yaml_quote_if_needed(name)) == name


@pytest.mark.parametrize("name", ["Fix: login 500", "true", "fix #3 regression"])
def test_task_body_and_isa_frontmatter_are_yaml_safe(tmp_path, name):
    repo = make_repo(tmp_path, base_registry(
        epics=[{"id": "E1", "status": "in_progress", "tasks": []}]))
    task = ops.add_task(repo / "docs" / "tasks" / "registry.json",
                        task_id="T1", epic_id="E1", name=name)

    body = ops.create_task_body_file(repo, task).read_text(encoding="utf-8")
    isa = ops.scaffold_task_isa(repo, task).read_text(encoding="utf-8")

    assert _frontmatter(body)["name"] == name
    assert _frontmatter(isa)["name"] == name
    # Headings keep the raw name; only the frontmatter line is quoted.
    assert f"# T1 — {name}\n" in body


def test_dashboard_shows_the_decoded_name_not_the_escapes():
    quoted = ops._yaml_quote_if_needed("Fix: a \"quoted\" name")
    fm, _ = markdown.parse_frontmatter(f"---\nname: {quoted}\n---\nbody\n")
    assert fm["name"] == 'Fix: a "quoted" name'
