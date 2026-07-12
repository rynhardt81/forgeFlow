"""Every hook command wired in hooks/settings.json must exist on disk.

This is the anti-bit-rot gate: the v3 memory pipeline was wired in settings
while its capture script silently failed for months, and a validator existed
on disk that nothing wired. Wiring and disk must agree in both directions.
"""

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SETTINGS = REPO_ROOT / "hooks" / "settings.json"

# Hooks legitimately not wired in settings.json: validators are bound via
# agent/skill frontmatter `hooks:` blocks instead.
FRONTMATTER_BOUND_DIRS = {"validators"}

# Shared library modules imported by hooks — not themselves hooks, so never
# wired in settings.json.
SHARED_LIBS = {"_hooklib.py"}


def _wired_scripts():
    data = json.loads(SETTINGS.read_text())
    scripts = []
    for event, matchers in data.get("hooks", {}).items():
        for matcher in matchers:
            for hook in matcher.get("hooks", []):
                cmd = hook.get("command", "")
                m = re.search(r"\.claude/(hooks/[\w\-/]+\.py)", cmd)
                if m:
                    scripts.append((event, m.group(1)))
    return scripts


def test_every_wired_hook_exists_on_disk():
    missing = [
        f"{event}: {rel}"
        for event, rel in _wired_scripts()
        if not (REPO_ROOT / rel).is_file()
    ]
    assert not missing, f"settings.json wires hooks that do not exist: {missing}"


def test_every_hook_on_disk_is_wired_or_frontmatter_bound():
    wired = {rel for _, rel in _wired_scripts()}

    # Collect frontmatter-bound validator references from agents/ + skills/
    frontmatter_refs = set()
    for md in list((REPO_ROOT / "agents").glob("*.md")) + list(
        (REPO_ROOT / "skills").glob("*/SKILL.md")
    ):
        for m in re.finditer(r"hooks/(validators/[\w\-/]+\.py)", md.read_text()):
            frontmatter_refs.add("hooks/" + m.group(1))

    unwired = []
    for py in (REPO_ROOT / "hooks").rglob("*.py"):
        rel = str(py.relative_to(REPO_ROOT))
        if "__pycache__" in rel:
            continue
        if py.name in SHARED_LIBS:
            continue
        top = py.relative_to(REPO_ROOT / "hooks").parts[0]
        if top in FRONTMATTER_BOUND_DIRS:
            # base.py is the shared class; concrete validators must be
            # referenced by at least one agent/skill frontmatter block.
            if py.name in ("base.py", "__init__.py"):
                continue
            if rel not in frontmatter_refs:
                unwired.append(f"{rel} (no agent/skill frontmatter binds it)")
        else:
            if py.name == "__init__.py":
                continue
            if rel not in wired:
                unwired.append(f"{rel} (not in settings.json)")
    assert not unwired, f"hooks on disk that nothing wires: {unwired}"
