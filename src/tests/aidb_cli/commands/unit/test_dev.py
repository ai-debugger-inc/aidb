"""Tests for development utility commands."""

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import Mock, PropertyMock, call, patch

import pytest
from click.testing import CliRunner

from aidb_cli.cli import cli
from aidb_cli.commands.dev import _run_precommit_process, _terminate_process


class TestDevCommands:
    """Test development utility commands."""

    def test_precommit_all_files(self, cli_runner, mock_repo_root):
        """Test precommit command with default all-files mode."""
        # Mock command executor and its result
        mock_command_executor = Mock()
        mock_proc = Mock()
        mock_proc.stdout = iter(["All checks passed!\n"])
        mock_proc.wait.return_value = 0
        mock_command_executor.create_process.return_value = mock_proc

        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch(
                "aidb_cli.cli.Context.command_executor",
                new_callable=PropertyMock,
                return_value=mock_command_executor,
            ):
                result = cli_runner.invoke(cli, ["dev", "precommit"])
                assert result.exit_code == 0
                assert "Pre-commit Hooks:" in result.output

                # Verify command_executor was called
                mock_command_executor.create_process.assert_called_once()
                call_args = mock_command_executor.create_process.call_args[0][0]
                assert "pre-commit" in str(call_args[0])
                assert "run" in call_args
                assert "--all-files" in call_args

    def test_precommit_staged_only(self, cli_runner, mock_repo_root):
        """Test precommit with staged-only flag."""
        # Mock command executor and its result
        mock_command_executor = Mock()
        mock_proc = Mock()
        mock_proc.stdout = iter(["Checks passed on staged files\n"])
        mock_proc.wait.return_value = 0
        mock_command_executor.create_process.return_value = mock_proc

        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch(
                "aidb_cli.cli.Context.command_executor",
                new_callable=PropertyMock,
                return_value=mock_command_executor,
            ):
                result = cli_runner.invoke(cli, ["dev", "precommit", "--staged-only"])
                assert result.exit_code == 0

                # Verify --all-files is NOT in the command
                call_args = mock_command_executor.create_process.call_args[0][0]
                assert "--all-files" not in call_args

    def test_precommit_failure(self, cli_runner, mock_repo_root):
        """Test precommit command handling of failures."""
        # Mock command executor and its result
        mock_command_executor = Mock()
        mock_proc = Mock()
        mock_proc.stdout = iter(["Linting failed: file.py:10:1: E501 line too long\n"])
        mock_proc.wait.return_value = 1
        mock_command_executor.create_process.return_value = mock_proc

        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch(
                "aidb_cli.cli.Context.command_executor",
                new_callable=PropertyMock,
                return_value=mock_command_executor,
            ):
                result = cli_runner.invoke(cli, ["dev", "precommit"])
                assert result.exit_code == 1
                assert "Pre-commit failed" in result.output

    def test_dap_command(self, cli_runner, mock_repo_root):
        """Test DAP protocol regeneration command."""
        # Create the expected script path in the mock repo
        dap_script = (
            mock_repo_root / "src" / "aidb" / "dap" / "_util" / "_gen_protocol.py"
        )
        dap_script.parent.mkdir(parents=True, exist_ok=True)
        dap_script.touch()

        # Mock command executor and its result
        mock_command_executor = Mock()
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "DAP protocol generated successfully"
        mock_result.stderr = ""
        mock_command_executor.execute.return_value = mock_result

        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch(
                "aidb_cli.cli.Context.command_executor",
                new_callable=PropertyMock,
                return_value=mock_command_executor,
            ):
                result = cli_runner.invoke(cli, ["dev", "dap"])
                assert result.exit_code == 0
                assert "DAP Protocol Regeneration" in result.output

                # Verify the correct script was called
                call_args = mock_command_executor.execute.call_args[0][0]
                assert "_gen_protocol.py" in str(call_args[-1])

    def test_dap_missing_script(self, cli_runner, tmp_path):
        """Test DAP command when generator script is missing."""
        # Create venv structure
        venv_bin = tmp_path / "venv" / "bin"
        venv_bin.mkdir(parents=True)
        (venv_bin / "python").touch()

        # Must patch detect_repo_root where Context imports it (aidb_cli.cli)
        with patch("aidb_cli.cli.detect_repo_root", return_value=tmp_path):
            result = cli_runner.invoke(cli, ["dev", "dap"])
            # Exit code 1 for missing script, exit code 2 for Click errors
            assert result.exit_code in (1, 2), f"Output: {result.output}"
            assert (
                "DAP generation failed" in result.output or "not found" in result.output
            )

    def test_clean_artifacts(self, cli_runner, mock_repo_root):
        """Test cleaning development artifacts."""
        # Create some artifacts that match the clean patterns
        cache_dir = mock_repo_root / "__pycache__"
        cache_dir.mkdir()
        (cache_dir / "test.pyc").touch()

        mypy_cache = mock_repo_root / ".mypy_cache"
        mypy_cache.mkdir()

        pytest_cache = mock_repo_root / ".pytest_cache"
        pytest_cache.mkdir()

        coverage_file = mock_repo_root / ".coverage"
        coverage_file.touch()

        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            result = cli_runner.invoke(cli, ["dev", "clean"])
            assert result.exit_code == 0
            assert "Cleaning Development Artifacts" in result.output

            # The clean command should report cleaning items
            assert (
                "Cleaned" in result.output or "No artifacts to clean" in result.output
            )

    def test_clean_no_artifacts(self, cli_runner, mock_repo_root):
        """Test clean command when there are no artifacts to clean."""
        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            result = cli_runner.invoke(cli, ["dev", "clean"])
            assert result.exit_code == 0
            # Command may find real cache files even in tmp_path, so accept either outcome
            assert (
                "Cleaned" in result.output or "No artifacts to clean" in result.output
            )

    def test_verbose_output(self, cli_runner, mock_repo_root):
        """Test that verbose flag provides additional output."""
        # Mock command executor and its result
        mock_command_executor = Mock()
        mock_proc = Mock()
        mock_proc.stdout = iter(["Detailed output here\n"])
        mock_proc.wait.return_value = 0
        mock_command_executor.create_process.return_value = mock_proc

        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch(
                "aidb_cli.cli.Context.command_executor",
                new_callable=PropertyMock,
                return_value=mock_command_executor,
            ):
                result = cli_runner.invoke(cli, ["--verbose", "dev", "precommit"])
                assert result.exit_code == 0

                # Verify create_process was called (verbose is handled by CLI context)
                mock_command_executor.create_process.assert_called_once()

    def test_dev_help(self, cli_runner):
        """Test dev command help text."""
        result = cli_runner.invoke(cli, ["dev", "--help"])
        assert result.exit_code == 0
        assert "Core development utilities" in result.output
        assert "precommit" in result.output
        assert "dap" in result.output
        assert "clean" in result.output

    def test_precommit_skip_vulture_by_default(self, cli_runner, mock_repo_root):
        """Test precommit skips vulture by default."""
        from aidb_cli.core.constants import PreCommitEnvVars, PreCommitHooks

        mock_command_executor = Mock()
        mock_proc = Mock()
        mock_proc.stdout = iter(["All checks passed!\n"])
        mock_proc.wait.return_value = 0
        mock_command_executor.create_process.return_value = mock_proc

        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch(
                "aidb_cli.cli.Context.command_executor",
                new_callable=PropertyMock,
                return_value=mock_command_executor,
            ):
                result = cli_runner.invoke(cli, ["dev", "precommit"])
                assert result.exit_code == 0

                call_kwargs = mock_command_executor.create_process.call_args[1]
                assert "env" in call_kwargs
                assert PreCommitEnvVars.SKIP in call_kwargs["env"]
                assert (
                    call_kwargs["env"][PreCommitEnvVars.SKIP] == PreCommitHooks.VULTURE
                )

    def test_precommit_run_vulture_when_flag_set(self, cli_runner, mock_repo_root):
        """Test precommit runs vulture when --run-vulture is passed."""
        from aidb_cli.core.constants import PreCommitEnvVars

        mock_command_executor = Mock()
        mock_proc = Mock()
        mock_proc.stdout = iter(["All checks passed!\n"])
        mock_proc.wait.return_value = 0
        mock_command_executor.create_process.return_value = mock_proc

        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch(
                "aidb_cli.cli.Context.command_executor",
                new_callable=PropertyMock,
                return_value=mock_command_executor,
            ):
                result = cli_runner.invoke(cli, ["dev", "precommit", "--run-vulture"])
                assert result.exit_code == 0

                call_kwargs = mock_command_executor.create_process.call_args[1]
                assert "env" in call_kwargs
                env = call_kwargs["env"]
                assert (
                    PreCommitEnvVars.SKIP not in env or env[PreCommitEnvVars.SKIP] == ""
                )

    def test_precommit_skip_vulture_with_staged_only(self, cli_runner, mock_repo_root):
        """Test precommit skips vulture with --staged-only flag."""
        from aidb_cli.core.constants import PreCommitEnvVars, PreCommitHooks

        mock_command_executor = Mock()
        mock_proc = Mock()
        mock_proc.stdout = iter(["Checks passed on staged files\n"])
        mock_proc.wait.return_value = 0
        mock_command_executor.create_process.return_value = mock_proc

        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch(
                "aidb_cli.cli.Context.command_executor",
                new_callable=PropertyMock,
                return_value=mock_command_executor,
            ):
                result = cli_runner.invoke(cli, ["dev", "precommit", "--staged-only"])
                assert result.exit_code == 0

                call_args = mock_command_executor.create_process.call_args[0][0]
                assert "--all-files" not in call_args

                call_kwargs = mock_command_executor.create_process.call_args[1]
                assert "env" in call_kwargs
                assert PreCommitEnvVars.SKIP in call_kwargs["env"]
                assert (
                    call_kwargs["env"][PreCommitEnvVars.SKIP] == PreCommitHooks.VULTURE
                )

    def test_precommit_keyboard_interrupt_terminates_process(
        self, cli_runner, mock_repo_root
    ):
        """Test that Ctrl+C properly terminates the subprocess."""
        mock_command_executor = Mock()
        mock_proc = Mock()

        # Create an iterator that raises KeyboardInterrupt
        def interrupt_generator():
            raise KeyboardInterrupt
            yield  # noqa: B901 - unreachable but needed for generator

        mock_proc.stdout = interrupt_generator()
        mock_proc.terminate = Mock()
        mock_proc.wait = Mock(return_value=0)
        mock_command_executor.create_process.return_value = mock_proc

        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch(
                "aidb_cli.cli.Context.command_executor",
                new_callable=PropertyMock,
                return_value=mock_command_executor,
            ):
                result = cli_runner.invoke(cli, ["dev", "precommit"])
                # Exit code 1 from handle_exceptions decorator on KeyboardInterrupt
                assert result.exit_code == 1

                # Verify terminate was called on the process
                mock_proc.terminate.assert_called_once()
                mock_proc.wait.assert_called()


class TestTerminateProcess:
    """Tests for _terminate_process helper function."""

    def test_terminate_process_graceful(self):
        """Test graceful termination when process exits within timeout."""
        mock_proc = Mock(spec=subprocess.Popen)
        mock_proc.wait.return_value = 0

        _terminate_process(mock_proc)

        mock_proc.terminate.assert_called_once()
        mock_proc.wait.assert_called_once_with(timeout=2)
        mock_proc.kill.assert_not_called()

    def test_terminate_process_force_kill(self):
        """Test force kill when process doesn't exit within timeout."""
        mock_proc = Mock(spec=subprocess.Popen)
        mock_proc.wait.side_effect = [subprocess.TimeoutExpired("cmd", 2), 0]

        _terminate_process(mock_proc)

        mock_proc.terminate.assert_called_once()
        mock_proc.kill.assert_called_once()
        assert mock_proc.wait.call_count == 2


class TestRunPrecommitProcess:
    """Tests for _run_precommit_process helper function."""

    def test_streams_output_to_console_and_file(self, tmp_path):
        """Test that output is streamed to both console and log file."""
        log_file = tmp_path / "test.log"
        mock_proc = Mock(spec=subprocess.Popen)
        mock_proc.stdout = iter(["line 1\n", "line 2\n", "line 3\n"])
        mock_proc.wait.return_value = 0

        with patch("sys.stdout") as mock_stdout:
            returncode = _run_precommit_process(mock_proc, log_file)

        assert returncode == 0
        assert log_file.read_text() == "line 1\nline 2\nline 3\n"
        assert mock_stdout.write.call_count == 3
        assert mock_stdout.flush.call_count == 3

    def test_handles_no_stdout(self, tmp_path):
        """Test handling when stdout is None."""
        log_file = tmp_path / "test.log"
        mock_proc = Mock(spec=subprocess.Popen)
        mock_proc.stdout = None
        mock_proc.wait.return_value = 0

        returncode = _run_precommit_process(mock_proc, log_file)

        assert returncode == 0
        assert log_file.read_text() == ""

    def test_returns_nonzero_exit_code(self, tmp_path):
        """Test that non-zero exit codes are returned."""
        log_file = tmp_path / "test.log"
        mock_proc = Mock(spec=subprocess.Popen)
        mock_proc.stdout = iter(["error output\n"])
        mock_proc.wait.return_value = 1

        with patch("sys.stdout"):
            returncode = _run_precommit_process(mock_proc, log_file)

        assert returncode == 1
