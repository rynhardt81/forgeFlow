"""The settings.json merge must union EVERY permission tier, not a named pair.

Regression gate. The merge block in install.sh once enumerated "allow" and
"deny" by name; when an "ask" tier was added to hooks/settings.json it was
dropped silently on every refresh — consumers got the allow and deny rules and
no ask rules, so "destructive commands require approval" was enforced by
nothing in permissive modes. The installer reported success throughout.

These tests execute the real merge block extracted from install.sh, not a copy
of its logic, so the gate cannot pass against a reverted installer.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_SH = REPO_ROOT / "scripts" / "install" / "install.sh"
SETTINGS = REPO_ROOT / "hooks" / "settings.json"


def merge_block() -> str:
    """The python heredoc install.sh uses to merge settings into a consumer."""
    text = INSTALL_SH.read_text(encoding="utf-8")
    m = re.search(r"<<'MERGE_EOF'\n(.*?)\nMERGE_EOF", text, re.DOTALL)
    assert m, "merge heredoc not found in install.sh — did the marker change?"
    return m.group(1)


def run_merge(tmp_path: Path, framework: dict, project: dict) -> dict:
    fw = tmp_path / "framework.json"
    pr = tmp_path / "project.json"
    fw.write_text(json.dumps(framework), encoding="utf-8")
    pr.write_text(json.dumps(project), encoding="utf-8")
    script = tmp_path / "merge.py"
    script.write_text(merge_block(), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(script), str(fw), str(pr)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, f"merge failed: {proc.stderr}"
    return json.loads(pr.read_text(encoding="utf-8"))


def test_every_tier_merges_including_ask(tmp_path):
    """A tier the merge does not name by hand must still reach the consumer."""
    framework = {"permissions": {"allow": ["Bash(awk *)"],
                                 "ask": ["Bash(rm *)"],
                                 "deny": ["Bash(find *)"]}}
    merged = run_merge(tmp_path, framework, {"permissions": {"allow": []}})
    for tier, rule in (("allow", "Bash(awk *)"), ("ask", "Bash(rm *)"), ("deny", "Bash(find *)")):
        assert rule in merged["permissions"].get(tier, []), f"{tier} tier was dropped"


def test_a_future_tier_ships_by_existing(tmp_path):
    """The point of iterating: a tier nobody has written code for still merges."""
    framework = {"permissions": {"someFutureTier": ["Bash(hypothetical *)"]}}
    merged = run_merge(tmp_path, framework, {"permissions": {}})
    assert merged["permissions"]["someFutureTier"] == ["Bash(hypothetical *)"]


def test_consumer_entries_survive_and_no_duplicates(tmp_path):
    """Merge is a union: never drop the consumer's own rules, never double one."""
    framework = {"permissions": {"ask": ["Bash(rm *)", "Bash(git push *)"]}}
    project = {"permissions": {"ask": ["Bash(rm *)", "Bash(terraform apply *)"]}}
    merged = run_merge(tmp_path, framework, project)
    ask = merged["permissions"]["ask"]
    assert "Bash(terraform apply *)" in ask, "consumer's own rule was dropped"
    assert ask.count("Bash(rm *)") == 1, "shared rule was duplicated"


def test_non_list_permission_keys_are_not_merged_as_rules(tmp_path):
    """`_permissions_note` and friends are documentation, not rule lists."""
    framework = {"permissions": {"_note": "prose, not a rule", "ask": ["Bash(rm *)"]}}
    merged = run_merge(tmp_path, framework, {"permissions": {}})
    assert merged["permissions"].get("_note") != ["prose, not a rule"]
    assert merged["permissions"]["ask"] == ["Bash(rm *)"]


@pytest.mark.parametrize("tier", ["allow", "ask", "deny"])
def test_shipped_settings_declares_every_tier(tier):
    """The shipped template must actually carry the tiers this gate protects."""
    perms = json.loads(SETTINGS.read_text(encoding="utf-8"))["permissions"]
    assert tier in perms and perms[tier], f"hooks/settings.json has no {tier} rules"


def test_no_interpreter_wildcard_in_allow():
    """A wildcard on an interpreter is arbitrary code execution.

    Patterns are prefix matches, so `Bash(python3 x.py *)` also matches
    `python3 x.py && rm -rf ~`. Named in docs/permission-profiles.md.
    """
    perms = json.loads(SETTINGS.read_text(encoding="utf-8"))["permissions"]
    interpreters = ("python", "python3", "node", "bun", "deno", "ruby", "perl",
                    "php", "sh", "bash", "zsh", "npx", "bunx", "uvx", "eval", "exec")
    for rule in perms.get("allow", []):
        m = re.match(r"^Bash\(([^\s)]+)", rule)
        if m and m.group(1) in interpreters:
            pytest.fail(f"interpreter wildcard in allow: {rule}")
