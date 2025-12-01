"""Unit tests for CommandExecutor service.

Tests the centralized command execution service including streaming detection,
environment handling, and error management.
"""

import os
import sys
from pathlib import Path
from unittest import mock

import pytest

from aidb.common.errors import AidbError
from aidb_cli.services.command_executor import CommandExecutor


class TestCommandExecutor:
    """Test CommandExecutor functionality."""

    def test_init_defaults(self):
        """Test CommandExecutor initialization with defaults."""
        executor = CommandExecutor()
        # Just verify it initializes successfully
        assert executor is not None

    def test_ci_detection(self):
        """Test CI environment detection."""
        executor = CommandExecutor()

        # Test no CI environment
        with mock.patch.dict(os.environ, {}, clear=True):
            # Reset cached value
            executor._tty_service._is_ci = None
            assert executor.is_ci is False

        # Test GitHub Actions
        with mock.patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}):
            # Reset cached value
            executor._tty_service._is_ci = None
            assert executor.is_ci is True

        # Test generic CI
        with mock.patch.dict(os.environ, {"CI": "1"}):
            # Reset cached value
            executor._tty_service._is_ci = None
            assert executor.is_ci is True

        # Test GitLab CI
        with mock.patch.dict(os.environ, {"GITLAB_CI": "true"}):
            # Reset cached value
            executor._tty_service._is_ci = None
            assert executor.is_ci is True

    def test_should_stream_logic(self):
        """Test streaming detection logic."""
        # Mock TTY as True
        with mock.patch("sys.stdout.isatty", return_value=True):
            with mock.patch.dict(os.environ, {}, clear=True):
                # Normal TTY environment - should stream
                executor = CommandExecutor()
                # Reset cached values
                executor._tty_service._is_ci = None
                executor._tty_service._is_tty = None
                assert executor.should_stream() is True

        # Test CI environment - should NOT stream
        with mock.patch("sys.stdout.isatty", return_value=True):
            with mock.patch.dict(os.environ, {"CI": "1"}):
                executor = CommandExecutor()
                # Reset cached values
                executor._tty_service._is_ci = None
                executor._tty_service._is_tty = None
                assert executor.should_stream() is False

        # Mock TTY as False
        with mock.patch("sys.stdout.isatty", return_value=False):
            with mock.patch.dict(os.environ, {}, clear=True):
                executor = CommandExecutor()
                # Reset cached values
                executor._tty_service._is_ci = None
                executor._tty_service._is_tty = None
                assert executor.should_stream() is False

    def test_force_streaming_env_var(self):
        """Test AIDB_CLI_FORCE_STREAMING environment variable."""
        from aidb_cli.core.constants import EnvVars

        with mock.patch.dict(os.environ, {EnvVars.CLI_FORCE_STREAMING: "1"}):
            # Mock no TTY - would normally disable streaming
            with mock.patch("sys.stdout.isatty", return_value=False):
                executor = CommandExecutor()
                # Reset cached values
                executor._tty_service._is_ci = None
                executor._tty_service._is_tty = None
                assert executor._force_streaming is True
                assert executor.should_stream() is True  # Force overrides TTY check

        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch("sys.stdout.isatty", return_value=False):
                executor = CommandExecutor()
                # Reset cached values
                executor._tty_service._is_ci = None
                executor._tty_service._is_tty = None
                assert executor._force_streaming is False
                assert executor.should_stream() is False  # No TTY = no streaming

    @mock.patch("subprocess.run")
    def test_execute_with_capture_output(self, mock_run):
        """Test execute with explicit capture_output."""
        mock_result = mock.Mock()
        mock_result.returncode = 0
        mock_result.stdout = "output"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        executor = CommandExecutor()
        result = executor.execute(["echo", "test"], capture_output=True)

        # Should call subprocess with capture_output
        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["capture_output"] is True
        assert result.returncode == 0

    @mock.patch("subprocess.run")
    def test_execute_with_string_command(self, mock_run):
        """Test execute with string command instead of list."""
        mock_result = mock.Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        executor = CommandExecutor()
        executor.execute("echo hello world", capture_output=True)

        # Should convert string to list
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd == ["echo", "hello", "world"]

    @mock.patch("subprocess.run")
    def test_execute_with_cwd(self, mock_run):
        """Test execute with working directory."""
        mock_result = mock.Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        executor = CommandExecutor()
        test_cwd = Path("/test/dir")
        executor.execute(["ls"], cwd=test_cwd, capture_output=True)

        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["cwd"] == test_cwd

    @mock.patch("subprocess.run")
    def test_execute_with_env(self, mock_run):
        """Test execute with environment variables."""
        mock_result = mock.Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        executor = CommandExecutor()
        test_env = {"TEST_VAR": "value"}
        executor.execute(["echo", "$TEST_VAR"], env=test_env, capture_output=True)

        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args[1]
        # Environment should contain our test variable
        assert "TEST_VAR" in call_kwargs["env"]
        assert call_kwargs["env"]["TEST_VAR"] == "value"

    @mock.patch("subprocess.run")
    def test_execute_with_check_false(self, mock_run):
        """Test execute with check=False doesn't raise on failure."""
        mock_result = mock.Mock()
        mock_result.returncode = 1
        mock_result.stdout = "error output"
        mock_result.stderr = "error"
        mock_run.return_value = mock_result

        executor = CommandExecutor()
        result = executor.execute(["false"], check=False, capture_output=True)

        # Should not raise exception
        assert result.returncode == 1

    @mock.patch("subprocess.run")
    def test_execute_with_check_true_raises(self, mock_run):
        """Test execute with check=True raises on failure."""
        # Mock a failed command result
        mock_result = mock.Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "command failed"
        mock_run.return_value = mock_result

        executor = CommandExecutor()

        with pytest.raises(AidbError) as exc_info:
            executor.execute(["false"], check=True, capture_output=True)

        # Check that the error message contains expected text
        assert "failed with exit code 1" in str(exc_info.value)
        assert "command failed" in str(exc_info.value)

    @mock.patch("subprocess.run")
    def test_execute_with_timeout(self, mock_run):
        """Test execute with timeout."""
        mock_result = mock.Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        executor = CommandExecutor()
        executor.execute(["sleep", "1"], timeout=5.0, capture_output=True)

        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs.get("timeout") == 5.0

    def test_capture_output_overrides_streaming(self):
        """Test that explicit capture_output overrides auto-detection."""
        # Even with TTY and no verbose, capture_output=True should not stream
        with mock.patch("sys.stdout.isatty", return_value=True):
            with mock.patch.dict(os.environ, {}, clear=True):
                executor = CommandExecutor()
                # Reset cached values
                executor._tty_service._is_ci = None
                executor._tty_service._is_tty = None

                # Normally would stream
                assert executor.should_stream() is True

                # But with capture_output=True, streaming is disabled
                with mock.patch.object(executor._exec_service, "execute") as mock_exec:
                    mock_exec.return_value = mock.Mock(returncode=0)
                    executor.execute(["echo", "test"], capture_output=True)
                    mock_exec.assert_called_once()
                    # Verify capture_output was passed through
                    call_kwargs = mock_exec.call_args[1]
                    assert call_kwargs["capture_output"] is True

    def test_streaming_mode(self):
        """Test that streaming mode uses StreamHandlerService."""
        with mock.patch("sys.stdout.isatty", return_value=True):
            with mock.patch.dict(os.environ, {}, clear=True):
                executor = CommandExecutor()
                # Reset cached values
                executor._tty_service._is_ci = None
                executor._tty_service._is_tty = None

                # Mock the stream service
                with mock.patch(
                    "aidb_cli.services.command_executor.StreamHandlerService",
                ) as mock_stream_class:
                    mock_stream_service = mock.Mock()
                    mock_stream_service.run_with_streaming.return_value = mock.Mock(
                        returncode=0,
                        stdout="",
                        stderr="",
                    )
                    mock_stream_class.return_value = mock_stream_service

                    # Should use streaming
                    result = executor.execute(["echo", "test"])

                    mock_stream_class.assert_called_once()
                    mock_stream_service.run_with_streaming.assert_called_once()
                    assert result.returncode == 0

    def test_streaming_window_size(self):
        """Test that streaming uses the correct window size."""
        from aidb_cli.core.constants import STREAM_WINDOW_SIZE

        with mock.patch("sys.stdout.isatty", return_value=True):
            with mock.patch.dict(os.environ, {}, clear=True):
                executor = CommandExecutor()
                # Reset cached values
                executor._tty_service._is_ci = None
                executor._tty_service._is_tty = None

                # Mock the stream service
                with mock.patch(
                    "aidb_cli.services.command_executor.StreamHandlerService",
                ) as mock_stream_class:
                    mock_stream_service = mock.Mock()
                    mock_stream_service.run_with_streaming.return_value = mock.Mock(
                        returncode=0,
                        stdout="",
                        stderr="",
                    )
                    mock_stream_class.return_value = mock_stream_service

                    # Should use streaming with 5-line window
                    executor.execute(["echo", "test"])

                    # Verify StreamHandlerService was called with max_lines=5
                    mock_stream_class.assert_called_once()
                    call_kwargs = mock_stream_class.call_args[1]
                    assert call_kwargs["max_lines"] == STREAM_WINDOW_SIZE  # Should be 5


class TestStreamingDetectionIntegration:
    """Integration tests for streaming detection in different environments."""

    def test_normal_enables_streaming(self):
        """Test that normal TTY environment enables streaming."""
        with mock.patch("sys.stdout.isatty", return_value=True):
            with mock.patch.dict(os.environ, {}, clear=True):
                executor = CommandExecutor()
                # Reset cached values
                executor._tty_service._is_ci = None
                executor._tty_service._is_tty = None
                assert executor.should_stream() is True

    def test_ci_disables_streaming(self):
        """Test that CI environment disables streaming."""
        with mock.patch("sys.stdout.isatty", return_value=True):
            with mock.patch.dict(os.environ, {"CI": "true"}):
                executor = CommandExecutor()
                # Reset cached values
                executor._tty_service._is_ci = None
                executor._tty_service._is_tty = None
                assert executor.should_stream() is False

    def test_no_tty_disables_streaming(self):
        """Test that lack of TTY disables streaming."""
        with mock.patch("sys.stdout.isatty", return_value=False):
            with mock.patch.dict(os.environ, {}, clear=True):
                executor = CommandExecutor()
                # Reset cached values
                executor._tty_service._is_ci = None
                executor._tty_service._is_tty = None
                assert executor.should_stream() is False

    def test_force_streaming_overrides_all(self):
        """Test that force streaming overrides all other conditions."""
        from aidb_cli.core.constants import EnvVars

        with mock.patch.dict(os.environ, {EnvVars.CLI_FORCE_STREAMING: "1", "CI": "1"}):
            with mock.patch("sys.stdout.isatty", return_value=False):
                executor = CommandExecutor()
                # Reset cached values
                executor._tty_service._is_ci = None
                executor._tty_service._is_tty = None
                # Despite CI=1 and no TTY saying no, force says yes
                assert executor.should_stream() is True
