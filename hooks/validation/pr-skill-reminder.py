#!/usr/bin/env python3
"""
pr-skill-reminder.py
PreToolUse Bash hook — informational reminder to route PR operations
through the /create-pr skill instead of bare `gh pr ...` invocations.

Why this exists:
  /create-pr provides Step 3.7 pr-review-toolkit specialist pre-flight,
  mandatory @codex review mention, size-aware PR descriptions, and
  post-create review/merge-order tracking. Bare `gh pr create` (or
  `gh pr merge` without the review loop) skips all of those — and on
  paid GitHub plans, skipped pre-flight burns Actions minutes the
  skill would have saved.

Behaviour:
  - Fires on Bash commands containing `gh pr {create|merge|ready|checks}`.
  - Self-suppresses when the /create-pr skill is the caller, detected
    by the `--body-file` flag (the skill always uses --body-file in
    Step 5; ad-hoc users typically use --body or HEREDOC).
  - Emits a one-line reminder to stderr; never blocks.
  - Exits 0 always (per hooks/README.md philosophy: hooks are purely
    informational, never return exit 2).

  Also self-skips `gh pr review` and `gh pr edit`/`view` because:
    - The skill itself calls `gh pr review --json` in its Step 6 review
      loop, so reminding there is noise.
    - `gh pr edit`/`view` are read-only or low-level surgery; the skill
      isn't the right wrapper for those.

Hook protocol:
  Stdin: JSON envelope from Claude Code with tool_name + tool_input.
  Stdout: ignored (would become context — we don't want extra context).
  Stderr: one-line reminder shown to user, when applicable.
  Exit:  always 0.
"""

from __future__ import annotations

import json
import sys


REMINDERS: dict[str, str] = {
    "create": (
        "PR-SKILL: consider /create-pr instead of bare `gh pr create` — "
        "adds Step 3.7 pr-review-toolkit specialist pre-flight + mandatory "
        "@codex review + size-aware description. Saves GitHub Actions minutes "
        "vs blind retries on review-class failures."
    ),
    "merge": (
        "PR-SKILL: pre-merge — run `/create-pr review <PR#>` first to verify "
        "codex feedback is addressed and Step 3.7 MUST-FIX findings are "
        "resolved before merging."
    ),
    "ready": (
        "PR-SKILL: draft→ready — /create-pr ensures Step 3.7 specialist "
        "pre-flight runs before reviewers see the PR. Run it if you skipped "
        "pre-flight on the original draft."
    ),
    "checks": (
        "PR-SKILL: `/create-pr review <PR#>` aggregates CI status + codex "
        "feedback + Step 3.7 findings into a single verdict — one command "
        "instead of three."
    ),
}


def read_stdin_input() -> dict:
    if sys.stdin.isatty():
        return {}
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return {}
        return json.loads(raw)
    except (json.JSONDecodeError, OSError):
        return {}


def detect_pr_subcommand(command: str) -> str | None:
    """Return the matched gh-pr subcommand, or None when no reminder applies."""
    if "gh pr create" in command:
        # /create-pr Step 5 always uses --body-file. Ad-hoc users typically
        # use --body or HEREDOC. Suppress when --body-file is present so the
        # skill's own invocation doesn't echo this reminder.
        if "--body-file" in command:
            return None
        return "create"
    if "gh pr merge" in command:
        return "merge"
    if "gh pr ready" in command:
        return "ready"
    if "gh pr checks" in command:
        return "checks"
    return None


def main() -> int:
    data = read_stdin_input()
    if data.get("tool_name") != "Bash":
        return 0
    command = (data.get("tool_input") or {}).get("command", "")
    if not command:
        return 0

    subcmd = detect_pr_subcommand(command)
    if subcmd is None:
        return 0

    reminder = REMINDERS.get(subcmd)
    if reminder:
        sys.stderr.write(reminder + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
