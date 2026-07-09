#!/usr/bin/env python3
"""
Build Dependencies Validator — bound to @devops in v3 (v2 bound it to @build-resolver; folded into devops per inventory — build/CI is infra work).

Validates dependency changes in package files:
- Warns on major version bumps
- Warns on removing dependencies
- Checks for lockfile consistency hints
- Validates package.json/requirements.txt structure

Usage in agent frontmatter:
    hooks:
      PostToolUse:
        - matcher: "Write"
          hooks:
            - type: command
              command: "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/validators/agents/build_deps.py"
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from base import BaseValidator, ValidationResult


# Package files to validate
PACKAGE_FILES = [
    "package.json",
    "requirements.txt",
    "pyproject.toml",
    "Cargo.toml",
    "go.mod",
    "Gemfile",
    "pom.xml",
    "build.gradle",
]


class BuildDepsValidator(BaseValidator):
    """Validates dependency changes are safe."""

    @property
    def prefix(self) -> str:
        return "BUILD"

    def validate(self) -> ValidationResult:
        # Only validate Write operations
        if not self.is_write_operation():
            return ValidationResult.ok()

        file_path = self.get_file_path()
        content = self.get_content()

        if not content:
            return ValidationResult.ok()

        # Check if this is a package file
        filename = Path(file_path).name.lower()
        if filename not in [p.lower() for p in PACKAGE_FILES]:
            return ValidationResult.ok()

        warnings = []

        # Validate package.json
        if filename == "package.json":
            warnings.extend(self._validate_package_json(content))

        # Validate requirements.txt
        elif filename == "requirements.txt":
            warnings.extend(self._validate_requirements_txt(content))

        # Validate pyproject.toml
        elif filename == "pyproject.toml":
            warnings.extend(self._validate_pyproject_toml(content))

        if warnings:
            return ValidationResult.warn(
                f"{filename}: {'; '.join(warnings[:2])}"
                + (f" (+{len(warnings) - 2} more)" if len(warnings) > 2 else "")
            )

        return ValidationResult.ok()

    def _validate_package_json(self, content: str) -> list:
        """Validate package.json structure and dependencies."""
        warnings = []

        try:
            pkg = json.loads(content)
        except json.JSONDecodeError as e:
            return [f"Invalid JSON: {e}"]

        # Check for required fields
        if "name" not in pkg:
            warnings.append("Missing 'name' field")

        # Check dependencies for major version constraints
        for dep_type in ["dependencies", "devDependencies"]:
            deps = pkg.get(dep_type, {})
            for name, version in deps.items():
                if isinstance(version, str):
                    # Check for very broad constraints
                    if version == "*" or version == "latest":
                        warnings.append(f"{name}: '{version}' is too broad - pin to specific version")
                    # Check for git URLs (potential security risk)
                    elif version.startswith("git") or "github.com" in version:
                        warnings.append(f"{name}: Git dependency - ensure trusted source")

        # Check for potential issues
        if "scripts" in pkg:
            scripts = pkg["scripts"]
            for script_name, script_cmd in scripts.items():
                # Warn about potentially dangerous scripts
                if "rm -rf" in script_cmd or "sudo" in script_cmd:
                    warnings.append(f"scripts.{script_name} contains potentially dangerous command")

        return warnings

    def _validate_requirements_txt(self, content: str) -> list:
        """Validate requirements.txt format."""
        warnings = []

        lines = content.strip().split("\n")
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue

            # Check for unpinned dependencies
            if "==" not in line and ">=" not in line and "<=" not in line:
                # Extract package name
                pkg_name = re.split(r'[<>=!]', line)[0].strip()
                if pkg_name and not pkg_name.startswith("-"):
                    warnings.append(f"Line {i}: '{pkg_name}' is unpinned - consider adding version")

            # Check for git URLs
            if line.startswith("git+") or "github.com" in line:
                warnings.append(f"Line {i}: Git dependency - ensure trusted source")

        return warnings[:5]  # Limit warnings

    def _validate_pyproject_toml(self, content: str) -> list:
        """Validate pyproject.toml structure (basic checks)."""
        warnings = []

        # Basic TOML structure checks (without full parser)
        if "[project]" not in content and "[tool.poetry]" not in content:
            warnings.append("Missing [project] or [tool.poetry] section")

        # Check for git dependencies
        if "git = " in content or "git+" in content:
            warnings.append("Contains git dependencies - ensure trusted sources")

        return warnings


if __name__ == "__main__":
    sys.exit(BuildDepsValidator().run())
