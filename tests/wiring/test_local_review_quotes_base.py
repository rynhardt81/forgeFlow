"""Doctrine test: the local-review gate must document quoting the branch.

`forge.localReview` holds a command template with a `{base}` placeholder, and
the resolved string is executed. `git check-ref-format` permits `;`, `$(…)`,
backticks, `&&` and `|` in a branch name, so `release/foo;id` is a legal branch
and substituting it raw appends a second command to the reviewer invocation.

The usual branch name needs no quoting, which is what makes the omission easy
to ship: every ordinary case works. Only a deliberately-shaped ref exposes it,
and by then the command has already run.
"""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL = REPO_ROOT / "skills" / "create-pr" / "SKILL.md"


def _step_38() -> str:
    text = SKILL.read_text(encoding="utf-8")
    start = text.index("## Step 3.8")
    return text[start:text.index("## Step 3.5", start)]


def test_step_38_requires_the_branch_to_be_quoted():
    section = _step_38().lower()
    assert "shell-quoted" in section or "quote the branch" in section


def test_step_38_says_why_rather_than_just_what():
    """A bare instruction gets dropped; the reason is what makes it stick."""
    section = _step_38()
    assert "check-ref-format" in section


def test_git_really_permits_shell_metacharacters_in_a_branch_name():
    """The premise. If git ever tightened this, the warning could be relaxed."""
    for ref in ("release/foo;id", "feat/$(id)", "fix/`id`", "feat/a&&b"):
        proc = subprocess.run(
            ["git", "check-ref-format", "--branch", ref],
            capture_output=True, text=True,
        )
        assert proc.returncode == 0, f"git now rejects {ref!r}"


def test_quoting_actually_neutralises_the_payload(tmp_path):
    """The fix works, demonstrated by a side effect rather than by inspection.

    Asserting on output text is not enough: a quoted payload still APPEARS in
    the command string. Only a side effect distinguishes 'ran' from 'printed'.
    """
    template = "echo reviewing --base {base}"
    branch = f"release/foo;touch {tmp_path / 'PWNED'}"

    for value, should_fire in ((branch, True), (shlex.quote(branch), False)):
        marker = tmp_path / "PWNED"
        marker.unlink(missing_ok=True)
        subprocess.run(
            ["bash", "-c", template.replace("{base}", value)],
            capture_output=True, text=True,
        )
        assert marker.exists() is should_fire


def test_background_guidance_survived():
    """Regression guard: a downstream edit reverted this once already."""
    section = _step_38()
    assert "run_in_background" in section
    assert "in flight" in section          # no-edits-while-running rule
    assert "does **not** relax" in section  # gate is not weakened by detaching
