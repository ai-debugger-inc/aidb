"""Environment variable validation utilities."""

import os
import re
from typing import Any

from aidb_common.env.reader import FALSY_VALUES, TRUTHY_VALUES


class EnvironmentValidationError(Exception):
    """Raised when environment variable validation fails."""


def validate_required_vars(required: list[str]) -> None:
    """Validate that all required environment variables are set.

    Parameters
    ----------
    required : list[str]
        List of required environment variable names

    Raises
    ------
    EnvironmentValidationError
        If any required variables are missing
    """
    missing = [var for var in required if var not in os.environ]
    if missing:
        msg = f"Missing required environment variables: {', '.join(missing)}"
        raise EnvironmentValidationError(
            msg,
        )


def validate_mutex_vars(groups: list[list[str]]) -> None:
    """Validate that mutually exclusive environment variable groups are properly set.

    Each group should have exactly one variable set, not zero and not multiple.

    Parameters
    ----------
    groups : list[list[str]]
        List of mutually exclusive variable groups

    Raises
    ------
    EnvironmentValidationError
        If any group has zero or multiple variables set
    """
    for group in groups:
        set_vars = [var for var in group if var in os.environ]

        if len(set_vars) == 0:
            group_str = ", ".join(group)
            msg = f"Exactly one of these environment variables must be set: {group_str}"
            raise EnvironmentValidationError(msg)
        if len(set_vars) > 1:
            set_vars_str = ", ".join(set_vars)
            msg = f"Only one of these environment variables can be set: {set_vars_str}"
            raise EnvironmentValidationError(msg)


def validate_var_format(key: str, pattern: str, required: bool = True) -> bool:
    """Validate that an environment variable matches a specific format.

    Parameters
    ----------
    key : str
        Environment variable name
    pattern : str
        Regular expression pattern to match
    required : bool
        Whether the variable is required to exist

    Returns
    -------
    bool
        True if validation passes

    Raises
    ------
    EnvironmentValidationError
        If validation fails
    """
    value = os.environ.get(key)

    if value is None:
        if required:
            msg = f"Required environment variable {key} is not set"
            raise EnvironmentValidationError(msg)
        return True

    if not re.match(pattern, value):
        msg = f"Environment variable {key} does not match required format: {pattern}"
        raise EnvironmentValidationError(
            msg,
        )

    return True


def validate_env_types(specs: dict[str, dict[str, Any]]) -> None:  # noqa: C901
    """Validate environment variables against type specifications.

    Parameters
    ----------
    specs : dict[str, dict[str, Any]]
        Dictionary mapping variable names to validation specs.
        Each spec can contain:
        - type: expected type ("str", "int", "float", "bool", "list")
        - required: whether variable is required (default: False)
        - choices: list of allowed values (for strings)
        - min_value/max_value: range constraints (for numbers)
        - pattern: regex pattern (for strings)

    Raises
    ------
    EnvironmentValidationError
        If any validation fails
    """
    from aidb_common.env.reader import (
        read_float,
        read_int,
        read_list,
        read_str,
    )

    for var_name, spec in specs.items():
        value = os.environ.get(var_name)
        required = spec.get("required", False)
        var_type = spec.get("type", "str")

        # Check if required variable exists
        if required and value is None:
            msg = f"Required environment variable {var_name} is not set"
            raise EnvironmentValidationError(msg)

        # Skip validation if variable is not set and not required
        if value is None:
            continue

        # Type-specific validation
        try:
            if var_type == "int":
                parsed_value = read_int(var_name)
                if parsed_value is None:
                    msg = f"Environment variable {var_name} is not a valid integer"
                    raise EnvironmentValidationError(msg)

                # Range validation
                if "min_value" in spec and parsed_value < spec["min_value"]:
                    min_val = spec["min_value"]
                    msg = f"Environment variable {var_name} must be >= {min_val}"
                    raise EnvironmentValidationError(msg)
                if "max_value" in spec and parsed_value > spec["max_value"]:
                    max_val = spec["max_value"]
                    msg = f"Environment variable {var_name} must be <= {max_val}"
                    raise EnvironmentValidationError(msg)

            elif var_type == "float":
                parsed_value = read_float(var_name)
                if parsed_value is None:
                    msg = f"Environment variable {var_name} is not a valid float"
                    raise EnvironmentValidationError(msg)

                # Range validation
                if "min_value" in spec and parsed_value < spec["min_value"]:
                    min_val = spec["min_value"]
                    msg = f"Environment variable {var_name} must be >= {min_val}"
                    raise EnvironmentValidationError(msg)
                if "max_value" in spec and parsed_value > spec["max_value"]:
                    max_val = spec["max_value"]
                    msg = f"Environment variable {var_name} must be <= {max_val}"
                    raise EnvironmentValidationError(msg)

            elif var_type == "bool":
                normalized = value.strip().lower()
                if normalized not in TRUTHY_VALUES | FALSY_VALUES:
                    msg = (
                        f"Environment variable {var_name} is not a valid boolean value"
                    )
                    raise EnvironmentValidationError(msg)

            elif var_type == "list":
                delimiter = spec.get("delimiter", ",")
                parsed_value = read_list(var_name, delimiter=delimiter)
                if parsed_value is None:
                    parsed_value = []

            elif var_type == "str":
                parsed_value = read_str(var_name)

                # Choice validation
                if "choices" in spec and parsed_value not in spec["choices"]:
                    choices_str = ", ".join(spec["choices"])
                    msg = (
                        f"Environment variable {var_name} must be one of: {choices_str}"
                    )
                    raise EnvironmentValidationError(msg)

                # Pattern validation
                if (
                    "pattern" in spec
                    and parsed_value
                    and not re.match(spec["pattern"], parsed_value)
                ):
                    pattern = spec["pattern"]
                    msg = (
                        f"Environment variable {var_name} does not match "
                        f"required pattern: {pattern}"
                    )
                    raise EnvironmentValidationError(msg)

        except Exception as e:
            if isinstance(e, EnvironmentValidationError):
                raise
            msg = f"Error validating {var_name}: {e}"
            raise EnvironmentValidationError(msg) from e
