"""Response and data validation helpers for tests."""

from typing import Any, Optional

import pytest


class ValidationMixin:
    """Mixin providing validation utilities for structured responses."""

    def assert_response_structure(
        self,
        response: dict[str, Any],
        required_fields: list,
        optional_fields: list | None = None,
    ) -> None:
        """Assert that a response has the expected structure.

        Parameters
        ----------
        response : Dict[str, Any]
            Response to validate
        required_fields : list
            Fields that must be present
        optional_fields : list, optional
            Fields that may be present
        """
        for field in required_fields:
            assert field in response, f"Missing required field: {field}"

        if optional_fields:
            all_fields = set(required_fields + optional_fields)
            extra_fields = set(response.keys()) - all_fields
            if extra_fields and hasattr(self, "logger"):
                self.logger.debug("Unexpected fields in response: %s", extra_fields)

    def assert_field_types(
        self,
        data: dict[str, Any],
        type_map: dict[str, type],
    ) -> None:
        """Assert that fields have expected types.

        Parameters
        ----------
        data : Dict[str, Any]
            Data to validate
        type_map : Dict[str, type]
            Mapping of field names to expected types
        """
        for field, expected_type in type_map.items():
            if field in data:
                value = data[field]
                if value is not None:  # Allow None unless type is explicitly checked
                    assert isinstance(value, expected_type), (
                        f"Field {field} has wrong type: expected "
                        f"{expected_type.__name__}, got {type(value).__name__}"
                    )

    def assert_nested_value(
        self,
        data: dict[str, Any],
        path: str,
        expected_value: Any = None,
        check_exists: bool = True,
    ) -> Any:
        """Assert and retrieve a nested value from a dictionary.

        Parameters
        ----------
        data : Dict[str, Any]
            Data dictionary
        path : str
            Dot-separated path (e.g., "user.profile.name")
        expected_value : Any, optional
            Expected value to assert
        check_exists : bool
            Whether to assert the path exists

        Returns
        -------
        Any
            The value at the path
        """
        keys = path.split(".")
        current = data

        for i, key in enumerate(keys):
            if check_exists:
                assert key in current, (
                    f"Missing key '{key}' at path '{'.'.join(keys[: i + 1])}'"
                )

            if key not in current:
                return None

            current = current[key]

        if expected_value is not None:
            assert current == expected_value, (
                f"Value at path '{path}' doesn't match expected"
            )

        return current

    def validate_api_response(
        self,
        response: dict[str, Any],
        success_field: str = "success",
        data_field: str = "data",
        error_field: str = "error",
    ) -> dict[str, Any]:
        """Validate a standard API response structure.

        Parameters
        ----------
        response : Dict[str, Any]
            API response
        success_field : str
            Name of success indicator field
        data_field : str
            Name of data field
        error_field : str
            Name of error field

        Returns
        -------
        Dict[str, Any]
            The data field if successful
        """
        assert success_field in response, f"Response missing {success_field} field"

        if response.get(success_field):
            assert data_field in response, (
                f"Success response missing {data_field} field"
            )
            return response[data_field]
        if error_field in response:
            error_msg = response.get(
                f"{error_field}_message",
                response.get(error_field),
            )
            pytest.fail(f"API request failed: {error_msg}")
        else:
            pytest.fail("API request failed with no error message")

        # This line should never be reached due to pytest.fail() above
        return {}

    def assert_list_contains(
        self,
        items: list,
        expected_item: Any,
        key: str | None = None,
    ) -> None:
        """Assert that a list contains an expected item.

        Parameters
        ----------
        items : list
            List to search
        expected_item : Any
            Item to find
        key : str, optional
            If items are dicts, compare using this key
        """
        if key:
            found = any(
                item.get(key) == expected_item
                for item in items
                if isinstance(item, dict)
            )
            assert found, f"No item with {key}={expected_item} found in list"
        else:
            assert expected_item in items
