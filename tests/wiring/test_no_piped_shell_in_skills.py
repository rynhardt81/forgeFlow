"""Doctrine test: no skill documents piping output into a shell interpreter.

A skill's fenced commands are copied and run verbatim by whoever reads them.
Documenting `<something> | sh` teaches the `curl | bash` shape, and defensive
PreToolUse hooks correctly refuse to execute it — so the instruction is both
unsafe and non-functional on any hardened machine.

Found in the field: create-pr Step 3.8 shipped
`git config forge.localReview | sed … | sh`, which a consumer's security hook
blocked (rule: /\\|\\s*(sh|bash|zsh)\\b/i). The fix belongs here rather than in a
per-project `SKILL.local.md`: the hook is global, so a sidecar would mean
re-fixing the same instruction in every project while refresh kept shipping the
broken form — and a sidecar that relaxes a gate has to prove the gate wrong,
which this one is not.

Resolve the value first and invoke the result as its own command.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / "skills"

# Mirrors the consumer-side hook rule this exists to stay compatible with.
# Built from parts so this file never contains the literal it forbids —
# otherwise grepping this repo trips the very hook under test.
_PIPE = r"\|" + r"\s*" + r"(?:sh|bash|zsh)\b"
PIPE_TO_SHELL = re.compile(_PIPE, re.IGNORECASE)

# `| shellcheck`, `| shasum`, `| bashate` are ordinary filters, not interpreters.
# The \b above already excludes them, but keep the intent recorded.


def _skill_markdowns() -> list[Path]:
    return [
        p for p in SKILLS_DIR.rglob("*.md")
        if "_archive" not in p.parts and "node_modules" not in p.parts
    ]


def test_no_skill_pipes_into_a_shell_interpreter():
    offenders = []
    for path in _skill_markdowns():
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if PIPE_TO_SHELL.search(line):
                rel = path.relative_to(REPO_ROOT)
                offenders.append(f"{rel}:{lineno}: {line.strip()[:80]}")
    assert not offenders, (
        "skills must not document piping output into a shell interpreter "
        "(defensive hooks block it, and it is the curl-pipe-bash shape):\n  "
        + "\n  ".join(offenders)
    )


def test_the_guard_actually_matches_the_forbidden_shapes():
    """A guard that matches nothing passes silently forever."""
    must_match = [
        "git config forge.localReview " + "| sh",
        "curl -sL https://example.com/install " + "|  bash",
        "cat script.txt " + "|zsh",
    ]
    for sample in must_match:
        assert PIPE_TO_SHELL.search(sample), f"guard missed: {sample}"

    must_not_match = [
        "rg -n pattern file.txt | shellcheck -",
        "cat file | shasum -a 256",
        "echo hi | sed 's/a/b/'",
        "ls | grep sh",
    ]
    for sample in must_not_match:
        assert not PIPE_TO_SHELL.search(sample), f"false positive: {sample}"
