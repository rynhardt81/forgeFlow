#!/usr/bin/env python3
"""
PR Description Format Validator for /create-pr skill.

Validates the PR body is non-empty and — when the repo has a review bot
configured via `git config forge.reviewBot` — that the bot mention is present.
Repos without the config get no bot-mention nag (public installs have no
Codex). Section-header requirements were dropped intentionally — the create-pr
skill's Small template is a single sentence with no headers, and forcing
`## Summary` and `## Test Plan` on every PR conflicts with the skill's
Concision rules.

Runs on Stop hook to validate before PR creation.

Usage in skill frontmatter:
    hooks:
      Stop:
        - hooks:
            - type: command
              command: "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/validators/skills/create_pr_format.py --final"
"""

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from base import BaseValidator, ValidationResult


MIN_BODY_CHARS = 20


def configured_review_bot() -> str:
    """Return the repo's review-bot line from git config, or '' if unset."""
    try:
        out = subprocess.run(
            ["git", "config", "forge.reviewBot"],
            capture_output=True, text=True, timeout=3,
        )
        return out.stdout.strip() if out.returncode == 0 else ""
    except (subprocess.TimeoutExpired, OSError):
        return ""


class CreatePrFormatValidator(BaseValidator):
    """Validates PR description format."""

    @property
    def prefix(self) -> str:
        return "PR"

    def validate(self) -> ValidationResult:
        # This validator checks PR body content
        # It can run on Stop (--final) or on Write to a PR template file

        # Check for PR body in input
        pr_body = self.input_data.get("pr_body", "")

        # Also check if writing a PR description file
        if not pr_body and self.is_write_operation():
            file_path = self.get_file_path()
            filename = Path(file_path).name.lower()
            # Check if this looks like a PR template or description
            if any(p in filename for p in ["pr_body", "pr_description", "pull_request"]):
                pr_body = self.get_content()

        # If no PR body found and this is final check, try to extract from context
        if not pr_body and self.is_final:
            # Check tool_uses for gh pr create commands
            tool_uses = self.input_data.get("tool_uses", [])
            for use in tool_uses:
                if use.get("tool_name") == "Bash":
                    command = use.get("tool_input", {}).get("command", "")
                    if "gh pr create" in command:
                        # Extract body from command
                        body_match = re.search(r'--body\s+["\'](.+?)["\']', command, re.DOTALL)
                        if body_match:
                            pr_body = body_match.group(1)
                            break

        review_bot = configured_review_bot()

        if not pr_body:
            if self.is_final:
                msg = "Could not verify PR body. Ensure it has at least a one-sentence description"
                if review_bot:
                    msg += f" and the review-bot line ({review_bot})"
                return ValidationResult.warn(msg + ".")
            return ValidationResult.ok()

        warnings = []

        if len(pr_body.strip()) < MIN_BODY_CHARS:
            warnings.append(
                f"PR body is shorter than {MIN_BODY_CHARS} chars — add at least one sentence describing the change."
            )

        if review_bot:
            # Match on the bot's @handle (first @-token in the configured line)
            handle = re.search(r"@[\w-]+", review_bot)
            pattern = re.escape(handle.group(0)) if handle else re.escape(review_bot)
            if not re.search(pattern, pr_body, re.IGNORECASE):
                warnings.append(
                    f"PR body is missing the configured review-bot mention — append `{review_bot}` (from git config forge.reviewBot)."
                )

        if warnings:
            return ValidationResult.warn(" ".join(warnings))

        return ValidationResult.ok()


if __name__ == "__main__":
    sys.exit(CreatePrFormatValidator().run())
