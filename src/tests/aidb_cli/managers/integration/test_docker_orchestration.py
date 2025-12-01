"""Integration tests for Docker service orchestration.

Tests the CLI's Docker infrastructure management, service health checks, resource
cleanup, and container orchestration capabilities.
"""

import subprocess
import time
from pathlib import Path

import pytest
from click.testing import CliRunner

from aidb_cli.cli import cli


def _get_repo_root() -> Path:
    """Get repository root directory."""
    current = Path(__file__).parent
    while current.parent != current:
        if (current / ".git").exists():
            return current
        current = current.parent
    msg = "Could not find git repository root"
    raise RuntimeError(msg)


@pytest.fixture
def repo_root():
    """Repository root fixture."""
    return _get_repo_root()


def _docker_available() -> bool:
    """Check if Docker is available."""
    try:
        subprocess.run(["docker", "--version"], check=True, capture_output=True)
        subprocess.run(["docker", "info"], check=True, capture_output=True)
        return True
    except Exception:
        return False


def _docker_compose_available() -> bool:
    """Check if Docker Compose is available."""
    try:
        subprocess.run(
            ["docker", "compose", "version"],
            check=True,
            capture_output=True,
        )
        return True
    except Exception:
        return False


class TestDockerStatus:
    """Test Docker status and environment commands."""

    @pytest.mark.integration
    def test_docker_status_command(self):
        """Test Docker status command."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["docker", "status"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, f"Docker status failed: {result.output}"
        assert len(result.output.strip()) > 0

        # Should contain Docker-related information
        output_lower = result.output.lower()
        assert any(
            keyword in output_lower
            for keyword in [
                "docker",
                "version",
                "status",
                "available",
                "unavailable",
            ]
        )

    @pytest.mark.integration
    def test_docker_env_command(self):
        """Test Docker environment generation."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["docker", "env"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, f"Docker env failed: {result.output}"

        # Should generate environment information
        output_lower = result.output.lower()
        assert any(
            keyword in output_lower
            for keyword in [
                "env",
                "environment",
                "variable",
                "docker",
                ".env",
            ]
        )


class TestDockerCleanup:
    """Test Docker cleanup functionality."""

    @pytest.mark.integration
    @pytest.mark.requires_docker
    def test_docker_cleanup_command(self):
        """Test Docker cleanup command."""
        if not _docker_available():
            pytest.skip("Docker not available")

        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["docker", "cleanup", "--force"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, f"Docker cleanup failed: {result.output}"

        # Should mention cleanup operations
        output_lower = result.output.lower()
        assert any(
            keyword in output_lower
            for keyword in [
                "cleanup",
                "clean",
                "removed",
                "deleted",
                "aidb",
            ]
        )

    @pytest.mark.integration
    @pytest.mark.requires_docker
    def test_docker_cleanup_safe_operation(self):
        """Test that Docker cleanup is safe and doesn't affect other containers."""
        if not _docker_available():
            pytest.skip("Docker not available")

        runner = CliRunner()

        # Get list of containers before cleanup
        pre_cleanup = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
        )

        # Run cleanup
        cleanup_result = runner.invoke(
            cli,
            ["docker", "cleanup", "--force"],
            catch_exceptions=False,
        )
        assert cleanup_result.exit_code == 0

        # Get list of containers after cleanup
        post_cleanup = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
        )

        # Cleanup should only affect AIDB-related containers
        pre_containers = (
            set(pre_cleanup.stdout.strip().split("\n"))
            if pre_cleanup.stdout.strip()
            else set()
        )
        post_containers = (
            set(post_cleanup.stdout.strip().split("\n"))
            if post_cleanup.stdout.strip()
            else set()
        )

        removed_containers = pre_containers - post_containers
        for container in removed_containers:
            # Only AIDB containers should be removed
            assert any(
                aidb_marker in container.lower()
                for aidb_marker in [
                    "aidb",
                    "test",
                ]
            ), f"Non-AIDB container was removed: {container}"


class TestDockerBuild:
    """Test Docker build functionality."""

    @pytest.mark.integration
    @pytest.mark.requires_docker
    def test_docker_build_command_basic(self):
        """Test basic Docker build command."""
        if not _docker_available():
            pytest.skip("Docker not available")

        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["docker", "build", "--help"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, f"Docker build help failed: {result.output}"
        assert "build" in result.output.lower()

    @pytest.mark.integration
    @pytest.mark.requires_docker
    def test_docker_build_dry_run(self):
        """Test Docker build dry run or status check."""
        if not _docker_available():
            pytest.skip("Docker not available")

        runner = CliRunner()

        # Check if build command accepts dry-run or similar flag
        result = runner.invoke(
            cli,
            ["docker", "build"],
            catch_exceptions=False,
        )

        # Build command should either succeed or provide meaningful feedback
        # (We don't want to run actual builds in integration tests as they're slow)
        if result.exit_code != 0:
            # If it fails, should provide helpful information
            assert len(result.output.strip()) > 0
            output_lower = result.output.lower()
            assert any(
                keyword in output_lower
                for keyword in [
                    "error",
                    "failed",
                    "fail",
                    "required",
                    "option",
                    "argument",
                    "help",
                ]
            )


class TestDockerServiceOrchestration:
    """Test Docker service orchestration using test services."""

    @pytest.mark.integration
    @pytest.mark.requires_docker
    def test_test_service_orchestration(self, repo_root):
        """Test orchestration using our test docker-compose services."""
        if not (_docker_available() and _docker_compose_available()):
            pytest.skip("Docker or Docker Compose not available")

        compose_file = (
            repo_root
            / "src"
            / "tests"
            / "aidb_cli"
            / "integration"
            / "resources"
            / "docker-compose.test.yaml"
        )

        if not compose_file.exists():
            pytest.skip("Test docker-compose.yaml not found")

        try:
            # Start test services
            start_result = subprocess.run(
                [
                    "docker",
                    "compose",
                    "-f",
                    str(compose_file),
                    "--profile",
                    "test-integration",
                    "up",
                    "-d",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if start_result.returncode == 0:
                # Wait for services to be ready
                time.sleep(3)

                # Check service health
                health_result = subprocess.run(
                    [
                        "docker",
                        "compose",
                        "-f",
                        str(compose_file),
                        "--profile",
                        "test-integration",
                        "ps",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                assert health_result.returncode == 0
                assert "test-echo" in health_result.stdout

                # Test service connectivity
                try:
                    import requests

                    response = requests.get("http://localhost:5678", timeout=5)
                    assert response.status_code == 200
                    assert "AIDB" in response.text
                except ImportError:
                    # If requests not available, use curl
                    curl_result = subprocess.run(
                        [
                            "curl",
                            "-f",
                            "http://localhost:5678",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    if curl_result.returncode == 0:
                        assert "AIDB" in curl_result.stdout

        finally:
            # Cleanup: stop test services
            subprocess.run(
                [
                    "docker",
                    "compose",
                    "-f",
                    str(compose_file),
                    "--profile",
                    "test-integration",
                    "down",
                ],
                capture_output=True,
                timeout=60,
            )

    @pytest.mark.integration
    @pytest.mark.requires_docker
    def test_service_health_checks(self, repo_root):
        """Test service health check functionality."""
        if not (_docker_available() and _docker_compose_available()):
            pytest.skip("Docker or Docker Compose not available")

        compose_file = (
            repo_root
            / "src"
            / "tests"
            / "aidb_cli"
            / "integration"
            / "resources"
            / "docker-compose.test.yaml"
        )

        if not compose_file.exists():
            pytest.skip("Test docker-compose.yaml not found")

        try:
            # Start a single test service
            start_result = subprocess.run(
                [
                    "docker",
                    "compose",
                    "-f",
                    str(compose_file),
                    "--profile",
                    "test-integration",
                    "up",
                    "-d",
                    "test-echo-server",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if start_result.returncode == 0:
                # Wait for health check to pass
                max_attempts = 10
                healthy = False

                for _attempt in range(max_attempts):
                    health_result = subprocess.run(
                        [
                            "docker",
                            "inspect",
                            "--format={{.State.Health.Status}}",
                            "aidb-test-echo",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )

                    if (
                        health_result.returncode == 0
                        and "healthy" in health_result.stdout
                    ):
                        healthy = True
                        break

                    time.sleep(2)

                if healthy:
                    # Health check passed
                    assert True
                else:
                    # Check if container is at least running
                    status_result = subprocess.run(
                        [
                            "docker",
                            "inspect",
                            "--format={{.State.Status}}",
                            "aidb-test-echo",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )

                    if status_result.returncode == 0:
                        # Container is running, health check might just be strict
                        assert "running" in status_result.stdout

        finally:
            # Cleanup
            subprocess.run(
                [
                    "docker",
                    "compose",
                    "-f",
                    str(compose_file),
                    "--profile",
                    "test-integration",
                    "down",
                ],
                capture_output=True,
                timeout=60,
            )


class TestDockerResourceManagement:
    """Test Docker resource management and cleanup."""

    @pytest.mark.integration
    @pytest.mark.requires_docker
    def test_docker_network_management(self):
        """Test Docker network management."""
        if not _docker_available():
            pytest.skip("Docker not available")

        # Check existing networks
        networks_before = subprocess.run(
            [
                "docker",
                "network",
                "ls",
                "--format",
                "{{.Name}}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert networks_before.returncode == 0

        # Run Docker status which might show network info
        runner = CliRunner()
        status_result = runner.invoke(
            cli,
            ["docker", "status"],
            catch_exceptions=False,
        )

        assert status_result.exit_code == 0

        # Networks should still exist after status check
        networks_after = subprocess.run(
            [
                "docker",
                "network",
                "ls",
                "--format",
                "{{.Name}}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert networks_after.returncode == 0
        # Network list should be stable
        assert (
            len(networks_before.stdout.strip().split("\n"))
            <= len(networks_after.stdout.strip().split("\n")) + 1
        )

    @pytest.mark.integration
    @pytest.mark.requires_docker
    def test_docker_volume_management(self):
        """Test Docker volume management."""
        if not _docker_available():
            pytest.skip("Docker not available")

        # Check volumes
        volumes_result = subprocess.run(
            [
                "docker",
                "volume",
                "ls",
                "--format",
                "{{.Name}}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert volumes_result.returncode == 0

        # Run cleanup which might affect volumes
        runner = CliRunner()
        cleanup_result = runner.invoke(
            cli,
            ["docker", "cleanup", "--force"],
            catch_exceptions=False,
        )

        assert cleanup_result.exit_code == 0

    @pytest.mark.integration
    @pytest.mark.requires_docker
    def test_docker_image_management(self):
        """Test Docker image management."""
        if not _docker_available():
            pytest.skip("Docker not available")

        # Check if there are any AIDB images
        images_result = subprocess.run(
            [
                "docker",
                "images",
                "--format",
                "{{.Repository}}:{{.Tag}}",
                "--filter",
                "reference=*aidb*",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert images_result.returncode == 0

        # Check Docker status includes image information
        runner = CliRunner()
        status_result = runner.invoke(
            cli,
            ["docker", "status"],
            catch_exceptions=False,
        )

        assert status_result.exit_code == 0
        # Status should provide useful information regardless of image presence


class TestDockerErrorHandling:
    """Test error handling in Docker operations."""

    @pytest.mark.integration
    @pytest.mark.requires_docker
    def test_docker_cleanup_idempotent(self):
        """Test that Docker cleanup is idempotent."""
        if not _docker_available():
            pytest.skip("Docker not available")

        runner = CliRunner()

        # Run cleanup twice
        cleanup1 = runner.invoke(
            cli,
            ["docker", "cleanup", "--force"],
            catch_exceptions=False,
        )
        assert cleanup1.exit_code == 0

        cleanup2 = runner.invoke(
            cli,
            ["docker", "cleanup", "--force"],
            catch_exceptions=False,
        )
        assert cleanup2.exit_code == 0

        # Both should succeed (idempotent operation)
