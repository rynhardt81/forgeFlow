"""The settings merge must not delete a consumer's own hook wiring.

Regression gate, filed 2026-09-07 after the third recorded occurrence in one
consumer. The merge did `pr_hooks[event] = entries` -- the framework's list
replaces the consumer's outright -- so any project-added matcher in an event
the framework also ships was deleted on every refresh. That consumer's
production guard (a PreToolUse hook on matcher "*") was silently disarmed by
v4.2.0, v4.4.1 and v4.5.1 in turn, each time discovered only because someone
ran the project's own test suite afterwards.

Silently is the operative word: install.sh reported success throughout, and a
disarmed guard looks exactly like a guard with nothing to block.

The framework's own wiring still wins -- a consumer cannot pin a stale version
of a framework hook, which is what the replace-per-event was protecting. The
distinction is by command path: a hook whose command points under
`.claude/hooks/` is framework territory and is replaced from the template;
anything else is the project's and is preserved. That is the same
classification the neighbouring dead-wiring prune already uses.

These tests execute the real merge block extracted from install.sh, not a copy
of its logic, so the gate cannot pass against a reverted installer.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_SH = REPO_ROOT / "scripts" / "install" / "install.sh"

FW_HOOK = 'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/validation/validate-edit.py"'
PROJECT_HOOK = 'python3 "$CLAUDE_PROJECT_DIR/tools/prod-guard/run_guard.py"'


def merge_block() -> str:
    text = INSTALL_SH.read_text(encoding="utf-8")
    m = re.search(r"<<'MERGE_EOF'\n(.*?)\nMERGE_EOF", text, re.DOTALL)
    assert m, "merge heredoc not found in install.sh — did the marker change?"
    return m.group(1)


def run_merge(tmp_path: Path, framework: dict, project: dict) -> dict:
    """Run the real merge. The consumer tree is laid out so the framework hook
    path EXISTS -- otherwise the dead-wiring prune removes it and the test
    would be measuring the wrong mechanism."""
    consumer = tmp_path / "consumer"
    (consumer / ".claude" / "hooks" / "validation").mkdir(parents=True)
    (consumer / ".claude" / "hooks" / "validation" / "validate-edit.py").write_text("#\n")
    fw = tmp_path / "framework.json"
    pr = consumer / ".claude" / "settings.json"
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


def _commands(merged: dict, event: str) -> list[str]:
    out = []
    for matcher in merged.get("hooks", {}).get(event, []):
        for h in matcher.get("hooks", []):
            out.append(h.get("command"))
    return out


FRAMEWORK = {"hooks": {"PreToolUse": [
    {"matcher": "Write|Edit", "hooks": [{"type": "command", "command": FW_HOOK, "timeout": 5}]}
]}}


def test_project_hook_survives_in_an_event_the_framework_also_ships(tmp_path):
    """The defect. A project PreToolUse matcher must not be deleted because the
    framework happens to ship its own PreToolUse wiring."""
    project = {"hooks": {"PreToolUse": [
        {"matcher": "*", "hooks": [{"type": "command", "command": PROJECT_HOOK, "timeout": 10}]}
    ]}}
    merged = run_merge(tmp_path, FRAMEWORK, project)
    assert PROJECT_HOOK in _commands(merged, "PreToolUse"), "project hook was deleted"


def test_framework_wiring_still_wins(tmp_path):
    """What the replace-per-event was protecting: a consumer cannot pin a stale
    copy of a framework hook. The template's version is what ships."""
    project = {"hooks": {"PreToolUse": [
        {"matcher": "Write|Edit", "hooks": [
            {"type": "command", "command": FW_HOOK, "timeout": 999}
        ]}
    ]}}
    merged = run_merge(tmp_path, FRAMEWORK, project)
    timeouts = [h["timeout"]
                for m in merged["hooks"]["PreToolUse"] for h in m["hooks"]
                if h["command"] == FW_HOOK]
    assert timeouts == [5], f"framework version did not win: {timeouts}"


def test_no_duplicate_framework_hook_when_consumer_already_had_it(tmp_path):
    """Preserving project entries must not re-add framework ones alongside the
    template's copy -- that would fire every framework hook twice."""
    project = {"hooks": {"PreToolUse": [
        {"matcher": "Write|Edit", "hooks": [{"type": "command", "command": FW_HOOK, "timeout": 5}]},
        {"matcher": "*", "hooks": [{"type": "command", "command": PROJECT_HOOK, "timeout": 10}]},
    ]}}
    merged = run_merge(tmp_path, FRAMEWORK, project)
    cmds = _commands(merged, "PreToolUse")
    assert cmds.count(FW_HOOK) == 1, f"framework hook duplicated: {cmds}"
    assert cmds.count(PROJECT_HOOK) == 1


def test_merge_is_idempotent(tmp_path):
    """A second refresh must not keep growing the file."""
    project = {"hooks": {"PreToolUse": [
        {"matcher": "*", "hooks": [{"type": "command", "command": PROJECT_HOOK, "timeout": 10}]}
    ]}}
    once = run_merge(tmp_path, FRAMEWORK, project)
    twice = run_merge(tmp_path / "second", FRAMEWORK, once)
    assert once == twice


def test_a_mixed_matcher_keeps_only_its_project_half(tmp_path):
    """A consumer matcher holding both a framework hook and its own: the
    framework copy comes from the template, the project one is preserved, and
    neither is duplicated."""
    project = {"hooks": {"PreToolUse": [
        {"matcher": "Write|Edit", "hooks": [
            {"type": "command", "command": FW_HOOK, "timeout": 999},
            {"type": "command", "command": PROJECT_HOOK, "timeout": 10},
        ]}
    ]}}
    merged = run_merge(tmp_path, FRAMEWORK, project)
    cmds = _commands(merged, "PreToolUse")
    assert cmds.count(FW_HOOK) == 1
    assert cmds.count(PROJECT_HOOK) == 1


def test_project_hook_in_an_event_the_framework_does_not_ship_is_untouched(tmp_path):
    """Unchanged behaviour, asserted so the fix cannot regress it."""
    project = {"hooks": {"Notification": [
        {"matcher": "*", "hooks": [{"type": "command", "command": PROJECT_HOOK}]}
    ]}}
    merged = run_merge(tmp_path, FRAMEWORK, project)
    assert PROJECT_HOOK in _commands(merged, "Notification")
