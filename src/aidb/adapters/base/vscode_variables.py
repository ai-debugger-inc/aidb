"""VS Code variable resolution for launch configurations."""

import os
import re
from pathlib import Path
from typing import Any

from aidb.common.errors import VSCodeVariableError
from aidb.patterns import Obj


class VSCodeVariableResolver(Obj):
    """Resolves VS Code variables in launch configurations.

    Handles common VS Code variables like ${workspaceFolder}, ${env:VAR}, etc. Raises
    helpful errors for variables that require VS Code runtime context.
    """

    # VS Code variables that require runtime context (cannot be resolved)
    RUNTIME_ONLY_VARIABLES = {
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
    }

    # Pattern to match VS Code variables: ${variableName} or ${prefix:value}
    VARIABLE_PATTERN = re.compile(r"\$\{([^}]+)\}")

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
            Additional context for variable resolution, e.g., {'target': '/path/to/file.py'}

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

        FILE_VARS = [
            "file",
            "fileBasename",
            "fileBasenameNoExtension",
            "fileExtname",
            "fileDirname",
        ]

        def replacer(match):
            var_expr = match.group(1)

            # Handle ${file} and related variables using target from context
            if var_expr in FILE_VARS:
                target = context.get("target")
                if target:
                    target_path = Path(target)
                    if var_expr == "file":
                        return str(target_path.absolute())
                    if var_expr == "fileBasename":
                        return target_path.name
                    if var_expr == "fileBasenameNoExtension":
                        return target_path.stem
                    if var_expr == "fileExtname":
                        return target_path.suffix
                    if var_expr == "fileDirname":
                        return str(target_path.parent.absolute())

            # Handle ${workspaceFolder} and variants
            if var_expr == "workspaceFolder":
                return str(self.workspace_root)
            if var_expr == "workspaceFolderBasename":
                return self.workspace_root.name

            # Handle ${env:VARIABLE_NAME}
            if var_expr.startswith("env:"):
                env_var = var_expr[4:]
                env_value = os.environ.get(env_var)
                if env_value is None:
                    msg = (
                        f"Environment variable '${{env:{env_var}}}' is not set. "
                        f"Please set the {env_var} environment variable or update "
                        "your launch configuration to use a specific value."
                    )
                    raise VSCodeVariableError(msg)
                return env_value

            # Handle ${command:commandID}
            if var_expr.startswith("command:"):
                command_id = var_expr[8:]
                msg = (
                    f"Command variable '${{command:{command_id}}}' requires "
                    "VS Code runtime context and cannot be resolved outside "
                    "of VS Code. Please update your launch configuration to "
                    "use a specific value instead."
                )
                raise VSCodeVariableError(msg)

            # Check if it's a runtime-only variable
            if var_expr in self.RUNTIME_ONLY_VARIABLES:
                msg = (
                    f"Variable '${{{var_expr}}}' requires VS Code runtime context "
                    "and cannot be resolved outside of VS Code.\n\n"
                )

                # Provide specific guidance based on the variable
                if var_expr in FILE_VARS:
                    msg += (
                        f"The '${{{var_expr}}}' variable represents the currently "
                        "active file in VS Code. In MCP, you can resolve this by "
                        "providing a 'target' parameter.\n\n"
                        "To fix this:\n"
                        "1. Add 'target' parameter to your session_start call:\n"
                        "   session_start(\n"
                        "       launch_config_name='Your Config',\n"
                        "       target='/path/to/file.py'  # <-- Resolves ${file}\n"
                        "   )\n\n"
                        "2. Or update your launch configuration to use a specific "
                        "file path instead"
                    )
                else:
                    msg += (
                        "Please update your launch configuration to use a specific "
                        "value instead of this runtime variable."
                    )

                raise VSCodeVariableError(msg)

            # Unknown variable
            msg = (
                f"Unknown VS Code variable '${{{var_expr}}}'. "
                "Please update your launch configuration to use a "
                "supported variable or specific value."
            )
            raise VSCodeVariableError(msg)

        return self.VARIABLE_PATTERN.sub(replacer, value)

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
            Additional context for variable resolution,
            e.g., {'target': '/path/to/file.py'}

        Returns
        -------
        dict
            Dictionary with resolved variables

        Raises
        ------
        VSCodeVariableError
            If any variable cannot be resolved
        """
        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                try:
                    result[key] = self.resolve(value, context)
                except VSCodeVariableError as e:
                    # Add context about which field had the error
                    msg = f"Error in field '{key}': {e}"
                    raise VSCodeVariableError(msg) from e
            elif isinstance(value, dict):
                result[key] = self.resolve_dict(value, context)  # type: ignore[assignment]
            elif isinstance(value, list):
                result[key] = [  # type: ignore[assignment]
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
        for var_expr in matches:
            # Check for runtime-only variables
            if var_expr in self.RUNTIME_ONLY_VARIABLES:
                return True
            # Check for command variables
            if var_expr.startswith("command:"):
                return True
        return False

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

        # Check common fields that might contain variables
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
                # Try to resolve it to get a helpful error message
                try:
                    self.resolve(value)
                except VSCodeVariableError as e:
                    # Add context about the configuration
                    msg = (
                        f"Launch configuration '{config_name}' contains "
                        f"unresolvable VS Code variable in {field_name}: {e}\n\n"
                        "To fix this, either:\n"
                        "1. Update the launch configuration to use a specific value\n"
                        "2. Run the debugger from within VS Code where these "
                        "variables can be resolved\n"
                        "3. Pass the target file directly when starting the "
                        "debug session"
                    )
                    summary = "Launch config contains unresolvable VS Code variables"
                    raise VSCodeVariableError(msg, summary=summary) from e
