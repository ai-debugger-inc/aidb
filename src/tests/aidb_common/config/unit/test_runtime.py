"""Tests for runtime configuration module."""

import os
from pathlib import Path

import pytest

from aidb_common.config.runtime import ConfigManager


class TestConfigManagerSingleton:
    """Test ConfigManager singleton behavior."""

    def test_config_manager_is_singleton(self) -> None:
        """Test that ConfigManager returns same instance."""
        config1 = ConfigManager()
        config2 = ConfigManager()
        assert config1 is config2

    def test_config_manager_stub_returns_new_instance(self) -> None:
        """Test that stub parameter returns new instance."""
        config1 = ConfigManager()
        config_stub = ConfigManager(stub=True)
        assert config_stub is not config1


class TestLoggingConfiguration:
    """Test logging and debugging configuration methods."""

    def test_get_log_level_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test get_log_level returns default value."""
        monkeypatch.delenv("AIDB_LOG_LEVEL", raising=False)
        config = ConfigManager()
        assert config.get_log_level() == "INFO"

    def test_get_log_level_custom(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test get_log_level returns custom value."""
        monkeypatch.setenv("AIDB_LOG_LEVEL", "DEBUG")
        config = ConfigManager()
        assert config.get_log_level() == "DEBUG"

    def test_get_log_level_lowercase_converted(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test get_log_level converts to uppercase."""
        monkeypatch.setenv("AIDB_LOG_LEVEL", "debug")
        config = ConfigManager()
        assert config.get_log_level() == "DEBUG"

    def test_get_log_level_strips_whitespace(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test get_log_level strips whitespace."""
        monkeypatch.setenv("AIDB_LOG_LEVEL", "  WARNING  ")
        config = ConfigManager()
        assert config.get_log_level() == "WARNING"

    def test_is_adapter_trace_enabled_default(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test is_adapter_trace_enabled returns default False."""
        monkeypatch.delenv("AIDB_ADAPTER_TRACE", raising=False)
        config = ConfigManager()
        assert config.is_adapter_trace_enabled() is False

    def test_is_adapter_trace_enabled_true(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test is_adapter_trace_enabled with enabled trace."""
        monkeypatch.setenv("AIDB_ADAPTER_TRACE", "1")
        config = ConfigManager()
        assert config.is_adapter_trace_enabled() is True

    def test_is_breakpoint_validation_enabled_default(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test is_breakpoint_validation_enabled returns default True."""
        monkeypatch.delenv("AIDB_VALIDATE_BREAKPOINTS", raising=False)
        config = ConfigManager()
        assert config.is_breakpoint_validation_enabled() is True

    def test_is_breakpoint_validation_enabled_false(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test is_breakpoint_validation_enabled can be disabled."""
        monkeypatch.setenv("AIDB_VALIDATE_BREAKPOINTS", "false")
        config = ConfigManager()
        assert config.is_breakpoint_validation_enabled() is False

    def test_get_code_context_lines_default(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test get_code_context_lines returns default 5."""
        monkeypatch.delenv("AIDB_CODE_CONTEXT_LINES", raising=False)
        config = ConfigManager()
        assert config.get_code_context_lines() == 5

    def test_get_code_context_lines_custom(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test get_code_context_lines with custom value."""
        monkeypatch.setenv("AIDB_CODE_CONTEXT_LINES", "10")
        config = ConfigManager()
        assert config.get_code_context_lines() == 10

    def test_get_code_context_max_width_default(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test get_code_context_max_width returns default 120."""
        monkeypatch.delenv("AIDB_CODE_CONTEXT_MAX_LINE_WIDTH", raising=False)
        config = ConfigManager()
        assert config.get_code_context_max_width() == 120

    def test_get_code_context_max_width_custom(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test get_code_context_max_width with custom value."""
        monkeypatch.setenv("AIDB_CODE_CONTEXT_MAX_LINE_WIDTH", "80")
        config = ConfigManager()
        assert config.get_code_context_max_width() == 80

    def test_get_code_context_minified_mode_default(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test get_code_context_minified_mode returns default 'auto'."""
        monkeypatch.delenv("AIDB_CODE_CONTEXT_MINIFIED_MODE", raising=False)
        config = ConfigManager()
        assert config.get_code_context_minified_mode() == "auto"

    def test_get_code_context_minified_mode_valid_values(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test get_code_context_minified_mode with valid values."""
        for mode in ["auto", "force", "disable"]:
            monkeypatch.setenv("AIDB_CODE_CONTEXT_MINIFIED_MODE", mode)
            config = ConfigManager()
            assert config.get_code_context_minified_mode() == mode

    def test_get_code_context_minified_mode_invalid_falls_back(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test get_code_context_minified_mode falls back to 'auto' for invalid."""
        monkeypatch.setenv("AIDB_CODE_CONTEXT_MINIFIED_MODE", "invalid")
        config = ConfigManager()
        assert config.get_code_context_minified_mode() == "auto"

    def test_get_code_context_minified_mode_case_insensitive(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test get_code_context_minified_mode is case insensitive."""
        monkeypatch.setenv("AIDB_CODE_CONTEXT_MINIFIED_MODE", "FORCE")
        config = ConfigManager()
        assert config.get_code_context_minified_mode() == "force"


class TestAuditConfiguration:
    """Test audit logging configuration methods."""

    def test_is_audit_enabled_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test is_audit_enabled returns default False."""
        monkeypatch.delenv("AIDB_AUDIT_LOG", raising=False)
        config = ConfigManager()
        assert config.is_audit_enabled() is False

    def test_is_audit_enabled_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test is_audit_enabled with enabled audit."""
        monkeypatch.setenv("AIDB_AUDIT_LOG", "1")
        config = ConfigManager()
        assert config.is_audit_enabled() is True

    def test_get_audit_log_size_mb_default(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test get_audit_log_size_mb returns default 100."""
        monkeypatch.delenv("AIDB_AUDIT_LOG_MB", raising=False)
        config = ConfigManager()
        assert config.get_audit_log_size_mb() == 100

    def test_get_audit_log_size_mb_custom(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test get_audit_log_size_mb with custom value."""
        monkeypatch.setenv("AIDB_AUDIT_LOG_MB", "50")
        config = ConfigManager()
        assert config.get_audit_log_size_mb() == 50


class TestConfigConstants:
    """Test ConfigManager constants."""

    def test_constant_names_exist(self) -> None:
        """Test that expected constant names exist."""
        config = ConfigManager()
        assert hasattr(config, "AIDB_LOG_LEVEL")
        assert hasattr(config, "AIDB_ADAPTER_TRACE")
        assert hasattr(config, "AIDB_MCP_MAX_SESSIONS")

    def test_constants_are_strings(self) -> None:
        """Test that constants are string environment variable names."""
        config = ConfigManager()
        assert config.AIDB_LOG_LEVEL == "AIDB_LOG_LEVEL"
        assert config.AIDB_ADAPTER_TRACE == "AIDB_ADAPTER_TRACE"
        assert config.AIDB_MCP_MAX_SESSIONS == "AIDB_MCP_MAX_SESSIONS"

    def test_adapter_path_template(self) -> None:
        """Test adapter path template constant."""
        config = ConfigManager()
        assert config.ADAPTER_PATH_TEMPLATE == "AIDB_{}_ADAPTER_PATH"

    def test_adapter_version_template(self) -> None:
        """Test adapter version template constant."""
        config = ConfigManager()
        assert config.ADAPTER_VERSION_TEMPLATE == "AIDB_{}_VERSION"


class TestEnvironmentIsolation:
    """Test that ConfigManager properly reads from environment."""

    def test_clean_environment(self) -> None:
        """Test ConfigManager with clean environment."""
        for key in list(os.environ.keys()):
            if key.startswith("AIDB_"):
                del os.environ[key]

        config = ConfigManager()
        assert config.get_log_level() == "INFO"
        assert config.is_adapter_trace_enabled() is False

    def test_multiple_env_vars_simultaneously(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test ConfigManager with multiple environment variables set."""
        monkeypatch.setenv("AIDB_LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("AIDB_ADAPTER_TRACE", "1")
        monkeypatch.setenv("AIDB_CODE_CONTEXT_LINES", "15")

        config = ConfigManager()
        assert config.get_log_level() == "DEBUG"
        assert config.is_adapter_trace_enabled() is True
        assert config.get_code_context_lines() == 15
