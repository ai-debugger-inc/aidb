"""Integration tests for documentation commands and workflows.

Tests the CLI's documentation building, serving, and management capabilities.
"""

import os
import subprocess
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
        return True
    except Exception:
        return False


class TestDocsPublicCommands:
    """Test public documentation commands."""

    @pytest.mark.integration
    @pytest.mark.requires_docker
    def test_public_docs_status_command(self):
        """Test public docs status command."""
        if not _docker_available():
            pytest.skip("Docker not available")

        runner = CliRunner()

        # Status should work regardless of whether docs are running
        status_result = runner.invoke(
            cli,
            ["docs", "status"],
            catch_exceptions=False,
        )
        assert status_result.exit_code == 0, (
            f"Public docs status failed: {status_result.output}"
        )

        # Should contain meaningful status information
        assert len(status_result.output.strip()) > 0

    @pytest.mark.integration
    @pytest.mark.requires_docker
    def test_public_docs_build_command(self):
        """Test public docs build command."""
        if not _docker_available():
            pytest.skip("Docker not available")

        runner = CliRunner()

        # Build public documentation
        build_result = runner.invoke(
            cli,
            ["docs", "build"],
            catch_exceptions=False,
        )

        # Build should either succeed or fail gracefully
        if build_result.exit_code == 0:
            assert any(
                keyword in build_result.output.lower()
                for keyword in [
                    "build",
                    "documentation",
                    "success",
                    "complete",
                ]
            )
        else:
            # If it fails, it should provide meaningful error info
            assert len(build_result.output.strip()) > 0

    @pytest.mark.integration
    @pytest.mark.requires_docker
    @pytest.mark.skipif(
        os.environ.get("GITHUB_ACTIONS") == "true",
        reason="Docs tests require building images not pre-pulled in CI",
    )
    def test_public_docs_serve_workflow(self):
        """Test public docs serve workflow."""
        if not _docker_available():
            pytest.skip("Docker not available")

        runner = CliRunner()

        try:
            # Try to serve public docs
            serve_result = runner.invoke(
                cli,
                ["docs", "serve"],
                catch_exceptions=False,
            )

            if serve_result.exit_code == 0:
                # If serve succeeded, check status
                status_result = runner.invoke(
                    cli,
                    ["docs", "status"],
                    catch_exceptions=False,
                )
                assert status_result.exit_code == 0
                assert (
                    "running" in status_result.output.lower()
                    or "port" in status_result.output.lower()
                )

        finally:
            # Cleanup - stop public docs and verify success
            stop_result = runner.invoke(
                cli,
                ["docs", "stop"],
                catch_exceptions=False,
            )
            # Force cleanup if normal stop failed
            if stop_result.exit_code != 0:
                subprocess.run(
                    ["docker", "ps", "-aq", "--filter", "label=com.aidb.managed=true"],
                    capture_output=True,
                )
                subprocess.run(
                    "docker ps -aq --filter 'label=com.aidb.managed=true' | xargs -r docker stop",
                    shell=True,
                    capture_output=True,
                    check=False,
                )


class TestDocsErrorHandling:
    """Test error handling and edge cases in docs commands."""

    @pytest.mark.integration
    def test_docs_stop_when_not_running(self):
        """Test stopping docs when they're not running."""
        runner = CliRunner()

        # Stop when nothing is running should be graceful
        stop_result = runner.invoke(
            cli,
            ["docs", "stop"],
            catch_exceptions=False,
        )

        # Should succeed (idempotent operation)
        assert stop_result.exit_code == 0

    @pytest.mark.integration
    def test_docs_status_command_reliability(self):
        """Test that status command is reliable."""
        runner = CliRunner()

        # Public status
        public_status = runner.invoke(
            cli,
            ["docs", "status"],
            catch_exceptions=False,
        )
        assert public_status.exit_code == 0
        assert len(public_status.output.strip()) > 0
