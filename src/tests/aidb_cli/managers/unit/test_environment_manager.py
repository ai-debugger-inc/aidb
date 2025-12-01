"""Unit tests for EnvironmentManager."""

import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from aidb_cli.managers.environment_manager import EnvironmentManager


class TestEnvironmentManager:
    """Test the EnvironmentManager."""

    @pytest.fixture
    def tmp_env_files(self, tmp_path):
        """Create temporary environment files."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        # Create .env.test template
        env_test = repo_root / ".env.test"
        env_test.write_text("TEST_VAR=test_value\nAIDB_TEST=1\n")

        # Create versions.yaml
        versions = repo_root / "versions.yaml"
        versions.write_text(
            "infrastructure:\n"
            "  python:\n"
            "    version: '3.12'\n"
            "    docker_tag: '3.12-slim'\n",
        )

        return repo_root

    @patch.dict(os.environ, {"PATH": "/usr/bin", "HOME": "/home/user"}, clear=True)
    @patch("aidb_cli.managers.environment_manager.resolve_env_template")
    def test_initialization_resolves_environment(
        self,
        mock_resolve,
        tmp_env_files,
    ):
        """Test initialization resolves environment."""
        mock_resolve.return_value = {"TEST_VAR": "test_value"}

        manager = EnvironmentManager(tmp_env_files)

        assert manager.repo_root == tmp_env_files
        assert len(manager._resolved_env) > 0
        assert "REPO_ROOT" in manager._resolved_env
        mock_resolve.assert_called_once()

    @patch.dict(os.environ, {"PATH": "/usr/bin", "HOME": "/home/user"}, clear=True)
    @patch("aidb_cli.managers.environment_manager.resolve_env_template")
    def test_resolve_includes_system_environment(
        self,
        mock_resolve,
        tmp_env_files,
    ):
        """Test resolve includes system environment variables."""
        mock_resolve.return_value = {}

        manager = EnvironmentManager(tmp_env_files)
        env = manager.get_environment()

        assert "PATH" in env
        assert "HOME" in env
        assert env["PATH"] == "/usr/bin"

    @patch.dict(os.environ, {}, clear=True)
    @patch("aidb_cli.managers.environment_manager.resolve_env_template")
    def test_resolve_adds_essential_defaults(
        self,
        mock_resolve,
        tmp_env_files,
    ):
        """Test resolve adds essential default variables."""
        mock_resolve.return_value = {}

        manager = EnvironmentManager(tmp_env_files)
        env = manager.get_environment()

        assert env["REPO_ROOT"] == str(tmp_env_files)
        assert "COMPOSE_PROJECT_NAME" in env

    @patch.dict(os.environ, {}, clear=True)
    @patch("aidb_cli.managers.environment_manager.resolve_env_template")
    def test_resolve_merges_env_test_template(
        self,
        mock_resolve,
        tmp_env_files,
    ):
        """Test resolve merges .env.test template variables."""
        mock_resolve.return_value = {"TEST_VAR": "test_value"}

        manager = EnvironmentManager(tmp_env_files)
        env = manager.get_environment()

        assert env["TEST_VAR"] == "test_value"

    @patch.dict(os.environ, {}, clear=True)
    @patch("aidb_cli.managers.environment_manager.resolve_env_template")
    def test_resolve_handles_missing_env_test(
        self,
        mock_resolve,
        tmp_path,
    ):
        """Test resolve handles missing .env.test file."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        mock_resolve.return_value = {}

        manager = EnvironmentManager(repo_root)

        assert len(manager._resolved_env) > 0
        assert "REPO_ROOT" in manager._resolved_env

    @patch.dict(os.environ, {}, clear=True)
    @patch("aidb_cli.managers.environment_manager.resolve_env_template")
    def test_get_environment_returns_copy(
        self,
        mock_resolve,
        tmp_env_files,
    ):
        """Test get_environment returns a copy."""
        mock_resolve.return_value = {}

        manager = EnvironmentManager(tmp_env_files)
        env1 = manager.get_environment()
        env2 = manager.get_environment()

        assert env1 is not env2
        assert env1 == env2

    @patch.dict(os.environ, {}, clear=True)
    @patch("aidb_cli.managers.environment_manager.resolve_env_template")
    def test_update_adds_new_variables(
        self,
        mock_resolve,
        tmp_env_files,
    ):
        """Test update adds new environment variables."""
        mock_resolve.return_value = {}

        manager = EnvironmentManager(tmp_env_files)
        manager.update({"NEW_VAR": "new_value"}, "test")

        env = manager.get_environment()
        assert env["NEW_VAR"] == "new_value"

    @patch.dict(os.environ, {}, clear=True)
    @patch("aidb_cli.managers.environment_manager.resolve_env_template")
    def test_update_overrides_existing_variables(
        self,
        mock_resolve,
        tmp_env_files,
    ):
        """Test update overrides existing variables."""
        mock_resolve.return_value = {"EXISTING": "old_value"}

        manager = EnvironmentManager(tmp_env_files)
        manager.update({"EXISTING": "new_value"}, "test")

        env = manager.get_environment()
        assert env["EXISTING"] == "new_value"

    @patch.dict(os.environ, {}, clear=True)
    @patch("aidb_cli.managers.environment_manager.resolve_env_template")
    def test_update_tracks_history(
        self,
        mock_resolve,
        tmp_env_files,
    ):
        """Test update tracks update history."""
        mock_resolve.return_value = {}

        manager = EnvironmentManager(tmp_env_files)
        manager.update({"VAR1": "value1"}, "source1")
        manager.update({"VAR2": "value2"}, "source2")

        history = manager.get_update_history()
        assert len(history) == 2
        assert history[0]["source"] == "source1"
        assert history[1]["source"] == "source2"

    @patch.dict(os.environ, {}, clear=True)
    @patch("aidb_cli.managers.environment_manager.resolve_env_template")
    def test_get_bool_true_values(
        self,
        mock_resolve,
        tmp_env_files,
    ):
        """Test get_bool parses true values correctly."""
        mock_resolve.return_value = {}
        manager = EnvironmentManager(tmp_env_files)

        true_values = ["1", "true", "TRUE", "yes", "YES", "on", "ON"]
        for val in true_values:
            manager.update({"TEST_BOOL": val}, "test")
            assert manager.get_bool("TEST_BOOL") is True

    @patch.dict(os.environ, {}, clear=True)
    @patch("aidb_cli.managers.environment_manager.resolve_env_template")
    def test_get_bool_false_values(
        self,
        mock_resolve,
        tmp_env_files,
    ):
        """Test get_bool parses false values correctly."""
        mock_resolve.return_value = {}
        manager = EnvironmentManager(tmp_env_files)

        false_values = ["0", "false", "FALSE", "no", "NO", "off", "OFF"]
        for val in false_values:
            manager.update({"TEST_BOOL": val}, "test")
            assert manager.get_bool("TEST_BOOL") is False

    @patch.dict(os.environ, {}, clear=True)
    @patch("aidb_cli.managers.environment_manager.resolve_env_template")
    def test_get_bool_returns_default(
        self,
        mock_resolve,
        tmp_env_files,
    ):
        """Test get_bool returns default for missing variable."""
        mock_resolve.return_value = {}
        manager = EnvironmentManager(tmp_env_files)

        assert manager.get_bool("MISSING", default=True) is True
        assert manager.get_bool("MISSING", default=False) is False

    @patch.dict(os.environ, {}, clear=True)
    @patch("aidb_cli.managers.environment_manager.resolve_env_template")
    def test_get_int_parses_correctly(
        self,
        mock_resolve,
        tmp_env_files,
    ):
        """Test get_int parses integer values."""
        mock_resolve.return_value = {}
        manager = EnvironmentManager(tmp_env_files)
        manager.update({"TEST_INT": "42"}, "test")

        assert manager.get_int("TEST_INT") == 42

    @patch.dict(os.environ, {}, clear=True)
    @patch("aidb_cli.managers.environment_manager.resolve_env_template")
    def test_get_int_returns_default_for_invalid(
        self,
        mock_resolve,
        tmp_env_files,
    ):
        """Test get_int returns default for invalid values."""
        mock_resolve.return_value = {}
        manager = EnvironmentManager(tmp_env_files)
        manager.update({"TEST_INT": "not_a_number"}, "test")

        assert manager.get_int("TEST_INT", default=10) == 10

    @patch.dict(os.environ, {}, clear=True)
    @patch("aidb_cli.managers.environment_manager.resolve_env_template")
    def test_get_str_returns_value(
        self,
        mock_resolve,
        tmp_env_files,
    ):
        """Test get_str returns string value."""
        mock_resolve.return_value = {}
        manager = EnvironmentManager(tmp_env_files)
        manager.update({"TEST_STR": "hello"}, "test")

        assert manager.get_str("TEST_STR") == "hello"

    @patch.dict(os.environ, {}, clear=True)
    @patch("aidb_cli.managers.environment_manager.resolve_env_template")
    def test_get_str_returns_default(
        self,
        mock_resolve,
        tmp_env_files,
    ):
        """Test get_str returns default for missing variable."""
        mock_resolve.return_value = {}
        manager = EnvironmentManager(tmp_env_files)

        assert manager.get_str("MISSING", default="default") == "default"

    @patch.dict(os.environ, {}, clear=True)
    @patch("aidb_cli.managers.environment_manager.resolve_env_template")
    def test_get_list_parses_comma_separated(
        self,
        mock_resolve,
        tmp_env_files,
    ):
        """Test get_list parses comma-separated values."""
        mock_resolve.return_value = {}
        manager = EnvironmentManager(tmp_env_files)
        manager.update({"TEST_LIST": "a,b,c"}, "test")

        result = manager.get_list("TEST_LIST")
        assert result == ["a", "b", "c"]

    @patch.dict(os.environ, {}, clear=True)
    @patch("aidb_cli.managers.environment_manager.resolve_env_template")
    def test_get_list_strips_whitespace(
        self,
        mock_resolve,
        tmp_env_files,
    ):
        """Test get_list strips whitespace from items."""
        mock_resolve.return_value = {}
        manager = EnvironmentManager(tmp_env_files)
        manager.update({"TEST_LIST": "a , b , c"}, "test")

        result = manager.get_list("TEST_LIST")
        assert result == ["a", "b", "c"]

    @patch.dict(os.environ, {}, clear=True)
    @patch("aidb_cli.managers.environment_manager.resolve_env_template")
    def test_validate_test_pattern_accepts_valid(
        self,
        mock_resolve,
        tmp_env_files,
    ):
        """Test validate_test_pattern accepts valid patterns."""
        mock_resolve.return_value = {}
        manager = EnvironmentManager(tmp_env_files)

        assert manager.validate_test_pattern("tests/test_foo.py") is not None
        assert manager.validate_test_pattern("test_*.py") is not None

    @patch.dict(os.environ, {}, clear=True)
    @patch("aidb_cli.managers.environment_manager.resolve_env_template")
    def test_validate_test_pattern_rejects_pytest_args(
        self,
        mock_resolve,
        tmp_env_files,
    ):
        """Test validate_test_pattern rejects pytest args."""
        mock_resolve.return_value = {}
        manager = EnvironmentManager(tmp_env_files)

        assert manager.validate_test_pattern("--verbose") is None

    @patch.dict(os.environ, {}, clear=True)
    @patch("aidb_cli.managers.environment_manager.resolve_env_template")
    def test_validate_pytest_addopts_parses_correctly(
        self,
        mock_resolve,
        tmp_env_files,
    ):
        """Test validate_pytest_addopts parses argument string."""
        mock_resolve.return_value = {}
        manager = EnvironmentManager(tmp_env_files)

        args = manager.validate_pytest_addopts("-v --tb=short")
        assert args == ["-v", "--tb=short"]

    @patch.dict(os.environ, {}, clear=True)
    @patch("aidb_cli.managers.environment_manager.resolve_env_template")
    def test_validate_pytest_addopts_filters_dangerous(
        self,
        mock_resolve,
        tmp_env_files,
    ):
        """Test validate_pytest_addopts filters dangerous arguments."""
        mock_resolve.return_value = {}
        manager = EnvironmentManager(tmp_env_files)

        args = manager.validate_pytest_addopts("-v --rootdir=/tmp")
        assert "--rootdir=/tmp" not in args
        assert "-v" in args

    @patch.dict(os.environ, {}, clear=True)
    @patch("aidb_cli.managers.environment_manager.resolve_env_template")
    def test_validate_test_suite_accepts_valid(
        self,
        mock_resolve,
        tmp_env_files,
    ):
        """Test validate_test_suite accepts valid suite names."""
        mock_resolve.return_value = {}
        manager = EnvironmentManager(tmp_env_files)

        assert manager.validate_test_suite("cli") == "cli"
        assert manager.validate_test_suite("mcp") == "mcp"

    @patch.dict(os.environ, {}, clear=True)
    @patch("aidb_cli.managers.environment_manager.resolve_env_template")
    def test_validate_test_suite_rejects_invalid(
        self,
        mock_resolve,
        tmp_env_files,
    ):
        """Test validate_test_suite rejects invalid suite names."""
        mock_resolve.return_value = {}
        manager = EnvironmentManager(tmp_env_files)

        assert manager.validate_test_suite("invalid_suite") is None

    @patch.dict(os.environ, {}, clear=True)
    @patch("aidb_cli.managers.environment_manager.resolve_env_template")
    def test_export_for_subprocess_returns_string_dict(
        self,
        mock_resolve,
        tmp_env_files,
    ):
        """Test export_for_subprocess returns all strings."""
        mock_resolve.return_value = {}
        manager = EnvironmentManager(tmp_env_files)
        manager.update({"TEST_VAR": "value"}, "test")

        exported = manager.export_for_subprocess()

        assert all(isinstance(v, str) for v in exported.values())
        assert "TEST_VAR" in exported

    @patch.dict(os.environ, {}, clear=True)
    @patch("aidb_cli.managers.environment_manager.resolve_env_template")
    def test_debug_dump_shows_relevant_variables(
        self,
        mock_resolve,
        tmp_env_files,
    ):
        """Test debug_dump shows relevant variables."""
        mock_resolve.return_value = {}
        manager = EnvironmentManager(tmp_env_files)
        manager.update({"AIDB_TEST": "value"}, "test")

        dump = manager.debug_dump(show_all=False)

        assert "AIDB_TEST" in dump
        assert "Relevant variables" in dump

    @patch.dict(os.environ, {}, clear=True)
    @patch("aidb_cli.managers.environment_manager.resolve_env_template")
    def test_debug_dump_masks_sensitive_values(
        self,
        mock_resolve,
        tmp_env_files,
    ):
        """Test debug_dump masks sensitive values in variables section."""
        mock_resolve.return_value = {}
        manager = EnvironmentManager(tmp_env_files)
        manager._resolved_env["API_SECRET"] = "secret_value"

        dump = manager.debug_dump(show_all=True)

        # Check that the variable section masks the value
        assert "***MASKED***" in dump
        # The update history may show unmasked values, so we only check
        # the variables section
        lines = dump.split("\n")
        vars_section = []
        in_vars = False
        for line in lines:
            if line.strip() == "All variables:":
                in_vars = True
            elif line.strip().startswith("==="):
                in_vars = False
            elif in_vars:
                vars_section.append(line)

        vars_text = "\n".join(vars_section)
        assert "API_SECRET=***MASKED***" in vars_text
