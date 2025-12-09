"""Service for validating version consistency across the codebase."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from aidb_cli.core.paths import ProjectPaths
from aidb_cli.managers.base.service import BaseService
from aidb_common.config import VersionManager


@dataclass
class VersionMismatch:
    """Represents a version mismatch between versions.json and a file."""

    file: str
    line: int
    variable: str
    expected: str
    found: str
    severity: Literal["error", "warning"] = "error"

    @property
    def message(self) -> str:
        """Generate human-readable message."""
        if self.severity == "warning":
            return f"{self.variable}: hardcoded as {self.found} (should use ARG)"
        return f"{self.variable}: expected {self.expected}, found {self.found}"


@dataclass
class ConsistencyReport:
    """Report of version consistency check results."""

    mismatches: list[VersionMismatch] = field(default_factory=list)
    files_checked: list[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        """Check if there are any error-level mismatches."""
        return any(m.severity == "error" for m in self.mismatches)

    @property
    def has_warnings(self) -> bool:
        """Check if there are any warning-level mismatches."""
        return any(m.severity == "warning" for m in self.mismatches)

    @property
    def error_count(self) -> int:
        """Count error-level mismatches."""
        return sum(1 for m in self.mismatches if m.severity == "error")

    @property
    def warning_count(self) -> int:
        """Count warning-level mismatches."""
        return sum(1 for m in self.mismatches if m.severity == "warning")


class VersionConsistencyService(BaseService):
    """Validates version consistency across codebase.

    Checks that version defaults in Docker files match versions.json.
    """

    # Files to check relative to repo root (using ProjectPaths constants)
    _DOCKERFILES_DIR = ProjectPaths.TEST_DOCKER_DIR / "dockerfiles"
    DOCKER_COMPOSE_FILE = ProjectPaths.TEST_DOCKER_BASE_COMPOSE
    DOCKERFILE_BASE = _DOCKERFILES_DIR / "Dockerfile.test.base"
    DOCKERFILE_JS = _DOCKERFILES_DIR / "Dockerfile.test.javascript"
    DOCKERFILE_JAVA = _DOCKERFILES_DIR / "Dockerfile.test.java"

    # Mapping from docker-compose variable names to VersionManager keys
    COMPOSE_VAR_MAPPING = {
        "PYTHON_VERSION": "PYTHON_VERSION",
        "PYTHON_BASE_TAG": "PYTHON_BASE_TAG",
        "NODE_VERSION": "NODE_VERSION",
        "JAVA_VERSION": "JAVA_VERSION",
        "DEBUGPY_VERSION": "DEBUGPY_VERSION",
        "JDTLS_VERSION": "JDTLS_VERSION",
        "PIP_VERSION": "PIP_VERSION",
        "SETUPTOOLS_VERSION": "SETUPTOOLS_VERSION",
        "WHEEL_VERSION": "WHEEL_VERSION",
        "TYPESCRIPT_VERSION": "TYPESCRIPT_VERSION",
        "TS_NODE_VERSION": "TS_NODE_VERSION",
    }

    def __init__(self, repo_root: Path, command_executor=None) -> None:
        """Initialize the service.

        Parameters
        ----------
        repo_root : Path
            Repository root directory
        command_executor : CommandExecutor, optional
            Command executor (not used but required by BaseService)
        """
        super().__init__(repo_root, command_executor)
        self._version_manager = VersionManager()

    def _initialize_service(self) -> None:
        """Initialize service resources."""

    def check_all(self) -> ConsistencyReport:
        """Run all consistency checks.

        Returns
        -------
        ConsistencyReport
            Report containing all mismatches found
        """
        report = ConsistencyReport()
        expected = self._version_manager.get_docker_build_args()

        # Check docker-compose defaults
        compose_mismatches = self._check_docker_compose(expected)
        report.mismatches.extend(compose_mismatches)

        # Check Dockerfile ARG defaults
        dockerfile_mismatches = self._check_dockerfiles(expected)
        report.mismatches.extend(dockerfile_mismatches)

        # Record files checked
        report.files_checked = [
            self.DOCKER_COMPOSE_FILE,
            self.DOCKERFILE_BASE,
            self.DOCKERFILE_JS,
            self.DOCKERFILE_JAVA,
        ]

        return report

    def _check_docker_compose(
        self,
        expected: dict[str, str],
    ) -> list[VersionMismatch]:
        """Check docker-compose.base.yaml defaults.

        Parameters
        ----------
        expected : dict[str, str]
            Expected versions from VersionManager

        Returns
        -------
        list[VersionMismatch]
            List of mismatches found
        """
        mismatches: list[VersionMismatch] = []
        compose_path = self.repo_root / self.DOCKER_COMPOSE_FILE

        if not compose_path.exists():
            return mismatches

        content = compose_path.read_text()
        lines = content.split("\n")

        # Pattern: VAR_NAME: ${VAR_NAME:-default}
        pattern = re.compile(r"^\s*(\w+):\s*\$\{\1:-([^}]+)\}")

        for line_num, line in enumerate(lines, start=1):
            match = pattern.match(line)
            if match:
                var_name = match.group(1)
                found_value = match.group(2)

                if var_name in self.COMPOSE_VAR_MAPPING:
                    expected_key = self.COMPOSE_VAR_MAPPING[var_name]
                    expected_value = expected.get(expected_key, "")

                    if str(found_value) != str(expected_value):
                        mismatches.append(
                            VersionMismatch(
                                file=self.DOCKER_COMPOSE_FILE,
                                line=line_num,
                                variable=var_name,
                                expected=str(expected_value),
                                found=str(found_value),
                            ),
                        )

        return mismatches

    def _check_dockerfiles(
        self,
        expected: dict[str, str],
    ) -> list[VersionMismatch]:
        """Check Dockerfile ARG defaults.

        Parameters
        ----------
        expected : dict[str, str]
            Expected versions from VersionManager

        Returns
        -------
        list[VersionMismatch]
            List of mismatches found
        """
        mismatches: list[VersionMismatch] = []

        # Check each Dockerfile with its expected variables
        dockerfile_checks = [
            (
                self.DOCKERFILE_BASE,
                [
                    "PYTHON_BASE_TAG",
                    "PIP_VERSION",
                    "SETUPTOOLS_VERSION",
                    "WHEEL_VERSION",
                ],
            ),
            (
                self.DOCKERFILE_JS,
                ["NODE_VERSION", "TYPESCRIPT_VERSION", "TS_NODE_VERSION"],
            ),
            (
                self.DOCKERFILE_JAVA,
                ["JAVA_VERSION", "JDTLS_VERSION"],
            ),
        ]

        for dockerfile, variables in dockerfile_checks:
            path = self.repo_root / dockerfile
            if not path.exists():
                continue

            content = path.read_text()
            lines = content.split("\n")

            # Pattern: ARG VAR_NAME=default
            arg_pattern = re.compile(r"^\s*ARG\s+(\w+)=(.+)$")

            for line_num, line in enumerate(lines, start=1):
                match = arg_pattern.match(line)
                if match:
                    var_name = match.group(1)
                    found_value = match.group(2).strip()

                    if var_name in variables:
                        expected_value = expected.get(var_name, "")

                        if str(found_value) != str(expected_value):
                            mismatches.append(
                                VersionMismatch(
                                    file=dockerfile,
                                    line=line_num,
                                    variable=var_name,
                                    expected=str(expected_value),
                                    found=str(found_value),
                                ),
                            )

        # Special check for hardcoded Java version in Dockerfile.test.java
        mismatches.extend(self._check_java_hardcoded_version(expected))

        return mismatches

    def _check_java_hardcoded_version(
        self,
        expected: dict[str, str],
    ) -> list[VersionMismatch]:
        """Check for hardcoded Java version in Dockerfile.test.java.

        Parameters
        ----------
        expected : dict[str, str]
            Expected versions from VersionManager

        Returns
        -------
        list[VersionMismatch]
            List of warnings for hardcoded versions
        """
        mismatches: list[VersionMismatch] = []
        java_path = self.repo_root / self.DOCKERFILE_JAVA

        if not java_path.exists():
            return mismatches

        content = java_path.read_text()
        lines = content.split("\n")

        # Pattern: openjdk-XX-jdk-headless (hardcoded version)
        pattern = re.compile(r"openjdk-(\d+)-jdk")
        expected_java = expected.get("JAVA_VERSION", "21")

        for line_num, line in enumerate(lines, start=1):
            match = pattern.search(line)
            if match:
                found_version = match.group(1)
                # This is a warning - the version should be parameterized via ARG
                mismatches.append(
                    VersionMismatch(
                        file=self.DOCKERFILE_JAVA,
                        line=line_num,
                        variable="JAVA_VERSION",
                        expected=str(expected_java),
                        found=str(found_version),
                        severity="warning",
                    ),
                )

        return mismatches

    def cleanup(self) -> None:
        """Cleanup service resources."""
