#!/usr/bin/env python3
"""
Regression Test Validator for /fix-bug skill.

Validates that a regression test was added before the bug fix is considered complete.
Runs on Stop hook (--final flag) to check session for test file writes.

Usage in skill frontmatter:
    hooks:
      Stop:
        - hooks:
            - type: command
              command: "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/validators/skills/fix_bug_regression.py --final"
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from base import BaseValidator, ValidationResult


# Test file patterns that indicate a test was written
TEST_FILE_PATTERNS = [
    r"test_.*\.py$",
    r".*_test\.py$",
    r".*\.test\.[tj]sx?$",
    r".*\.spec\.[tj]sx?$",
    r".*Tests?\.java$",
    r".*_test\.go$",
    r".*_test\.rs$",
]


class FixBugRegressionValidator(BaseValidator):
    """Validates that /fix-bug skill includes a regression test."""

    @property
    def prefix(self) -> str:
        return "FIXBUG"

    def validate(self) -> ValidationResult:
        # Only enforce on Stop (final validation)
        if not self.is_final:
            return ValidationResult.ok()

        # Check skill context if available
        skill_context = self.input_data.get("skill_context", {})
        skill_name = skill_context.get("name", "")

        # Only validate for fix-bug skill
        if skill_name and skill_name != "fix-bug":
            return ValidationResult.ok()

        # Check session_writes for test files
        session_writes = self.input_data.get("session_writes", [])

        # Also check tool_uses if available
        tool_uses = self.input_data.get("tool_uses", [])
        for use in tool_uses:
            if use.get("tool_name") == "Write":
                file_path = use.get("tool_input", {}).get("file_path", "")
                if file_path:
                    session_writes.append(file_path)

        # Check if any written file matches test patterns
        has_test = False
        for file_path in session_writes:
            filename = Path(file_path).name.lower()
            if any(re.search(p, filename) for p in TEST_FILE_PATTERNS):
                has_test = True
                break

        # Fallback: Check working directory for recently modified test files
        # This helps when session_writes isn't populated
        if not has_test and not session_writes:
            # We can't determine without more context, so warn instead of block
            return ValidationResult.warn(
                "Cannot verify regression test was added. "
                "Ensure a test reproducing the bug exists before completing."
            )

        if not has_test and session_writes:
            return ValidationResult.warn(
                "No regression test detected. "
                "Consider adding a test that reproduces the bug before completing the fix."
            )

        return ValidationResult.ok()


if __name__ == "__main__":
    sys.exit(FixBugRegressionValidator().run())
