"""Doctrine test: no tracked text file carries a carriage return.

This repo is not merely checked out — it is rsynced into consumer projects,
whose pre-commit hooks normalize line endings to LF. A CRLF file here is
therefore not cosmetic: it shows as modified in every consumer, gets normalized
on their next commit, and drifts again on the following refresh. Perpetual
churn, and it masks real drift in the same diff.

`.gitattributes` pins `* text=auto eol=lf` to stop CRLF entering the repo. This
test is the belt to that braces — attributes only apply on checkout/commit
normalization, so a file written directly with CRLF by a tool or a re-vendored
third-party skill can still land in the working tree.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Extensions whose content is binary and legitimately may contain 0x0D bytes.
BINARY_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".gz",
    ".woff", ".woff2", ".ttf", ".otf",
}


def _tracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    ).stdout
    return [REPO_ROOT / p for p in out.split("\0") if p]


def test_no_tracked_text_file_contains_carriage_return():
    offenders = []
    for path in _tracked_files():
        if path.suffix.lower() in BINARY_SUFFIXES or not path.is_file():
            continue
        data = path.read_bytes()
        if b"\r" in data:
            offenders.append(str(path.relative_to(REPO_ROOT)))

    assert not offenders, (
        "these tracked files contain CR and will churn in every consumer on "
        f"every refresh — convert to LF: {sorted(offenders)}"
    )


def test_gitattributes_pins_lf():
    """The attributes file is the primary defence; assert it stays put."""
    attrs = REPO_ROOT / ".gitattributes"
    assert attrs.is_file(), ".gitattributes is missing — CRLF can re-enter the repo"
    text = attrs.read_text()
    assert "* text=auto eol=lf" in text, (
        ".gitattributes must pin `* text=auto eol=lf`; without it each machine's "
        "core.autocrlf decides, and a Windows contributor reintroduces CRLF"
    )
