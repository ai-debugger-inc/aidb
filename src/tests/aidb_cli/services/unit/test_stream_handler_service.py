"""Unit tests for StreamHandler.

Tests focus on behavior, not implementation details. Initialization tests and tests that
verify obvious things like "print(x) prints x" are omitted.
"""

import subprocess
from io import StringIO
from unittest.mock import Mock, patch

import pytest

from aidb.common.errors import AidbError
from aidb_cli.core.constants import ExitCode
from aidb_cli.services.command_executor import StreamHandler


class TestStreamHandler:
    """Test StreamHandler behavior."""

    @pytest.fixture
    def handler(self):
        """Create handler with ANSI support."""
        return StreamHandler(
            max_lines=8,
            clear_on_exit=True,
            supports_ansi=True,
            terminal_width=80,
        )

    @pytest.fixture
    def handler_no_ansi(self):
        """Create handler without ANSI support."""
        return StreamHandler(
            max_lines=8,
            clear_on_exit=False,
            supports_ansi=False,
            terminal_width=80,
        )

    # -------------------------------------------------------------------------
    # Command Execution Tests
    # -------------------------------------------------------------------------

    @patch("subprocess.Popen")
    @patch("time.sleep")
    def test_run_with_streaming_success(self, mock_sleep, mock_popen, handler):
        """Test successful command execution returns CompletedProcess."""
        mock_process = Mock()
        mock_process.poll.side_effect = [None, 0, 0, 0]
        mock_process.stdout = StringIO("line1\nline2\n")
        mock_popen.return_value = mock_process

        result = handler.run_with_streaming(["echo", "test"])

        assert isinstance(result, subprocess.CompletedProcess)
        assert result.returncode == 0
        assert result.args == ["echo", "test"]

    @patch("subprocess.Popen")
    def test_python_commands_get_unbuffered_flag(self, mock_popen, handler):
        """Test that Python commands get -u flag for unbuffered output."""
        mock_process = Mock()
        mock_process.poll.return_value = 0
        mock_process.stdout = StringIO("")
        mock_popen.return_value = mock_process

        handler.run_with_streaming(["python", "script.py"])

        call_args = mock_popen.call_args[0][0]
        assert call_args == ["python", "-u", "script.py"]

    @patch("subprocess.Popen")
    def test_cwd_and_env_passed_through(self, mock_popen, handler, tmp_path):
        """Test that working directory and environment are honored."""
        mock_process = Mock()
        mock_process.poll.return_value = 0
        mock_process.stdout = StringIO("")
        mock_popen.return_value = mock_process

        test_env = {"TEST_VAR": "value"}
        handler.run_with_streaming(["ls"], cwd=tmp_path, env=test_env)

        assert mock_popen.call_args[1]["cwd"] == tmp_path
        assert mock_popen.call_args[1]["env"] == test_env

    # -------------------------------------------------------------------------
    # Error Handling Tests
    # -------------------------------------------------------------------------

    @patch("subprocess.Popen")
    def test_failure_with_check_raises_error(self, mock_popen, handler):
        """Test that non-zero exit with check=True raises AidbError."""
        mock_process = Mock()
        mock_process.poll.return_value = 1
        mock_process.stdout = StringIO("error output\n")
        mock_popen.return_value = mock_process

        with pytest.raises(AidbError) as exc_info:
            handler.run_with_streaming(["failing", "command"], check=True)

        assert "exit 1" in str(exc_info.value)

    @patch("subprocess.Popen")
    def test_failure_without_check_returns_result(self, mock_popen, handler):
        """Test that non-zero exit with check=False returns result."""
        mock_process = Mock()
        mock_process.poll.return_value = 42
        mock_process.stdout = StringIO("")
        mock_popen.return_value = mock_process

        result = handler.run_with_streaming(["failing", "command"], check=False)

        assert result.returncode == 42

    @patch("subprocess.Popen")
    def test_file_not_found_raises_error(self, mock_popen, handler):
        """Test FileNotFoundError handling."""
        mock_popen.side_effect = FileNotFoundError("command not found")

        with pytest.raises(AidbError) as exc_info:
            handler.run_with_streaming(["nonexistent"], check=True)

        assert "Command not found: nonexistent" in str(exc_info.value)

    @patch("subprocess.Popen")
    def test_file_not_found_without_check(self, mock_popen, handler):
        """Test FileNotFoundError with check=False returns error code."""
        mock_popen.side_effect = FileNotFoundError("command not found")

        result = handler.run_with_streaming(["nonexistent"], check=False)

        assert result.returncode == ExitCode.NOT_FOUND

    @patch("subprocess.Popen")
    @patch("time.time")
    def test_timeout_raises_error(self, mock_time, mock_popen, handler):
        """Test that timeout raises TimeoutError."""
        mock_process = Mock()
        mock_process.poll.return_value = None
        mock_process.stdout = StringIO("")
        mock_popen.return_value = mock_process
        mock_time.side_effect = [0, 0, 5.5]

        with pytest.raises(TimeoutError) as exc_info:
            handler.run_with_streaming(["slow"], timeout=5.0)

        assert "timed out" in str(exc_info.value).lower()

    # -------------------------------------------------------------------------
    # Output Capture Tests
    # -------------------------------------------------------------------------

    def test_read_stream_populates_buffers(self, handler):
        """Test that _read_stream populates display and full output."""
        stream = StringIO("line1\nline2\nline3\n")

        handler._read_stream(stream)

        assert list(handler.display_lines) == ["line1", "line2", "line3"]
        assert handler.full_output == ["line1", "line2", "line3"]

    def test_read_stream_respects_stop_event(self, handler):
        """Test that _read_stream stops when stop event is set."""
        stream = StringIO("line1\nline2\n")
        handler._stop_event.set()

        handler._read_stream(stream)

        assert len(handler.full_output) == 0

    def test_read_stream_handles_none(self, handler):
        """Test that _read_stream handles None stream."""
        handler._read_stream(None)
        assert handler.full_output == []

    def test_read_stream_strips_newlines(self, handler):
        """Test that trailing newlines are stripped."""
        stream = StringIO("line1\r\nline2\n")

        handler._read_stream(stream)

        assert handler.full_output == ["line1", "line2"]

    # -------------------------------------------------------------------------
    # Display Tests
    # -------------------------------------------------------------------------

    @patch("builtins.print")
    def test_update_display_with_ansi(self, mock_print, handler):
        """Test display update with ANSI support."""
        handler.display_lines.extend(["line1", "line2"])

        handler._update_display()

        assert handler._has_output is True
        assert mock_print.call_count > 0

    @patch("builtins.print")
    def test_update_display_fallback(self, mock_print, handler_no_ansi):
        """Test display update without ANSI (prints lines directly)."""
        handler_no_ansi.display_lines.extend(["line1", "line2"])
        handler_no_ansi.full_output.extend(["line1", "line2"])

        handler_no_ansi._update_display()

        assert handler_no_ansi._has_output is True
        assert mock_print.call_count == 2

    def test_update_display_empty_does_nothing(self, handler):
        """Test that empty display doesn't set has_output flag."""
        handler._update_display()
        assert handler._has_output is False

    @patch("builtins.print")
    @patch("sys.stdout.flush")
    def test_clear_display_resets_state(self, mock_flush, mock_print, handler):
        """Test that _clear_display resets window state."""
        handler._has_output = True
        handler._current_window_size = 3
        handler._frame_initialized = True

        handler._clear_display()

        assert handler._current_window_size == 0
        assert handler._frame_initialized is False

    # -------------------------------------------------------------------------
    # Sanitization Tests
    # -------------------------------------------------------------------------

    def test_truncates_long_lines(self, handler):
        """Test that lines over terminal width are truncated."""
        long_line = "a" * 100

        result = handler._sanitize_and_truncate(long_line)

        assert len(result) == handler.terminal_width
        assert result.endswith("...")

    def test_preserves_short_lines(self, handler):
        """Test that short lines are unchanged."""
        short_line = "hello"

        result = handler._sanitize_and_truncate(short_line)

        assert result == short_line

    def test_ansi_codes_excluded_from_width_calc(self, handler):
        """Test that ANSI codes don't count toward width limit."""
        # 8 visible chars + ANSI codes
        line = "\033[31mRed text\033[0m"

        result = handler._sanitize_and_truncate(line)

        # Should not truncate since visible content is only 8 chars
        assert result == line

    # -------------------------------------------------------------------------
    # Edge Cases
    # -------------------------------------------------------------------------

    @patch("subprocess.Popen")
    def test_empty_output(self, mock_popen, handler):
        """Test handling of command with no output."""
        mock_process = Mock()
        mock_process.poll.return_value = 0
        mock_process.stdout = StringIO("")
        mock_popen.return_value = mock_process

        result = handler.run_with_streaming(["true"])

        assert result.returncode == 0
        assert result.stdout == ""

    def test_rolling_window_respects_max_lines(self, handler):
        """Test that deque enforces max_lines limit."""
        for i in range(15):
            handler.display_lines.append(f"line{i}")

        assert len(handler.display_lines) == handler.max_lines
        assert list(handler.display_lines)[0] == "line7"
        assert list(handler.display_lines)[-1] == "line14"

    @patch("subprocess.Popen")
    def test_state_reset_between_runs(self, mock_popen, handler):
        """Test that state is reset between runs."""
        mock_process = Mock()
        mock_process.poll.return_value = 0
        mock_process.stdout = StringIO("first\n")
        mock_popen.return_value = mock_process

        handler.run_with_streaming(["test1"])

        mock_process.stdout = StringIO("second\n")
        handler.run_with_streaming(["test2"])

        # Should not contain output from first run
        assert "first" not in handler.full_output
