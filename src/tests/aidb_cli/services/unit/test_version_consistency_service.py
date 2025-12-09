"""Unit tests for VersionConsistencyService.

Tests for version consistency checking across Docker files.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from aidb_cli.services.version.version_consistency_service import (
    ConsistencyReport,
    VersionConsistencyService,
    VersionMismatch,
)


class TestVersionMismatch:
    """Test the VersionMismatch dataclass."""

    def test_error_message(self):
        """Test error severity message format."""
        mismatch = VersionMismatch(
            file="test.yaml",
            line=10,
            variable="PYTHON_VERSION",
            expected="3.12",
            found="3.11",
            severity="error",
        )
        assert mismatch.message == "PYTHON_VERSION: expected 3.12, found 3.11"

    def test_warning_message(self):
        """Test warning severity message format."""
        mismatch = VersionMismatch(
            file="Dockerfile",
            line=18,
            variable="JAVA_VERSION",
            expected="21",
            found="21",
            severity="warning",
        )
        assert mismatch.message == "JAVA_VERSION: hardcoded as 21 (should use ARG)"


class TestConsistencyReport:
    """Test the ConsistencyReport dataclass."""

    def test_empty_report(self):
        """Test empty report has no errors or warnings."""
        report = ConsistencyReport()
        assert not report.has_errors
        assert not report.has_warnings
        assert report.error_count == 0
        assert report.warning_count == 0

    def test_report_with_errors(self):
        """Test report correctly identifies errors."""
        report = ConsistencyReport(
            mismatches=[
                VersionMismatch(
                    file="test.yaml",
                    line=1,
                    variable="VAR1",
                    expected="1.0",
                    found="2.0",
                    severity="error",
                ),
                VersionMismatch(
                    file="test.yaml",
                    line=2,
                    variable="VAR2",
                    expected="3.0",
                    found="4.0",
                    severity="error",
                ),
            ],
        )
        assert report.has_errors
        assert not report.has_warnings
        assert report.error_count == 2
        assert report.warning_count == 0

    def test_report_with_warnings(self):
        """Test report correctly identifies warnings."""
        report = ConsistencyReport(
            mismatches=[
                VersionMismatch(
                    file="Dockerfile",
                    line=18,
                    variable="JAVA_VERSION",
                    expected="21",
                    found="21",
                    severity="warning",
                ),
            ],
        )
        assert not report.has_errors
        assert report.has_warnings
        assert report.error_count == 0
        assert report.warning_count == 1

    def test_report_with_mixed(self):
        """Test report with both errors and warnings."""
        report = ConsistencyReport(
            mismatches=[
                VersionMismatch(
                    file="compose.yaml",
                    line=1,
                    variable="NODE_VERSION",
                    expected="22",
                    found="20",
                    severity="error",
                ),
                VersionMismatch(
                    file="Dockerfile",
                    line=18,
                    variable="JAVA_VERSION",
                    expected="21",
                    found="21",
                    severity="warning",
                ),
            ],
        )
        assert report.has_errors
        assert report.has_warnings
        assert report.error_count == 1
        assert report.warning_count == 1


class TestVersionConsistencyService:
    """Test the VersionConsistencyService."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create a VersionConsistencyService instance."""
        return VersionConsistencyService(repo_root=tmp_path)

    @pytest.fixture
    def mock_versions(self):
        """Mock version values from VersionManager."""
        return {
            "PYTHON_VERSION": "3.12",
            "PYTHON_BASE_TAG": "3.12-slim-bookworm",
            "NODE_VERSION": "22",
            "JAVA_VERSION": "21",
            "DEBUGPY_VERSION": "1.8.14",
            "JDTLS_VERSION": "1.55.0-202511271007",
            "PIP_VERSION": "25.0.1",
            "SETUPTOOLS_VERSION": "80.9.0",
            "WHEEL_VERSION": "0.45.1",
            "TYPESCRIPT_VERSION": "5.8.3",
            "TS_NODE_VERSION": "10.9.2",
        }


class TestCheckDockerCompose:
    """Test docker-compose.base.yaml checking."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create a VersionConsistencyService instance."""
        return VersionConsistencyService(repo_root=tmp_path)

    def test_no_mismatches_when_versions_match(self, tmp_path, service):
        """Test no mismatches when docker-compose defaults match expected."""
        compose_dir = tmp_path / "src/tests/_docker"
        compose_dir.mkdir(parents=True)
        compose_file = compose_dir / "docker-compose.base.yaml"
        compose_file.write_text("""
x-common-build-args: &common-build-args
  PYTHON_VERSION: ${PYTHON_VERSION:-3.12}
  NODE_VERSION: ${NODE_VERSION:-22}
  JAVA_VERSION: ${JAVA_VERSION:-21}
""")

        expected = {
            "PYTHON_VERSION": "3.12",
            "NODE_VERSION": "22",
            "JAVA_VERSION": "21",
        }

        mismatches = service._check_docker_compose(expected)
        assert len(mismatches) == 0

    def test_detects_version_mismatch(self, tmp_path, service):
        """Test detection of version mismatch in docker-compose."""
        compose_dir = tmp_path / "src/tests/_docker"
        compose_dir.mkdir(parents=True)
        compose_file = compose_dir / "docker-compose.base.yaml"
        compose_file.write_text("""
x-common-build-args: &common-build-args
  PYTHON_VERSION: ${PYTHON_VERSION:-3.11}
  NODE_VERSION: ${NODE_VERSION:-22}
""")

        expected = {
            "PYTHON_VERSION": "3.12",
            "NODE_VERSION": "22",
        }

        mismatches = service._check_docker_compose(expected)
        assert len(mismatches) == 1
        assert mismatches[0].variable == "PYTHON_VERSION"
        assert mismatches[0].expected == "3.12"
        assert mismatches[0].found == "3.11"
        assert mismatches[0].severity == "error"

    def test_returns_empty_when_file_missing(self, service):
        """Test returns empty list when compose file doesn't exist."""
        expected = {"PYTHON_VERSION": "3.12"}
        mismatches = service._check_docker_compose(expected)
        assert len(mismatches) == 0


class TestCheckDockerfiles:
    """Test Dockerfile ARG checking."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create a VersionConsistencyService instance."""
        return VersionConsistencyService(repo_root=tmp_path)

    def test_no_mismatches_when_args_match(self, tmp_path, service):
        """Test no mismatches when Dockerfile ARGs match expected."""
        dockerfile_dir = tmp_path / "src/tests/_docker/dockerfiles"
        dockerfile_dir.mkdir(parents=True)

        # Create base Dockerfile
        base_file = dockerfile_dir / "Dockerfile.test.base"
        base_file.write_text("""
FROM python:3.12-slim
ARG PYTHON_BASE_TAG=3.12-slim-bookworm
ARG PIP_VERSION=25.0.1
ARG SETUPTOOLS_VERSION=80.9.0
ARG WHEEL_VERSION=0.45.1
""")

        expected = {
            "PYTHON_BASE_TAG": "3.12-slim-bookworm",
            "PIP_VERSION": "25.0.1",
            "SETUPTOOLS_VERSION": "80.9.0",
            "WHEEL_VERSION": "0.45.1",
        }

        mismatches = service._check_dockerfiles(expected)
        assert len(mismatches) == 0

    def test_detects_arg_mismatch(self, tmp_path, service):
        """Test detection of ARG mismatch in Dockerfile."""
        dockerfile_dir = tmp_path / "src/tests/_docker/dockerfiles"
        dockerfile_dir.mkdir(parents=True)

        js_file = dockerfile_dir / "Dockerfile.test.javascript"
        js_file.write_text("""
FROM node:20
ARG NODE_VERSION=20
ARG TYPESCRIPT_VERSION=5.7.0
ARG TS_NODE_VERSION=10.9.2
""")

        expected = {
            "NODE_VERSION": "22",
            "TYPESCRIPT_VERSION": "5.8.3",
            "TS_NODE_VERSION": "10.9.2",
        }

        mismatches = service._check_dockerfiles(expected)
        assert len(mismatches) == 2

        # Check NODE_VERSION mismatch
        node_mismatch = next(m for m in mismatches if m.variable == "NODE_VERSION")
        assert node_mismatch.expected == "22"
        assert node_mismatch.found == "20"

        # Check TYPESCRIPT_VERSION mismatch
        ts_mismatch = next(m for m in mismatches if m.variable == "TYPESCRIPT_VERSION")
        assert ts_mismatch.expected == "5.8.3"
        assert ts_mismatch.found == "5.7.0"


class TestCheckJavaHardcodedVersion:
    """Test detection of hardcoded Java version."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create a VersionConsistencyService instance."""
        return VersionConsistencyService(repo_root=tmp_path)

    def test_detects_hardcoded_java_version(self, tmp_path, service):
        """Test detection of hardcoded openjdk version."""
        dockerfile_dir = tmp_path / "src/tests/_docker/dockerfiles"
        dockerfile_dir.mkdir(parents=True)

        java_file = dockerfile_dir / "Dockerfile.test.java"
        java_file.write_text("""
FROM base-image
RUN apt-get install -y openjdk-21-jdk-headless maven
""")

        expected = {"JAVA_VERSION": "21"}

        mismatches = service._check_java_hardcoded_version(expected)
        assert len(mismatches) == 1
        assert mismatches[0].variable == "JAVA_VERSION"
        assert mismatches[0].severity == "warning"
        assert mismatches[0].found == "21"

    def test_no_warning_when_parameterized(self, tmp_path, service):
        """Test no warning when Java version uses ARG substitution."""
        dockerfile_dir = tmp_path / "src/tests/_docker/dockerfiles"
        dockerfile_dir.mkdir(parents=True)

        java_file = dockerfile_dir / "Dockerfile.test.java"
        java_file.write_text("""
FROM base-image
ARG JAVA_VERSION=21
RUN apt-get install -y openjdk-${JAVA_VERSION}-jdk-headless maven
""")

        expected = {"JAVA_VERSION": "21"}

        mismatches = service._check_java_hardcoded_version(expected)
        # No hardcoded pattern found
        assert len(mismatches) == 0


class TestCheckAll:
    """Test the check_all method."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create a VersionConsistencyService instance."""
        return VersionConsistencyService(repo_root=tmp_path)

    def test_aggregates_all_checks(self, tmp_path, service):
        """Test check_all aggregates results from all check methods."""
        # Create Docker file structure
        compose_dir = tmp_path / "src/tests/_docker"
        compose_dir.mkdir(parents=True)
        dockerfile_dir = tmp_path / "src/tests/_docker/dockerfiles"
        dockerfile_dir.mkdir(parents=True)

        # Create compose with mismatch
        compose_file = compose_dir / "docker-compose.base.yaml"
        compose_file.write_text("""
  PYTHON_VERSION: ${PYTHON_VERSION:-3.11}
""")

        # Create base Dockerfile (matching)
        base_file = dockerfile_dir / "Dockerfile.test.base"
        base_file.write_text("""
ARG PYTHON_BASE_TAG=3.12-slim-bookworm
""")

        # Create JS Dockerfile (matching)
        js_file = dockerfile_dir / "Dockerfile.test.javascript"
        js_file.write_text("""
ARG NODE_VERSION=22
""")

        # Create Java Dockerfile with hardcoded version (warning)
        java_file = dockerfile_dir / "Dockerfile.test.java"
        java_file.write_text("""
ARG JAVA_VERSION=21
RUN apt-get install openjdk-21-jdk-headless
""")

        with patch.object(
            service._version_manager,
            "get_docker_build_args",
            return_value={
                "PYTHON_VERSION": "3.12",
                "PYTHON_BASE_TAG": "3.12-slim-bookworm",
                "NODE_VERSION": "22",
                "JAVA_VERSION": "21",
            },
        ):
            report = service.check_all()

        # Should have 1 error (PYTHON_VERSION) and 1 warning (hardcoded Java)
        assert report.error_count == 1
        assert report.warning_count == 1
        assert len(report.files_checked) == 4
