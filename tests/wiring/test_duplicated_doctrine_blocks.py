"""The reproduction-evidence table is duplicated ON PURPOSE. Keep the copies identical.

A Fable 5 audit flagged three "duplicated doctrine tables" as consolidation
candidates. Measured, two of the three claims do not survive:

1. **Reproduction-evidence table** — real: 322 chars, byte-identical in
   `ALGORITHM/v1.2.0.md` (Gate A) and `skills/fix-bug/SKILL.md` (step 2).
   Consolidating it would be a net loss. `fix-bug` contains zero references to
   ALGORITHM — it is a standalone skill read in Native mode — so replacing the
   table with a pointer forces a `/fix-bug` invocation to load 12,647 chars of
   ALGORITHM to reach 322 chars of table. 39x worse than the duplication.
2. **ISC splitting test** — not duplicated. ALGORITHM carries a table; the ISA
   skill carries the same five gates as prose bullets for a different reader.
3. **Checkpoint-discipline one-liners** — single lines across agent files.
   Replacing a one-line rule with a one-line pointer saves nothing and adds a
   hop.

So the duplication stays. Its only real cost is drift: someone edits Gate A and
`fix-bug` silently keeps the old requirements. This test removes that cost at
zero token cost, which is why consolidating was never the right fix.

If you are here because this test failed: you changed one copy. Change the
other to match — do not delete either.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ALGORITHM = REPO_ROOT / "ALGORITHM" / "v1.2.0.md"
FIX_BUG = REPO_ROOT / "skills" / "fix-bug" / "SKILL.md"

TABLE_HEAD = "| Symptom | Required reproduction |"


def repro_table(path: Path) -> str:
    """The reproduction-evidence table as it appears in `path`."""
    text = path.read_text(encoding="utf-8")
    assert TABLE_HEAD in text, f"{path.name} no longer carries the reproduction table"
    body = text[text.index(TABLE_HEAD):]
    # The table ends at the first blank line after its rows.
    rows = []
    for line in body.splitlines():
        if line.startswith("|"):
            rows.append(line.rstrip())
        elif rows:
            break
    return "\n".join(rows)


def test_reproduction_table_is_identical_in_both_homes():
    a, b = repro_table(ALGORITHM), repro_table(FIX_BUG)
    assert a == b, (
        "The reproduction-evidence table has drifted between ALGORITHM Gate A and "
        "fix-bug step 2. They are duplicated deliberately (see this file's docstring) "
        "— make them match again rather than deleting either copy.\n\n"
        f"ALGORITHM:\n{a}\n\nfix-bug:\n{b}"
    )


def test_both_copies_are_non_trivial():
    """Guard the guard: an empty parse would make the equality test vacuous."""
    rows = repro_table(ALGORITHM).splitlines()
    assert len(rows) >= 4, f"parsed only {len(rows)} rows — the extractor is broken, not the doc"


def test_fix_bug_stays_standalone():
    """The reason the duplication is correct: fix-bug must not depend on ALGORITHM.

    If fix-bug ever starts referencing ALGORITHM, the cost calculation that
    justifies duplicating the table changes and it is worth re-deciding.
    """
    text = FIX_BUG.read_text(encoding="utf-8")
    assert not re.search(r"ALGORITHM/v\d", text), (
        "fix-bug now references ALGORITHM — re-evaluate whether the reproduction "
        "table should be consolidated after all"
    )
