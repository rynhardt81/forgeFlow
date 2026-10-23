#!/usr/bin/env python3
"""Digest a Claude Code session transcript for `/reflect retro <session>`.

A transcript (~/.claude/projects/<project-slug>/<session-id>.jsonl) runs to
thousands of lines; a retro needs four things from it: what the user said,
which tool calls failed, how often each tool ran, and the largest outputs
(the tool-economy candidates). Prints them as markdown. Read-only.

    transcript_digest.py <session-id | path.jsonl> [--project-dir DIR]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path


def resolve(session: str, project_dir: Path) -> Path:
    """A path as given, else <session>.jsonl under the project's transcript dir."""
    p = Path(session).expanduser()
    if p.is_file():
        return p
    slug = re.sub(r"[^A-Za-z0-9-]", "-", str(project_dir.resolve()))
    return Path.home() / ".claude" / "projects" / slug / f"{session.removesuffix('.jsonl')}.jsonl"


def _text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(x.get("text", "") for x in content if isinstance(x, dict) and x.get("type") == "text")
    return ""


def digest(path: Path, *, clip: int = 300, top: int = 5) -> str:
    said: list[str] = []
    errors: list[str] = []
    uses: Counter[str] = Counter()
    names: dict[str, str] = {}
    sizes: list[tuple[int, str]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg = entry.get("message") or {}
        content = msg.get("content")
        if entry.get("type") == "assistant" and isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "tool_use":
                    uses[part.get("name", "?")] += 1
                    names[part.get("id", "")] = part.get("name", "?")
        if entry.get("type") != "user":
            continue
        if not entry.get("isMeta"):
            text = _text(content).strip()
            # Harness-injected wrappers are not the user speaking.
            if text and not text.startswith(("<command-", "<local-command", "<system-reminder", "<task-notification")):
                said.append(text[:clip])
        for part in content if isinstance(content, list) else []:
            if not (isinstance(part, dict) and part.get("type") == "tool_result"):
                continue
            body = _text(part.get("content")) if not isinstance(part.get("content"), str) else part["content"]
            tool = names.get(part.get("tool_use_id", ""), "?")
            sizes.append((len(body), tool))
            if part.get("is_error"):
                errors.append(f"{tool}: {' '.join(body.split())[:clip]}")

    out = [f"# Transcript digest: {path.name}", "", f"## User messages ({len(said)})", ""]
    out += [f"{i}. {s}" for i, s in enumerate(said, 1)] or ["(none)"]
    out += ["", f"## Tool errors ({len(errors)})", ""] + ([f"- {e}" for e in errors] or ["(none)"])
    out += ["", "## Tool calls", ""] + [f"- {n}: {c}" for n, c in uses.most_common()]
    out += ["", f"## Largest tool results (top {top})", ""]
    out += [f"- {tool}: {n:,} chars" for n, tool in sorted(sizes, reverse=True)[:top]]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("session", help="session id or transcript path")
    ap.add_argument("--project-dir", type=Path, default=Path.cwd())
    args = ap.parse_args(argv)
    path = resolve(args.session, args.project_dir)
    if not path.is_file():
        print(f"error: no transcript at {path}", file=sys.stderr)
        return 1
    sys.stdout.write(digest(path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
