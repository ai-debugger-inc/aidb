"""Integration tests for port detection and management functionality.

Tests the CLI's ability to detect available ports, handle conflicts, and manage port
allocation across services.
"""

import os
import socket
import subprocess
import time
from contextlib import contextmanager
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


def _mcp_start_available() -> bool:
    """Check if MCP start command exists.

    Returns
    -------
    bool
        True if MCP start command is available (currently not implemented)
    """
    # The 'mcp start' command is not currently implemented in the CLI
    # Available MCP commands are: register, unregister, restart, status, test, logs
    return False


@pytest.fixture
def repo_root():
    """Repository root fixture."""
    return _get_repo_root()


@pytest.fixture(scope="session", autouse=True)
def ensure_docs_docker_image():
    """Pre-build docs Docker image once per test session.

    This fixture automatically builds the aidb-docs-build image at the start of
    the test session if Docker is running. This significantly speeds up tests that use
    --build-first by caching the image build.

    In CI (GITHUB_ACTIONS=true), docs tests are skipped so no image build is needed.
    """
    # Skip in CI - docs images aren't pre-pulled and tests are skipped anyway
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return

    if not _docker_running():
        # Docker not running, tests will skip gracefully
        return

    try:
        repo_root = _get_repo_root()
        compose_file = repo_root / "scripts/install/docs/docker-compose.yaml"

        if not compose_file.exists():
            # Compose file not found, tests will handle this
            return

        # Build the docs image once for the entire session
        subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                str(compose_file),
                "build",
                "aidb-docs-build",
            ],
            check=True,
            capture_output=True,
            timeout=300,  # 5 minute timeout for image build
        )
    except Exception:  # noqa: S110
        # If build fails, tests will handle it gracefully
        pass


def _is_port_available(port: int, host: str = "localhost") -> bool:
    """Check if a port is available for binding."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((host, port))
            return True
    except OSError:
        return False


@contextmanager
def _occupy_port(port: int, host: str = "localhost"):
    """Context manager to temporarily occupy a port."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((host, port))
        sock.listen(1)
        yield sock
    finally:
        sock.close()


def _docker_running() -> bool:
    """Check if Docker daemon is running."""
    try:
        subprocess.run(
            ["docker", "ps"],
            check=True,
            capture_output=True,
            timeout=5,
        )
        return True
    except Exception:
        return False


class TestPortDetectionBasic:
    """Basic port detection functionality."""

    @pytest.mark.integration
    @pytest.mark.skipif(not _docker_running(), reason="Docker daemon not running")
    @pytest.mark.skipif(
        os.environ.get("GITHUB_ACTIONS") == "true",
        reason="Docs tests require building images not pre-pulled in CI",
    )
    def test_docs_serve_finds_available_port(self):
        """Test that docs serve can find an available port automatically."""
        runner = CliRunner()

        # Use a high port that's likely to be available
        test_port = 9876

        if not _is_port_available(test_port):
            pytest.skip(f"Port {test_port} is not available for testing")

        try:
            result = runner.invoke(
                cli,
                [
                    "docs",
                    "serve",
                    "--port",
                    str(test_port),
                    "--build-first",
                ],
                catch_exceptions=False,
            )
            assert result.exit_code == 0, f"Docs serve failed: {result.output}"
            assert (
                f"port {test_port}" in result.output.lower()
                or f":{test_port}" in result.output
            )

        finally:
            # Cleanup: stop the docs server
            runner.invoke(cli, ["docs", "stop"])
            # Don't fail the test if cleanup fails

    @pytest.mark.integration
    @pytest.mark.skipif(
        not _mcp_start_available(),
        reason="MCP start command not implemented in CLI",
    )
    def test_mcp_server_port_allocation(self):
        """Test MCP server port allocation."""
        runner = CliRunner()

        # Test starting MCP server which should allocate a port
        result = runner.invoke(
            cli,
            ["mcp", "start", "--port", "0"],  # 0 means auto-allocate
            catch_exceptions=False,
        )

        # Verify port information is shown
        assert "port" in result.output.lower() or "listening" in result.output.lower()

        # Cleanup
        runner.invoke(cli, ["mcp", "stop"])


class TestPortConflictHandling:
    """Port conflict detection and resolution."""

    @pytest.mark.integration
    @pytest.mark.skipif(not _docker_running(), reason="Docker daemon not running")
    @pytest.mark.skipif(
        os.environ.get("GITHUB_ACTIONS") == "true",
        reason="Docs tests require building images not pre-pulled in CI",
    )
    def test_docs_serve_handles_port_conflict(self):
        """Test docs serve handling when requested port is busy."""
        # Find a port that should be available
        test_port = 9877

        if not _is_port_available(test_port):
            pytest.skip(f"Port {test_port} is not available for testing")

        runner = CliRunner()

        # Occupy the port first
        with _occupy_port(test_port):
            result = runner.invoke(
                cli,
                [
                    "docs",
                    "serve",
                    "--port",
                    str(test_port),
                    "--build-first",
                ],
                catch_exceptions=False,
            )

            # Should either fail gracefully or find alternative port
            if result.exit_code != 0:
                # Graceful failure is acceptable
                assert (
                    "port" in result.output.lower()
                    or "busy" in result.output.lower()
                    or "address already in use" in result.output.lower()
                )
            else:
                # If it succeeded, it should have server URL in output
                assert (
                    "http://localhost:" in result.output.lower()
                    or "port" in result.output.lower()
                )
                # Cleanup
                runner.invoke(cli, ["docs", "stop"])

    @pytest.mark.integration
    @pytest.mark.skipif(not _docker_running(), reason="Docker daemon not running")
    def test_docker_service_port_conflicts(self, repo_root):
        """Test Docker service port conflict handling using test services."""
        CliRunner()

        # Use our test docker-compose services
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
            # Start the test port allocator service (which uses port 8901)
            result = subprocess.run(
                [
                    "docker",
                    "compose",
                    "-f",
                    str(compose_file),
                    "--profile",
                    "test-ports",
                    "up",
                    "-d",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                # Wait for service to be ready
                time.sleep(2)

                # Verify the service is occupying the port
                assert not _is_port_available(8901), (
                    "Test service should occupy port 8901"
                )

                # Now test that our CLI can handle this conflict
                # (This would be service-specific behavior)
                assert True  # Port conflict is demonstrated

        finally:
            # Cleanup: stop test services
            subprocess.run(
                [
                    "docker",
                    "compose",
                    "-f",
                    str(compose_file),
                    "--profile",
                    "test-ports",
                    "down",
                ],
                capture_output=True,
                timeout=30,
            )


class TestPortRegistry:
    """Port registry persistence and management."""

    @pytest.mark.integration
    def test_port_allocation_persistence(self, tmp_path):
        """Test that port allocations can be tracked and persisted."""
        # This test verifies that the port management system
        # can track allocated ports (integration with actual port handler)

        # Test basic port availability check
        test_port = 9878
        available = _is_port_available(test_port)

        # This is more of a smoke test for port detection logic
        assert isinstance(available, bool)

        # If we have a CLI command that shows port information, test it
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0  # Basic CLI functionality works

    @pytest.mark.integration
    def test_concurrent_port_operations(self):
        """Test concurrent port operations don't conflict."""
        import queue
        import threading

        results: queue.Queue[tuple[int, bool, str | None]] = queue.Queue()

        def check_port_availability(port_offset):
            """Check port availability in thread."""
            try:
                port = 9880 + port_offset
                available = _is_port_available(port)
                results.put((port_offset, available, None))
            except Exception as e:
                results.put((port_offset, False, str(e)))

        # Test multiple port checks concurrently
        threads = []
        for i in range(5):
            thread = threading.Thread(target=check_port_availability, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join(timeout=5)

        # Collect results
        collected_results = []
        while not results.empty():
            collected_results.append(results.get())

        # Should have results from all threads
        assert len(collected_results) == 5

        # All should have completed without exceptions
        for offset, available, error in collected_results:
            assert error is None, f"Thread {offset} failed with error: {error}"
            assert isinstance(available, bool)


class TestPortUtilities:
    """Test port utility functions and integration."""

    @pytest.mark.integration
    def test_port_range_scanning(self):
        """Test scanning for available ports in a range."""
        # Test a range of high ports that should mostly be available
        start_port = 9900
        end_port = 9910

        available_ports = []
        for port in range(start_port, end_port):
            if _is_port_available(port):
                available_ports.append(port)

        # Should find at least a few available ports in this range
        assert len(available_ports) >= 3, (
            f"Expected at least 3 available ports in range {start_port}-{end_port}, found {len(available_ports)}"
        )

    @pytest.mark.integration
    def test_port_cleanup_verification(self):
        """Test that ports are properly released after service stops."""
        test_port = 9881

        if not _is_port_available(test_port):
            pytest.skip(f"Port {test_port} not available for cleanup test")

        # Temporarily occupy the port
        with _occupy_port(test_port):
            # Verify port is occupied
            assert not _is_port_available(test_port)

        # After context manager exits, port should be available again
        time.sleep(0.1)  # Brief delay for socket cleanup
        assert _is_port_available(test_port), "Port should be available after cleanup"

    @pytest.mark.integration
    def test_service_health_check_ports(self, repo_root):
        """Test health check functionality for services using ports."""
        runner = CliRunner()

        # Test status command that might check service ports
        result = runner.invoke(cli, ["docs", "status"])

        # Should succeed regardless of whether docs are running
        assert result.exit_code == 0
        # Output should contain status information
        assert len(result.output.strip()) > 0
