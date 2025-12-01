"""Tests for enhanced CLI parameter types."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import click
import pytest

from aidb_cli.core.param_types import (
    FlexiblePatternParamType,
    TestMarkerParamType,
    TestPatternParamType,
)
from aidb_common.test.markers import get_marker_descriptions


class TestFlexiblePatternParamType:
    """Test the flexible pattern parameter type."""

    def setup_method(self):
        """Set up test fixtures."""
        self.param_type = FlexiblePatternParamType()
        self.mock_param = Mock()
        self.mock_ctx = Mock()

    def test_convert_accepts_any_string(self):
        """Test that FlexiblePatternParamType accepts any string."""
        test_patterns = [
            "*adapter*",
            "test_session*",
            "*_integration*",
            "test_*_real*",
            "*slow* and not unit",
            "requires_docker or docker",
            "not flaky",
            "TestAdapter* or test_adapter*",
            "*framework* and integration",
            "complex and (pattern or expression) and not (slow or flaky)",
        ]

        for pattern in test_patterns:
            result = self.param_type.convert(pattern, self.mock_param, self.mock_ctx)
            assert result == pattern

    def test_convert_handles_none(self):
        """Test that None values are handled correctly."""
        result = self.param_type.convert(None, self.mock_param, self.mock_ctx)
        assert result is None

    def test_get_metavar(self):
        """Test that metavar shows pytest expression format."""
        metavar = self.param_type.get_metavar(self.mock_param, self.mock_ctx)
        assert metavar == "<pytest_expression>"

    def test_shell_complete(self):
        """Test shell completion provides useful suggestions."""
        # Test partial completion
        completions = self.param_type.shell_complete(
            self.mock_ctx,
            self.mock_param,
            "test_",
        )
        completion_values = [c.value for c in completions]

        assert "test_*" in completion_values
        assert len(completion_values) > 0

    def test_shell_complete_case_insensitive(self):
        """Test shell completion is case insensitive."""
        completions_lower = self.param_type.shell_complete(
            self.mock_ctx,
            self.mock_param,
            "test",
        )
        completions_upper = self.param_type.shell_complete(
            self.mock_ctx,
            self.mock_param,
            "TEST",
        )

        # Should return same completions regardless of case
        assert len(completions_lower) > 0
        assert len(completions_upper) > 0

    def test_backward_compatibility(self):
        """Test that TestPatternParamType redirects to FlexiblePatternParamType."""
        legacy_type = TestPatternParamType()

        # Should behave exactly like FlexiblePatternParamType
        test_pattern = "*payment*"
        result = legacy_type.convert(test_pattern, self.mock_param, self.mock_ctx)
        assert result == test_pattern


class TestEnhancedMarkerDiscovery:
    """Test enhanced marker discovery from pyproject.toml."""

    def setup_method(self):
        """Set up test fixtures."""
        self.marker_type = TestMarkerParamType()

    def test_marker_descriptions_available(self):
        """Test that marker descriptions are available."""
        descriptions = get_marker_descriptions()

        expected_markers = {
            "unit": "Unit tests",
            "integration": "Integration tests",
            "e2e": "End-to-end tests",
            "slow": "Slow tests",
            "asyncio": "Async tests",
        }

        for marker, description in expected_markers.items():
            assert marker in descriptions
            assert descriptions[marker] == description

    def test_discovers_pyproject_markers(self):
        """Test that markers are discovered from pyproject.toml."""
        with patch("aidb_cli.core.param_types._get_repo_root_from_ctx") as mock_root:
            # Create a temporary directory structure
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)
                mock_root.return_value = tmp_path

                # Create a mock pyproject.toml with markers
                pyproject = tmp_path / "pyproject.toml"
                pyproject.write_text("""
[tool.pytest.ini_options]
markers = [
    "custom_marker: A custom test marker",
    "requires_docker: Needs Docker runtime",
    "integration: Integration tests"
]
""")

                choices = self.marker_type._choices(None)

                # Should include both common and custom markers
                assert "custom_marker" in choices
                assert "requires_docker" in choices
                assert "integration" in choices
                assert "unit" in choices  # Common marker

    def test_handles_missing_pyproject(self):
        """Test that missing pyproject.toml doesn't break marker discovery."""
        with patch("aidb_cli.core.param_types._get_repo_root_from_ctx") as mock_root:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)
                mock_root.return_value = tmp_path
                # No pyproject.toml file created

                choices = self.marker_type._choices(None)

                # Should still return common markers
                assert "unit" in choices
                assert "integration" in choices
                assert len(choices) > 0

    def test_handles_malformed_pyproject(self):
        """Test that malformed pyproject.toml is handled gracefully."""
        with patch("aidb_cli.core.param_types._get_repo_root_from_ctx") as mock_root:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)
                mock_root.return_value = tmp_path

                # Create malformed pyproject.toml
                pyproject = tmp_path / "pyproject.toml"
                pyproject.write_text("invalid toml content [[[")

                choices = self.marker_type._choices(None)

                # Should still return common markers despite malformed file
                assert "unit" in choices
                assert len(choices) > 0

    def test_marker_validation(self):
        """Test that marker validation works correctly."""
        # Test valid marker
        result = self.marker_type.convert("unit", Mock(), None)
        assert result == "unit"

        # Test case insensitive matching
        result = self.marker_type.convert("UNIT", Mock(), None)
        assert result == "unit"  # Should return canonical form

    def test_marker_validation_invalid(self):
        """Test that invalid markers are rejected appropriately."""
        with pytest.raises(click.exceptions.BadParameter):
            self.marker_type.convert("nonexistent_marker_12345", Mock(), None)

    def test_shell_completion(self):
        """Test that shell completion works for markers."""
        completions = self.marker_type.shell_complete(None, Mock(), "int")
        completion_values = [c.value for c in completions]

        assert "integration" in completion_values


class TestMarkerOrderingAndDisplay:
    """Test marker ordering and display functionality."""

    def test_marker_ordering(self):
        """Test that markers are ordered by importance."""
        marker_type = TestMarkerParamType()
        choices = marker_type._choices(None)

        # Important markers should appear first
        important_markers = ["unit", "integration", "e2e", "slow"]

        for _i, marker in enumerate(important_markers):
            if marker in choices:
                # Find position of this marker
                position = choices.index(marker)
                # Should appear relatively early in the list
                assert position < len(choices) // 2, (
                    f"{marker} should appear early in list"
                )

    def test_max_help_choices_respected(self):
        """Test that help text respects max_help_choices setting."""
        marker_type = TestMarkerParamType()

        # TestMarkerParamType uses max_help_choices=8
        metavar = marker_type.get_metavar(Mock(), None)

        if metavar and "|" in metavar:
            # Count the number of choices shown
            choices_shown = metavar.count("|") + 1
            # Should respect the limit (may be less if fewer choices available)
            assert choices_shown <= 8 or "..." in metavar


class TestParameterIntegration:
    """Test parameter types work correctly with Click commands."""

    def test_flexible_pattern_in_click_command(self):
        """Test that FlexiblePatternParamType works in a Click command."""

        @click.command()
        @click.option("--pattern", type=FlexiblePatternParamType())
        def test_cmd(pattern):
            return pattern

        # Test with complex pattern
        runner = click.testing.CliRunner()
        result = runner.invoke(test_cmd, ["--pattern", "*payment* and not slow"])

        assert result.exit_code == 0
        # The pattern should be accepted without validation errors

    def test_marker_type_in_click_command(self):
        """Test that TestMarkerParamType works in a Click command."""

        @click.command()
        @click.option("--marker", type=TestMarkerParamType())
        def test_cmd(marker):
            return marker

        runner = click.testing.CliRunner()
        result = runner.invoke(test_cmd, ["--marker", "unit"])

        assert result.exit_code == 0
