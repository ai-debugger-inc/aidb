"""Unit tests for VSCodeVariableResolver.

Tests VS Code variable resolution including workspaceFolder, env:, file-related
variables, and validation.
"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aidb.adapters.base.vscode_variables import VSCodeVariableResolver
from aidb.common.errors import VSCodeVariableError

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def resolver(mock_ctx: MagicMock, tmp_path: Path) -> VSCodeVariableResolver:
    """Create a VSCodeVariableResolver instance for testing."""
    return VSCodeVariableResolver(workspace_root=tmp_path, ctx=mock_ctx)


@pytest.fixture
def resolver_no_workspace(mock_ctx: MagicMock) -> VSCodeVariableResolver:
    """Create a resolver without workspace root."""
    return VSCodeVariableResolver(ctx=mock_ctx)


# =============================================================================
# TestVSCodeVariableResolverInit
# =============================================================================


class TestVSCodeVariableResolverInit:
    """Tests for VSCodeVariableResolver initialization."""

    def test_init_with_workspace_root(
        self,
        mock_ctx: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test initialization with workspace root."""
        resolver = VSCodeVariableResolver(workspace_root=tmp_path, ctx=mock_ctx)

        assert resolver.workspace_root == tmp_path

    def test_init_without_workspace_root_uses_cwd(
        self,
        mock_ctx: MagicMock,
    ) -> None:
        """Test initialization uses cwd when no workspace root."""
        resolver = VSCodeVariableResolver(ctx=mock_ctx)

        assert resolver.workspace_root == Path.cwd()


# =============================================================================
# TestVSCodeVariableResolverResolve
# =============================================================================


class TestVSCodeVariableResolverResolve:
    """Tests for resolve() method."""

    def test_resolve_workspace_folder(
        self,
        resolver: VSCodeVariableResolver,
        tmp_path: Path,
    ) -> None:
        """Test resolving ${workspaceFolder}."""
        result = resolver.resolve("${workspaceFolder}/src")

        assert result == f"{tmp_path}/src"

    def test_resolve_workspace_folder_basename(
        self,
        resolver: VSCodeVariableResolver,
        tmp_path: Path,
    ) -> None:
        """Test resolving ${workspaceFolderBasename}."""
        result = resolver.resolve("project-${workspaceFolderBasename}")

        assert result == f"project-{tmp_path.name}"

    def test_resolve_env_variable(
        self,
        resolver: VSCodeVariableResolver,
    ) -> None:
        """Test resolving ${env:VAR}."""
        with patch.dict(os.environ, {"MY_VAR": "my_value"}):
            result = resolver.resolve("prefix-${env:MY_VAR}-suffix")

        assert result == "prefix-my_value-suffix"

    def test_resolve_env_variable_not_set_raises(
        self,
        resolver: VSCodeVariableResolver,
    ) -> None:
        """Test resolving unset env variable raises error."""
        with (
            patch.dict(os.environ, {}, clear=True),
            pytest.raises(VSCodeVariableError, match="Environment variable"),
        ):
            resolver.resolve("${env:NONEXISTENT_VAR}")

    def test_resolve_command_variable_raises(
        self,
        resolver: VSCodeVariableResolver,
    ) -> None:
        """Test resolving command variable raises error."""
        with pytest.raises(VSCodeVariableError, match="Command variable"):
            resolver.resolve("${command:pickProcess}")

    def test_resolve_file_with_target_context(
        self,
        resolver: VSCodeVariableResolver,
        tmp_path: Path,
    ) -> None:
        """Test resolving ${file} with target in context."""
        target_file = tmp_path / "src" / "main.py"
        target_file.parent.mkdir(exist_ok=True)
        target_file.touch()

        result = resolver.resolve("${file}", context={"target": str(target_file)})

        assert result == str(target_file.absolute())

    def test_resolve_file_basename_with_target_context(
        self,
        resolver: VSCodeVariableResolver,
        tmp_path: Path,
    ) -> None:
        """Test resolving ${fileBasename} with target in context."""
        target_file = tmp_path / "main.py"

        result = resolver.resolve(
            "${fileBasename}",
            context={"target": str(target_file)},
        )

        assert result == "main.py"

    def test_resolve_file_basename_no_extension_with_target_context(
        self,
        resolver: VSCodeVariableResolver,
        tmp_path: Path,
    ) -> None:
        """Test resolving ${fileBasenameNoExtension} with target in context."""
        target_file = tmp_path / "main.py"

        result = resolver.resolve(
            "${fileBasenameNoExtension}",
            context={"target": str(target_file)},
        )

        assert result == "main"

    def test_resolve_file_extname_with_target_context(
        self,
        resolver: VSCodeVariableResolver,
        tmp_path: Path,
    ) -> None:
        """Test resolving ${fileExtname} with target in context."""
        target_file = tmp_path / "main.py"

        result = resolver.resolve(
            "${fileExtname}",
            context={"target": str(target_file)},
        )

        assert result == ".py"

    def test_resolve_file_dirname_with_target_context(
        self,
        resolver: VSCodeVariableResolver,
        tmp_path: Path,
    ) -> None:
        """Test resolving ${fileDirname} with target in context."""
        target_file = tmp_path / "src" / "main.py"
        target_file.parent.mkdir(exist_ok=True)

        result = resolver.resolve(
            "${fileDirname}",
            context={"target": str(target_file)},
        )

        assert result == str(target_file.parent.absolute())

    def test_resolve_file_without_context_raises(
        self,
        resolver: VSCodeVariableResolver,
    ) -> None:
        """Test resolving ${file} without context raises error."""
        with pytest.raises(VSCodeVariableError, match="runtime context"):
            resolver.resolve("${file}")

    def test_resolve_runtime_only_variable_raises(
        self,
        resolver: VSCodeVariableResolver,
    ) -> None:
        """Test resolving runtime-only variable raises error."""
        with pytest.raises(VSCodeVariableError, match="selectedText"):
            resolver.resolve("${selectedText}")

    def test_resolve_unknown_variable_raises(
        self,
        resolver: VSCodeVariableResolver,
    ) -> None:
        """Test resolving unknown variable raises error."""
        with pytest.raises(VSCodeVariableError, match="Unknown VS Code variable"):
            resolver.resolve("${unknownVar}")

    def test_resolve_string_without_variables(
        self,
        resolver: VSCodeVariableResolver,
    ) -> None:
        """Test resolving string without variables returns unchanged."""
        result = resolver.resolve("/path/to/file.py")

        assert result == "/path/to/file.py"

    def test_resolve_multiple_variables(
        self,
        resolver: VSCodeVariableResolver,
        tmp_path: Path,
    ) -> None:
        """Test resolving multiple variables in one string."""
        with patch.dict(os.environ, {"VENV": "venv"}):
            result = resolver.resolve("${workspaceFolder}/${env:VENV}/bin/python")

        assert result == f"{tmp_path}/venv/bin/python"


# =============================================================================
# TestVSCodeVariableResolverResolveDict
# =============================================================================


class TestVSCodeVariableResolverResolveDict:
    """Tests for resolve_dict() method."""

    def test_resolve_dict_resolves_string_values(
        self,
        resolver: VSCodeVariableResolver,
        tmp_path: Path,
    ) -> None:
        """Test resolve_dict resolves string values."""
        data = {"path": "${workspaceFolder}/src", "name": "test"}

        result = resolver.resolve_dict(data)

        assert result["path"] == f"{tmp_path}/src"
        assert result["name"] == "test"

    def test_resolve_dict_resolves_nested_dicts(
        self,
        resolver: VSCodeVariableResolver,
        tmp_path: Path,
    ) -> None:
        """Test resolve_dict resolves nested dictionaries."""
        data = {"config": {"path": "${workspaceFolder}/config"}}

        result = resolver.resolve_dict(data)

        assert result["config"]["path"] == f"{tmp_path}/config"

    def test_resolve_dict_resolves_lists(
        self,
        resolver: VSCodeVariableResolver,
        tmp_path: Path,
    ) -> None:
        """Test resolve_dict resolves list items."""
        data = {"args": ["${workspaceFolder}/file1", "${workspaceFolder}/file2"]}

        result = resolver.resolve_dict(data)

        assert result["args"] == [f"{tmp_path}/file1", f"{tmp_path}/file2"]

    def test_resolve_dict_preserves_non_strings(
        self,
        resolver: VSCodeVariableResolver,
    ) -> None:
        """Test resolve_dict preserves non-string values."""
        data = {"port": 5678, "enabled": True, "count": None}

        result = resolver.resolve_dict(data)

        assert result["port"] == 5678
        assert result["enabled"] is True
        assert result["count"] is None

    def test_resolve_dict_adds_field_context_on_error(
        self,
        resolver: VSCodeVariableResolver,
    ) -> None:
        """Test resolve_dict adds field context to error."""
        data = {"program": "${command:pickFile}"}

        with pytest.raises(VSCodeVariableError, match="Error in field 'program'"):
            resolver.resolve_dict(data)

    def test_resolve_dict_with_context(
        self,
        resolver: VSCodeVariableResolver,
        tmp_path: Path,
    ) -> None:
        """Test resolve_dict passes context to resolve."""
        target = tmp_path / "main.py"
        data = {"program": "${file}"}

        result = resolver.resolve_dict(data, context={"target": str(target)})

        assert str(target.absolute()) in result["program"]


# =============================================================================
# TestVSCodeVariableResolverHasUnresolvableVariables
# =============================================================================


class TestVSCodeVariableResolverHasUnresolvableVariables:
    """Tests for has_unresolvable_variables() method."""

    def test_returns_false_for_no_variables(
        self,
        resolver: VSCodeVariableResolver,
    ) -> None:
        """Test returns False when no variables present."""
        result = resolver.has_unresolvable_variables("/path/to/file")

        assert result is False

    def test_returns_false_for_resolvable_variables(
        self,
        resolver: VSCodeVariableResolver,
    ) -> None:
        """Test returns False for resolvable variables."""
        result = resolver.has_unresolvable_variables("${workspaceFolder}/src")

        assert result is False

    def test_returns_true_for_runtime_only_variable(
        self,
        resolver: VSCodeVariableResolver,
    ) -> None:
        """Test returns True for runtime-only variable."""
        result = resolver.has_unresolvable_variables("${file}")

        assert result is True

    def test_returns_true_for_command_variable(
        self,
        resolver: VSCodeVariableResolver,
    ) -> None:
        """Test returns True for command variable."""
        result = resolver.has_unresolvable_variables("${command:pickFile}")

        assert result is True

    def test_returns_true_for_selected_text(
        self,
        resolver: VSCodeVariableResolver,
    ) -> None:
        """Test returns True for selectedText variable."""
        result = resolver.has_unresolvable_variables("${selectedText}")

        assert result is True


# =============================================================================
# TestVSCodeVariableResolverValidateLaunchConfig
# =============================================================================


class TestVSCodeVariableResolverValidateLaunchConfig:
    """Tests for validate_launch_config() method."""

    def test_validate_passes_for_valid_config(
        self,
        resolver: VSCodeVariableResolver,
        tmp_path: Path,
    ) -> None:
        """Test validation passes for valid config."""
        config = MagicMock()
        config.program = str(tmp_path / "main.py")
        config.cwd = str(tmp_path)
        config.args = ["--debug"]

        resolver.validate_launch_config(config, "TestConfig")

    def test_validate_raises_for_file_variable(
        self,
        resolver: VSCodeVariableResolver,
    ) -> None:
        """Test validation raises for ${file} variable."""
        config = MagicMock()
        config.program = "${file}"
        config.cwd = None
        config.args = None

        with pytest.raises(VSCodeVariableError, match="unresolvable"):
            resolver.validate_launch_config(config, "TestConfig")

    def test_validate_raises_for_command_variable(
        self,
        resolver: VSCodeVariableResolver,
    ) -> None:
        """Test validation raises for command variable."""
        config = MagicMock()
        config.program = "${command:AskForProgramName}"
        config.cwd = None
        config.args = None

        with pytest.raises(VSCodeVariableError, match="unresolvable"):
            resolver.validate_launch_config(config, "TestConfig")

    def test_validate_checks_args_list(
        self,
        resolver: VSCodeVariableResolver,
    ) -> None:
        """Test validation checks args list items."""
        config = MagicMock()
        config.program = "/path/to/main.py"
        config.cwd = None
        config.args = ["--config", "${file}"]

        with pytest.raises(VSCodeVariableError, match="args"):
            resolver.validate_launch_config(config, "TestConfig")

    def test_validate_includes_config_name_in_error(
        self,
        resolver: VSCodeVariableResolver,
    ) -> None:
        """Test validation includes config name in error message."""
        config = MagicMock()
        config.program = "${file}"
        config.cwd = None
        config.args = None

        with pytest.raises(VSCodeVariableError, match="MyLaunchConfig"):
            resolver.validate_launch_config(config, "MyLaunchConfig")

    def test_validate_handles_missing_attributes(
        self,
        resolver: VSCodeVariableResolver,
    ) -> None:
        """Test validation handles config without attributes."""
        config = MagicMock(spec=[])  # No attributes

        resolver.validate_launch_config(config, "EmptyConfig")


# =============================================================================
# TestVSCodeVariableResolverRuntimeOnlyVariables
# =============================================================================


class TestVSCodeVariableResolverRuntimeOnlyVariables:
    """Tests for runtime-only variable detection."""

    @pytest.mark.parametrize(
        "variable",
        [
            "file",
            "fileBasename",
            "fileBasenameNoExtension",
            "fileExtname",
            "fileDirname",
            "relativeFile",
            "relativeFileDirname",
            "selectedText",
            "execPath",
            "pathSeparator",
            "lineNumber",
            "selectedPosition",
            "currentYear",
            "currentMonth",
            "currentDay",
            "currentHour",
            "currentMinute",
            "currentSecond",
        ],
    )
    def test_runtime_only_variable_is_detected(
        self,
        resolver: VSCodeVariableResolver,
        variable: str,
    ) -> None:
        """Test all runtime-only variables are detected."""
        assert variable in VSCodeVariableResolver.RUNTIME_ONLY_VARIABLES
