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


# --- dead framework hook wiring ------------------------------------------------

def _consumer_layout(tmp_path: Path, project: dict) -> tuple[Path, Path]:
    """Build <project>/.claude/settings.json so the merge can resolve hook paths."""
    claude = tmp_path / ".claude"
    (claude / "hooks" / "session").mkdir(parents=True)
    pr = claude / "settings.json"
    pr.write_text(json.dumps(project), encoding="utf-8")
    return claude, pr


def _hook(cmd: str) -> dict:
    return {"matcher": "*", "hooks": [{"type": "command", "command": cmd}]}


def run_merge_at(fw_path: Path, pr_path: Path, framework: dict, tmp_path: Path) -> dict:
    fw_path.write_text(json.dumps(framework), encoding="utf-8")
    script = tmp_path / "merge_hooks.py"
    script.write_text(merge_block(), encoding="utf-8")
    proc = subprocess.run([sys.executable, str(script), str(fw_path), str(pr_path)],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return json.loads(pr_path.read_text(encoding="utf-8"))


def test_dead_framework_hook_is_pruned(tmp_path):
    """A hook whose script the cut-paths sweep deleted must not stay wired."""
    claude, pr = _consumer_layout(tmp_path, {"hooks": {
        "SessionStart": [_hook("python3 $CLAUDE_PROJECT_DIR/.claude/hooks/session/gone.py")]}})
    merged = run_merge_at(tmp_path / "fw.json", pr, {"hooks": {}}, tmp_path)
    assert "SessionStart" not in merged.get("hooks", {}), "dead wiring survived the merge"


def test_live_framework_hook_is_kept(tmp_path):
    claude, pr = _consumer_layout(tmp_path, {"hooks": {
        "SessionStart": [_hook("python3 $CLAUDE_PROJECT_DIR/.claude/hooks/session/live.py")]}})
    (claude / "hooks" / "session" / "live.py").write_text("", encoding="utf-8")
    merged = run_merge_at(tmp_path / "fw.json", pr, {"hooks": {}}, tmp_path)
    assert merged["hooks"]["SessionStart"], "a hook whose script exists was pruned"


def test_consumer_hooks_outside_framework_territory_are_never_pruned(tmp_path):
    """Only .claude/hooks/ paths are framework territory. Nothing else is evidence."""
    claude, pr = _consumer_layout(tmp_path, {"hooks": {
        "Stop": [_hook("bash scripts/my-own-hook.sh")],
        "PreToolUse": [_hook("python3 $CLAUDE_PROJECT_DIR/tools/mine.py")]}})
    merged = run_merge_at(tmp_path / "fw.json", pr, {"hooks": {}}, tmp_path)
    assert merged["hooks"]["Stop"], "consumer's own hook was pruned"
    assert merged["hooks"]["PreToolUse"], "consumer hook outside .claude/hooks was pruned"


def test_deliberately_empty_events_are_kept(tmp_path):
    """PreCompact/Stop ship as [] to clear v3 wiring — settings.json says so.

    Deleting them drops framework config, and the next merge re-adds it: churn
    in a tracked file on every refresh. Only an event this prune emptied goes.
    """
    claude, pr = _consumer_layout(tmp_path, {"hooks": {"PreCompact": [], "Stop": []}})
    merged = run_merge_at(tmp_path / "fw.json", pr,
                          {"hooks": {"PreCompact": [], "Stop": []}}, tmp_path)
    assert merged["hooks"].get("PreCompact") == [], "deliberately-empty event was deleted"
    assert merged["hooks"].get("Stop") == [], "deliberately-empty event was deleted"


# --- withdrawn rules ------------------------------------------------------------

def test_retired_rule_is_removed_from_the_consumer(tmp_path):
    """The union can only add. A rule the framework drops must still leave.

    A blanket `Read(./**/dist/**)` was narrowed in the framework and survived in
    every consumer anyway, still blocking documentation, because merging only
    ever appended.
    """
    framework = {"permissions": {"deny": ["Read(./**/dist/**/*.js)"]},
                 "_retired_permissions": {"deny": ["Read(./**/dist/**)"]}}
    project = {"permissions": {"deny": ["Read(./**/dist/**)", "Read(./**/coverage/**)"]}}
    merged = run_merge(tmp_path, framework, project)
    deny = merged["permissions"]["deny"]
    assert "Read(./**/dist/**)" not in deny, "withdrawn rule survived the merge"
    assert "Read(./**/dist/**/*.js)" in deny, "replacement rule did not arrive"
    assert "Read(./**/coverage/**)" in deny, "an unrelated rule was collateral damage"


def test_retirement_never_touches_a_consumers_own_rule(tmp_path):
    """Only rules the framework names are removed."""
    framework = {"permissions": {"deny": []}, "_retired_permissions": {"deny": ["Read(./**/dist/**)"]}}
    project = {"permissions": {"deny": ["Read(./secrets/**)", "Bash(terraform destroy *)"]}}
    merged = run_merge(tmp_path, framework, project)
    assert merged["permissions"]["deny"] == ["Read(./secrets/**)", "Bash(terraform destroy *)"]


def test_retirement_is_idempotent(tmp_path):
    """Refreshing twice must not error or reintroduce anything."""
    framework = {"permissions": {"deny": ["Read(./**/dist/**/*.js)"]},
                 "_retired_permissions": {"deny": ["Read(./**/dist/**)"]}}
    pr = tmp_path / "s.json"
    pr.write_text(json.dumps({"permissions": {"deny": ["Read(./**/dist/**)"]}}), encoding="utf-8")
    first = run_merge_at(tmp_path / "fw.json", pr, framework, tmp_path)
    second = run_merge_at(tmp_path / "fw.json", pr, framework, tmp_path)
    assert first["permissions"]["deny"] == second["permissions"]["deny"] == ["Read(./**/dist/**/*.js)"]


def test_shipped_settings_retires_the_blanket_dist_rules():
    """The live template must actually declare the two rules this release drops."""
    d = json.loads(SETTINGS.read_text(encoding="utf-8"))
    retired = d.get("_retired_permissions", {}).get("deny", [])
    for r in ("Read(./**/dist/**)", "Read(./**/build/**)"):
        assert r in retired, f"{r} was narrowed but never retired — consumers keep the old rule"
