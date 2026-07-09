#!/usr/bin/env python3
"""
TDD AAA Pattern Validator — bound to @quality-engineer in v3 (v2 bound it to @tdd-guide; folded into quality-engineer per inventory — TDD is part of test-strategy).

Validates that test files follow the Arrange-Act-Assert pattern:
- Tests have clear setup (Arrange)
- Tests perform an action (Act)
- Tests verify results (Assert)

Also checks for test isolation and naming conventions.

Usage in agent frontmatter:
    hooks:
      PostToolUse:
        - matcher: "Write"
          hooks:
            - type: command
              command: "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/validators/agents/tdd_aaa.py"
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
]

# Assertion patterns by language
ASSERTION_PATTERNS = {
    "python": [
        r"\bassert\s+",
        r"self\.assert",
        r"pytest\.raises",
        r"with\s+pytest\.raises",
    ],
    "javascript": [
        r"expect\s*\(",
        r"\.toBe\(",
        r"\.toEqual\(",
        r"\.toThrow\(",
        r"\.rejects\.",
        r"assert\.",
    ],
}

# Anti-patterns to warn about
ANTI_PATTERNS = [
    (r"time\.sleep\s*\(\s*\d+\s*\)", "Avoid time.sleep() in tests - makes tests slow and flaky"),
    (r"import\s+random(?!\s+as)", "Random values in tests may cause flakiness"),
    (r"datetime\.now\(\)", "datetime.now() in tests may cause flakiness - consider freezing time"),
]


class TddAaaValidator(BaseValidator):
    """Validates test files follow AAA pattern and TDD best practices."""

    @property
    def prefix(self) -> str:
        return "TDD"

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

        # Determine language
        ext = Path(file_path).suffix.lower()
        if ext == ".py":
            lang = "python"
        elif ext in [".js", ".jsx", ".ts", ".tsx"]:
            lang = "javascript"
        else:
            return ValidationResult.ok()

        warnings = []

        # Check for assertions
        assertion_patterns = ASSERTION_PATTERNS.get(lang, [])
        has_assertions = any(re.search(p, content) for p in assertion_patterns)

        if not has_assertions:
            return ValidationResult.warn(
                f"Test file '{filename}' missing assertions. "
                "Tests should verify outcomes (Assert phase of AAA)."
            )

        # Check for anti-patterns
        for pattern, message in ANTI_PATTERNS:
            if re.search(pattern, content):
                warnings.append(message)

        # Check test function naming (Python)
        if lang == "python":
            test_funcs = re.findall(r"def\s+(test_\w+)", content)
            for func in test_funcs:
                # Good names describe behavior: test_user_can_login, test_raises_on_invalid_input
                if func in ["test_1", "test_2", "test_it", "test_this", "test_test"]:
                    warnings.append(f"'{func}' - use descriptive test names that explain behavior")

        if warnings:
            return ValidationResult.warn(
                f"{filename}: {'; '.join(warnings[:2])}"
                + (f" (+{len(warnings) - 2} more)" if len(warnings) > 2 else "")
            )

        return ValidationResult.ok()


if __name__ == "__main__":
    sys.exit(TddAaaValidator().run())
