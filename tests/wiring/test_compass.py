"""/compass runs on the forge registry; /run-epic never builds its tickets (T968)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SKILL = (ROOT / "skills" / "compass" / "SKILL.md").read_text(encoding="utf-8")
LOOP = (ROOT / "skills" / "run-epic" / "LOOP.md").read_text(encoding="utf-8")


def test_every_ticket_type_is_a_decision_category():
    for kind in ("research", "prototype", "grilling", "task"):
        assert f"`decision:{kind}`" in SKILL


def test_tracker_operations_map_to_forge_cli():
    for op in ("forge epic add", "--category decision:", "forge task set-deps",
               "forge task lock", "forge task complete", "--ready"):
        assert op in SKILL, op


def test_one_ticket_per_session_and_claim_first():
    assert "never resolve more than one ticket per session" in SKILL
    assert "**first**, before any work" in SKILL


@pytest.mark.skipif(shutil.which("jq") is None, reason="jq not installed")
def test_run_epic_pick_filter_skips_decision_tickets():
    line = next(l for l in LOOP.splitlines() if "jq -r" in l)
    expr = line.split("jq -r ", 1)[1].strip().strip("'")
    ready = [{"id": "T1", "category": "decision:grilling"}, {"id": "T2", "category": ""}, {"id": "T3"}]
    out = subprocess.run(["jq", "-r", expr], input=json.dumps(ready), capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "T2"
    only = subprocess.run(["jq", "-r", expr], input=json.dumps(ready[:1]), capture_output=True, text=True, check=True)
    assert only.stdout.strip() == "null"


def test_registered():
    manifest = json.loads((ROOT / "skills" / "skills-manifest.json").read_text(encoding="utf-8"))
    assert any(s["name"] == "compass" for s in manifest["skills"])
    assert "/compass" in (ROOT / "CLAUDE.md").read_text(encoding="utf-8")


@pytest.mark.skipif(shutil.which("jq") is None, reason="jq not installed")
def test_pick_filter_on_real_cli_output(tmp_path):
    """The call site: real `task ls --ready --json`, through the exact LOOP.md expression."""
    import os
    import sys
    (tmp_path / "docs" / "tasks").mkdir(parents=True)
    (tmp_path / "docs" / "tasks" / "registry.json").write_text(
        '{"project":"t","version":"1","settings":{},"stats":{},"tasks":[],"epics":[]}')
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(tmp_path)}
    forge = [sys.executable, "-B", str(ROOT / "scripts" / "forge" / "forge.py")]
    for argv in (["epic", "add", "E1", "--name", "m"],
                 ["task", "add", "T1", "--epic", "E1", "--name", "q?", "--category", "decision:grilling"],
                 ["task", "add", "T2", "--epic", "E1", "--name", "build"]):
        subprocess.run(forge + argv, env=env, check=True, capture_output=True)
    ready = subprocess.run(forge + ["task", "ls", "--epic", "E1", "--ready", "--json"],
                           env=env, check=True, capture_output=True, text=True).stdout
    expr = next(l for l in LOOP.splitlines() if "jq -r" in l).split("jq -r ", 1)[1].strip().strip("'")
    out = subprocess.run(["jq", "-r", expr], input=ready, capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "T2"
