"""The `forge` shorthand must be a shell function, never a variable.

Skills say `forge task ls`. In a Bash tool call there is no alias (each call is
a fresh non-interactive shell), so the model invents one — and the usual
invention, `FORGE="python3 .claude/scripts/forge/forge.py"; $FORGE task ls`,
fails under zsh, which does not word-split an unquoted parameter: the whole
string is looked up as one command name. Measured at 180 failures across
session logs. A function takes its arguments as words in every shell.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FUNCTION = 'forge() { python3 .claude/scripts/forge/forge.py "$@"; }'
VARIABLE_FORM = re.compile(r'FORGE="python3|\$\{?FORGE\}?\s+(task|epic|agent|memory|doctor|dashboard)')


def test_claude_md_defines_forge_as_a_function():
    assert FUNCTION in (ROOT / "CLAUDE.md").read_text(encoding="utf-8")


def test_no_shipped_doc_uses_the_variable_form():
    hits = []
    for d in ("skills", "rules", "agents", "templates", "ALGORITHM", "reference"):
        for p in (ROOT / d).rglob("*.md"):
            for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                if VARIABLE_FORM.search(line) and FUNCTION not in line:
                    hits.append(f"{p.relative_to(ROOT)}:{n}")
    for p in (ROOT / "CLAUDE.md",):
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            # The canonical line quotes the variable form as the thing not to do.
            if VARIABLE_FORM.search(line) and FUNCTION not in line:
                hits.append(f"CLAUDE.md:{n}")
    assert not hits, f"variable-form forge shorthand (breaks under zsh): {hits}"
