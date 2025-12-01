"""Variable state verification utilities.

This module provides the VariableStateVerifier class for validating variable state
during debugging sessions.
"""

from typing import Any


class VariableStateVerifier:
    """Verify variable state across execution.

    This verifier provides methods to validate variable existence, values, types, and
    changes during debugging sessions.
    """

    @staticmethod
    def _extract_value(var_info: Any) -> Any:
        """Extract value from variable info dict or return raw value.

        Parameters
        ----------
        var_info : Any
            Variable info (dict with 'value' key, AidbVariable object, or raw value)

        Returns
        -------
        Any
            Extracted value
        """
        # Handle AidbVariable dataclass or any object with .value attribute
        if hasattr(var_info, "value"):
            return var_info.value
        # Handle dict format
        if isinstance(var_info, dict) and "value" in var_info:
            return var_info["value"]
        return var_info

    @staticmethod
    def verify_variable_exists(
        variables: dict[str, Any],
        name: str,
    ) -> None:
        """Verify a variable exists in the variables dictionary.

        Parameters
        ----------
        variables : dict[str, Any]
            Variables dictionary from get_variables()
        name : str
            Variable name to check

        Raises
        ------
        AssertionError
            If variable doesn't exist
        """
        if name not in variables:
            available = list(variables.keys())
            msg = f"Variable '{name}' not found. Available variables: {available}"
            raise AssertionError(msg)

    @staticmethod
    def verify_variable_value(
        variables: dict[str, Any],
        name: str,
        expected_value: Any,
    ) -> None:
        """Verify a variable has the expected value.

        Parameters
        ----------
        variables : dict[str, Any]
            Variables dictionary from get_variables()
        name : str
            Variable name to check
        expected_value : Any
            Expected value

        Raises
        ------
        AssertionError
            If variable doesn't exist or has wrong value
        """
        VariableStateVerifier.verify_variable_exists(variables, name)

        var_info = variables[name]
        actual_value = VariableStateVerifier._extract_value(var_info)

        # Compare as strings for flexibility across types
        if str(actual_value) != str(expected_value):
            msg = (
                f"Variable '{name}': expected value {expected_value!r}, "
                f"but got {actual_value!r}"
            )
            raise AssertionError(msg)

    @staticmethod
    def verify_variable_type(
        variables: dict[str, Any],
        name: str,
        expected_type: type | str,
    ) -> None:
        """Verify a variable has the expected type.

        Parameters
        ----------
        variables : dict[str, Any]
            Variables dictionary from get_variables()
        name : str
            Variable name to check
        expected_type : type | str
            Expected type (class or string type name)

        Raises
        ------
        AssertionError
            If variable doesn't exist or has wrong type
        """
        VariableStateVerifier.verify_variable_exists(variables, name)

        var_info = variables[name]
        actual_value = VariableStateVerifier._extract_value(var_info)
        type_info = var_info.get("type") if isinstance(var_info, dict) else None

        # Get expected type name
        if isinstance(expected_type, type):
            expected_type_name = expected_type.__name__
        else:
            expected_type_name = expected_type

        # Check type
        if isinstance(expected_type, type):
            if not isinstance(actual_value, expected_type):
                actual_type_name = type(actual_value).__name__
                msg = (
                    f"Variable '{name}': expected type {expected_type_name}, "
                    f"but got {actual_type_name}"
                )
                raise AssertionError(msg)
        elif (
            type_info is not None
            and expected_type_name.lower() not in type_info.lower()
        ):
            # Use type info from dict if available
            msg = (
                f"Variable '{name}': expected type '{expected_type_name}', "
                f"but got '{type_info}'"
            )
            raise AssertionError(msg)

    @staticmethod
    def verify_variable_changed(
        before: dict[str, Any],
        after: dict[str, Any],
        name: str,
    ) -> None:
        """Verify a variable value changed between two states.

        Parameters
        ----------
        before : dict[str, Any]
            Variables before the change
        after : dict[str, Any]
            Variables after the change
        name : str
            Variable name to check

        Raises
        ------
        AssertionError
            If variable doesn't exist in both states or didn't change
        """
        VariableStateVerifier.verify_variable_exists(before, name)
        VariableStateVerifier.verify_variable_exists(after, name)

        before_value = VariableStateVerifier._extract_value(before[name])
        after_value = VariableStateVerifier._extract_value(after[name])

        if str(before_value) == str(after_value):
            msg = f"Variable '{name}' did not change: value is still {before_value!r}"
            raise AssertionError(msg)

    @staticmethod
    def verify_variables_match(
        variables: dict[str, Any],
        expected_dict: dict[str, Any],
    ) -> None:
        """Verify multiple variables match expected values.

        Parameters
        ----------
        variables : dict[str, Any]
            Variables dictionary from get_variables()
        expected_dict : dict[str, Any]
            Dictionary of expected variable names to values

        Raises
        ------
        AssertionError
            If any variable doesn't match expectations
        """
        for name, expected_value in expected_dict.items():
            VariableStateVerifier.verify_variable_value(variables, name, expected_value)

    @staticmethod
    def verify_scope_variables(
        variables: dict[str, Any],
        scope: str,
        expected_names: list[str],
    ) -> None:
        """Verify specific variables exist in a scope.

        Parameters
        ----------
        variables : dict[str, Any]
            Variables dictionary from get_variables()
        scope : str
            Scope name (for error messages)
        expected_names : list[str]
            List of expected variable names

        Raises
        ------
        AssertionError
            If any expected variable is missing
        """
        missing = [name for name in expected_names if name not in variables]

        if missing:
            available = list(variables.keys())
            msg = (
                f"Missing variables in {scope} scope: {missing}. Available: {available}"
            )
            raise AssertionError(msg)

    @staticmethod
    def verify_variable_count(
        variables: dict[str, Any],
        min_count: int | None = None,
        max_count: int | None = None,
        exact_count: int | None = None,
    ) -> None:
        """Verify variable count meets expectations.

        Parameters
        ----------
        variables : dict[str, Any]
            Variables dictionary from get_variables()
        min_count : int, optional
            Minimum expected number of variables
        max_count : int, optional
            Maximum expected number of variables
        exact_count : int, optional
            Exact expected number of variables

        Raises
        ------
        AssertionError
            If variable count doesn't meet expectations
        """
        actual_count = len(variables)

        if exact_count is not None and actual_count != exact_count:
            msg = f"Expected exactly {exact_count} variables, got {actual_count}"
            raise AssertionError(msg)

        if min_count is not None and actual_count < min_count:
            msg = f"Expected at least {min_count} variables, got {actual_count}"
            raise AssertionError(msg)

        if max_count is not None and actual_count > max_count:
            msg = f"Expected at most {max_count} variables, got {actual_count}"
            raise AssertionError(msg)
