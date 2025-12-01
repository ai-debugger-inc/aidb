"""Tests for aidb_common.validation module."""

import pytest

from aidb_common.validation import (
    EnvironmentValidationError,
    validate_env_types,
    validate_mutex_vars,
    validate_required_vars,
    validate_var_format,
)


class TestValidation:
    """Test environment variable validation."""

    def test_validate_required_vars_success(self, set_env):
        """Test validate_required_vars with all variables present."""
        set_env("VAR1", "value1")
        set_env("VAR2", "value2")

        # Should not raise
        validate_required_vars(["VAR1", "VAR2"])

    def test_validate_required_vars_missing(self, set_env):
        """Test validate_required_vars with missing variables."""
        set_env("VAR1", "value1")

        with pytest.raises(
            EnvironmentValidationError,
            match="Missing required environment variables: VAR2",
        ):
            validate_required_vars(["VAR1", "VAR2"])

    def test_validate_mutex_vars_success(self, set_env):
        """Test validate_mutex_vars with exactly one var per group."""
        set_env("VAR1", "value1")
        set_env("VAR3", "value3")

        # Should not raise - one from each group
        validate_mutex_vars([["VAR1", "VAR2"], ["VAR3", "VAR4"]])

    def test_validate_mutex_vars_none_set(self):
        """Test validate_mutex_vars with no variables set in a group."""
        with pytest.raises(
            EnvironmentValidationError,
            match="Exactly one of these environment variables must be set",
        ):
            validate_mutex_vars([["VAR1", "VAR2"]])

    def test_validate_mutex_vars_multiple_set(self, set_env):
        """Test validate_mutex_vars with multiple variables set in a group."""
        set_env("VAR1", "value1")
        set_env("VAR2", "value2")

        with pytest.raises(
            EnvironmentValidationError,
            match="Only one of these environment variables can be set",
        ):
            validate_mutex_vars([["VAR1", "VAR2"]])

    def test_validate_var_format_success(self, set_env):
        """Test validate_var_format with valid format."""
        set_env("TEST_VAR", "test123")

        # Should not raise
        assert validate_var_format("TEST_VAR", r"^test\d+$") is True

    def test_validate_var_format_invalid(self, set_env):
        """Test validate_var_format with invalid format."""
        set_env("TEST_VAR", "invalid")

        with pytest.raises(
            EnvironmentValidationError,
            match="does not match required format",
        ):
            validate_var_format("TEST_VAR", r"^test\d+$")

    def test_validate_var_format_missing_required(self):
        """Test validate_var_format with missing required variable."""
        with pytest.raises(
            EnvironmentValidationError,
            match="Required environment variable .* is not set",
        ):
            validate_var_format("MISSING_VAR", r".*", required=True)

    def test_validate_var_format_missing_optional(self):
        """Test validate_var_format with missing optional variable."""
        # Should not raise
        assert validate_var_format("MISSING_VAR", r".*", required=False) is True

    def test_validate_env_types_success(self, set_env):
        """Test validate_env_types with valid types."""
        set_env("INT_VAR", "42")
        set_env("BOOL_VAR", "true")
        set_env("STR_VAR", "hello")

        specs = {
            "INT_VAR": {"type": "int", "required": True},
            "BOOL_VAR": {"type": "bool"},
            "STR_VAR": {"type": "str", "choices": ["hello", "world"]},
        }

        # Should not raise
        validate_env_types(specs)

    def test_validate_env_types_invalid_choice(self, set_env):
        """Test validate_env_types with invalid choice."""
        set_env("STR_VAR", "invalid")

        specs = {
            "STR_VAR": {"type": "str", "choices": ["hello", "world"]},
        }

        with pytest.raises(EnvironmentValidationError, match="must be one of"):
            validate_env_types(specs)

    def test_validate_env_types_out_of_range(self, set_env):
        """Test validate_env_types with out of range value."""
        set_env("INT_VAR", "150")

        specs = {
            "INT_VAR": {"type": "int", "min_value": 0, "max_value": 100},
        }

        with pytest.raises(EnvironmentValidationError, match="must be <="):
            validate_env_types(specs)
