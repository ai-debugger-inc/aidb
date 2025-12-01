"""Tests for MCP management commands."""

import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import Mock, PropertyMock, patch

from aidb_cli.cli import cli
from aidb_cli.core.constants import DEFAULT_LOG_LINES


class TestMCPCommands:
    """Test MCP management commands."""

    def test_mcp_logs_command(self, cli_runner, mock_repo_root):
        """Test MCP logs command points to correct log path."""
        # Mock command executor and its results
        mock_command_executor = Mock()
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Server starts OK\n"
        mock_result.stderr = ""
        mock_command_executor.execute.return_value = mock_result

        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch("aidb_cli.commands.mcp.get_log_file_path") as mock_get_log_path:
                # Mock the log file path
                with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as tmp:
                    mock_log_file = Path(tmp.name)
                mock_get_log_path.return_value = str(mock_log_file)

                # Create a sample log file with some content
                mock_log_file.write_text(
                    "2024-01-01 10:00:00 INFO MCP server started\n"
                    "2024-01-01 10:00:01 DEBUG Processing request\n"
                    "2024-01-01 10:00:02 INFO Request completed\n",
                )

                with patch(
                    "aidb_cli.cli.Context.command_executor",
                    new_callable=PropertyMock,
                    return_value=mock_command_executor,
                ):
                    result = cli_runner.invoke(cli, ["mcp", "logs"])

                    assert result.exit_code == 0
                    assert "MCP Server Debug Analysis:" in result.output
                    assert "Checking MCP logs for errors:" in result.output

                    # Verify get_log_file_path was called with "mcp"
                    mock_get_log_path.assert_called_with("mcp")
                    # Verify command executor was called
                    mock_command_executor.execute.assert_called()

                    # Clean up
                    mock_log_file.unlink()

    def test_mcp_logs_no_log_file(self, cli_runner, mock_repo_root):
        """Test MCP logs command when no log file exists."""
        # Mock command executor and its results
        mock_command_executor = Mock()
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Server starts OK\n"
        mock_result.stderr = ""
        mock_command_executor.execute.return_value = mock_result

        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch("aidb_cli.commands.mcp.get_log_file_path") as mock_get_log_path:
                # Mock non-existent log file path
                mock_get_log_path.return_value = "/nonexistent/path/mcp.log"

                with patch(
                    "aidb_cli.cli.Context.command_executor",
                    new_callable=PropertyMock,
                    return_value=mock_command_executor,
                ):
                    result = cli_runner.invoke(cli, ["mcp", "logs"])

                    assert result.exit_code == 0
                    assert "No MCP log file found" in result.output
                    mock_get_log_path.assert_called_with("mcp")

    def test_mcp_logs_with_errors(self, cli_runner, mock_repo_root):
        """Test MCP logs command detects errors in log file."""
        # Mock command executor and its results
        mock_command_executor = Mock()
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Server starts OK\n"
        mock_result.stderr = ""
        mock_command_executor.execute.return_value = mock_result

        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch("aidb_cli.commands.mcp.get_log_file_path") as mock_get_log_path:
                # Mock log file with errors
                with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as tmp:
                    mock_log_file = Path(tmp.name)
                mock_get_log_path.return_value = str(mock_log_file)

                mock_log_file.write_text(
                    "2024-01-01 10:00:00 INFO MCP server started\n"
                    "2024-01-01 10:00:01 ERROR Connection failed to debug adapter\n"
                    "2024-01-01 10:00:02 WARNING Retrying connection\n",
                )

                with patch(
                    "aidb_cli.cli.Context.command_executor",
                    new_callable=PropertyMock,
                    return_value=mock_command_executor,
                ):
                    result = cli_runner.invoke(cli, ["mcp", "logs"])

                    assert result.exit_code == 0
                    assert "Found recent errors:" in result.output
                    assert "Connection failed" in result.output

                    # Clean up
                    mock_log_file.unlink()

    def test_mcp_logs_verbose_flag(self, cli_runner, mock_repo_root):
        """Test MCP logs command with verbose flag shows more lines."""
        # Mock command executor and its results
        mock_command_executor = Mock()
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Server starts OK\n"
        mock_result.stderr = ""
        mock_command_executor.execute.return_value = mock_result

        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch("aidb_cli.commands.mcp.get_log_file_path") as mock_get_log_path:
                # Mock log file with many lines
                with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as tmp:
                    mock_log_file = Path(tmp.name)
                mock_get_log_path.return_value = str(mock_log_file)

                # Create log file with 250 lines
                log_lines = []
                for i in range(250):
                    log_lines.append(f"2024-01-01 10:00:{i:02d} INFO Line {i + 1}\n")
                mock_log_file.write_text("".join(log_lines))

                with patch(
                    "aidb_cli.cli.Context.command_executor",
                    new_callable=PropertyMock,
                    return_value=mock_command_executor,
                ):
                    # Test with verbose flag (at CLI level)
                    result = cli_runner.invoke(cli, ["-v", "mcp", "logs"])

                    assert result.exit_code == 0
                    assert (
                        f"Last {DEFAULT_LOG_LINES} lines of MCP log:" in result.output
                    )
                    # First line shown: 250 - DEFAULT_LOG_LINES + 1
                    first_line = 250 - DEFAULT_LOG_LINES + 1
                    assert f"Line {first_line}" in result.output
                    assert "Line 250" in result.output  # Should show the last line

                    # Clean up
                    mock_log_file.unlink()

    def test_mcp_status_command(self, cli_runner, mock_repo_root):
        """Test MCP status command."""
        # Create a mock Claude config
        claude_config_content = {
            "projects": {
                str(mock_repo_root): {
                    "mcpServers": {
                        "aidb-debug": {
                            "command": "python",
                            "args": ["-m", "aidb_mcp"],
                        },
                    },
                },
            },
        }

        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch("pathlib.Path.home") as mock_home:
                mock_claude_config = mock_home.return_value / ".claude.json"
                mock_claude_config.exists.return_value = True

                # Use mock_open for file reading
                with patch("builtins.open", create=True) as mock_open:
                    mock_open.return_value.__enter__.return_value = Mock()

                    with patch("json.load", return_value=claude_config_content):
                        result = cli_runner.invoke(cli, ["mcp", "status"])

                        assert result.exit_code == 0
                        assert "Registration Status:" in result.output
                        assert "aidb-debug" in result.output
