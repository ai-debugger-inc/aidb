"""Unit tests for ExecutionService from command_executor package."""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from aidb.common.errors import AidbError
from aidb_cli.core.constants import ExitCode
from aidb_cli.services.command_executor.execution_service import (
    ExecutionService,
)


class TestExecutionService:
    """Test the ExecutionService."""

    @pytest.fixture
    def service(self):
        """Create service instance without CLI context."""
        return ExecutionService(ctx=None)

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
        return ExecutionService(ctx=mock_ctx)

    def test_init_without_context(self, service):
        """Test initialization without context."""
        assert service.ctx is None
        assert service._env_service is not None
        assert service._env is None

    def test_init_with_context(self, service_with_ctx, mock_ctx):
        """Test initialization with context."""
        assert service_with_ctx.ctx == mock_ctx
        assert service_with_ctx._env_service is not None
        assert service_with_ctx._env == mock_ctx.obj.resolved_env

    @patch("subprocess.run")
    def test_execute_success(self, mock_run, service):
        """Test successful command execution."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="output",
            stderr="",
        )

        result = service.execute(["echo", "test"])

        assert result.returncode == 0
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_execute_with_cwd(self, mock_run, service, tmp_path):
        """Test execution with working directory."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        service.execute(["ls"], cwd=tmp_path)

        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["cwd"] == tmp_path

    @patch("subprocess.run")
    def test_execute_with_env(self, mock_run, service):
        """Test execution with environment variables."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
        env = {"TEST_VAR": "test_value"}

        service.execute(["echo", "test"], env=env)

        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["env"] == env

    @patch("subprocess.run")
    def test_execute_capture_output(self, mock_run, service):
        """Test execution with output capture."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="captured",
            stderr="",
        )

        result = service.execute(["echo", "test"], capture_output=True)

        assert result.returncode == 0
        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["capture_output"] is True

    @patch("subprocess.run")
    def test_execute_failure_check_true(self, mock_run, service):
        """Test failed command with check=True raises AidbError."""
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="error message",
        )

        with pytest.raises(AidbError) as exc_info:
            service.execute(["false"], check=True)

        assert "Command failed with exit code 1" in str(exc_info.value)
        assert "error message" in str(exc_info.value)

    @patch("subprocess.run")
    def test_execute_failure_check_false(self, mock_run, service):
        """Test failed command with check=False returns result."""
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="error",
        )

        result = service.execute(["false"], check=False)

        assert result.returncode == 1

    @patch("subprocess.run")
    def test_execute_timeout_check_true(self, mock_run, service):
        """Test timeout with check=True raises AidbError."""
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd=["sleep", "10"],
            timeout=1,
        )

        with pytest.raises(AidbError) as exc_info:
            service.execute(["sleep", "10"], timeout=1, check=True)

        assert "timed out after 1 seconds" in str(exc_info.value)

    @patch("subprocess.run")
    def test_execute_timeout_check_false(self, mock_run, service):
        """Test timeout with check=False returns CompletedProcess."""
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd=["sleep", "10"],
            timeout=1,
        )

        result = service.execute(["sleep", "10"], timeout=1, check=False)

        assert result.returncode == ExitCode.TIMEOUT
        assert result.args == ["sleep", "10"]

    @patch("subprocess.run")
    def test_execute_file_not_found_check_true(self, mock_run, service):
        """Test FileNotFoundError with check=True raises AidbError."""
        mock_run.side_effect = FileNotFoundError("command not found")

        with pytest.raises(AidbError) as exc_info:
            service.execute(["nonexistent"], check=True)

        assert "Command not found: nonexistent" in str(exc_info.value)

    @patch("subprocess.run")
    def test_execute_file_not_found_check_false(self, mock_run, service):
        """Test FileNotFoundError with check=False returns result."""
        mock_run.side_effect = FileNotFoundError("command not found")

        result = service.execute(["nonexistent"], check=False)

        assert result.returncode == ExitCode.NOT_FOUND
        assert result.args == ["nonexistent"]

    @patch("subprocess.Popen")
    def test_create_process_success(self, mock_popen, service):
        """Test successful process creation."""
        mock_process = Mock()
        mock_popen.return_value = mock_process

        result = service.create_process(["echo", "test"])

        assert result == mock_process
        mock_popen.assert_called_once()

    @patch("subprocess.Popen")
    def test_create_process_with_cwd(self, mock_popen, service, tmp_path):
        """Test process creation with working directory."""
        mock_process = Mock()
        mock_popen.return_value = mock_process

        service.create_process(["ls"], cwd=tmp_path)

        mock_popen.assert_called_once()
        call_kwargs = mock_popen.call_args[1]
        assert call_kwargs["cwd"] == tmp_path

    @patch("subprocess.Popen")
    def test_create_process_file_not_found(self, mock_popen, service):
        """Test process creation with nonexistent command raises AidbError."""
        mock_popen.side_effect = FileNotFoundError("command not found")

        with pytest.raises(AidbError) as exc_info:
            service.create_process(["nonexistent"])

        assert "Command not found: nonexistent" in str(exc_info.value)

    def test_is_ci_environment_github_actions(self, service):
        """Test CI detection for GitHub Actions."""
        service._env = {"GITHUB_ACTIONS": "true"}

        assert service._is_ci_environment() is True

    def test_is_ci_environment_gitlab_ci(self, service):
        """Test CI detection for GitLab CI."""
        service._env = {"GITLAB_CI": "true"}

        assert service._is_ci_environment() is True

    def test_is_ci_environment_generic_ci(self, service):
        """Test CI detection for generic CI."""
        service._env = {"CI": "true"}

        assert service._is_ci_environment() is True

    def test_is_ci_environment_jenkins(self, service):
        """Test CI detection for Jenkins."""
        service._env = {"JENKINS_HOME": "/var/jenkins"}

        assert service._is_ci_environment() is True

    def test_is_ci_environment_github_workflow(self, service):
        """Test CI detection via GITHUB_WORKFLOW."""
        service._env = {"GITHUB_WORKFLOW": "test"}

        assert service._is_ci_environment() is True

    @patch.dict("os.environ", {}, clear=True)
    def test_is_ci_environment_not_ci(self, service):
        """Test CI detection returns False in non-CI environment."""
        service._env = None

        assert service._is_ci_environment() is False

    def test_is_ci_environment_uses_context_env(self, service_with_ctx):
        """Test CI detection uses context environment when available."""
        service_with_ctx._env = {"CI": "true"}

        assert service_with_ctx._is_ci_environment() is True
