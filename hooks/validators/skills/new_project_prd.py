#!/usr/bin/env python3
"""
PRD Completeness Validator for /new-project skill.

Validates that Product Requirements Documents have essential sections:
- Vision: What problem are we solving?
- Goals: What are we trying to achieve?
- User Stories: Who are the users and what do they need?
- Success Criteria: How do we know we succeeded?

Usage in skill frontmatter:
    hooks:
      PostToolUse:
        - matcher: "Write"
          hooks:
            - type: command
              command: "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/validators/skills/new_project_prd.py"
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from base import BaseValidator, ValidationResult


# Required sections in PRD (with alternative names)
REQUIRED_SECTIONS = [
    ("vision", [r"##\s*vision", r"##\s*problem\s*statement", r"##\s*overview", r"##\s*introduction"],
     "Missing Vision/Overview section - explain the problem being solved"),
    ("goals", [r"##\s*goals", r"##\s*objectives", r"##\s*requirements"],
     "Missing Goals/Objectives section - list what we're trying to achieve"),
    ("users", [r"##\s*user\s*stories", r"##\s*users", r"##\s*personas", r"##\s*target\s*audience"],
     "Missing User Stories section - define who the users are"),
    ("success", [r"##\s*success\s*criteria", r"##\s*acceptance\s*criteria", r"##\s*definition\s*of\s*done", r"##\s*metrics"],
     "Missing Success Criteria - define how we measure success"),
]


class NewProjectPrdValidator(BaseValidator):
    """Validates PRD documents have required sections."""

    @property
    def prefix(self) -> str:
        return "PRD"

    def validate(self) -> ValidationResult:
        # Only validate Write operations
        if not self.is_write_operation():
            return ValidationResult.ok()

        file_path = self.get_file_path()
        content = self.get_content()

        if not content:
            return ValidationResult.ok()

        # Only validate PRD files
        file_lower = file_path.lower()
        filename = Path(file_path).name.lower()

        is_prd = (
            "prd" in filename or
            "product-requirements" in filename or
            "product_requirements" in filename or
            (("requirements" in filename or "spec" in filename) and
             filename.endswith(".md") and
             "docs/" in file_lower)
        )

        if not is_prd:
            return ValidationResult.ok()

        # Check for required sections
        content_lower = content.lower()
        missing = []

        for name, patterns, message in REQUIRED_SECTIONS:
            found = False
            for pattern in patterns:
                if re.search(pattern, content_lower):
                    found = True
                    break
            if not found:
                missing.append(message)

        if missing:
            # Allow partial PRDs during drafting, but warn
            if len(missing) >= 3:
                return ValidationResult.warn(
                    f"PRD incomplete: {'; '.join(missing[:2])}"
                    + (f" (+{len(missing) - 2} more)" if len(missing) > 2 else "")
                )
            else:
                return ValidationResult.warn(
                    f"PRD may be incomplete: {'; '.join(missing)}"
                )

        # Check for minimal content
        if len(content) < 500:
            return ValidationResult.warn(
                "PRD appears too brief. Consider adding more detail to each section."
            )

        return ValidationResult.ok()


if __name__ == "__main__":
    sys.exit(NewProjectPrdValidator().run())
