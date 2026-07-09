"""Shared helpers for visualize generators."""

from __future__ import annotations

import json
import re
from pathlib import Path


# Convention-only role classification — hardcoded path patterns.
# Hit-order matters: tests first (so a test file in api/ doesn't get tagged API).
# Roles are file-level tags — at the module-overview layer, color comes from
# the top-level directory (more useful when most files share a role).
ROLE_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("tests",     re.compile(r"(^|/)tests?/|\.test\.|\.spec\.|_test\.")),
    ("frontend",  re.compile(r"(^|/)(frontend|ui|components|pages|app)/|\.(tsx|jsx)$")),
    ("api",       re.compile(r"(^|/)(api|routes|handlers|controllers|endpoints)/")),
    ("database",  re.compile(r"(^|/)(db|database|models|migrations|schema)/")),
    ("hooks",     re.compile(r"(^|/)hooks/")),
    ("scripts",   re.compile(r"(^|/)scripts/")),
    ("skills",    re.compile(r"(^|/)skills/")),
    ("infra",     re.compile(r"(^|/)(config|infra|deploy|terraform|docker)/")),
    ("docs",      re.compile(r"(^|/)docs/|\.(md|rst|adoc)$")),
]

ROLE_COLORS = {
    "api":      "#60a5fa",  # blue
    "frontend": "#f472b6",  # pink
    "database": "#34d399",  # green
    "hooks":    "#fbbf24",  # amber
    "scripts":  "#fb923c",  # orange
    "skills":   "#a78bfa",  # purple
    "infra":    "#facc15",  # yellow
    "docs":     "#22d3ee",  # cyan
    "tests":    "#f87171",  # red
    "other":    "#9ca3af",  # grey
}


def classify_role(path: str) -> str:
    """Return one of: tests, frontend, api, database, config, other."""
    for role, pat in ROLE_RULES:
        if pat.search(path):
            return role
    return "other"


# Unicode line/paragraph separators — break unquoted JS strings if left raw.
_LS = chr(0x2028)
_PS = chr(0x2029)


def json_safe(obj) -> str:
    """Serialize to JSON safe for embedding inside a <script> tag.

    `<script type="application/json">` blocks are inert (no eval), but a
    literal `</script>` substring would close the tag and break the HTML.
    Escape `</` to `<\\/`. Also escape U+2028 / U+2029 which break JS string
    literals (only relevant if a downstream consumer string-evals, but cheap
    insurance).
    """
    raw = json.dumps(obj, ensure_ascii=False)
    return (
        raw.replace("</", "<\\/")
           .replace(_LS, "\\u2028")
           .replace(_PS, "\\u2029")
    )


def default_output(name: str, root: Path) -> Path:
    return root / "docs" / "visualizations" / f"{name}.html"


def ensure_output_dir(output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)


def read_vendor(name: str) -> str:
    """Read a vendored JS file from Tools/templates/vendor/<name>."""
    here = Path(__file__).resolve().parent
    path = here / "templates" / "vendor" / name
    if not path.exists():
        raise FileNotFoundError(f"vendored library missing: {path}")
    return path.read_text(encoding="utf-8")


def framework_root() -> Path:
    """The directory where framework code lives.

    _shared.py is at <framework_root>/skills/visualize/Tools/_shared.py, so
    framework_root is __file__.parents[3].
    """
    return Path(__file__).resolve().parents[3]


def project_root() -> Path:
    """The project the framework is operating on.

    In a vendored install, framework_root is `<project>/.claude/`, so the
    project root is its parent. In the framework's own dev repo,
    framework_root IS the project (self-hosting). Detect "vendored" by
    checking whether framework_root's basename is `.claude`.

    Note: `.git` is the only walk-up marker. `docs/code-map.json` is NOT a
    marker because it's a derived artifact that can be rsync-leaked into
    `.claude/docs/` (false-positive trap).
    """
    fr = framework_root()
    if fr.name == ".claude":
        return fr.parent
    for parent in [fr, *fr.parents]:
        if (parent / ".git").exists():
            return parent
    return fr
