"""Unit tests for TtyDetectionService."""

import os
import sys
from unittest.mock import Mock, patch

import pytest

from aidb_cli.core.constants import EnvVars
from aidb_cli.services.command_executor.tty_detection_service import (
    TtyDetectionService,
)


class TestTtyDetectionService:
    """Test the TtyDetectionService."""

    @pytest.fixture
    def service(self):
        """Create service instance without CLI context."""
        return TtyDetectionService(ctx=None)

    @pytest.fixture
    def mock_ctx(self):
        """Create a mock CLI context with resolved environment."""
        ctx = Mock()
        ctx.obj = Mock()
        ctx.obj.resolved_env = {
            "PATH": "/usr/bin:/bin",
            "HOME": "/home/user",
        }
        return ctx

    @pytest.fixture
    def service_with_ctx(self, mock_ctx):
        """Create service instance with CLI context."""
        return TtyDetectionService(ctx=mock_ctx)

    def test_init_without_context_uses_os_environ_fallback(self, service):
        """Test initialization without context falls back to os.environ."""
        assert service.ctx is None
        assert service._env is None
        assert service._is_ci is None
        assert service._is_tty is None
        assert service._supports_ansi is None

    def test_init_with_context_uses_resolved_env(self, service_with_ctx, mock_ctx):
        """Test initialization with context uses resolved environment."""
        assert service_with_ctx.ctx == mock_ctx
        assert service_with_ctx._env == mock_ctx.obj.resolved_env

    def test_is_ci_returns_false_when_no_ci_vars_set(self, service):
        """Test is_ci returns False when no CI environment variables set."""
        with patch.dict(os.environ, {}, clear=True):
            assert service.is_ci is False

    def test_is_ci_detects_ci_via_generic_ci_var(self, service):
        """Test is_ci detects CI environment via CI variable."""
        with patch.dict(os.environ, {"CI": "true"}, clear=True):
            service._is_ci = None
            assert service.is_ci is True

    def test_is_ci_detects_github_actions(self, service):
        """Test is_ci detects GitHub Actions environment."""
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}, clear=True):
            service._is_ci = None
            assert service.is_ci is True

    def test_is_ci_detects_gitlab_ci(self, service):
        """Test is_ci detects GitLab CI environment."""
        with patch.dict(os.environ, {"GITLAB_CI": "true"}, clear=True):
            service._is_ci = None
            assert service.is_ci is True

    def test_is_ci_detects_jenkins(self, service):
        """Test is_ci detects Jenkins environment."""
        with patch.dict(os.environ, {"JENKINS_HOME": "/var/jenkins"}, clear=True):
            service._is_ci = None
            assert service.is_ci is True

    def test_is_ci_detects_github_workflow(self, service):
        """Test is_ci detects GitHub Actions via GITHUB_WORKFLOW."""
        with patch.dict(os.environ, {"GITHUB_WORKFLOW": "test"}, clear=True):
            service._is_ci = None
            assert service.is_ci is True

    def test_is_ci_caches_result(self, service):
        """Test is_ci property caches the result."""
        with patch.dict(os.environ, {}, clear=True):
            first_result = service.is_ci
            service._env = {"CI": "true"}
            second_result = service.is_ci
            assert first_result == second_result
            assert first_result is False

    @patch("sys.stdout.isatty")
    def test_is_tty_returns_true_when_stdout_is_tty(self, mock_isatty, service):
        """Test is_tty returns True when sys.stdout.isatty() is True."""
        mock_isatty.return_value = True
        service._is_tty = None

        assert service.is_tty is True

    @patch("sys.stdout.isatty")
    def test_is_tty_returns_false_when_not_tty(self, mock_isatty, service):
        """Test is_tty returns False when not a TTY."""
        mock_isatty.return_value = False
        service._is_tty = None

        assert service.is_tty is False

    @patch("sys.stdout.isatty")
    def test_is_tty_caches_result(self, mock_isatty, service):
        """Test is_tty property caches the result."""
        mock_isatty.return_value = True
        first_result = service.is_tty
        mock_isatty.return_value = False
        second_result = service.is_tty

        assert first_result == second_result
        assert first_result is True

    @patch("sys.stdout.isatty")
    def test_supports_ansi_true_when_is_tty(self, mock_isatty, service):
        """Test supports_ansi returns True when is_tty is True."""
        mock_isatty.return_value = True
        service._is_tty = None
        service._supports_ansi = None

        with patch.dict(os.environ, {}, clear=True):
            assert service.supports_ansi is True

    @patch("sys.stdout.isatty")
    def test_supports_ansi_true_with_force_ansi_env_var(self, mock_isatty, service):
        """Test supports_ansi returns True when AIDB_CLI_FORCE_ANSI is set."""
        mock_isatty.return_value = False
        service._is_tty = None
        service._supports_ansi = None

        with patch.dict(os.environ, {EnvVars.CLI_FORCE_ANSI: "true"}, clear=True):
            assert service.supports_ansi is True

    @patch("sys.stdout.isatty")
    def test_supports_ansi_false_when_not_tty_and_no_force(
        self,
        mock_isatty,
        service,
    ):
        """Test supports_ansi returns False when not TTY and no force flag."""
        mock_isatty.return_value = False
        service._is_tty = None
        service._supports_ansi = None

        with patch.dict(os.environ, {}, clear=True):
            assert service.supports_ansi is False

    @patch("sys.stdout.isatty")
    def test_should_stream_returns_false_in_ci(self, mock_isatty, service):
        """Test should_stream returns False in CI environment."""
        mock_isatty.return_value = True
        service._is_tty = None
        service._is_ci = None

        with patch.dict(os.environ, {"CI": "true"}, clear=True):
            assert service.should_stream(verbose=False) is False

    @patch("sys.stdout.isatty")
    def test_should_stream_returns_true_with_tty_not_ci(self, mock_isatty, service):
        """Test should_stream returns True when TTY and not CI."""
        mock_isatty.return_value = True
        service._is_tty = None
        service._is_ci = None

        with patch.dict(os.environ, {}, clear=True):
            assert service.should_stream(verbose=False) is True

    @patch("sys.stdout.isatty")
    def test_should_stream_force_streaming_overrides(self, mock_isatty, service):
        """Test should_stream with AIDB_CLI_FORCE_STREAMING overrides all."""
        mock_isatty.return_value = False
        service._is_tty = None
        service._is_ci = None

        with patch.dict(
            os.environ,
            {"CI": "true", EnvVars.CLI_FORCE_STREAMING: "true"},
            clear=True,
        ):
            assert service.should_stream(verbose=False) is True

    @patch("sys.stdout.isatty")
    def test_should_stream_respects_verbose_param(self, mock_isatty, service):
        """Test should_stream respects verbose parameter."""
        mock_isatty.return_value = True
        service._is_tty = None
        service._is_ci = None

        with patch.dict(os.environ, {}, clear=True):
            assert service.should_stream(verbose=True) is True
            assert service.should_stream(verbose=False) is True

    @patch("sys.stdout.isatty")
    def test_should_stream_for_verbosity_false_in_ci(self, mock_isatty, service):
        """Test should_stream_for_verbosity returns False in CI."""
        mock_isatty.return_value = True
        service._is_tty = None
        service._is_ci = None

        with patch.dict(os.environ, {"CI": "true"}, clear=True):
            assert service.should_stream_for_verbosity(verbose=True) is False

    @patch("sys.stdout.isatty")
    def test_should_stream_for_verbosity_false_with_no_verbose_flags(
        self,
        mock_isatty,
        service,
    ):
        """Test should_stream_for_verbosity returns False with no verbose flags."""
        mock_isatty.return_value = True
        service._is_tty = None
        service._is_ci = None

        with patch.dict(os.environ, {}, clear=True):
            assert service.should_stream_for_verbosity(verbose=False) is False

    @patch("sys.stdout.isatty")
    def test_should_stream_for_verbosity_true_with_verbose_and_tty(
        self,
        mock_isatty,
        service,
    ):
        """Test should_stream_for_verbosity returns True with -v and TTY."""
        mock_isatty.return_value = True
        service._is_tty = None
        service._is_ci = None

        with patch.dict(os.environ, {}, clear=True):
            assert (
                service.should_stream_for_verbosity(verbose=True, verbose_debug=False)
                is True
            )

    @patch("sys.stdout.isatty")
    def test_should_stream_for_verbosity_true_with_verbose_debug_and_tty(
        self,
        mock_isatty,
        service,
    ):
        """Test should_stream_for_verbosity returns True with -vvv and TTY."""
        mock_isatty.return_value = True
        service._is_tty = None
        service._is_ci = None

        with patch.dict(os.environ, {}, clear=True):
            assert (
                service.should_stream_for_verbosity(verbose=False, verbose_debug=True)
                is True
            )

    @patch("sys.stdout.isatty")
    def test_should_stream_for_verbosity_false_with_verbose_but_no_tty(
        self,
        mock_isatty,
        service,
    ):
        """Test should_stream_for_verbosity returns False with verbose but no TTY."""
        mock_isatty.return_value = False
        service._is_tty = None
        service._is_ci = None

        with patch.dict(os.environ, {}, clear=True):
            assert (
                service.should_stream_for_verbosity(verbose=True, verbose_debug=False)
                is False
            )

    @patch("shutil.get_terminal_size")
    def test_get_terminal_width_returns_actual_width(
        self,
        mock_get_size,
        service,
    ):
        """Test get_terminal_width returns actual width from shutil."""
        from collections import namedtuple

        Size = namedtuple("Size", ["columns", "lines"])
        mock_get_size.return_value = Size(columns=120, lines=40)

        width = service.get_terminal_width()

        assert width == 120
        mock_get_size.assert_called_once_with(fallback=(80, 24))

    @patch("shutil.get_terminal_size")
    def test_get_terminal_width_returns_fallback_on_exception(
        self,
        mock_get_size,
        service,
    ):
        """Test get_terminal_width returns fallback on exception."""
        mock_get_size.side_effect = Exception("Terminal size unavailable")

        width = service.get_terminal_width(fallback=100)

        assert width == 100

    @patch("shutil.get_terminal_size")
    def test_get_terminal_width_default_fallback(self, mock_get_size, service):
        """Test get_terminal_width uses default fallback of 80."""
        mock_get_size.side_effect = Exception("Terminal size unavailable")

        width = service.get_terminal_width()

        assert width == 80

    def test_detect_ci_environment_uses_resolved_env_from_ctx(self):
        """Test _detect_ci_environment uses resolved_env from context."""
        ctx = Mock()
        ctx.obj = Mock()
        ctx.obj.resolved_env = {"TRAVIS": "true"}
        service = TtyDetectionService(ctx=ctx)

        assert service._detect_ci_environment() is True

    def test_detect_ci_environment_falls_back_to_os_environ(self, service):
        """Test _detect_ci_environment falls back to os.environ when no context."""
        with patch.dict(os.environ, {"CIRCLECI": "true"}, clear=True):
            assert service._detect_ci_environment() is True
