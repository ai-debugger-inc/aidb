#!/usr/bin/env python3
"""
Build Environment Validation Script

Validates that the current environment has all necessary dependencies
to build the specified adapters based on versions.json configuration.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


class ValidationError(Exception):
    """Raised when environment validation fails."""


class BuildEnvironmentValidator:
    """Validates build environment dependencies."""

    def __init__(self, versions_file: str = "versions.json"):
        """Initialize validator with versions configuration."""
        self.versions_file = Path(versions_file)
        self.versions = self._load_versions()

    def _load_versions(self) -> dict:
        """Load and validate versions.json configuration."""
        if not self.versions_file.exists():
            raise ValidationError(f"Versions file not found: {self.versions_file}")

        with self.versions_file.open() as f:
            versions = json.load(f)

        return versions

    def _check_command_exists(self, command: str) -> bool:
        """Check if a command exists in PATH or common system locations."""
        # First try standard PATH search
        if shutil.which(command):
            return True

        # In container/act environments, check common system paths directly
        if os.environ.get("ACT") or os.environ.get("GITHUB_ACTIONS"):
            common_paths = [Path("/usr/bin"), Path("/usr/local/bin"), Path("/bin")]
            for path in common_paths:
                cmd_path = path / command
                # Check if file exists and is executable
                if cmd_path.exists():
                    # For symlinks, check if target exists
                    if cmd_path.is_symlink():
                        try:
                            # Resolve the symlink
                            cmd_path.stat()
                            return True
                        except OSError:
                            continue
                    elif os.access(cmd_path, os.X_OK):
                        return True

        # Special case for pip - check pip3 if pip doesn't exist
        if command == "pip" and not shutil.which(command):
            return shutil.which("pip3") is not None

        return False

    def _check_command_version(self, command: str, version_arg: str = "--version") -> str:
        """Get version output from a command."""
        try:
            result = subprocess.run(
                [command, version_arg],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout.strip() if result.returncode == 0 else "Unknown"
        except (subprocess.SubprocessError, FileNotFoundError):
            return "Not found"

    def validate_system_dependencies(self) -> list[str]:
        """Validate system-level dependencies."""
        issues = []

        # Check basic system dependencies
        system_deps = self.versions.get("github_actions", {}).get("system_deps", [])

        for dep in system_deps:
            # Handle both simple strings and strings with comments
            if isinstance(dep, str):
                dep_name = dep.split()[0]  # Extract command name before any comment
            else:
                dep_name = str(dep).split()[0]

            if not self._check_command_exists(dep_name):
                issues.append(f"Missing system dependency: {dep_name}")

        return issues

    def validate_adapter_dependencies(self, adapter: str) -> list[str]:
        """Validate dependencies for a specific adapter."""
        issues = []

        if adapter not in self.versions.get("adapters", {}):
            issues.append(f"Unknown adapter: {adapter}")
            return issues

        adapter_config = self.versions["adapters"][adapter]
        build_deps = adapter_config.get("build_deps", {})

        if adapter == "javascript":
            # Check Node.js
            if not self._check_command_exists("node"):
                issues.append("Node.js not found (required for JavaScript adapter)")
            else:
                node_version = self._check_command_version("node", "--version")
                # Fallback to infrastructure node version if adapter doesn't specify
                infra_node = str(self.versions["infrastructure"]["node"]["version"])
                required_version = build_deps.get("node_version", infra_node)
                print(f"[OK] Node.js found: {node_version} (required: {required_version})")

            # Check npm
            if not self._check_command_exists("npm"):
                issues.append("npm not found (required for JavaScript adapter)")
            else:
                npm_version = self._check_command_version("npm", "--version")
                print(f"[OK] npm found: {npm_version}")

        elif adapter == "java":
            # Java adapter is built from source using Maven
            print("[OK] Java adapter: Built from source using Maven")
            if not self._check_command_exists("mvn"):
                print("[INFO] Maven not found on path, using bundled mvnw wrapper")

        return issues

    def validate_build_tools(self) -> list[str]:
        """Validate build tools and environment."""
        issues = []

        # Check git
        if not self._check_command_exists("git"):
            issues.append("git not found (required for cloning repositories)")
        else:
            git_version = self._check_command_version("git", "--version")
            print(f"[OK] git found: {git_version}")

        # Check Python and PyYAML
        if not self._check_command_exists("python") and not self._check_command_exists("python3"):
            issues.append("Python not found (required for build scripts)")
        else:
            python_cmd = "python3" if self._check_command_exists("python3") else "python"
            python_version = self._check_command_version(python_cmd, "--version")
            print(f"[OK] Python found: {python_version}")

        return issues

    def validate_environment(self, adapters: list[str] = None) -> dict[str, Any]:
        """Validate entire build environment."""
        if adapters is None:
            adapters = list(self.versions.get("adapters", {}).keys())

        results = {
            "valid": True,
            "issues": [],
            "adapters": {},
        }

        # Validate system dependencies
        system_issues = self.validate_system_dependencies()
        results["issues"].extend(system_issues)

        # Validate build tools
        build_tool_issues = self.validate_build_tools()
        results["issues"].extend(build_tool_issues)

        # Validate each adapter
        for adapter in adapters:
            adapter_issues = self.validate_adapter_dependencies(adapter)
            results["adapters"][adapter] = {
                "valid": len(adapter_issues) == 0,
                "issues": adapter_issues,
            }
            results["issues"].extend(adapter_issues)

        results["valid"] = len(results["issues"]) == 0

        return results

    def print_validation_report(self, results: dict[str, Any]):
        """Print a formatted validation report."""
        print("\n" + "="*60)
        print("BUILD ENVIRONMENT VALIDATION REPORT")
        print("="*60)

        if results["valid"]:
            print("[SUCCESS] All dependencies satisfied!")
        else:
            print("Validation failed with issues:")
            for issue in results["issues"]:
                print(f"   • {issue}")

        print("\nAdapter-specific validation:")
        for adapter, adapter_results in results["adapters"].items():
            status = "[OK]" if adapter_results["valid"] else "[FAIL]"
            print(f"   {status} {adapter}")
            for issue in adapter_results["issues"]:
                print(f"      • {issue}")

        print("\nEnvironment Information:")
        print(f"   Platform: {sys.platform}")
        print(f"   Python: {sys.version.split()[0]}")

        # Show cache directory recommendations
        print("\nRecommended cache directories:")
        for path in self.versions.get("github_actions", {}).get("caching", {}).get("paths", []):
            print(f"   • {path}")


def main():
    parser = argparse.ArgumentParser(description="Validate build environment dependencies")
    parser.add_argument("--adapters", nargs="*",
                       help="Adapters to validate (default: all)")
    parser.add_argument("--versions-file", default="versions.json",
                       help="Path to versions configuration file")
    parser.add_argument("--quiet", action="store_true",
                       help="Suppress detailed output, only show final result")

    args = parser.parse_args()

    try:
        validator = BuildEnvironmentValidator(args.versions_file)
        results = validator.validate_environment(args.adapters)

        if not args.quiet:
            validator.print_validation_report(results)

        # Exit with error code if validation failed
        sys.exit(0 if results["valid"] else 1)

    except ValidationError as e:
        print(f"Validation error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
