"""`/reflect retro <session>` digests a past transcript (T967)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

TOOL = Path(__file__).resolve().parents[2] / "skills" / "reflect" / "Tools" / "transcript_digest.py"
spec = importlib.util.spec_from_file_location("transcript_digest", TOOL)
td = importlib.util.module_from_spec(spec)
spec.loader.exec_module(td)


def _write(path: Path, entries: list[dict]) -> Path:
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\nnot json\n")
    return path


def test_digest_keeps_user_words_errors_and_tool_economy(tmp_path):
    t = _write(tmp_path / "s.jsonl", [
        {"type": "user", "message": {"content": "fix the login bug"}},
        {"type": "user", "isMeta": True, "message": {"content": "injected"}},
        {"type": "user", "message": {"content": "<system-reminder>noise</system-reminder>"}},
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "a", "name": "Bash"},
            {"type": "tool_use", "id": "b", "name": "Read"}]}},
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "a", "is_error": True, "content": "Exit code 127\nno such file"},
            {"type": "tool_result", "tool_use_id": "b", "content": [{"type": "text", "text": "x" * 5000}]}]}},
    ])
    out = td.digest(t)
    assert "## User messages (1)" in out and "1. fix the login bug" in out
    assert "injected" not in out and "noise" not in out
    assert "- Bash: Exit code 127 no such file" in out
    assert "- Read: 5,000 chars" in out
    assert "- Bash: 1" in out and "- Read: 1" in out


def test_bare_id_resolves_under_the_project_slug(tmp_path):
    got = td.resolve("abc-123", Path("/Users/x/My.Proj"))
    assert got == Path.home() / ".claude/projects/-Users-x-My-Proj/abc-123.jsonl"


def test_missing_transcript_exits_1(tmp_path, capsys):
    assert td.main(["nope", "--project-dir", str(tmp_path)]) == 1
    assert "no transcript at" in capsys.readouterr().err


def test_flow_documents_both_retro_gaps():
    flow = (TOOL.parents[1] / "flows" / "manual-reflection.md").read_text()
    assert "**Steering files**" in flow
    assert "/reflect retro <session-id | transcript path>" in flow
    assert "transcript_digest.py" in flow
