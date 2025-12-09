"""Unit tests for CommandExecutor service.

Tests the centralized command execution service including streaming detection,
environment handling, and error management.
"""

import os
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
        assert executor is not None

    def test_ci_detection(self):
        """Test CI environment detection."""
        # Test GitHub Actions
        with mock.patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}, clear=True):
            executor = CommandExecutor()
            assert executor.is_ci is True

        # Test generic CI
        with mock.patch.dict(os.environ, {"CI": "1"}, clear=True):
            executor = CommandExecutor()
            assert executor.is_ci is True

        # Test no CI environment
        with mock.patch.dict(os.environ, {}, clear=True):
            executor = CommandExecutor()
            assert executor.is_ci is False

    def test_should_stream_logic(self):
        """Test streaming detection logic."""
        # Normal TTY environment - should stream
        with mock.patch("sys.stdout.isatty", return_value=True):
            with mock.patch.dict(os.environ, {}, clear=True):
                executor = CommandExecutor()
                assert executor.should_stream() is True

        # CI environment - should NOT stream
        with mock.patch("sys.stdout.isatty", return_value=True):
            with mock.patch.dict(os.environ, {"CI": "1"}, clear=True):
                executor = CommandExecutor()
                assert executor.should_stream() is False

        # No TTY - should NOT stream
        with mock.patch("sys.stdout.isatty", return_value=False):
            with mock.patch.dict(os.environ, {}, clear=True):
                executor = CommandExecutor()
                assert executor.should_stream() is False

    def test_force_streaming_env_var(self):
        """Test AIDB_CLI_FORCE_STREAMING environment variable."""
        from aidb_cli.core.constants import EnvVars

        # Force streaming overrides no TTY
        with mock.patch.dict(
            os.environ, {EnvVars.CLI_FORCE_STREAMING: "1"}, clear=True
        ):
            with mock.patch("sys.stdout.isatty", return_value=False):
                executor = CommandExecutor()
                assert executor.should_stream() is True

        # Without force, no TTY means no streaming
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch("sys.stdout.isatty", return_value=False):
                executor = CommandExecutor()
                assert executor.should_stream() is False

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

        assert result.returncode == 1

    @mock.patch("subprocess.run")
    def test_execute_with_check_true_raises(self, mock_run):
        """Test execute with check=True raises on failure."""
        mock_result = mock.Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "command failed"
        mock_run.return_value = mock_result

        executor = CommandExecutor()

        with pytest.raises(AidbError) as exc_info:
            executor.execute(["false"], check=True, capture_output=True)

        assert "exit 1" in str(exc_info.value)
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

    def test_streaming_uses_stream_handler(self):
        """Test that streaming mode uses StreamHandler."""
        with mock.patch("sys.stdout.isatty", return_value=True):
            with mock.patch.dict(os.environ, {}, clear=True):
                executor = CommandExecutor()

                with mock.patch(
                    "aidb_cli.services.command_executor.StreamHandler",
                ) as mock_stream_class:
                    mock_stream = mock.Mock()
                    mock_stream.run_with_streaming.return_value = mock.Mock(
                        returncode=0,
                        stdout="",
                        stderr="",
                    )
                    mock_stream_class.return_value = mock_stream

                    result = executor.execute(["echo", "test"])

                    mock_stream_class.assert_called_once()
                    mock_stream.run_with_streaming.assert_called_once()
                    assert result.returncode == 0

    def test_streaming_window_size(self):
        """Test that streaming uses the correct window size."""
        from aidb_cli.core.constants import STREAM_WINDOW_SIZE

        with mock.patch("sys.stdout.isatty", return_value=True):
            with mock.patch.dict(os.environ, {}, clear=True):
                executor = CommandExecutor()

                with mock.patch(
                    "aidb_cli.services.command_executor.StreamHandler",
                ) as mock_stream_class:
                    mock_stream = mock.Mock()
                    mock_stream.run_with_streaming.return_value = mock.Mock(
                        returncode=0,
                        stdout="",
                        stderr="",
                    )
                    mock_stream_class.return_value = mock_stream

                    executor.execute(["echo", "test"])

                    mock_stream_class.assert_called_once()
                    call_kwargs = mock_stream_class.call_args[1]
                    assert call_kwargs["max_lines"] == STREAM_WINDOW_SIZE


class TestStreamingDetection:
    """Tests for streaming detection in different environments."""

    def test_tty_enables_streaming(self):
        """Test that TTY environment enables streaming."""
        with mock.patch("sys.stdout.isatty", return_value=True):
            with mock.patch.dict(os.environ, {}, clear=True):
                executor = CommandExecutor()
                assert executor.should_stream() is True

    def test_ci_disables_streaming(self):
        """Test that CI environment disables streaming."""
        with mock.patch("sys.stdout.isatty", return_value=True):
            with mock.patch.dict(os.environ, {"CI": "true"}, clear=True):
                executor = CommandExecutor()
                assert executor.should_stream() is False

    def test_no_tty_disables_streaming(self):
        """Test that lack of TTY disables streaming."""
        with mock.patch("sys.stdout.isatty", return_value=False):
            with mock.patch.dict(os.environ, {}, clear=True):
                executor = CommandExecutor()
                assert executor.should_stream() is False

    def test_force_streaming_overrides_all(self):
        """Test that force streaming overrides all other conditions."""
        from aidb_cli.core.constants import EnvVars

        with mock.patch.dict(
            os.environ,
            {EnvVars.CLI_FORCE_STREAMING: "1", "CI": "1"},
            clear=True,
        ):
            with mock.patch("sys.stdout.isatty", return_value=False):
                executor = CommandExecutor()
                assert executor.should_stream() is True
