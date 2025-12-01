"""Unit tests for OutputStrategy."""

from unittest.mock import patch

import pytest

from aidb_cli.core.output.strategy import OutputStrategy
from aidb_cli.core.output.verbosity import Verbosity


class TestOutputStrategyInit:
    """Tests for OutputStrategy initialization."""

    def test_default_initialization(self):
        """Test default values are set correctly."""
        strategy = OutputStrategy()
        assert strategy.verbosity == Verbosity.NORMAL
        assert isinstance(strategy.is_tty, bool)
        assert isinstance(strategy.is_ci, bool)

    def test_explicit_verbosity(self):
        """Test explicit verbosity level is used."""
        strategy = OutputStrategy(verbosity=Verbosity.VERBOSE)
        assert strategy.verbosity == Verbosity.VERBOSE

        strategy = OutputStrategy(verbosity=Verbosity.DEBUG)
        assert strategy.verbosity == Verbosity.DEBUG

    def test_explicit_tty_setting(self):
        """Test explicit TTY setting overrides detection."""
        strategy = OutputStrategy(is_tty=True)
        assert strategy.is_tty is True

        strategy = OutputStrategy(is_tty=False)
        assert strategy.is_tty is False

    def test_explicit_ci_setting(self):
        """Test explicit CI setting overrides detection."""
        strategy = OutputStrategy(is_ci=True)
        assert strategy.is_ci is True

        strategy = OutputStrategy(is_ci=False)
        assert strategy.is_ci is False

    def test_last_was_blank_is_instance_variable(self):
        """Test _last_was_blank is an instance variable, not shared."""
        strategy1 = OutputStrategy()
        strategy2 = OutputStrategy()

        # Modify one instance's state
        strategy1._last_was_blank = True

        # Other instance should be unaffected
        assert strategy2._last_was_blank is False


class TestVerbosityFiltering:
    """Tests for verbosity-based output filtering."""

    def test_info_hidden_at_normal(self, capsys):
        """Test info() is hidden at NORMAL verbosity."""
        strategy = OutputStrategy(verbosity=Verbosity.NORMAL)
        strategy.info("test message")
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_info_visible_at_verbose(self, capsys):
        """Test info() is visible at VERBOSE verbosity."""
        strategy = OutputStrategy(verbosity=Verbosity.VERBOSE)
        strategy.info("test message")
        captured = capsys.readouterr()
        assert "test message" in captured.out

    def test_info_visible_at_debug(self, capsys):
        """Test info() is visible at DEBUG verbosity."""
        strategy = OutputStrategy(verbosity=Verbosity.DEBUG)
        strategy.info("test message")
        captured = capsys.readouterr()
        assert "test message" in captured.out

    def test_detail_hidden_at_normal(self, capsys):
        """Test detail() is hidden at NORMAL verbosity."""
        strategy = OutputStrategy(verbosity=Verbosity.NORMAL)
        strategy.detail("test message")
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_detail_visible_at_verbose(self, capsys):
        """Test detail() is visible at VERBOSE verbosity."""
        strategy = OutputStrategy(verbosity=Verbosity.VERBOSE)
        strategy.detail("test message")
        captured = capsys.readouterr()
        assert "test message" in captured.out

    def test_debug_hidden_at_normal(self, capsys):
        """Test debug() is hidden at NORMAL verbosity."""
        strategy = OutputStrategy(verbosity=Verbosity.NORMAL)
        strategy.debug("test message")
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_debug_hidden_at_verbose(self, capsys):
        """Test debug() is hidden at VERBOSE verbosity."""
        strategy = OutputStrategy(verbosity=Verbosity.VERBOSE)
        strategy.debug("test message")
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_debug_visible_at_debug(self, capsys):
        """Test debug() is visible at DEBUG verbosity."""
        strategy = OutputStrategy(verbosity=Verbosity.DEBUG)
        strategy.debug("test message")
        captured = capsys.readouterr()
        assert "[DEBUG]" in captured.out
        assert "test message" in captured.out


class TestAlwaysVisibleOutput:
    """Tests for always-visible output methods."""

    def test_plain_always_visible(self, capsys):
        """Test plain() is always visible."""
        strategy = OutputStrategy(verbosity=Verbosity.NORMAL)
        strategy.plain("test message")
        captured = capsys.readouterr()
        assert "test message" in captured.out

    def test_success_always_visible(self, capsys):
        """Test success() is always visible."""
        strategy = OutputStrategy(verbosity=Verbosity.NORMAL)
        strategy.success("test message")
        captured = capsys.readouterr()
        assert "test message" in captured.out

    def test_warning_always_visible(self, capsys):
        """Test warning() is always visible."""
        strategy = OutputStrategy(verbosity=Verbosity.NORMAL)
        strategy.warning("test message")
        captured = capsys.readouterr()
        assert "test message" in captured.out

    def test_error_always_visible(self, capsys):
        """Test error() is always visible."""
        strategy = OutputStrategy(verbosity=Verbosity.NORMAL)
        strategy.error("test message")
        captured = capsys.readouterr()
        assert "test message" in captured.err

    def test_error_to_stdout(self, capsys):
        """Test error() can output to stdout."""
        strategy = OutputStrategy(verbosity=Verbosity.NORMAL)
        strategy.error("test message", to_stderr=False)
        captured = capsys.readouterr()
        assert "test message" in captured.out
        assert captured.err == ""


class TestBlankLineCoalescing:
    """Tests for blank line coalescing behavior."""

    def test_single_blank_line_emitted(self, capsys):
        """Test a single blank line is emitted."""
        strategy = OutputStrategy(verbosity=Verbosity.NORMAL)
        strategy.plain("")
        captured = capsys.readouterr()
        assert captured.out == "\n"

    def test_consecutive_blanks_coalesced(self, capsys):
        """Test consecutive blank lines are coalesced to one."""
        strategy = OutputStrategy(verbosity=Verbosity.NORMAL)
        strategy.plain("")
        strategy.plain("")
        strategy.plain("")
        captured = capsys.readouterr()
        assert captured.out == "\n"

    def test_blank_reset_after_content(self, capsys):
        """Test blank line state resets after content."""
        strategy = OutputStrategy(verbosity=Verbosity.NORMAL)
        strategy.plain("")
        strategy.plain("content")
        strategy.plain("")
        captured = capsys.readouterr()
        assert captured.out == "\ncontent\n\n"


class TestShouldStream:
    """Tests for should_stream() method."""

    def test_no_streaming_at_normal(self):
        """Test streaming disabled at NORMAL verbosity."""
        strategy = OutputStrategy(verbosity=Verbosity.NORMAL, is_tty=True, is_ci=False)
        assert strategy.should_stream() is False

    def test_streaming_at_verbose_tty_non_ci(self):
        """Test streaming enabled at VERBOSE with TTY and not CI."""
        strategy = OutputStrategy(verbosity=Verbosity.VERBOSE, is_tty=True, is_ci=False)
        assert strategy.should_stream() is True

    def test_no_streaming_in_ci(self):
        """Test streaming disabled in CI even at VERBOSE."""
        strategy = OutputStrategy(verbosity=Verbosity.VERBOSE, is_tty=True, is_ci=True)
        assert strategy.should_stream() is False

    def test_no_streaming_without_tty(self):
        """Test streaming disabled without TTY even at VERBOSE."""
        strategy = OutputStrategy(
            verbosity=Verbosity.VERBOSE, is_tty=False, is_ci=False
        )
        assert strategy.should_stream() is False


class TestCIDetection:
    """Tests for CI environment detection."""

    def test_detects_ci_environment(self):
        """Test CI detection with CI=true."""
        with patch.dict("os.environ", {"CI": "true"}, clear=True):
            assert OutputStrategy._detect_ci() is True

    def test_detects_github_actions(self):
        """Test CI detection with GITHUB_ACTIONS."""
        with patch.dict("os.environ", {"GITHUB_ACTIONS": "true"}, clear=True):
            assert OutputStrategy._detect_ci() is True

    def test_no_ci_without_vars(self):
        """Test CI detection returns False without CI vars."""
        with patch.dict("os.environ", {}, clear=True):
            assert OutputStrategy._detect_ci() is False


class TestFromClickContext:
    """Tests for from_click_context factory method."""

    def test_creates_with_verbose(self):
        """Test factory creates VERBOSE strategy when verbose=True."""
        from unittest.mock import Mock

        ctx = Mock()
        ctx.obj = Mock()
        ctx.obj.verbose = True
        ctx.obj.verbose_debug = False

        strategy = OutputStrategy.from_click_context(ctx)
        assert strategy.verbosity == Verbosity.VERBOSE

    def test_creates_with_debug(self):
        """Test factory creates DEBUG strategy when verbose_debug=True."""
        from unittest.mock import Mock

        ctx = Mock()
        ctx.obj = Mock()
        ctx.obj.verbose = False
        ctx.obj.verbose_debug = True

        strategy = OutputStrategy.from_click_context(ctx)
        assert strategy.verbosity == Verbosity.DEBUG

    def test_handles_none_context_obj(self):
        """Test factory handles None context.obj gracefully."""
        from unittest.mock import Mock

        ctx = Mock()
        ctx.obj = None

        strategy = OutputStrategy.from_click_context(ctx)
        assert strategy.verbosity == Verbosity.NORMAL
