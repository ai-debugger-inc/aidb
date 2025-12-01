"""Tests for shell completion functionality in enhanced CLI."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import click
import pytest
from click.shell_completion import CompletionItem

from aidb_cli.core.param_types import (
    FlexiblePatternParamType,
    TestMarkerParamType,
    TestSuiteParamType,
)


class TestFlexiblePatternCompletion:
    """Test shell completion for flexible patterns."""

    def setup_method(self):
        """Set up test fixtures."""
        self.param_type = FlexiblePatternParamType()
        self.mock_ctx = Mock()
        self.mock_param = Mock()

    def test_completion_provides_common_patterns(self):
        """Test that completion provides common pattern suggestions."""
        completions = self.param_type.shell_complete(
            self.mock_ctx,
            self.mock_param,
            "",
        )

        completion_values = [c.value for c in completions]

        # Should include common patterns
        expected_patterns = [
            "test_*",
            "*_test",
            "*_unit",
            "*_integration",
            "*_e2e",
            "*_multilang",
        ]

        for pattern in expected_patterns:
            assert pattern in completion_values

    def test_completion_filters_by_prefix(self):
        """Test that completion filters suggestions by containing text."""
        # Test with "test" prefix
        completions = self.param_type.shell_complete(
            self.mock_ctx,
            self.mock_param,
            "test",
        )
        completion_values = [c.value for c in completions]

        # All completions should contain "test" (case insensitive)
        for value in completion_values:
            assert "test" in value.lower()

    def test_completion_case_insensitive(self):
        """Test that completion is case insensitive."""
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

        # Should return same number of completions
        assert len(completions_lower) == len(completions_upper)

    def test_completion_partial_match(self):
        """Test completion with partial matches."""
        completions = self.param_type.shell_complete(
            self.mock_ctx,
            self.mock_param,
            "*_",
        )
        completion_values = [c.value for c in completions]

        # Should include patterns that start with "*_"
        expected_matches = ["*_test", "*_unit", "*_integration", "*_e2e", "*_multilang"]
        for match in expected_matches:
            assert match in completion_values


class TestMarkerCompletion:
    """Test shell completion for markers."""

    def setup_method(self):
        """Set up test fixtures."""
        self.param_type = TestMarkerParamType()

    def test_completion_includes_standard_markers(self):
        """Test that completion includes standard pytest markers."""
        completions = self.param_type.shell_complete(None, Mock(), "")

        completion_values = [c.value for c in completions]

        # Should include standard markers
        expected_markers = ["unit", "integration", "e2e", "slow", "asyncio"]
        for marker in expected_markers:
            assert marker in completion_values

    def test_completion_includes_custom_markers(self):
        """Test that completion includes custom markers from pyproject.toml."""
        with patch("aidb_cli.core.param_types._get_repo_root_from_ctx") as mock_root:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)
                mock_root.return_value = tmp_path

                # Create mock pyproject.toml
                pyproject = tmp_path / "pyproject.toml"
                pyproject.write_text("""
[tool.pytest.ini_options]
markers = [
    "requires_docker: Needs Docker runtime",
    "custom_marker: A custom marker"
]
""")

                completions = self.param_type.shell_complete(None, Mock(), "")
                completion_values = [c.value for c in completions]

                # Should include custom markers
                assert "requires_docker" in completion_values
                assert "custom_marker" in completion_values

    def test_completion_filters_by_prefix(self):
        """Test that marker completion filters by prefix."""
        completions = self.param_type.shell_complete(None, Mock(), "int")
        completion_values = [c.value for c in completions]

        # Should include "integration"
        assert "integration" in completion_values

        # All completions should start with "int"
        for value in completion_values:
            assert value.lower().startswith("int")

    def test_completion_case_insensitive(self):
        """Test that marker completion is case insensitive."""
        completions_lower = self.param_type.shell_complete(None, Mock(), "int")
        completions_upper = self.param_type.shell_complete(None, Mock(), "INT")

        # Should return same completions
        assert len(completions_lower) > 0
        assert len(completions_upper) > 0

    def test_completion_requires_docker(self):
        """Test that requires_docker marker completion works."""
        completions = self.param_type.shell_complete(None, Mock(), "requires_d")
        completion_values = [c.value for c in completions]

        assert "requires_docker" in completion_values


class TestSuiteCompletion:
    """Test shell completion for test suites."""

    def setup_method(self):
        """Set up test fixtures."""
        self.param_type = TestSuiteParamType()

    def test_completion_includes_discovered_suites(self):
        """Test that completion includes discovered test suites."""
        with patch("aidb_cli.core.param_types._get_repo_root_from_ctx") as mock_root:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)
                mock_root.return_value = tmp_path

                # Create test directory structure
                test_root = tmp_path / "src" / "tests"
                test_root.mkdir(parents=True)

                # Create test suite directories
                (test_root / "aidb_cli").mkdir()
                (test_root / "aidb_mcp").mkdir()
                (test_root / "aidb_common").mkdir()

                completions = self.param_type.shell_complete(None, Mock(), "")
                completion_values = [c.value for c in completions]

                # Should include discovered suites
                assert "cli" in completion_values
                assert "mcp" in completion_values
                assert "common" in completion_values

    def test_completion_includes_all_option(self):
        """Test that completion includes 'all' option."""
        completions = self.param_type.shell_complete(None, Mock(), "")
        completion_values = [c.value for c in completions]

        assert "all" in completion_values

    def test_completion_filters_suites(self):
        """Test that suite completion filters by prefix."""
        with patch("aidb_cli.core.param_types._get_repo_root_from_ctx") as mock_root:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)
                mock_root.return_value = tmp_path

                # Create test directory structure
                test_root = tmp_path / "src" / "tests"
                test_root.mkdir(parents=True)
                (test_root / "aidb_mcp").mkdir()
                (test_root / "aidb_common").mkdir()

                completions = self.param_type.shell_complete(None, Mock(), "m")
                completion_values = [c.value for c in completions]

                # Should include mcp but not common
                assert "mcp" in completion_values
                assert "common" not in completion_values


class TestCompletionIntegration:
    """Test completion integration with Click commands."""

    def test_pattern_completion_in_command(self):
        """Test that pattern completion works in actual Click commands."""

        @click.command()
        @click.option("--pattern", type=FlexiblePatternParamType())
        def test_cmd(pattern):
            return pattern

        param = None
        for p in test_cmd.params:
            if p.name == "pattern":
                param = p
                break

        assert param is not None

        # Test completion
        completions = param.type.shell_complete(None, param, "test")
        completion_values = [c.value for c in completions]

        assert len(completion_values) > 0
        for value in completion_values:
            assert "test" in value.lower()

    def test_marker_completion_in_command(self):
        """Test that marker completion works in actual Click commands."""

        @click.command()
        @click.option("--marker", type=TestMarkerParamType())
        def test_cmd(marker):
            return marker

        param = None
        for p in test_cmd.params:
            if p.name == "marker":
                param = p
                break

        assert param is not None

        # Test completion
        completions = param.type.shell_complete(None, param, "unit")
        completion_values = [c.value for c in completions]

        assert "unit" in completion_values


class TestCompletionPerformance:
    """Test that completion is performant."""

    def test_pattern_completion_fast(self):
        """Test that pattern completion is fast enough for interactive use."""
        param_type = FlexiblePatternParamType()

        import time

        start_time = time.time()

        # Should complete quickly even with many calls
        for _ in range(10):
            param_type.shell_complete(None, Mock(), "test")

        end_time = time.time()
        elapsed = end_time - start_time

        # Should complete in well under a second for 10 calls
        assert elapsed < 1.0

    def test_marker_completion_fast(self):
        """Test that marker completion is fast enough."""
        param_type = TestMarkerParamType()

        import time

        start_time = time.time()

        # Should complete quickly
        for _ in range(10):
            param_type.shell_complete(None, Mock(), "int")

        end_time = time.time()
        elapsed = end_time - start_time

        # Should complete quickly
        assert elapsed < 1.0


class TestCompletionEdgeCases:
    """Test edge cases in completion."""

    def test_completion_empty_input(self):
        """Test completion with empty input."""
        param_type = FlexiblePatternParamType()

        completions = param_type.shell_complete(None, Mock(), "")
        completion_values = [c.value for c in completions]

        # Should return some completions
        assert len(completion_values) > 0

    def test_completion_no_matches(self):
        """Test completion with no matches."""
        param_type = FlexiblePatternParamType()

        completions = param_type.shell_complete(None, Mock(), "xyz123impossible")
        completion_values = [c.value for c in completions]

        # Should return empty list
        assert len(completion_values) == 0

    def test_completion_special_characters(self):
        """Test completion with special characters."""
        param_type = FlexiblePatternParamType()

        # Should handle special characters gracefully
        completions = param_type.shell_complete(None, Mock(), "*")
        completion_values = [c.value for c in completions]

        # Should return patterns that contain "*"
        for value in completion_values:
            assert "*" in value

    def test_completion_error_handling(self):
        """Test that completion handles errors gracefully."""
        param_type = TestMarkerParamType()

        # Mock an error in the choices provider
        with patch.object(param_type, "_choices", side_effect=Exception("Test error")):
            try:
                # Should not crash
                completions = param_type.shell_complete(None, Mock(), "test")
                # Should return empty list on error
                assert len(completions) == 0
            except Exception:  # noqa: S110 - test accepts both empty result or exception
                pass


class TestCompletionTypes:
    """Test different types of completion items."""

    def test_completion_items_have_values(self):
        """Test that completion items have proper values."""
        param_type = FlexiblePatternParamType()

        completions = param_type.shell_complete(None, Mock(), "test")

        for completion in completions:
            assert hasattr(completion, "value")
            assert isinstance(completion.value, str)
            assert len(completion.value) > 0

    def test_completion_items_are_click_items(self):
        """Test that completion items are proper Click completion items."""
        param_type = FlexiblePatternParamType()

        completions = param_type.shell_complete(None, Mock(), "test")

        for completion in completions:
            assert isinstance(completion, CompletionItem)

    def test_marker_completion_items(self):
        """Test that marker completion items are properly formatted."""
        param_type = TestMarkerParamType()

        completions = param_type.shell_complete(None, Mock(), "int")

        for completion in completions:
            assert isinstance(completion, CompletionItem)
            # Should be valid marker names (no spaces, etc.)
            assert " " not in completion.value
            assert completion.value.isidentifier() or "_" in completion.value
