"""VS Code variable resolution for launch configurations.

This module resolves VS Code-style variables in launch.json configurations.
It supports the official VS Code variable syntax plus AIDB extensions.

Reference: https://code.visualstudio.com/docs/reference/variables-reference
"""

import os
import re
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aidb.common.errors import VSCodeVariableError
from aidb.patterns import Obj

# Type alias for variable resolver functions
VariableResolver = Callable[["VSCodeVariableResolver", str, dict[str, Any]], str | None]


class VSCodeVariableResolver(Obj):
    """Resolves VS Code variables in launch configurations.

    Supports the official VS Code variable reference syntax:
    https://code.visualstudio.com/docs/reference/variables-reference

    Supported variable categories:
    - Predefined: ${workspaceFolder}, ${userHome}, ${pathSeparator}, etc.
    - File-based: ${file}, ${fileBasename}, ${fileDirname}, etc. (require target)
    - Environment: ${env:NAME} (reads from os.environ)
    - Config: ${config:NAME} (not supported - requires VS Code settings)
    - Command: ${command:ID} (not supported - requires VS Code runtime)
    - Input: ${input:ID} (not supported - requires VS Code runtime)

    AIDB Extensions (not in official VS Code spec):
    - ${env:NAME:default} - Environment variable with fallback default value
    """

    # Pattern to match VS Code variables: ${variableName} or ${prefix:value}
    VARIABLE_PATTERN = re.compile(r"\$\{([^}]+)\}")

    # Predefined variables that can always be resolved
    PREDEFINED_VARIABLES: dict[str, VariableResolver] = {}

    # File-based variables that require a target file in context
    FILE_VARIABLES: dict[str, VariableResolver] = {}

    # Variables that require VS Code runtime (cannot be resolved)
    UNSUPPORTED_VARIABLES = {
        "selectedText",
        "execPath",
        "defaultBuildTask",
        "lineNumber",
        "columnNumber",
    }

    def __init__(self, workspace_root: Path | None = None, ctx: Any | None = None):
        """Initialize the resolver.

        Parameters
        ----------
        workspace_root : Path, optional
            The workspace root directory, defaults to current directory
        ctx : Any, optional
            Context object for logging and configuration
        """
        super().__init__(ctx)
        self.workspace_root = workspace_root or Path.cwd()

    def resolve(self, value: str, context: dict[str, Any] | None = None) -> str:
        """Resolve VS Code variables in a string.

        Parameters
        ----------
        value : str
            String potentially containing VS Code variables
        context : dict, optional
            Additional context for resolution:
            - 'target': Path to target file (resolves ${file} variables)

        Returns
        -------
        str
            String with resolved variables

        Raises
        ------
        VSCodeVariableError
            If a variable cannot be resolved
        """
        context = context or {}

        def replacer(match: re.Match) -> str:
            var_expr = match.group(1)
            resolved = self._resolve_variable(var_expr, context)
            if resolved is None:
                msg = self._get_error_message(var_expr)
                raise VSCodeVariableError(msg)
            return resolved

        return self.VARIABLE_PATTERN.sub(replacer, value)

    def _resolve_variable(
        self,
        var_expr: str,
        context: dict[str, Any],
    ) -> str | None:
        """Resolve a single variable expression.

        Parameters
        ----------
        var_expr : str
            Variable expression without ${} wrapper
        context : dict
            Resolution context

        Returns
        -------
        str | None
            Resolved value or None if cannot be resolved
        """
        # Check predefined variables first
        if var_expr in self.PREDEFINED_VARIABLES:
            return self.PREDEFINED_VARIABLES[var_expr](self, var_expr, context)

        # Check file-based variables
        if var_expr in self.FILE_VARIABLES:
            return self.FILE_VARIABLES[var_expr](self, var_expr, context)

        # Handle prefixed variables (env:, config:, command:, input:)
        if ":" in var_expr:
            prefix, rest = var_expr.split(":", 1)

            if prefix == "env":
                return self._resolve_env(rest)
            if prefix == "config":
                return self._resolve_config(rest)
            if prefix == "command":
                return self._resolve_command(rest)
            if prefix == "input":
                return self._resolve_input(rest)

            # Check for workspace-scoped variables (e.g., workspaceFolder:FolderName)
            base_var = prefix
            if base_var in self.PREDEFINED_VARIABLES:
                # Multi-root workspace scoping - not fully supported
                return self.PREDEFINED_VARIABLES[base_var](self, var_expr, context)

        return None

    def _resolve_env(self, env_expr: str) -> str | None:
        """Resolve ${env:NAME} or ${env:NAME:default} variables.

        The default value syntax is an AIDB extension not in official VS Code.

        Parameters
        ----------
        env_expr : str
            Environment expression (NAME or NAME:default)

        Returns
        -------
        str | None
            Environment variable value or default, None if not set and no default
        """
        # AIDB extension: support ${env:NAME:default} syntax
        if ":" in env_expr:
            env_var, default_value = env_expr.split(":", 1)
            return os.environ.get(env_var, default_value)

        # Standard VS Code: ${env:NAME}
        return os.environ.get(env_expr)

    def _resolve_config(self, _config_name: str) -> str | None:
        """Resolve ${config:NAME} variables.

        Not supported - requires VS Code settings context.
        """
        return None

    def _resolve_command(self, _command_id: str) -> str | None:
        """Resolve ${command:ID} variables.

        Not supported - requires VS Code runtime.
        """
        return None

    def _resolve_input(self, _input_id: str) -> str | None:
        """Resolve ${input:ID} variables.

        Not supported - requires VS Code runtime.
        """
        return None

    def _get_error_message(self, var_expr: str) -> str:
        """Get a helpful error message for an unresolvable variable."""
        # Handle prefixed variables
        if ":" in var_expr:
            prefix, value = var_expr.split(":", 1)

            if prefix == "env":
                # Check if it has a nested colon (default value)
                env_var = value.split(":", 1)[0] if ":" in value else value
                return (
                    f"Environment variable '${{{var_expr}}}' is not set. "
                    f"Set the {env_var} environment variable, or use the "
                    f"AIDB default syntax: ${{env:{env_var}:default_value}}"
                )

            if prefix == "config":
                return (
                    f"Config variable '${{{var_expr}}}' requires VS Code settings "
                    "context and cannot be resolved outside VS Code. "
                    "Replace with a specific value in your launch configuration."
                )

            if prefix == "command":
                return (
                    f"Command variable '${{{var_expr}}}' requires VS Code runtime "
                    "and cannot be resolved outside VS Code. "
                    "Replace with a specific value in your launch configuration."
                )

            if prefix == "input":
                return (
                    f"Input variable '${{{var_expr}}}' requires VS Code runtime "
                    "and cannot be resolved outside VS Code. "
                    "Replace with a specific value in your launch configuration."
                )

        # Check file-based variables
        if var_expr in self.FILE_VARIABLES:
            return (
                f"Variable '${{{var_expr}}}' requires a target file. "
                "Provide the 'target' parameter when starting the debug session."
            )

        # Check unsupported runtime variables
        if var_expr in self.UNSUPPORTED_VARIABLES:
            return (
                f"Variable '${{{var_expr}}}' requires VS Code runtime context "
                "and cannot be resolved outside VS Code."
            )

        return (
            f"Unknown variable '${{{var_expr}}}'. "
            "See https://code.visualstudio.com/docs/reference/variables-reference"
        )

    def resolve_dict(
        self,
        data: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Recursively resolve VS Code variables in a dictionary.

        Parameters
        ----------
        data : dict
            Dictionary potentially containing VS Code variables in values
        context : dict, optional
            Additional context for variable resolution

        Returns
        -------
        dict
            Dictionary with resolved variables

        Raises
        ------
        VSCodeVariableError
            If any variable cannot be resolved
        """
        result: dict[str, Any] = {}
        for key, value in data.items():
            if isinstance(value, str):
                try:
                    result[key] = self.resolve(value, context)
                except VSCodeVariableError as e:
                    msg = f"Error in field '{key}': {e}"
                    raise VSCodeVariableError(msg) from e
            elif isinstance(value, dict):
                result[key] = self.resolve_dict(value, context)
            elif isinstance(value, list):
                result[key] = [
                    self.resolve(item, context) if isinstance(item, str) else item
                    for item in value
                ]
            else:
                result[key] = value
        return result

    def has_unresolvable_variables(self, value: str) -> bool:
        """Check if a string contains unresolvable VS Code variables.

        Parameters
        ----------
        value : str
            String to check

        Returns
        -------
        bool
            True if unresolvable variables are present
        """
        matches = self.VARIABLE_PATTERN.findall(value)
        return any(self._resolve_variable(var_expr, {}) is None for var_expr in matches)

    def validate_launch_config(self, config: Any, config_name: str = "unknown") -> None:
        """Validate a launch configuration for unresolvable VS Code variables.

        Parameters
        ----------
        config : Any
            Launch configuration object with fields like program, cwd, args
        config_name : str
            Name of the configuration for error messages

        Raises
        ------
        VSCodeVariableError
            If unresolvable variables are found
        """
        self.ctx.debug(
            f"Validating launch config '{config_name}' for VS Code variables",
        )

        fields_to_check = []

        if hasattr(config, "program") and config.program:
            fields_to_check.append(("program", config.program))
        if hasattr(config, "cwd") and config.cwd:
            fields_to_check.append(("cwd", config.cwd))
        if hasattr(config, "args") and config.args:
            for i, arg in enumerate(config.args):
                fields_to_check.append((f"args[{i}]", arg))

        for field_name, value in fields_to_check:
            if isinstance(value, str) and self.has_unresolvable_variables(value):
                try:
                    self.resolve(value)
                except VSCodeVariableError as e:
                    msg = (
                        f"Launch configuration '{config_name}' has "
                        f"unresolvable variable in {field_name}: {e}"
                    )
                    summary = "Launch config contains unresolvable VS Code variables"
                    raise VSCodeVariableError(msg, summary=summary) from e


# =============================================================================
# Variable Resolver Registry
# =============================================================================
# Register predefined variable resolvers using decorators for clean organization


def _predefined(name: str) -> Callable[[VariableResolver], VariableResolver]:
    """Register a predefined variable resolver."""

    def decorator(func: VariableResolver) -> VariableResolver:
        VSCodeVariableResolver.PREDEFINED_VARIABLES[name] = func
        return func

    return decorator


def _file_var(name: str) -> Callable[[VariableResolver], VariableResolver]:
    """Register a file-based variable resolver."""

    def decorator(func: VariableResolver) -> VariableResolver:
        VSCodeVariableResolver.FILE_VARIABLES[name] = func
        return func

    return decorator


# -----------------------------------------------------------------------------
# Predefined Variables (always resolvable)
# -----------------------------------------------------------------------------


@_predefined("workspaceFolder")
def _resolve_workspace_folder(
    resolver: VSCodeVariableResolver,
    _var_expr: str,
    _context: dict[str, Any],
) -> str:
    return str(resolver.workspace_root)


@_predefined("workspaceFolderBasename")
def _resolve_workspace_folder_basename(
    resolver: VSCodeVariableResolver,
    _var_expr: str,
    _context: dict[str, Any],
) -> str:
    return resolver.workspace_root.name


@_predefined("userHome")
def _resolve_user_home(
    _resolver: VSCodeVariableResolver,
    _var_expr: str,
    _context: dict[str, Any],
) -> str:
    return str(Path.home())


@_predefined("pathSeparator")
def _resolve_path_separator(
    _resolver: VSCodeVariableResolver,
    _var_expr: str,
    _context: dict[str, Any],
) -> str:
    return os.sep


@_predefined("/")
def _resolve_path_separator_short(
    _resolver: VSCodeVariableResolver,
    _var_expr: str,
    _context: dict[str, Any],
) -> str:
    return os.sep


@_predefined("cwd")
def _resolve_cwd(
    _resolver: VSCodeVariableResolver,
    _var_expr: str,
    _context: dict[str, Any],
) -> str:
    return str(Path.cwd())


# Date/time variables - use local time for consistency with VS Code behavior
@_predefined("currentYear")
def _resolve_current_year(
    _resolver: VSCodeVariableResolver,
    _var_expr: str,
    _context: dict[str, Any],
) -> str:
    return str(datetime.now(tz=timezone.utc).astimezone().year)


@_predefined("currentMonth")
def _resolve_current_month(
    _resolver: VSCodeVariableResolver,
    _var_expr: str,
    _context: dict[str, Any],
) -> str:
    return f"{datetime.now(tz=timezone.utc).astimezone().month:02d}"


@_predefined("currentDay")
def _resolve_current_day(
    _resolver: VSCodeVariableResolver,
    _var_expr: str,
    _context: dict[str, Any],
) -> str:
    return f"{datetime.now(tz=timezone.utc).astimezone().day:02d}"


@_predefined("currentHour")
def _resolve_current_hour(
    _resolver: VSCodeVariableResolver,
    _var_expr: str,
    _context: dict[str, Any],
) -> str:
    return f"{datetime.now(tz=timezone.utc).astimezone().hour:02d}"


@_predefined("currentMinute")
def _resolve_current_minute(
    _resolver: VSCodeVariableResolver,
    _var_expr: str,
    _context: dict[str, Any],
) -> str:
    return f"{datetime.now(tz=timezone.utc).astimezone().minute:02d}"


@_predefined("currentSecond")
def _resolve_current_second(
    _resolver: VSCodeVariableResolver,
    _var_expr: str,
    _context: dict[str, Any],
) -> str:
    return f"{datetime.now(tz=timezone.utc).astimezone().second:02d}"


# -----------------------------------------------------------------------------
# File-based Variables (require target in context)
# -----------------------------------------------------------------------------


def _get_target_path(context: dict[str, Any]) -> Path | None:
    """Get target path from context."""
    target = context.get("target")
    return Path(target) if target else None


@_file_var("file")
def _resolve_file(
    _resolver: VSCodeVariableResolver,
    _var_expr: str,
    context: dict[str, Any],
) -> str | None:
    target = _get_target_path(context)
    return str(target.absolute()) if target else None


@_file_var("fileBasename")
def _resolve_file_basename(
    _resolver: VSCodeVariableResolver,
    _var_expr: str,
    context: dict[str, Any],
) -> str | None:
    target = _get_target_path(context)
    return target.name if target else None


@_file_var("fileBasenameNoExtension")
def _resolve_file_basename_no_ext(
    _resolver: VSCodeVariableResolver,
    _var_expr: str,
    context: dict[str, Any],
) -> str | None:
    target = _get_target_path(context)
    return target.stem if target else None


@_file_var("fileExtname")
def _resolve_file_extname(
    _resolver: VSCodeVariableResolver,
    _var_expr: str,
    context: dict[str, Any],
) -> str | None:
    target = _get_target_path(context)
    return target.suffix if target else None


@_file_var("fileDirname")
def _resolve_file_dirname(
    _resolver: VSCodeVariableResolver,
    _var_expr: str,
    context: dict[str, Any],
) -> str | None:
    target = _get_target_path(context)
    return str(target.parent.absolute()) if target else None


@_file_var("fileDirnameBasename")
def _resolve_file_dirname_basename(
    _resolver: VSCodeVariableResolver,
    _var_expr: str,
    context: dict[str, Any],
) -> str | None:
    target = _get_target_path(context)
    return target.parent.name if target else None


@_file_var("relativeFile")
def _resolve_relative_file(
    resolver: VSCodeVariableResolver,
    _var_expr: str,
    context: dict[str, Any],
) -> str | None:
    target = _get_target_path(context)
    if not target:
        return None
    try:
        return str(target.relative_to(resolver.workspace_root))
    except ValueError:
        return str(target)


@_file_var("relativeFileDirname")
def _resolve_relative_file_dirname(
    resolver: VSCodeVariableResolver,
    _var_expr: str,
    context: dict[str, Any],
) -> str | None:
    target = _get_target_path(context)
    if not target:
        return None
    try:
        return str(target.parent.relative_to(resolver.workspace_root))
    except ValueError:
        return str(target.parent)


@_file_var("fileWorkspaceFolder")
def _resolve_file_workspace_folder(
    resolver: VSCodeVariableResolver,
    _var_expr: str,
    context: dict[str, Any],
) -> str | None:
    # In single-root workspace, this is the same as workspaceFolder
    target = _get_target_path(context)
    return str(resolver.workspace_root) if target else None
