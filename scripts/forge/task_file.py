"""Task body files: where they live and what their frontmatter says.

The one owner of the `docs/epics/E*/tasks/T*.md` format. `registry_ops`
mirrors registry changes into these files and `check_consistency` reads them
to detect drift; both go through this module so the regexes, the YAML
quoting and the directory layout exist once.

Every write here is best-effort: the registry is the source of truth, and a
missing or unreadable file is surfaced later as drift, never raised.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterator

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?\n)---\s*(?:\n|$)", re.DOTALL)
# Field patterns end in `[ \t]*` (not `\s*`) so they don't consume the newline
# that separates the field line from the closing `---` delimiter.
_FIELD_RE = {
    "status": re.compile(r"^(status[ \t]*:[ \t]*)(\S+)[ \t]*$", re.MULTILINE),
    # Rest of the line (names have spaces); quotes are stripped on read.
    "name": re.compile(r"^(name[ \t]*:[ \t]*)(.+?)[ \t]*$", re.MULTILINE),
    "epic": re.compile(r"^(epic:\s*)(.*)$", re.MULTILINE),
}
# Strictly Tnnn-... or Tnnn.md: split-task suffixes (T149a) are not T149.
_TASK_FILENAME_RE = re.compile(r"^T(\d+)(?=[-.])")
_EPIC_DIR_RE = re.compile(r"^E(\d+)")
# YAML forbids C0 and C1 controls and splits plain scalars on NEL/LS/PS.
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f-\x9f  ￾￿]")
# Plain scalars YAML 1.1 (PyYAML) types implicitly: numbers, dates and
# sexagesimals all start with a digit/sign/dot; the rest are keywords.
# Conservative on purpose -- a needlessly quoted string still round-trips.
_YAML_TYPED_START_RE = re.compile(r"^[-+.0-9]")
_YAML_KEYWORDS = frozenset(
    {"y", "n", "yes", "no", "true", "false", "on", "off", "null", "~", ".inf", ".nan", "<<", "="}
)
_ESCAPE_RE = re.compile(r'\\(["\\ntr]|x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4})')
_UNESCAPE = {'"': '"', "\\": "\\", "n": "\n", "t": "\t", "r": "\r"}


# --- YAML scalars ----------------------------------------------------------


def quote(value: str) -> str:
    """Quote a YAML scalar if it contains chars YAML would interpret.

    Conservative: only quote when needed so common names round-trip
    unquoted. Uses double-quotes and escapes embedded `"`, backslashes and
    control characters (a raw newline in a name split the frontmatter line
    and forge's regex reader silently kept the first half).
    """
    if not value:
        return '""'
    needs_quote = (
        value[0] in ("-", "?", ":", ",", "[", "]", "{", "}", "#", "&", "*",
                     "!", "|", ">", "'", "\"", "%", "@", "`")
        or ":" in value
        or "#" in value
        or value.strip() != value
        or _CONTROL_CHAR_RE.search(value) is not None
        or _YAML_TYPED_START_RE.match(value) is not None
        or value.lower() in _YAML_KEYWORDS
    )
    if not needs_quote:
        return value
    escaped = (
        value.replace("\\", "\\\\")
        .replace("\"", "\\\"")
        .replace("\n", "\\n")
        .replace("\t", "\\t")
        .replace("\r", "\\r")
    )
    # Any other control byte (NUL, VT, FF, DEL, ...) is illegal raw inside a
    # YAML double-quoted scalar; emit the \xNN form YAML defines for it.
    escaped = _CONTROL_CHAR_RE.sub(
        lambda m: f"\\x{ord(m.group()):02x}" if ord(m.group()) < 0x100 else f"\\u{ord(m.group()):04x}",
        escaped,
    )
    return f"\"{escaped}\""


def unquote(raw: str) -> str:
    # Inverse of quote(): strip a balanced surrounding pair of `"` or `'` and
    # reverse the encoder's escapes. Without this, names containing `"` or `\`
    # round-trip asymmetrically and re-fire drift #8 on every consistency pass.
    if len(raw) >= 2 and raw[0] == raw[-1]:
        if raw[0] == '"':
            # One left-to-right pass over the encoder's escapes. Sequential
            # replace() calls are order-sensitive: the literal characters
            # `\n` inside an escaped backslash (`\\n`) would be re-read as a
            # newline by a later pass.
            return _ESCAPE_RE.sub(
                lambda m: _UNESCAPE.get(m.group(1)) or chr(int(m.group(1)[1:], 16)),
                raw[1:-1],
            )
        if raw[0] == "'":
            return raw[1:-1].replace("''", "'")
    return raw


# --- Frontmatter on a string -----------------------------------------------


def parse(content: str) -> dict[str, str]:
    """Return {field: unquoted value} for status, name and epic.

    A field the frontmatter lacks (or a file with no frontmatter) maps to "".
    """
    fm = _FRONTMATTER_RE.match(content)
    block = fm.group(1) if fm else ""
    out = {}
    for field, pattern in _FIELD_RE.items():
        m = pattern.search(block)
        out[field] = unquote(m.group(2).strip()) if m else ""
    return out


def rewrite(content: str, field: str, value: str) -> tuple[str, bool]:
    """Rewrite one scalar field inside the first frontmatter block.

    Returns (new_content, changed). No-op when the file has no frontmatter or
    no such field -- we don't invent structure that wasn't there. `name` is
    YAML-quoted when needed; status and epic values are written as given.
    """
    fm = _FRONTMATTER_RE.match(content)
    if not fm:
        return content, False
    block = fm.group(1)
    written = quote(value) if field == "name" else value
    new_block, n = _FIELD_RE[field].subn(lambda m: f"{m.group(1)}{written}", block, count=1)
    if n == 0 or new_block == block:
        return content, False
    return content[: fm.start(1)] + new_block + content[fm.end(1) :], True


# --- Files on disk ---------------------------------------------------------


def find(project_root: Path, task: dict[str, Any]) -> Path | None:
    """The task's body file: the registry's `file` (legacy `path`), else discovery.

    Discovery globs docs/epics/{epic}-*/tasks/{id}-*.md and returns the first
    match. Returns None when nothing exists on disk.
    """
    rel = task.get("file") or task.get("path")
    if rel and (project_root / rel).exists():
        return project_root / rel
    epic_id, task_id = task.get("epic"), task.get("id")
    epics_dir = project_root / "docs" / "epics"
    if not (epic_id and task_id) or not epics_dir.exists():
        return None
    for epic_dir in epics_dir.glob(f"{epic_id}-*"):
        if not epic_dir.is_dir():
            continue
        candidates = list((epic_dir / "tasks").glob(f"{task_id}-*.md"))
        if candidates:
            return candidates[0]
    return None


def read(path: Path) -> dict[str, str] | None:
    """parse() of a file, or None when it can't be read."""
    try:
        return parse(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return None


def set_field(path: Path | None, field: str, value: str) -> bool:
    """Rewrite one frontmatter field in place. True when a write happened."""
    if path is None or not path.exists():
        return False
    try:
        new_content, changed = rewrite(path.read_text(encoding="utf-8"), field, value)
        if changed:
            path.write_text(new_content, encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    return changed


def set_scope(path: Path | None, scope: dict[str, Any]) -> None:
    """Replace the frontmatter `scope:` block, appending one when absent.

    Unlike the scalar fields this does add structure: frontmatter that omits
    scope is what let registry and file disagree silently in the first place.
    """
    if path is None or not path.exists():
        return
    try:
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---"):
            return
        end = text.index("\n---", 3)
        head, rest = text[:end], text[end:]
        block = [
            "scope:",
            f"  directories: [{', '.join(scope['directories'])}]",
            f"  files: [{', '.join(scope['files'])}]",
        ]
        out, skipping, found = [], False, False
        for line in head.splitlines():
            if line.startswith("scope:"):
                skipping, found = True, True
                out.extend(block)
                continue
            if skipping:
                # Consume the old block's indented children only.
                if line.startswith(("  ", "\t")):
                    continue
                skipping = False
            out.append(line)
        if not found:
            out.extend(block)
        path.write_text("\n".join(out) + rest)
    except (OSError, ValueError):
        return


def iter_all(project_root: Path) -> Iterator[tuple[Path, str, str]]:
    """Yield (path, task_id, epic_id) for every task file, sorted.

    Walks docs/epics/E<n>*/tasks/T<n>[-.]*.md. The filename match is looser
    than find()'s glob (it also takes `T12.md`); both shapes exist in the wild.
    """
    epics_dir = project_root / "docs" / "epics"
    if not epics_dir.exists():
        return
    for epic_dir in sorted(epics_dir.iterdir()):
        em = _EPIC_DIR_RE.match(epic_dir.name)
        if not (epic_dir.is_dir() and em):
            continue
        tasks_dir = epic_dir / "tasks"
        if not tasks_dir.exists():
            continue
        for tf in sorted(tasks_dir.glob("T*.md")):
            m = _TASK_FILENAME_RE.match(tf.name)
            if m:
                yield tf, f"T{m.group(1)}", f"E{em.group(1)}"
