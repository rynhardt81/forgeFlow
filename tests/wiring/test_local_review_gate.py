"""Doctrine test: the local review-bot gate runs pre-push, and never in a loop.

`forge.localReview` (create-pr Step 3.8) exists to move the review-fix cycle off
GitHub Actions. The configured bot only sees the code once a PR exists, so every
finding it raises costs a full Actions matrix: fix -> push -> matrix re-runs ->
bot re-scans -> repeat. A PR that took 19 review rounds burned 19 matrices.

Two properties have to hold for that to work, and both are silently losable:

  1. The gate is positioned BEFORE the PR is created. Below Step 5 it reviews
     code that has already triggered CI, which is the cost it exists to avoid.
  2. It stays bounded and attended. An LLM CLI on an interactive-use
     subscription, invoked by a process that never gets tired, is the shape
     that produces a surprise bill — so no hook and no scheduled loop may
     invoke it, and the round cap must stay documented.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL = REPO_ROOT / "skills" / "create-pr" / "SKILL.md"
HOOKS_DIR = REPO_ROOT / "hooks"

# An *invocation* of the local reviewer, in the forms a hook could plausibly use.
# Deliberately not a bare `codex review` match: hooks legitimately mention the
# PR-body handle (`@codex review mention`) in docstrings and reminder strings,
# and a guard that cries wolf on prose gets deleted by the next person.
_INVOCATION = re.compile(
    r"""
      (?<!@)\bcodex\s+review\b          # shell string: os.system("codex review …")
    | ["']codex["']\s*,\s*["']review["'] # list form: subprocess.run(["codex","review"])
    | forge\.localReview                 # reading the configured command at all
    """,
    re.VERBOSE,
)


def _skill_text() -> str:
    return SKILL.read_text(encoding="utf-8")


def test_config_key_is_documented():
    assert "forge.localReview" in _skill_text()


def test_gate_runs_before_the_pr_is_created():
    """Step 3.8 must sit above Step 5, or it reviews code CI already ran on."""
    text = _skill_text()
    gate = text.find("## Step 3.8")
    create = text.find("## Step 5: Create PR")
    assert gate != -1, "Step 3.8 (local review gate) is missing"
    assert create != -1, "Step 5 (Create PR) is missing"
    assert gate < create, "local review gate must precede PR creation"


def test_round_cap_is_stated():
    """The bound is the cost control. Losing it restores the runaway shape."""
    text = _skill_text()
    section = text[text.find("## Step 3.8"):text.find("## Step 3.5")]
    assert re.search(r"\b3\b.{0,40}round", section, re.IGNORECASE | re.DOTALL), (
        "Step 3.8 must state its round cap"
    )
    assert "unattended" in section.lower()


def test_a_missing_reviewer_never_blocks():
    """Bare installs have no reviewer CLI; the gate must degrade, not gate."""
    section = _skill_text()
    section = section[section.find("## Step 3.8"):section.find("## Step 3.5")]
    assert "Never block" in section or "never block" in section


def test_no_hook_invokes_the_local_reviewer():
    """A hook fires on every matching tool call — unattended by definition."""
    offenders = []
    for path in HOOKS_DIR.rglob("*"):
        if not path.is_file() or path.suffix not in {".py", ".sh", ".json", ".ts"}:
            continue
        if "__pycache__" in path.parts:
            continue
        body = path.read_text(encoding="utf-8", errors="replace")
        if _INVOCATION.search(body):
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert not offenders, (
        "hooks must never invoke the local reviewer (unattended loop risk): "
        + ", ".join(offenders)
    )
