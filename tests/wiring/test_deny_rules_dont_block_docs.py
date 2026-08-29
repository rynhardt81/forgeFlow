"""A deny rule must block build output, not documentation that sits beside it.

Reported from a consumer project: `node_modules/next/dist/docs/` was unreadable
because `Read(./**/dist/**)` denied the whole directory. The rule's own note
says it exists to block "build outputs, caches, generated code, minified
bundles" — documentation is none of those, and CLAUDE.md told the session to
read exactly those files.

`dist/` and `build/` are the two roots that legitimately carry docs beside
compiled output, so they are denied by extension. Cache directories (.next,
.turbo, .vite, __pycache__, …) keep their blanket rule: they never carry docs.

The matcher below approximates the harness's glob rather than reimplementing
it. That is enough to catch a blanket rule reappearing, which is the defect.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SETTINGS = REPO_ROOT / "hooks" / "settings.json"


def deny_patterns() -> list[str]:
    perms = json.loads(SETTINGS.read_text(encoding="utf-8"))["permissions"]
    return [r[len("Read("):-1] for r in perms["deny"] if r.startswith("Read(")]


def _matches(pattern: str, path: str) -> bool:
    """Approximate gitignore-style glob: ** spans separators, * does not."""
    p = pattern[2:] if pattern.startswith("./") else pattern
    rx = ""
    i = 0
    while i < len(p):
        if p.startswith("**/", i):
            rx += "(?:.*/)?"; i += 3
        elif p.startswith("**", i):
            rx += ".*"; i += 2
        elif p[i] == "*":
            rx += "[^/]*"; i += 1
        elif p[i] == "?":
            rx += "[^/]"; i += 1
        else:
            rx += re.escape(p[i]); i += 1
    return re.fullmatch(rx, path) is not None


def denied(path: str) -> bool:
    return any(_matches(pat, path) for pat in deny_patterns())


@pytest.mark.parametrize("path", [
    "node_modules/next/dist/docs/01-app/index.md",   # the reported blocker
    "node_modules/next/dist/docs/README.md",
    "packages/thing/dist/CHANGELOG.md",
    "build/docs/guide.md",
    "dist/LICENSE",
    "dist/package.json",
])
def test_documentation_beside_build_output_is_readable(path):
    assert not denied(path), (
        f"{path} is denied. dist/ and build/ must be denied by extension, not wholesale — "
        "a blanket rule also blocks documentation, which is not what the deny note says "
        "the rule is for."
    )


@pytest.mark.parametrize("path", [
    "dist/bundle.js",
    "dist/nested/chunk.mjs",
    "packages/x/dist/styles.css",
    "build/main.cjs",
    "app/dist/vendor.min.js",
    "src/thing.generated.ts",
    "static/app.min.css",
    "dist/bundle.js.map",
])
def test_compiled_output_is_still_denied(path):
    assert denied(path), f"{path} should stay denied — it is the context-waste this rule exists for"


@pytest.mark.parametrize("path", [
    ".next/server/pages.js",
    "__pycache__/mod.cpython-312.pyc",
    ".venv/lib/python3.12/site-packages/x.py",
    "coverage/index.html",
])
def test_cache_dirs_keep_their_blanket_rule(path):
    """Caches never carry docs, so narrowing them would only weaken the rule."""
    assert denied(path), f"{path} should stay denied"


def test_no_blanket_rule_on_dist_or_build():
    """Gate the shape, so the blanket rule cannot quietly come back."""
    for pat in deny_patterns():
        assert pat not in ("./**/dist/**", "./**/build/**"), (
            f"blanket deny on {pat} reintroduced — it blocks documentation alongside output"
        )
