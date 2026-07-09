#!/usr/bin/env python3
"""
CI Diagnosis Format Validator for /diagnose-ci skill.

Enforces the diagnosis-only contract:
- No git push, git commit, or gh pr edit ran during the skill session.
- Output contains a "Proposed fix" block (advisory plan).

Runs on Stop hook to validate the session before exit.

Usage in skill frontmatter:
    hooks:
      Stop:
        - hooks:
            - type: command
              command: "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/validators/skills/diagnose_ci_format.py --final"
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from base import BaseValidator, ValidationResult


FORBIDDEN_COMMAND_PATTERNS = [
    (r"\bgit\s+push\b", "git push detected — diagnose-ci is diagnosis-only"),
    (r"\bgit\s+commit\b", "git commit detected — diagnose-ci is diagnosis-only"),
    (r"\bgh\s+pr\s+edit\b", "gh pr edit detected — diagnose-ci is diagnosis-only"),
    (r"\bgh\s+run\s+rerun\b", "gh run rerun detected — diagnose-ci must not re-burn CI minutes"),
]

PROPOSED_FIX_MARKERS = [
    r"###\s*diagnosis",
    r"#### proposed fix",
    r"\*\*proposed fix",
    r"proposed fix plan",
]


class DiagnoseCiFormatValidator(BaseValidator):
    """Validates /diagnose-ci skill output and enforces diagnosis-only contract."""

    @property
    def prefix(self) -> str:
        return "DIAGNOSE-CI"

    def validate(self) -> ValidationResult:
        tool_uses = self.input_data.get("tool_uses", [])

        violations = []
        for use in tool_uses:
            if use.get("tool_name") != "Bash":
                continue
            command = use.get("tool_input", {}).get("command", "")
            for pattern, message in FORBIDDEN_COMMAND_PATTERNS:
                if re.search(pattern, command, re.IGNORECASE):
                    violations.append(f"{message}: `{command[:80]}`")

        if violations:
            return ValidationResult.warn(
                "diagnose-ci violated diagnosis-only contract: "
                + "; ".join(violations)
            )

        if self.is_final:
            transcript = self.input_data.get("transcript", "") or self.get_content() or ""
            transcript_lower = transcript.lower()
            if not any(re.search(m, transcript_lower) for m in PROPOSED_FIX_MARKERS):
                return ValidationResult.warn(
                    "No proposed-fix block detected in diagnose-ci output. "
                    "Skill should emit a '### Diagnosis' / 'Proposed fix' block."
                )

        return ValidationResult.ok()


if __name__ == "__main__":
    sys.exit(DiagnoseCiFormatValidator().run())
