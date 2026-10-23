"""Orchestrated (subagent-driven) development is the default, behind one ask (T969)."""

from __future__ import annotations

from pathlib import Path

SKILLS = Path(__file__).resolve().parents[2] / "skills"
DOC = (SKILLS / "_shared" / "orchestrated-development.md").read_text(encoding="utf-8")


def _read(rel: str) -> str:
    return (SKILLS / rel).read_text(encoding="utf-8")


def test_asked_once_at_the_existing_confirmation_with_yes_as_default():
    assert "Ask exactly once" in DOC and "**yes** (default)" in DOC
    step1 = _read("run-epic/SKILL.md").split("## Step 1")[1].split("## Step 2")[0]
    assert "subagent-driven development" in step1 and "default yes" in step1
    nf = _read("new-feature/SKILL.md").split("## Step 1")[1].split("## Step 2")[0]
    assert "subagent-driven development" in nf


def test_loop_execute_dispatches_when_orchestrated_and_keeps_inline_path():
    execute = _read("run-epic/LOOP.md").split("## Execute")[1].split("## Verify")[0]
    assert execute.index("Orchestrated") < execute.index("Inline")
    assert "_shared/orchestrated-development.md" in execute
    assert "_shared/orchestrated-development.md" in _read("new-feature/PHASES.md")


def test_orchestrator_never_fixes_and_verifies_itself():
    assert "never fixes findings itself" in DOC
    assert "run the covering tests yourself" in DOC
    assert "rules/agent-verification.md" in DOC


def test_fix_loop_is_capped_with_resume_then_escalate():
    assert "five rounds maximum" in DOC
    assert "Rounds 1–3 — resume the original implementer" in DOC
    assert "Rounds 4–5 — a fresh implementer one tier up" in DOC


def test_routing_follows_model_routing_and_hard_floors():
    assert "_shared/model-routing.md" in DOC
    assert "Hard-floor tasks" in DOC and "session model" in DOC


def test_resume_restores_the_answer():
    assert "orchestrated: yes|no" in _read("reflect/flows/resume.md")
