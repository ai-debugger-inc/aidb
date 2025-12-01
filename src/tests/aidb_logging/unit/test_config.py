"""Tests for aidb_logging.config module."""

import logging
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from aidb_logging.config import (
    configure_logger,
    get_aidb_logger,
    get_cli_logger,
    get_mcp_logger,
    get_test_logger,
    setup_global_debug_logging,
    setup_root_logger,
)
from aidb_logging.filters import CallerFilter, SessionContextFilter
from aidb_logging.formatters import (
    ColoredFormatter,
    JSONFormatter,
    SafeFormatter,
    SessionFormatter,
)
from aidb_logging.handlers import HalvingFileHandler


class TestConfigureLogger:
    """Tests for configure_logger function."""

    def test_clears_existing_handlers(self, clean_logger: logging.Logger):
        """Test that existing handlers are cleared."""
        clean_logger.addHandler(logging.StreamHandler())
        clean_logger.addFilter(logging.Filter())

        configure_logger(clean_logger.name, profile="test")

        assert len(clean_logger.filters) > 0

    def test_sets_log_level_from_parameter(self, clean_logger: logging.Logger):
        """Test that log level is set from parameter."""
        configure_logger(clean_logger.name, profile="test", level="ERROR")
        assert clean_logger.level == logging.ERROR

    def test_uses_default_log_level_when_not_specified(
        self,
        clean_logger: logging.Logger,
    ):
        """Test that default log level is used when not specified."""
        with patch("aidb_logging.config.get_log_level", return_value="WARNING"):
            configure_logger(clean_logger.name, profile="test")
            assert clean_logger.level == logging.WARNING

    def test_raises_error_for_invalid_profile(self, clean_logger: logging.Logger):
        """Test that error is raised for invalid profile."""
        with pytest.raises(ValueError, match="Unknown profile"):
            configure_logger(clean_logger.name, profile="invalid")


class TestAidbProfile:
    """Tests for aidb profile configuration."""

    def test_adds_caller_filter(self, clean_logger: logging.Logger, tmp_path: Path):
        """Test that CallerFilter is added."""
        with patch("aidb_logging.config.should_use_file_logging", return_value=False):
            configure_logger(
                clean_logger.name,
                profile="aidb",
                log_file=str(tmp_path / "test.log"),
                to_console=True,
            )
            assert any(isinstance(f, CallerFilter) for f in clean_logger.filters)

    def test_adds_file_handler_when_enabled(
        self,
        clean_logger: logging.Logger,
        tmp_path: Path,
    ):
        """Test that file handler is added when enabled."""
        log_file = tmp_path / "test.log"
        with patch("aidb_logging.config.should_use_file_logging", return_value=True):
            configure_logger(
                clean_logger.name,
                profile="aidb",
                log_file=str(log_file),
            )
            assert any(isinstance(h, HalvingFileHandler) for h in clean_logger.handlers)

    def test_uses_safe_formatter(self, clean_logger: logging.Logger, tmp_path: Path):
        """Test that SafeFormatter is used."""
        with patch("aidb_logging.config.should_use_file_logging", return_value=False):
            configure_logger(
                clean_logger.name,
                profile="aidb",
                to_console=True,
            )
            handler = clean_logger.handlers[0]
            assert isinstance(handler.formatter, SafeFormatter)


class TestMcpProfile:
    """Tests for mcp profile configuration."""

    def test_adds_session_context_filter(
        self,
        clean_logger: logging.Logger,
        tmp_path: Path,
    ):
        """Test that SessionContextFilter is added."""
        with patch("aidb_logging.config.should_use_file_logging", return_value=False):
            configure_logger(clean_logger.name, profile="mcp")
            assert any(
                isinstance(f, SessionContextFilter) for f in clean_logger.filters
            )

    def test_adds_stderr_handler(self, clean_logger: logging.Logger):
        """Test that stderr handler is added."""
        with patch("aidb_logging.config.should_use_file_logging", return_value=False):
            configure_logger(clean_logger.name, profile="mcp")
            assert any(
                isinstance(h, logging.StreamHandler) and h.stream is sys.stderr
                for h in clean_logger.handlers
            )

    def test_uses_session_formatter_with_colors(
        self,
        clean_logger: logging.Logger,
    ):
        """Test that SessionFormatter with colors is used."""
        with patch("aidb_logging.config.should_use_file_logging", return_value=False):
            configure_logger(clean_logger.name, profile="mcp")
            handler = next(
                h for h in clean_logger.handlers if isinstance(h, logging.StreamHandler)
            )
            assert isinstance(handler.formatter, SessionFormatter)


class TestCliProfile:
    """Tests for cli profile configuration."""

    def test_adds_caller_filter(self, clean_logger: logging.Logger):
        """Test that CallerFilter is added."""
        with patch("aidb_logging.config.should_use_file_logging", return_value=False):
            configure_logger(
                clean_logger.name,
                profile="cli",
                to_console=True,
            )
            assert any(isinstance(f, CallerFilter) for f in clean_logger.filters)

    def test_uses_safe_formatter(self, clean_logger: logging.Logger):
        """Test that SafeFormatter is used."""
        with patch("aidb_logging.config.should_use_file_logging", return_value=False):
            configure_logger(
                clean_logger.name,
                profile="cli",
                to_console=True,
            )
            handler = clean_logger.handlers[0]
            assert isinstance(handler.formatter, SafeFormatter)

    def test_calls_setup_global_debug_when_verbose(
        self,
        clean_logger: logging.Logger,
        tmp_path: Path,
    ):
        """Test that setup_global_debug_logging is called when verbose_debug=True."""
        log_file = tmp_path / "test.log"
        with (
            patch("aidb_logging.config.should_use_file_logging", return_value=False),
            patch("aidb_logging.config.setup_global_debug_logging") as mock_setup,
        ):
            configure_logger(
                clean_logger.name,
                profile="cli",
                log_file=str(log_file),
                verbose_debug=True,
            )
            mock_setup.assert_called_once()


class TestTestProfile:
    """Tests for test profile configuration."""

    def test_adds_caller_filter(self, clean_logger: logging.Logger):
        """Test that CallerFilter is added."""
        with (
            patch("aidb_logging.config.should_use_file_logging", return_value=False),
            patch("aidb_common.env.reader.read_bool", return_value=False),
        ):
            configure_logger(clean_logger.name, profile="test")
            assert any(isinstance(f, CallerFilter) for f in clean_logger.filters)

    def test_enables_propagation_in_pytest(self, clean_logger: logging.Logger):
        """Test that propagation is enabled in pytest."""
        with (
            patch("aidb_logging.config.should_use_file_logging", return_value=False),
            patch.dict("sys.modules", {"pytest": Mock()}),
            patch("aidb_common.env.reader.read_bool", return_value=False),
        ):
            configure_logger(clean_logger.name, profile="test")
            assert clean_logger.propagate is True

    def test_disables_logger_when_requested(self, clean_logger: logging.Logger):
        """Test that logger is disabled when AIDB_TEST_LOGGING_DISABLED is set."""
        with patch("aidb_common.env.reader.read_bool", return_value=True):
            configure_logger(clean_logger.name, profile="test")
            assert clean_logger.disabled is True

    def test_sets_debug_level(self, clean_logger: logging.Logger):
        """Test that DEBUG level is set by default."""
        with (
            patch("aidb_logging.config.should_use_file_logging", return_value=False),
            patch("aidb_common.env.reader.read_bool", return_value=False),
        ):
            configure_logger(clean_logger.name, profile="test")
            assert clean_logger.level == logging.DEBUG


class TestCustomProfile:
    """Tests for custom profile configuration."""

    def test_uses_custom_formatter(self, clean_logger: logging.Logger):
        """Test that custom formatter is used."""
        custom_formatter = logging.Formatter("%(message)s")
        with patch("aidb_logging.config.should_use_file_logging", return_value=False):
            configure_logger(
                clean_logger.name,
                profile="custom",
                formatter=custom_formatter,
                to_console=True,
            )
            handler = clean_logger.handlers[0]
            assert handler.formatter is custom_formatter

    def test_uses_custom_filters(self, clean_logger: logging.Logger):
        """Test that custom filters are used."""
        custom_filter = logging.Filter()
        with patch("aidb_logging.config.should_use_file_logging", return_value=False):
            configure_logger(
                clean_logger.name,
                profile="custom",
                filters=[custom_filter],
                to_console=True,
            )
            assert custom_filter in clean_logger.filters

    def test_uses_custom_handlers(self, clean_logger: logging.Logger):
        """Test that custom handlers are used."""
        custom_handler = logging.StreamHandler()
        configure_logger(
            clean_logger.name,
            profile="custom",
            handlers=[custom_handler],
        )
        assert custom_handler in clean_logger.handlers


class TestSetupRootLogger:
    """Tests for setup_root_logger function."""

    def test_configures_root_logger(self):
        """Test that root logger is configured."""
        with (
            patch("aidb_logging.config.configure_logger") as mock_configure,
            patch("aidb_logging.config.should_use_file_logging", return_value=False),
        ):
            setup_root_logger("test")
            mock_configure.assert_called_once_with("", profile="test")


class TestConvenienceFunctions:
    """Tests for convenience logger functions."""

    def test_get_aidb_logger(self):
        """Test get_aidb_logger function."""
        with (
            patch("aidb_logging.config.configure_logger") as mock_configure,
            patch("aidb_logging.config.should_use_file_logging", return_value=False),
        ):
            get_aidb_logger("test")
            mock_configure.assert_called_once_with("test", profile="aidb")

    def test_get_mcp_logger(self):
        """Test get_mcp_logger function."""
        with (
            patch("aidb_logging.config.configure_logger") as mock_configure,
            patch("aidb_logging.config.should_use_file_logging", return_value=False),
        ):
            get_mcp_logger("test")
            mock_configure.assert_called_once_with("test", profile="mcp")

    def test_get_cli_logger(self):
        """Test get_cli_logger function."""
        with (
            patch("aidb_logging.config.configure_logger") as mock_configure,
            patch("aidb_logging.config.should_use_file_logging", return_value=False),
        ):
            get_cli_logger("test")
            mock_configure.assert_called_once_with("test", profile="cli")

    def test_get_test_logger(self):
        """Test get_test_logger function."""
        with (
            patch("aidb_logging.config.configure_logger") as mock_configure,
            patch("aidb_logging.config.should_use_file_logging", return_value=False),
        ):
            get_test_logger("test")
            mock_configure.assert_called_once_with("test", profile="test")


class TestSetupGlobalDebugLogging:
    """Tests for setup_global_debug_logging function."""

    def test_configures_root_logger_debug_level(self, tmp_path: Path):
        """Test that root logger is set to DEBUG."""
        log_file = tmp_path / "test.log"
        with patch.object(logging.Logger, "addHandler"):
            setup_global_debug_logging(str(log_file))
            root_logger = logging.getLogger()
            assert root_logger.level == logging.DEBUG

    def test_creates_log_directory(self, tmp_path: Path):
        """Test that log directory is created."""
        log_file = tmp_path / "subdir" / "test.log"
        with patch.object(logging.Logger, "addHandler"):
            setup_global_debug_logging(str(log_file))
            assert log_file.parent.exists()

    def test_prevents_duplicate_global_handlers(self, tmp_path: Path):
        """Test that duplicate handlers are not added."""
        log_file = tmp_path / "test.log"

        root_logger = logging.getLogger()
        initial_handler_count = len(root_logger.handlers)

        setup_global_debug_logging(str(log_file))
        count_after_first = len(root_logger.handlers)

        setup_global_debug_logging(str(log_file))
        count_after_second = len(root_logger.handlers)

        assert count_after_second == count_after_first

        for handler in root_logger.handlers[initial_handler_count:]:
            root_logger.removeHandler(handler)
            handler.close()

    def test_uses_default_log_file_when_none_specified(self, tmp_path: Path):
        """Test that default log file is used when none specified."""
        with (
            patch("aidb_logging.config.get_log_file_path") as mock_get_path,
            patch.object(logging.Logger, "addHandler"),
        ):
            mock_get_path.return_value = str(tmp_path / "cli.log")
            setup_global_debug_logging()
            mock_get_path.assert_called_once_with("cli")
