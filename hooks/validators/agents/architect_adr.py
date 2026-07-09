#!/usr/bin/env python3
"""
ADR Format Validator for @architect agent.

Validates that Architecture Decision Records have required sections:
- Context: What is the issue?
- Decision: What is the change?
- Consequences: What are the trade-offs?
- Status: Proposed | Accepted | Deprecated | Superseded

Usage in agent frontmatter:
    hooks:
      PostToolUse:
        - matcher: "Write"
          hooks:
            - type: command
              command: "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/validators/agents/architect_adr.py"
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from base import BaseValidator, ValidationResult


# Required sections in an ADR (case-insensitive)
REQUIRED_SECTIONS = [
    ("context", r"##\s*context", "Missing '## Context' section - explain the issue"),
    ("decision", r"##\s*decision", "Missing '## Decision' section - state the change"),
    ("consequences", r"##\s*consequences", "Missing '## Consequences' section - list trade-offs"),
]

# Status field validation
STATUS_PATTERN = r'\*\*status\*\*\s*:\s*(proposed|accepted|deprecated|superseded)'
VALID_STATUSES = ["proposed", "accepted", "deprecated", "superseded"]


class ArchitectAdrValidator(BaseValidator):
    """Validates ADR files have required sections."""

    @property
    def prefix(self) -> str:
        return "ADR"

    def validate(self) -> ValidationResult:
        # Only validate Write operations
        if not self.is_write_operation():
            return ValidationResult.ok()

        file_path = self.get_file_path()
        content = self.get_content()

        if not content:
            return ValidationResult.ok()

        # Only validate ADR files
        file_lower = file_path.lower()
        is_adr_file = (
            "adr" in file_lower or
            "architecture-decision" in file_lower or
            (("architecture" in file_lower or "decisions" in file_lower) and
             file_lower.endswith(".md"))
        )

        if not is_adr_file:
            return ValidationResult.ok()

        # Check for required sections
        content_lower = content.lower()
        missing = []

        for name, pattern, message in REQUIRED_SECTIONS:
            if not re.search(pattern, content_lower):
                missing.append(message)

        # Check for status field
        status_match = re.search(STATUS_PATTERN, content_lower)
        if not status_match:
            # Check alternative status formats
            alt_status = re.search(r'status\s*:\s*(proposed|accepted|deprecated|superseded)', content_lower)
            if not alt_status:
                missing.append(f"Missing Status field (valid: {', '.join(VALID_STATUSES)})")

        if missing:
            return ValidationResult.warn(
                f"ADR incomplete: {'; '.join(missing[:2])}"
                + (f" (+{len(missing) - 2} more)" if len(missing) > 2 else "")
            )

        return ValidationResult.ok()


if __name__ == "__main__":
    sys.exit(ArchitectAdrValidator().run())
