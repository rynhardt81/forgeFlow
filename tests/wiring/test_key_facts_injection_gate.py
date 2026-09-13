"""T919: key-facts.md must be injected on content, never on formatting.

The original gate looked for a line starting with `- **`. Bold came from the
template's example bullets; MEMORY-SCHEMA.md asks only that entries be single
lines. So a conformant file of plain bullets was silently never injected — no
error, no marker, nothing to notice. Two independent reconcile runs tripped it
by legitimately rewriting key-facts as plain one-liners and watching the whole
file disappear from SessionStart.

Both directions matter. Injecting a pristine template is noise on every new
project; skipping a real file is silent knowledge loss. These tests pin both.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK = REPO_ROOT / "hooks" / "session" / "session-context.py"
TEMPLATE = REPO_ROOT / "templates" / "project-memory" / "key-facts.md"


def _hook():
    spec = importlib.util.spec_from_file_location("session_context", HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_pristine_template_is_not_injected():
    """A project that has never written a fact should not pay for the template."""
    assert TEMPLATE.is_file(), f"template missing at {TEMPLATE}"
    assert _hook()._has_real_content(TEMPLATE.read_text()) is False


@pytest.mark.parametrize(
    "body",
    [
        "# Key facts\n\n- Dev server runs on port 4000, not 4001.\n",
        "# Key facts\n\n- **Staging:** nn-staging, prod is nn-prod.\n",
        "# Key facts\n\n> Keep it short.\n\n- Plain bullet under a blockquote.\n",
        "# Key facts\n\n<!-- Examples:\n- not a real fact\n-->\n\n- A real fact.\n",
        "Just a bare line with no markdown at all.\n",
    ],
    ids=["plain-bullet", "bold-label", "after-blockquote", "after-comment", "bare-line"],
)
def test_real_content_is_injected(body):
    assert _hook()._has_real_content(body) is True, (
        "this file carries a fact and would be silently dropped from every session"
    )


@pytest.mark.parametrize(
    "body",
    [
        "",
        "# Key facts\n",
        "# Key facts\n\n> Always loaded at SessionStart — keep it SHORT.\n",
        "# Key facts\n\n<!-- Examples:\n- Staging: myapp-staging\n-->\n",
    ],
    ids=["empty", "heading-only", "heading-and-blockquote", "examples-in-comment"],
)
def test_scaffolding_alone_is_not_content(body):
    assert _hook()._has_real_content(body) is False
