"""Unit tests for StreamHandlerService."""

import subprocess
import threading
import time
from collections import deque
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from aidb.common.errors import AidbError
from aidb_cli.core.constants import ExitCode
from aidb_cli.services.command_executor.stream_handler_service import (
    StreamHandlerService,
)


class TestStreamHandlerService:
    """Test the StreamHandlerService."""

    @pytest.fixture
    def service(self):
        """Create service instance with default parameters."""
        return StreamHandlerService(
            max_lines=8,
            clear_on_exit=True,
            supports_ansi=True,
            terminal_width=80,
        )

    @pytest.fixture
    def service_no_ansi(self):
        """Create service instance without ANSI support."""
        return StreamHandlerService(
            max_lines=8,
            clear_on_exit=False,
            supports_ansi=False,
            terminal_width=80,
        )

    # -------------------------------------------------------------------------
    # Initialization Tests (3 tests)
    # -------------------------------------------------------------------------

    def test_initialization_default_params(self, service):
        """Test service initialization with default parameters."""
        assert service.max_lines == 8
        assert service.clear_on_exit is True
        assert service.supports_ansi is True
        assert service.terminal_width == 80
        assert isinstance(service.display_lines, deque)
        assert service.display_lines.maxlen == 8
        assert service.full_output == []
        assert service.process is None
        assert isinstance(service._stop_event, threading.Event)
        assert service._frame_initialized is False
        assert service._current_window_size == 0
        assert service._min_render_interval == 0.08
        assert service._has_output is False

    def test_initialization_custom_params(self):
        """Test service initialization with custom parameters."""
        service = StreamHandlerService(
            max_lines=15,
            clear_on_exit=False,
            supports_ansi=False,
            terminal_width=120,
        )
        assert service.max_lines == 15
        assert service.clear_on_exit is False
        assert service.supports_ansi is False
        assert service.terminal_width == 120
        assert service.display_lines.maxlen == 15

    def test_initialization_internal_state(self, service):
        """Test internal state initialization."""
        assert hasattr(service, "_display_lock")
        assert isinstance(service._display_lock, type(threading.Lock()))
        assert service._last_render_time == 0.0
        assert not service._stop_event.is_set()

    # -------------------------------------------------------------------------
    # run_with_streaming() - Happy Path Tests (6 tests)
    # -------------------------------------------------------------------------

    @patch("subprocess.Popen")
    @patch("time.sleep")
    def test_run_with_streaming_success(self, mock_sleep, mock_popen, service):
        """Test successful command execution."""
        mock_process = Mock()
        # Process completes on second poll check
        mock_process.poll.side_effect = [None, 0, 0, 0]
        mock_process.stdout = StringIO("line1\nline2\nline3\n")
        mock_popen.return_value = mock_process

        result = service.run_with_streaming(["echo", "test"])

        assert isinstance(result, subprocess.CompletedProcess)
        assert result.returncode == 0
        assert result.args == ["echo", "test"]
        assert result.stderr == ""

    @patch("subprocess.Popen")
    @patch("time.sleep")
    def test_run_with_streaming_returns_completed_process(
        self,
        mock_sleep,
        mock_popen,
        service,
    ):
        """Test that run_with_streaming returns CompletedProcess with correct fields."""
        mock_process = Mock()
        # poll() called in: loop (2x), get returncode (1x), finally cleanup (2x)
        mock_process.poll.side_effect = [None, 0, 0, 0, 0]
        mock_process.stdout = StringIO("output line\n")
        mock_popen.return_value = mock_process

        result = service.run_with_streaming(["test", "cmd"])

        assert result.args == ["test", "cmd"]
        assert result.returncode == 0
        assert isinstance(result.stdout, str)
        assert result.stderr == ""

    @patch("subprocess.Popen")
    def test_run_with_streaming_full_output_populated(self, mock_popen, service):
        """Test that full_output is populated correctly."""
        mock_process = Mock()
        # poll() is called multiple times in loop, need enough None values
        mock_process.poll.side_effect = [None] * 3 + [0] * 5
        mock_process.stdout = StringIO("line1\nline2\nline3\n")
        mock_popen.return_value = mock_process

        # Give threads time to read
        with patch.object(service, "_read_stream") as mock_read:

            def read_side_effect(stream):
                service.full_output.extend(["line1", "line2", "line3"])

            mock_read.side_effect = read_side_effect
            service.run_with_streaming(["test"])

            assert len(service.full_output) == 3

    @patch("subprocess.Popen")
    def test_run_with_streaming_python_gets_unbuffered_flag(self, mock_popen, service):
        """Test that Python commands get -u flag for unbuffered output."""
        mock_process = Mock()
        mock_process.poll.return_value = 0
        mock_process.stdout = StringIO("")
        mock_popen.return_value = mock_process

        service.run_with_streaming(["python", "script.py"])

        call_args = mock_popen.call_args[0][0]
        assert call_args == ["python", "-u", "script.py"]

    @patch("subprocess.Popen")
    def test_run_with_streaming_python3_gets_unbuffered_flag(
        self,
        mock_popen,
        service,
    ):
        """Test that python3 commands also get -u flag."""
        mock_process = Mock()
        mock_process.poll.return_value = 0
        mock_process.stdout = StringIO("")
        mock_popen.return_value = mock_process

        service.run_with_streaming(["python3", "-m", "pytest"])

        call_args = mock_popen.call_args[0][0]
        assert call_args == ["python3", "-u", "-m", "pytest"]

    @patch("subprocess.Popen")
    def test_run_with_streaming_cwd_and_env_honored(
        self,
        mock_popen,
        service,
        tmp_path,
    ):
        """Test that working directory and environment are passed through."""
        mock_process = Mock()
        mock_process.poll.return_value = 0
        mock_process.stdout = StringIO("")
        mock_popen.return_value = mock_process

        test_env = {"TEST_VAR": "value"}
        service.run_with_streaming(["ls"], cwd=tmp_path, env=test_env)

        assert mock_popen.call_args[1]["cwd"] == tmp_path
        assert mock_popen.call_args[1]["env"] == test_env

    # -------------------------------------------------------------------------
    # run_with_streaming() - Error Handling Tests (7 tests)
    # -------------------------------------------------------------------------

    @patch("subprocess.Popen")
    def test_run_with_streaming_failure_with_check_raises(self, mock_popen, service):
        """Test that command failure with check=True raises AidbError."""
        mock_process = Mock()
        mock_process.poll.return_value = 1
        mock_process.stdout = StringIO("error output\n")
        mock_popen.return_value = mock_process

        with pytest.raises(AidbError) as exc_info:
            service.run_with_streaming(["failing", "command"], check=True)

        assert "failed with exit code 1" in str(exc_info.value)

    @patch("subprocess.Popen")
    def test_run_with_streaming_failure_without_check_returns_result(
        self,
        mock_popen,
        service,
    ):
        """Test that command failure with check=False returns CompletedProcess."""
        mock_process = Mock()
        mock_process.poll.return_value = 42
        mock_process.stdout = StringIO("")
        mock_popen.return_value = mock_process

        result = service.run_with_streaming(["failing", "command"], check=False)

        assert result.returncode == 42
        assert isinstance(result, subprocess.CompletedProcess)

    @patch("subprocess.Popen")
    def test_run_with_streaming_file_not_found_with_check(self, mock_popen, service):
        """Test FileNotFoundError handling when check=True."""
        mock_popen.side_effect = FileNotFoundError("command not found")

        with pytest.raises(AidbError) as exc_info:
            service.run_with_streaming(["nonexistent"], check=True)

        assert "Command not found: nonexistent" in str(exc_info.value)

    @patch("subprocess.Popen")
    def test_run_with_streaming_file_not_found_without_check(
        self,
        mock_popen,
        service,
    ):
        """Test FileNotFoundError handling when check=False."""
        mock_popen.side_effect = FileNotFoundError("command not found")

        result = service.run_with_streaming(["nonexistent"], check=False)

        assert result.returncode == ExitCode.NOT_FOUND
        assert result.stdout == ""
        assert "command not found" in result.stderr.lower()

    @patch("subprocess.Popen")
    @patch("time.time")
    def test_run_with_streaming_timeout_raises(self, mock_time, mock_popen, service):
        """Test that timeout raises TimeoutError."""
        mock_process = Mock()
        mock_process.poll.return_value = None  # Never completes
        mock_process.stdout = StringIO("")
        mock_popen.return_value = mock_process

        # Simulate time passing
        mock_time.side_effect = [0, 0, 5.5]  # Start, check, timeout exceeded

        with pytest.raises(TimeoutError) as exc_info:
            service.run_with_streaming(["slow", "command"], timeout=5.0)

        assert "timed out after 5" in str(exc_info.value).lower()

    @patch("subprocess.Popen")
    @patch("time.time")
    def test_run_with_streaming_timeout_terminates_process(
        self,
        mock_time,
        mock_popen,
        service,
    ):
        """Test that process is terminated on timeout."""
        mock_process = Mock()
        # Need enough None values for loop iterations, then 0 after terminate
        mock_process.poll.side_effect = [None] * 10 + [0] * 5
        mock_process.stdout = StringIO("")
        mock_popen.return_value = mock_process

        mock_time.side_effect = [0, 0, 6.0]

        with pytest.raises(TimeoutError):
            service.run_with_streaming(["slow", "command"], timeout=5.0)

        # terminate() is called in timeout handler AND finally cleanup
        assert mock_process.terminate.call_count >= 1

    @patch("subprocess.Popen")
    @patch("time.time")
    def test_run_with_streaming_timeout_kills_if_terminate_fails(
        self,
        mock_time,
        mock_popen,
        service,
    ):
        """Test that process is killed if terminate fails."""
        mock_process = Mock()
        # Need enough values for loop + terminate + kill checks
        mock_process.poll.side_effect = [None] * 12 + [0] * 5
        mock_process.stdout = StringIO("")
        mock_popen.return_value = mock_process

        mock_time.side_effect = [0, 0, 6.0]

        with pytest.raises(TimeoutError):
            service.run_with_streaming(["slow", "command"], timeout=5.0)

        # terminate() called in timeout handler AND finally cleanup
        assert mock_process.terminate.call_count >= 1
        assert mock_process.kill.call_count >= 1

    # -------------------------------------------------------------------------
    # Threading & Output Capture Tests (5 tests)
    # -------------------------------------------------------------------------

    def test_read_stream_populates_display_lines(self, service):
        """Test that _read_stream populates display_lines."""
        stream = StringIO("line1\nline2\nline3\n")

        service._read_stream(stream)

        assert len(service.display_lines) == 3
        assert list(service.display_lines) == ["line1", "line2", "line3"]

    def test_read_stream_populates_full_output(self, service):
        """Test that _read_stream populates full_output."""
        stream = StringIO("line1\nline2\nline3\n")

        service._read_stream(stream)

        assert service.full_output == ["line1", "line2", "line3"]

    def test_read_stream_respects_stop_event(self, service):
        """Test that _read_stream stops when _stop_event is set."""
        stream = StringIO("line1\nline2\nline3\n")
        service._stop_event.set()

        service._read_stream(stream)

        # Should not read anything since stop event is set
        assert len(service.full_output) == 0

    def test_read_stream_handles_none_stream(self, service):
        """Test that _read_stream handles None stream gracefully."""
        service._read_stream(None)

        assert service.full_output == []
        assert len(service.display_lines) == 0

    def test_read_stream_strips_newlines(self, service):
        """Test that _read_stream strips trailing newlines."""
        stream = StringIO("line1\r\nline2\nline3\r\n")

        service._read_stream(stream)

        assert service.full_output == ["line1", "line2", "line3"]

    # -------------------------------------------------------------------------
    # Display Rendering Tests (4 tests)
    # -------------------------------------------------------------------------

    @patch("builtins.print")
    def test_update_display_with_ansi_support(self, mock_print, service):
        """Test _update_display with ANSI support."""
        service.display_lines.extend(["line1", "line2", "line3"])

        service._update_display()

        assert service._has_output is True
        # Should have printed ANSI codes and lines
        assert mock_print.call_count > 0

    @patch("builtins.print")
    def test_update_display_fallback_no_ansi(self, mock_print, service_no_ansi):
        """Test _update_display fallback when ANSI not supported."""
        service_no_ansi.display_lines.extend(["line1", "line2", "line3"])
        service_no_ansi.full_output.extend(["line1", "line2", "line3"])

        service_no_ansi._update_display()

        assert service_no_ansi._has_output is True
        # Should print all lines in non-ANSI mode (line by line)
        assert mock_print.call_count == 3

    def test_update_display_sets_has_output_flag(self, service):
        """Test that _update_display sets _has_output flag."""
        service.display_lines.append("test line")
        assert service._has_output is False

        service._update_display()

        assert service._has_output is True

    def test_update_display_no_output_does_nothing(self, service):
        """Test that _update_display does nothing with no output."""
        initial_has_output = service._has_output

        service._update_display()

        assert service._has_output == initial_has_output

    # -------------------------------------------------------------------------
    # ANSI Operations Tests (4 tests)
    # -------------------------------------------------------------------------

    @patch("builtins.print")
    def test_ansi_cursor_up_outputs_correct_escape(self, mock_print, service):
        """Test _ansi_cursor_up outputs correct ANSI escape code."""
        service._ansi_cursor_up(5)

        mock_print.assert_called_once_with("\033[5A", end="")

    @patch("builtins.print")
    def test_ansi_cursor_up_zero_does_nothing(self, mock_print, service):
        """Test _ansi_cursor_up with 0 does nothing."""
        service._ansi_cursor_up(0)

        mock_print.assert_not_called()

    @patch("builtins.print")
    def test_ansi_clear_line_outputs_correct_escape(self, mock_print, service):
        """Test _ansi_clear_line outputs correct ANSI escape code."""
        service._ansi_clear_line()

        mock_print.assert_called_once_with("\033[K", end="")

    @patch("builtins.print")
    @patch("sys.stdout.flush")
    def test_clear_display_clears_window(self, mock_flush, mock_print, service):
        """Test _clear_display clears the display window."""
        service._has_output = True
        service._current_window_size = 3
        service._frame_initialized = True

        service._clear_display()

        # Should reset state
        assert service._current_window_size == 0
        assert service._frame_initialized is False
        # Should have printed ANSI clear codes
        assert mock_print.call_count > 0

    # -------------------------------------------------------------------------
    # Sanitization Tests (3 tests)
    # -------------------------------------------------------------------------

    def test_sanitize_and_truncate_removes_ansi_from_width_calc(self, service):
        """Test that ANSI codes are removed for width calculation."""
        line_with_ansi = "\033[31mRed text\033[0m"
        result = service._sanitize_and_truncate(line_with_ansi)

        # Should preserve ANSI but calculate width without it
        assert "\033[31m" in result
        assert len(result) <= service.terminal_width

    def test_sanitize_and_truncate_truncates_long_lines(self, service):
        """Test that lines longer than terminal_width are truncated."""
        long_line = "a" * 100
        result = service._sanitize_and_truncate(long_line)

        assert len(result) == service.terminal_width
        assert result.endswith("...")

    def test_sanitize_and_truncate_preserves_short_lines(self, service):
        """Test that lines under width limit are preserved."""
        short_line = "short line"
        result = service._sanitize_and_truncate(short_line)

        assert result == short_line

    # -------------------------------------------------------------------------
    # Edge Cases Tests (3 tests)
    # -------------------------------------------------------------------------

    @patch("subprocess.Popen")
    def test_empty_command_output(self, mock_popen, service):
        """Test handling of command with no output."""
        mock_process = Mock()
        mock_process.poll.return_value = 0
        mock_process.stdout = StringIO("")
        mock_popen.return_value = mock_process

        result = service.run_with_streaming(["echo", "-n", ""])

        assert result.returncode == 0
        assert result.stdout == ""

    def test_very_long_lines_truncated(self, service):
        """Test that very long lines are properly truncated."""
        very_long_line = "x" * 200
        service.display_lines.append(very_long_line)

        result = service._sanitize_and_truncate(very_long_line)

        assert len(result) == service.terminal_width
        assert result.endswith("...")

    def test_rolling_window_respects_max_lines(self, service):
        """Test that rolling window respects max_lines limit."""
        # Add more lines than max_lines
        for i in range(15):
            service.display_lines.append(f"line{i}")

        # deque should only keep last max_lines
        assert len(service.display_lines) == service.max_lines
        assert list(service.display_lines)[-1] == "line14"
        assert list(service.display_lines)[0] == "line7"

    # -------------------------------------------------------------------------
    # Additional Coverage Tests (2 tests)
    # -------------------------------------------------------------------------

    @patch("subprocess.Popen")
    def test_state_reset_between_runs(self, mock_popen, service):
        """Test that state is properly reset between runs."""
        mock_process = Mock()
        mock_process.poll.return_value = 0
        mock_process.stdout = StringIO("line1\n")
        mock_popen.return_value = mock_process

        # First run
        service.run_with_streaming(["test1"])
        first_output = service.full_output.copy()

        # Verify first run populated output
        assert len(first_output) > 0

        # Second run should reset state
        mock_process.stdout = StringIO("line2\n")
        service.run_with_streaming(["test2"])

        # full_output should be fresh (not accumulated from first run)
        assert "line1" not in service.full_output
        assert len(service.display_lines) <= service.max_lines

    @patch("subprocess.Popen")
    def test_clear_display_no_op_without_output(self, mock_popen, service):
        """Test _clear_display is no-op if no output was shown."""
        service._has_output = False
        service._current_window_size = 0

        # Should not raise and should do nothing
        service._clear_display()

        assert service._has_output is False
