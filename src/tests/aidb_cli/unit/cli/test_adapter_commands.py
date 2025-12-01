"""Unit tests for adapter CLI commands."""

import platform
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, Mock, call, patch

import pytest

from aidb_cli.services.adapter.adapter_build_service import AdapterBuildService


@pytest.mark.unit
class TestAdapterBuildCommand:
    """Unit tests for adapter build command with --use-host-platform flag."""

    def test_use_host_platform_flag_sets_environment_variables(self):
        """Test that --use-host-platform flag sets correct environment variables.

        Verifies that when the flag is set, AIDB_USE_HOST_PLATFORM=1,
        AIDB_BUILD_PLATFORM, and AIDB_BUILD_ARCH are passed to the command executor.
        """
        mock_executor = Mock()
        mock_executor.execute = Mock(
            return_value=subprocess.CompletedProcess(
                args=["act"],
                returncode=0,
                stdout="",
                stderr="",
            ),
        )

        service = AdapterBuildService(
            repo_root=Path("/fake/repo"),
            command_executor=mock_executor,
        )

        # Simulate the environment that the CLI command sets up
        resolved_env = {
            "AIDB_USE_HOST_PLATFORM": "1",
            "AIDB_BUILD_PLATFORM": platform.system().lower(),
            "AIDB_BUILD_ARCH": platform.machine().lower(),
        }

        with patch.object(Path, "exists", return_value=True):
            with patch("aidb_cli.services.adapter.adapter_build_service.CachePaths"):
                service.build_locally(
                    languages=["python"],
                    verbose=False,
                    resolved_env=resolved_env,
                )

        # Find the call for the actual build command (not the "which act" check)
        build_call = None
        for call_args in mock_executor.execute.call_args_list:
            cmd = call_args[0][0]
            if "act" in cmd and "workflow_dispatch" in cmd:
                build_call = call_args
                break

        assert build_call is not None, "Build command should have been called"
        call_kwargs = build_call[1]
        env = call_kwargs["env"]

        assert env is not None, "Environment variables should be set"
        assert env["AIDB_USE_HOST_PLATFORM"] == "1"
        assert "AIDB_BUILD_PLATFORM" in env
        assert "AIDB_BUILD_ARCH" in env
        assert env["AIDB_BUILD_PLATFORM"] == platform.system().lower()
        assert env["AIDB_BUILD_ARCH"] == platform.machine().lower()

    def test_use_host_platform_flag_default_behavior(self):
        """Test that without the flag, environment variables are NOT set.

        Verifies that when use_host_platform is False, the special environment variables
        are not passed to the command executor.
        """
        mock_executor = Mock()
        mock_executor.execute = Mock(
            return_value=subprocess.CompletedProcess(
                args=["act"],
                returncode=0,
                stdout="",
                stderr="",
            ),
        )

        service = AdapterBuildService(
            repo_root=Path("/fake/repo"),
            command_executor=mock_executor,
        )

        # No resolved_env passed - simulates default behavior
        with patch.object(Path, "exists", return_value=True):
            with patch("aidb_cli.services.adapter.adapter_build_service.CachePaths"):
                service.build_locally(
                    languages=["python"],
                    verbose=False,
                    resolved_env=None,
                )

        # Find the call for the actual build command
        build_call = None
        for call_args in mock_executor.execute.call_args_list:
            cmd = call_args[0][0]
            if "act" in cmd and "workflow_dispatch" in cmd:
                build_call = call_args
                break

        assert build_call is not None, "Build command should have been called"
        call_kwargs = build_call[1]
        env = call_kwargs.get("env")

        assert env is None, "Environment variables should not be set by default"

    def test_use_host_platform_flag_with_multiple_languages(self):
        """Test that environment variables are set for all languages when flag is used.

        Verifies that the flag properly integrates with the build command when building
        multiple adapters.
        """
        mock_executor = Mock()
        mock_executor.execute = Mock(
            return_value=subprocess.CompletedProcess(
                args=["act"],
                returncode=0,
                stdout="",
                stderr="",
            ),
        )

        service = AdapterBuildService(
            repo_root=Path("/fake/repo"),
            command_executor=mock_executor,
        )

        # Simulate the environment that the CLI command sets up
        resolved_env = {
            "AIDB_USE_HOST_PLATFORM": "1",
            "AIDB_BUILD_PLATFORM": platform.system().lower(),
            "AIDB_BUILD_ARCH": platform.machine().lower(),
        }

        with patch.object(Path, "exists", return_value=True):
            with patch("aidb_cli.services.adapter.adapter_build_service.CachePaths"):
                service.build_locally(
                    languages=["python", "javascript"],
                    verbose=False,
                    resolved_env=resolved_env,
                )

        # Find all build command calls
        build_calls = []
        for call_args in mock_executor.execute.call_args_list:
            cmd = call_args[0][0]
            if "act" in cmd and "workflow_dispatch" in cmd:
                build_calls.append(call_args)

        # Implementation now batches multiple languages into a single build call
        assert len(build_calls) == 1, "Should have 1 build call for multiple languages"

        build_call = build_calls[0]
        cmd = build_call[0][0]
        call_kwargs = build_call[1]
        env = call_kwargs["env"]

        # Verify both languages are in the command
        assert "--input" in cmd
        input_idx = cmd.index("--input")
        assert "python" in cmd[input_idx + 1]
        assert "javascript" in cmd[input_idx + 1]

        # Verify platform environment variables
        assert env is not None
        assert env["AIDB_USE_HOST_PLATFORM"] == "1"
        assert env["AIDB_BUILD_PLATFORM"] == platform.system().lower()
        assert env["AIDB_BUILD_ARCH"] == platform.machine().lower()

    def test_use_host_platform_flag_integration_with_build_command(self):
        """Test that the flag properly integrates with the build command.

        Verifies that the command executor receives the correct act command along with
        the platform-specific environment variables.
        """
        mock_executor = Mock()
        mock_executor.execute = Mock(
            return_value=subprocess.CompletedProcess(
                args=["act"],
                returncode=0,
                stdout="",
                stderr="",
            ),
        )

        service = AdapterBuildService(
            repo_root=Path("/fake/repo"),
            command_executor=mock_executor,
        )

        # Simulate the environment that the CLI command sets up
        resolved_env = {
            "AIDB_USE_HOST_PLATFORM": "1",
            "AIDB_BUILD_PLATFORM": platform.system().lower(),
            "AIDB_BUILD_ARCH": platform.machine().lower(),
        }

        with patch.object(Path, "exists", return_value=True):
            with patch("aidb_cli.services.adapter.adapter_build_service.CachePaths"):
                service.build_locally(
                    languages=["python"],
                    verbose=False,
                    resolved_env=resolved_env,
                )

        # Find the build command call
        build_call = None
        for call_args in mock_executor.execute.call_args_list:
            cmd = call_args[0][0]
            if "act" in cmd and "workflow_dispatch" in cmd:
                build_call = call_args
                break

        assert build_call is not None, "Build command should have been called"
        cmd = build_call[0][0]

        assert "act" in cmd
        assert "workflow_dispatch" in cmd
        assert "--input" in cmd
        assert "adapters=python" in cmd

    def test_use_host_platform_preserves_existing_environment(self):
        """Test that platform variables are added to, not replacing, existing env.

        Verifies that when use_host_platform is True, the platform-specific variables
        are merged with any existing environment.
        """
        mock_executor = Mock()
        mock_executor.execute = Mock(
            return_value=subprocess.CompletedProcess(
                args=["act"],
                returncode=0,
                stdout="",
                stderr="",
            ),
        )

        service = AdapterBuildService(
            repo_root=Path("/fake/repo"),
            command_executor=mock_executor,
        )

        # Simulate environment with both existing and new platform vars
        resolved_env = {
            "EXISTING_VAR": "existing_value",
            "AIDB_USE_HOST_PLATFORM": "1",
            "AIDB_BUILD_PLATFORM": platform.system().lower(),
            "AIDB_BUILD_ARCH": platform.machine().lower(),
        }

        with patch.object(Path, "exists", return_value=True):
            with patch("aidb_cli.services.adapter.adapter_build_service.CachePaths"):
                service.build_locally(
                    languages=["python"],
                    verbose=False,
                    resolved_env=resolved_env,
                )

        # Find the build command call
        build_call = None
        for call_args in mock_executor.execute.call_args_list:
            cmd = call_args[0][0]
            if "act" in cmd and "workflow_dispatch" in cmd:
                build_call = call_args
                break

        assert build_call is not None, "Build command should have been called"
        call_kwargs = build_call[1]
        env = call_kwargs["env"]

        assert env["AIDB_USE_HOST_PLATFORM"] == "1"
        assert env["AIDB_BUILD_PLATFORM"] == platform.system().lower()
        assert env["AIDB_BUILD_ARCH"] == platform.machine().lower()
        assert "EXISTING_VAR" in env
        assert env["EXISTING_VAR"] == "existing_value"

    def test_use_host_platform_flag_values_are_lowercase(self):
        """Test that AIDB_BUILD_PLATFORM and AIDB_BUILD_ARCH are lowercase.

        Verifies that platform.system() and platform.machine() are converted to
        lowercase for consistency.
        """
        mock_executor = Mock()
        mock_executor.execute = Mock(
            return_value=subprocess.CompletedProcess(
                args=["act"],
                returncode=0,
                stdout="",
                stderr="",
            ),
        )

        service = AdapterBuildService(
            repo_root=Path("/fake/repo"),
            command_executor=mock_executor,
        )

        # Simulate the environment that the CLI command sets up
        resolved_env = {
            "AIDB_USE_HOST_PLATFORM": "1",
            "AIDB_BUILD_PLATFORM": platform.system().lower(),
            "AIDB_BUILD_ARCH": platform.machine().lower(),
        }

        with patch.object(Path, "exists", return_value=True):
            with patch("aidb_cli.services.adapter.adapter_build_service.CachePaths"):
                service.build_locally(
                    languages=["python"],
                    verbose=False,
                    resolved_env=resolved_env,
                )

        # Find the build command call
        build_call = None
        for call_args in mock_executor.execute.call_args_list:
            cmd = call_args[0][0]
            if "act" in cmd and "workflow_dispatch" in cmd:
                build_call = call_args
                break

        assert build_call is not None, "Build command should have been called"
        call_kwargs = build_call[1]
        env = call_kwargs["env"]

        assert env["AIDB_BUILD_PLATFORM"].islower()
        assert env["AIDB_BUILD_ARCH"].islower()
