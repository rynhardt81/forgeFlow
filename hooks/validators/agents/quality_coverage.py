#!/usr/bin/env python3
"""
Test Coverage Validator for @quality-engineer agent.

Validates that test files follow naming conventions and basic structure:
- Test file naming: test_*.py, *_test.py, *.test.ts, *.spec.ts
- Contains at least one test function/method
- Uses appropriate test framework patterns

Usage in agent frontmatter:
    hooks:
      PostToolUse:
        - matcher: "Write"
          hooks:
            - type: command
              command: "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/validators/agents/quality_coverage.py"
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from base import BaseValidator, ValidationResult


# Test file patterns
TEST_FILE_PATTERNS = [
    r"test_.*\.py$",
    r".*_test\.py$",
    r".*\.test\.[tj]sx?$",
    r".*\.spec\.[tj]sx?$",
    r".*Tests?\.java$",
    r".*_test\.go$",
    r".*_test\.rs$",
]

# Patterns indicating test content exists
TEST_CONTENT_PATTERNS = {
    "python": [
        r"def\s+test_",
        r"class\s+Test",
        r"@pytest\.mark",
        r"unittest\.TestCase",
        r"assert\s+",
    ],
    "javascript": [
        r"\b(describe|it|test)\s*\(",
        r"expect\s*\(",
        r"@Test",
        r"\.toBe\(",
        r"\.toEqual\(",
    ],
    "java": [
        r"@Test",
        r"@ParameterizedTest",
        r"assert(Equals|True|False|NotNull)",
    ],
    "go": [
        r"func\s+Test",
        r"t\.Run\(",
        r"t\.(Error|Fatal|Log)",
    ],
    "rust": [
        r"#\[test\]",
        r"#\[cfg\(test\)\]",
        r"assert!",
    ],
}


class QualityCoverageValidator(BaseValidator):
    """Validates test files follow conventions and contain tests."""

    @property
    def prefix(self) -> str:
        return "QUALITY"

    def validate(self) -> ValidationResult:
        # Only validate Write operations
        if not self.is_write_operation():
            return ValidationResult.ok()

        file_path = self.get_file_path()
        content = self.get_content()

        if not content:
            return ValidationResult.ok()

        # Check if this is a test file
        filename = Path(file_path).name.lower()
        is_test_file = any(re.search(p, filename) for p in TEST_FILE_PATTERNS)

        if not is_test_file:
            return ValidationResult.ok()

        # Determine file type
        ext = Path(file_path).suffix.lower()
        lang = None
        if ext == ".py":
            lang = "python"
        elif ext in [".js", ".jsx", ".ts", ".tsx"]:
            lang = "javascript"
        elif ext == ".java":
            lang = "java"
        elif ext == ".go":
            lang = "go"
        elif ext == ".rs":
            lang = "rust"

        if not lang:
            return ValidationResult.ok()

        # Check for test content
        patterns = TEST_CONTENT_PATTERNS.get(lang, [])
        has_test_content = any(re.search(p, content) for p in patterns)

        if not has_test_content:
            return ValidationResult.warn(
                f"Test file '{filename}' may be missing test functions. "
                "Ensure it contains actual test cases."
            )

        # Additional check: Empty test file
        lines = [l.strip() for l in content.split("\n") if l.strip() and not l.strip().startswith("#")]
        if len(lines) < 5:
            return ValidationResult.warn(
                f"Test file '{filename}' appears incomplete (very few lines). "
                "Add meaningful test cases."
            )

        return ValidationResult.ok()


if __name__ == "__main__":
    sys.exit(QualityCoverageValidator().run())
