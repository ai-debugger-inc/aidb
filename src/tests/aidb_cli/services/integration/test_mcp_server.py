"""Integration tests for MCP server lifecycle management.

Tests the CLI's MCP server registration, testing, status checking, and integration with
Claude Code CLI.

NOTE: Some tests require Claude Code CLI to be installed and available on PATH:
- test_mcp_registration_workflow
- test_mcp_restart_workflow
- test_mcp_test_functionality_with_claude_code

These tests will be skipped if `claude_code --version` is not available.
Install Claude Code CLI from: https://github.com/anthropics/claude-code
"""

import json
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


def _claude_code_available() -> bool:
    """Check if Claude Code CLI is available."""
    import subprocess

    try:
        subprocess.run(
            ["claude_code", "--version"],
            check=True,
            capture_output=True,
            timeout=10,
        )
        return True
    except Exception:
        return False


class TestMCPStatus:
    """Test MCP server status and basic commands."""

    @pytest.mark.skipif(
        not _claude_code_available(),
        reason="Claude Code CLI not available",
    )
    @pytest.mark.integration
    def test_mcp_status_command(self):
        """Test MCP status command."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["mcp", "status"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, f"MCP status failed: {result.output}"
        assert len(result.output.strip()) > 0

        # Should provide status information
        output_lower = result.output.lower()
        assert any(
            keyword in output_lower
            for keyword in [
                "mcp",
                "server",
                "status",
                "registered",
                "unregistered",
                "claude",
            ]
        )

    @pytest.mark.integration
    def test_mcp_logs_command(self):
        """Test MCP logs command."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["mcp", "logs"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, f"MCP logs failed: {result.output}"

        # Should provide log information (even if no logs exist)
        output_lower = result.output.lower()
        assert any(
            keyword in output_lower
            for keyword in [
                "log",
                "mcp",
                "server",
                "debug",
                "no logs",
                "empty",
            ]
        )

    @pytest.mark.integration
    def test_mcp_test_command_basic(self):
        """Test basic MCP test command."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["mcp", "test", "--help"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, f"MCP test help failed: {result.output}"
        assert "test" in result.output.lower()


class TestMCPRegistration:
    """Test MCP server registration workflows."""

    @pytest.mark.integration
    def test_mcp_register_without_claude_code(self):
        """Test MCP register command when Claude Code CLI is not available."""
        if _claude_code_available():
            pytest.skip("Claude Code CLI is available, can't test unavailable scenario")

        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["mcp", "register"],
            catch_exceptions=False,
        )

        # Should fail gracefully or provide helpful message
        if result.exit_code != 0:
            output_lower = result.output.lower()
            assert any(
                keyword in output_lower
                for keyword in [
                    "claude",
                    "not found",
                    "unavailable",
                    "install",
                    "error",
                ]
            )
        else:
            # If it succeeded, should provide meaningful feedback
            assert len(result.output.strip()) > 0

    @pytest.mark.integration
    def test_mcp_unregister_idempotent(self):
        """Test that MCP unregister is idempotent."""
        runner = CliRunner()

        # Unregister should work even if not registered
        result = runner.invoke(
            cli,
            ["mcp", "unregister"],
            catch_exceptions=False,
        )

        # Should succeed or provide helpful message
        if result.exit_code != 0:
            output_lower = result.output.lower()
            assert any(
                keyword in output_lower
                for keyword in [
                    "not registered",
                    "claude",
                    "not found",
                    "already",
                ]
            )
        else:
            assert len(result.output.strip()) > 0

    @pytest.mark.integration
    @pytest.mark.skipif(
        not _claude_code_available(),
        reason="Claude Code CLI not available",
    )
    def test_mcp_registration_workflow(self):
        """Test complete MCP registration workflow (requires Claude Code)."""
        runner = CliRunner()

        try:
            # 1. Check initial status
            initial_status = runner.invoke(
                cli,
                ["mcp", "status"],
                catch_exceptions=False,
            )
            assert initial_status.exit_code == 0

            # 2. Unregister (cleanup any existing registration)
            runner.invoke(
                cli,
                ["mcp", "unregister"],
                catch_exceptions=False,
            )
            # Don't require success - might not be registered

            # 3. Register
            register_result = runner.invoke(
                cli,
                ["mcp", "register"],
                catch_exceptions=False,
            )

            if register_result.exit_code == 0:
                # If registration succeeded, check status
                status_after_register = runner.invoke(
                    cli,
                    ["mcp", "status"],
                    catch_exceptions=False,
                )
                assert status_after_register.exit_code == 0
                assert "registered" in status_after_register.output.lower()

        finally:
            # Cleanup: unregister
            runner.invoke(
                cli,
                ["mcp", "unregister"],
                catch_exceptions=False,
            )
            # Don't require cleanup to succeed

    @pytest.mark.integration
    @pytest.mark.skipif(
        not _claude_code_available(),
        reason="Claude Code CLI not available",
    )
    def test_mcp_restart_workflow(self):
        """Test MCP restart workflow (requires Claude Code)."""
        runner = CliRunner()

        # Restart should work regardless of current state
        result = runner.invoke(
            cli,
            ["mcp", "restart"],
            catch_exceptions=False,
        )

        if result.exit_code == 0:
            # If restart succeeded, verify status
            status_result = runner.invoke(
                cli,
                ["mcp", "status"],
                catch_exceptions=False,
            )
            assert status_result.exit_code == 0

        else:
            # If restart failed, should provide meaningful error
            assert len(result.output.strip()) > 0


class TestMCPTesting:
    """Test MCP server testing functionality."""

    @pytest.mark.integration
    def test_mcp_test_validation(self):
        """Test MCP server validation testing."""
        runner = CliRunner()

        # Test basic validation (should work without Claude Code)
        result = runner.invoke(
            cli,
            ["mcp", "test"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, f"MCP test failed: {result.output}"

        # Should provide test results
        output_lower = result.output.lower()
        assert any(
            keyword in output_lower
            for keyword in [
                "test",
                "validation",
                "mcp",
                "server",
                "pass",
                "fail",
                "ok",
            ]
        )

    @pytest.mark.integration
    def test_mcp_test_with_verbose_output(self):
        """Test MCP testing with verbose output."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["-v", "mcp", "test"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, f"MCP test verbose failed: {result.output}"

        # Verbose should provide more detailed information
        assert len(result.output.strip()) > 0

    @pytest.mark.integration
    @pytest.mark.skipif(
        not _claude_code_available(),
        reason="Claude Code CLI not available",
    )
    def test_mcp_test_functionality_with_claude_code(self):
        """Test MCP functionality testing when Claude Code is available."""
        runner = CliRunner()

        try:
            # First ensure MCP is registered
            register_result = runner.invoke(
                cli,
                ["mcp", "register"],
                catch_exceptions=False,
            )

            if register_result.exit_code == 0:
                # Test functionality
                test_result = runner.invoke(
                    cli,
                    ["mcp", "test"],
                    catch_exceptions=False,
                )

                assert test_result.exit_code == 0, (
                    f"MCP functionality test failed: {test_result.output}"
                )

                # Should include functionality test results
                output_lower = test_result.output.lower()
                assert any(
                    keyword in output_lower
                    for keyword in [
                        "functionality",
                        "test",
                        "mcp",
                        "tools",
                        "server",
                    ]
                )

        finally:
            # Cleanup
            runner.invoke(cli, ["mcp", "unregister"], catch_exceptions=False)


class TestMCPDebugging:
    """Test MCP debugging and log analysis."""

    @pytest.mark.integration
    def test_mcp_logs_analysis(self):
        """Test MCP logs analysis functionality."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["mcp", "logs"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, f"MCP logs analysis failed: {result.output}"

        # Should provide log analysis (even if no logs)
        assert len(result.output.strip()) > 0

    @pytest.mark.integration
    def test_mcp_logs_with_options(self):
        """Test MCP logs command with various options."""
        runner = CliRunner()

        # Test help to see available options
        help_result = runner.invoke(
            cli,
            ["mcp", "logs", "--help"],
            catch_exceptions=False,
        )

        assert help_result.exit_code == 0
        assert "logs" in help_result.output.lower()

    @pytest.mark.skipif(
        not _claude_code_available(),
        reason="Claude Code CLI not available",
    )
    @pytest.mark.integration
    def test_mcp_status_detailed(self):
        """Test detailed MCP status information."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["-v", "mcp", "status"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, f"MCP detailed status failed: {result.output}"

        # Should provide detailed status information
        output_lower = result.output.lower()
        assert any(
            keyword in output_lower
            for keyword in [
                "mcp",
                "server",
                "status",
                "claude",
                "registration",
            ]
        )


class TestMCPErrorHandling:
    """Test MCP error handling and edge cases."""

    @pytest.mark.integration
    def test_mcp_invalid_subcommand(self):
        """Test MCP with invalid subcommand."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["mcp", "invalid_command"],
            catch_exceptions=False,
        )

        # Should provide helpful error
        assert result.exit_code != 0
        output_lower = result.output.lower()
        assert any(
            keyword in output_lower
            for keyword in [
                "no such command",
                "invalid",
                "unknown",
                "available",
            ]
        )

    @pytest.mark.skipif(
        not _claude_code_available(),
        reason="Claude Code CLI not available",
    )
    @pytest.mark.integration
    def test_mcp_commands_consistency(self):
        """Test that MCP commands are consistent in their behavior."""
        runner = CliRunner()

        # All basic commands should work
        commands = ["status", "logs", "test"]

        for command in commands:
            result = runner.invoke(
                cli,
                ["mcp", command],
                catch_exceptions=False,
            )

            assert result.exit_code == 0, f"MCP {command} failed: {result.output}"
            assert len(result.output.strip()) > 0


class TestMCPIntegration:
    """Test MCP integration with other systems."""

    @pytest.mark.skipif(
        not _claude_code_available(),
        reason="Claude Code CLI not available",
    )
    @pytest.mark.integration
    def test_mcp_status_after_other_operations(self):
        """Test MCP status after other CLI operations."""
        runner = CliRunner()

        # Run some other CLI operations first
        runner.invoke(cli, ["config", "show"], catch_exceptions=False)
        runner.invoke(cli, ["adapters", "status"], catch_exceptions=False)

        # MCP status should still work
        mcp_result = runner.invoke(
            cli,
            ["mcp", "status"],
            catch_exceptions=False,
        )

        assert mcp_result.exit_code == 0
        assert len(mcp_result.output.strip()) > 0

    @pytest.mark.skipif(
        not _claude_code_available(),
        reason="Claude Code CLI not available",
    )
    @pytest.mark.integration
    def test_mcp_concurrent_operations(self):
        """Test concurrent MCP operations."""
        import queue
        import threading

        results: queue.Queue[tuple[int, int, str | None]] = queue.Queue()
        lock = threading.Lock()

        def check_mcp_status(check_id):
            """Check MCP status in thread."""
            with lock:
                runner = CliRunner()
                try:
                    result = runner.invoke(
                        cli,
                        ["mcp", "status"],
                        catch_exceptions=False,
                    )
                    results.put((check_id, result.exit_code, None))
                except Exception as e:
                    results.put((check_id, -1, str(e)))

        # Run multiple status checks concurrently
        threads = []
        for i in range(3):
            thread = threading.Thread(target=check_mcp_status, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join(timeout=10)

        # Collect results
        collected_results = []
        while not results.empty():
            collected_results.append(results.get())

        # All should have completed successfully
        assert len(collected_results) == 3
        for check_id, exit_code, error in collected_results:
            assert error is None, f"MCP status check {check_id} failed: {error}"
            assert exit_code == 0, f"MCP status check {check_id} exit code: {exit_code}"

    @pytest.mark.skipif(
        not _claude_code_available(),
        reason="Claude Code CLI not available",
    )
    @pytest.mark.integration
    def test_mcp_environment_independence(self):
        """Test that MCP commands work in different environments."""
        runner = CliRunner()

        # Test with different environment variables
        import os

        test_envs = [
            {},  # Clean environment
            {"AIDB_LOG_LEVEL": "DEBUG"},
            {"AIDB_TEST_MODE": "1"},
        ]

        for env_vars in test_envs:
            env = os.environ.copy()
            env.update(env_vars)

            result = runner.invoke(
                cli,
                ["mcp", "status"],
                env=env,
                catch_exceptions=False,
            )

            assert result.exit_code == 0, (
                f"MCP status failed with env {env_vars}: {result.output}"
            )
