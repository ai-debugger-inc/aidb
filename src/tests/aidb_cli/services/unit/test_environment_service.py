"""Unit tests for EnvironmentService."""

import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from aidb_cli.services.command_executor.environment_service import (
    EnvironmentService,
)


class TestEnvironmentService:
    """Test the EnvironmentService."""

    @pytest.fixture
    def service(self):
        """Create service instance without CLI context."""
        return EnvironmentService(ctx=None)

    @pytest.fixture
    def mock_ctx(self):
        """Create a mock CLI context with resolved environment."""
        ctx = Mock()
        ctx.obj = Mock()
        ctx.obj.resolved_env = {
            "PATH": "/usr/bin:/bin",
            "HOME": "/home/user",
            "CUSTOM_VAR": "custom_value",
        }
        return ctx

    @pytest.fixture
    def service_with_ctx(self, mock_ctx):
        """Create service instance with CLI context."""
        return EnvironmentService(ctx=mock_ctx)

    def test_init_without_context_uses_os_environ(self, service):
        """Test initialization without context uses os.environ."""
        # The service should have copied os.environ
        assert "PATH" in service._base_env
        # Base env should be a copy, not reference
        assert service._base_env is not os.environ

    def test_init_with_context_uses_resolved_env(self, service_with_ctx, mock_ctx):
        """Test initialization with context uses resolved environment."""
        assert service_with_ctx._base_env == mock_ctx.obj.resolved_env
        assert "CUSTOM_VAR" in service_with_ctx._base_env

    def test_build_environment_no_overrides_returns_none(self, service):
        """Test build_environment with no overrides returns None."""
        result = service.build_environment()

        assert result is None

    def test_build_environment_with_overrides_returns_dict(self, service):
        """Test build_environment with overrides returns environment dict."""
        overrides = {"TEST_VAR": "test_value"}

        result = service.build_environment(env_overrides=overrides)

        assert result is not None
        assert isinstance(result, dict)
        assert result["TEST_VAR"] == "test_value"
        # Should also include base environment
        assert "PATH" in result

    def test_build_environment_inherit_true(self, service):
        """Test build_environment with inherit=True includes base env."""
        overrides = {"NEW_VAR": "new_value"}

        result = service.build_environment(env_overrides=overrides, inherit=True)

        assert result is not None
        assert result["NEW_VAR"] == "new_value"
        assert "PATH" in result  # Inherited from base env

    def test_build_environment_inherit_false(self, service):
        """Test build_environment with inherit=False excludes base env."""
        overrides = {"NEW_VAR": "new_value"}

        result = service.build_environment(env_overrides=overrides, inherit=False)

        assert result is not None
        assert result["NEW_VAR"] == "new_value"
        # Should only have overrides, not base env
        assert len(result) == 1
        assert "PATH" not in result

    def test_build_environment_overrides_existing_vars(
        self,
        service_with_ctx,
        mock_ctx,
    ):
        """Test that overrides replace existing environment variables."""
        overrides = {"HOME": "/different/home"}

        result = service_with_ctx.build_environment(env_overrides=overrides)

        assert result["HOME"] == "/different/home"

    def test_setup_python_environment_unbuffered_true(self, service):
        """Test setup_python_environment sets PYTHONUNBUFFERED."""
        result = service.setup_python_environment(unbuffered=True)

        assert "PYTHONUNBUFFERED" in result
        assert result["PYTHONUNBUFFERED"] == "1"

    def test_setup_python_environment_unbuffered_false(self, service):
        """Test setup_python_environment without unbuffered flag."""
        result = service.setup_python_environment(unbuffered=False)

        assert "PYTHONUNBUFFERED" not in result

    def test_setup_python_environment_preserves_base_env(self, service):
        """Test setup_python_environment preserves base environment."""
        result = service.setup_python_environment(unbuffered=True)

        assert "PATH" in result
        assert "PYTHONUNBUFFERED" in result

    def test_setup_python_environment_with_custom_env(self, service):
        """Test setup_python_environment with custom base environment."""
        custom_env = {"CUSTOM": "value"}

        result = service.setup_python_environment(env=custom_env, unbuffered=True)

        assert result["CUSTOM"] == "value"
        assert result["PYTHONUNBUFFERED"] == "1"

    def test_get_path_components_returns_list(self, service):
        """Test get_path_components returns list of directories."""
        components = service.get_path_components()

        assert isinstance(components, list)
        assert len(components) > 0
        # Should have split on os.pathsep
        for component in components:
            assert os.pathsep not in component

    def test_get_path_components_empty_path(self):
        """Test get_path_components with empty PATH."""
        service = EnvironmentService(ctx=None)
        service._base_env = {"PATH": ""}

        components = service.get_path_components()

        assert components == []

    def test_get_path_components_missing_path(self):
        """Test get_path_components with missing PATH variable."""
        service = EnvironmentService(ctx=None)
        service._base_env = {}

        components = service.get_path_components()

        assert components == []

    @patch("shutil.which")
    def test_find_executable_found(self, mock_which, service):
        """Test finding an executable that exists."""
        mock_which.return_value = "/usr/bin/python"

        result = service.find_executable("python")

        assert result == Path("/usr/bin/python")
        mock_which.assert_called_once_with("python")

    @patch("shutil.which")
    def test_find_executable_not_found(self, mock_which, service):
        """Test finding an executable that doesn't exist."""
        mock_which.return_value = None

        result = service.find_executable("nonexistent")

        assert result is None
        mock_which.assert_called_once_with("nonexistent")

    def test_add_to_path_prepend(self, service):
        """Test adding a directory to PATH (prepend)."""
        new_dir = Path("/new/bin")
        service._base_env.get("PATH", "")

        result = service.add_to_path(new_dir, prepend=True)

        assert str(new_dir) in result["PATH"]
        # Should be at the beginning
        assert result["PATH"].startswith(str(new_dir))

    def test_add_to_path_append(self, service):
        """Test adding a directory to PATH (append)."""
        new_dir = Path("/new/bin")

        result = service.add_to_path(new_dir, prepend=False)

        assert str(new_dir) in result["PATH"]
        # Should be at the end
        assert result["PATH"].endswith(str(new_dir))

    def test_add_to_path_already_in_path(self, service):
        """Test adding a directory that's already in PATH."""
        # Get first directory in PATH
        components = service.get_path_components()
        if components:
            existing_dir = Path(components[0])

            result = service.add_to_path(existing_dir, prepend=True)

            # PATH should be unchanged (directory not duplicated)
            path_components = result["PATH"].split(os.pathsep)
            count = sum(1 for comp in path_components if comp == str(existing_dir))
            assert count == 1

    def test_add_to_path_with_custom_env(self, service):
        """Test adding to PATH with custom environment."""
        custom_env = {"PATH": "/original/bin", "OTHER": "value"}
        new_dir = Path("/new/bin")

        result = service.add_to_path(new_dir, env=custom_env, prepend=True)

        assert str(new_dir) in result["PATH"]
        assert "/original/bin" in result["PATH"]
        assert result["OTHER"] == "value"

    def test_add_to_path_empty_path(self, service):
        """Test adding to PATH when PATH is empty."""
        service._base_env = {"PATH": ""}
        new_dir = Path("/new/bin")

        result = service.add_to_path(new_dir, prepend=True)

        assert result["PATH"] == str(new_dir)

    def test_get_env_info_returns_dict(self, service):
        """Test get_env_info returns information dictionary."""
        info = service.get_env_info()

        assert isinstance(info, dict)
        assert "platform" in info
        assert "path_count" in info
        assert "python" in info
        assert "env_vars" in info
        assert "home" in info
        assert "cwd" in info

    def test_get_env_info_platform_is_os_name(self, service):
        """Test get_env_info platform matches os.name."""
        info = service.get_env_info()

        assert info["platform"] == os.name

    def test_get_env_info_path_count_correct(self, service):
        """Test get_env_info path_count matches actual PATH components."""
        info = service.get_env_info()
        actual_components = service.get_path_components()

        assert info["path_count"] == len(actual_components)

    def test_get_env_info_home_is_path(self, service):
        """Test get_env_info home is a Path object."""
        info = service.get_env_info()

        assert isinstance(info["home"], Path)
        assert info["home"] == Path.home()

    def test_get_env_info_cwd_is_path(self, service):
        """Test get_env_info cwd is a Path object."""
        info = service.get_env_info()

        assert isinstance(info["cwd"], Path)
        assert info["cwd"] == Path.cwd()

    def test_get_env_info_env_vars_count(self, service):
        """Test get_env_info env_vars count matches base environment."""
        info = service.get_env_info()

        assert info["env_vars"] == len(service._base_env)
