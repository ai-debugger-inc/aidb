"""Unit tests for TestProfileResolver."""

from unittest.mock import patch

import pytest

from aidb_cli.core.constants import DockerProfiles
from aidb_cli.managers.test.orchestrator.test_profile_resolver import (
    TestProfileResolver,
)
from aidb_common.constants import Language


class TestTestProfileResolver:
    """Test the TestProfileResolver."""

    def test_determine_profile_explicit_profile_priority(self):
        """Test explicit --profile flag overrides everything."""
        result = TestProfileResolver.determine_profile(
            suite="core",
            profile="mcp",
            target=["frameworks/python/"],
        )

        assert result == "mcp"

    def test_determine_profile_language_detection_python(self):
        """Test detects Python from path."""
        result = TestProfileResolver.determine_profile(
            suite=None,
            profile=None,
            target=["src/tests/frameworks/python/test_django.py"],
        )

        assert result == Language.PYTHON.value

    def test_determine_profile_language_detection_javascript(self):
        """Test detects JavaScript from path."""
        result = TestProfileResolver.determine_profile(
            suite=None,
            profile=None,
            target=["frameworks/javascript/test_express.py"],
        )

        assert result == Language.JAVASCRIPT.value

    def test_determine_profile_language_detection_java(self):
        """Test detects Java from path."""
        result = TestProfileResolver.determine_profile(
            suite=None,
            profile=None,
            target=["frameworks/java/test_spring.py"],
        )

        assert result == Language.JAVA.value

    def test_determine_profile_language_detection_frameworks_generic(self):
        """Test falls back to frameworks when path contains frameworks/ but no
        language."""
        result = TestProfileResolver.determine_profile(
            suite=None,
            profile=None,
            target=["frameworks/test_common.py"],
        )

        assert result == "frameworks"

    def test_determine_profile_multiple_targets_uses_first(self):
        """Test uses first target for profile detection."""
        result = TestProfileResolver.determine_profile(
            suite=None,
            profile=None,
            target=["frameworks/python/", "frameworks/java/"],
        )

        assert result == Language.PYTHON.value

    def test_determine_profile_suite_name_mcp(self):
        """Test known suite maps to profile."""
        result = TestProfileResolver.determine_profile(
            suite="mcp",
            profile=None,
            target=None,
        )

        assert result == "mcp"

    def test_determine_profile_suite_name_adapters(self):
        """Test known suite maps to profile."""
        result = TestProfileResolver.determine_profile(
            suite="adapters",
            profile=None,
            target=None,
        )

        assert result == "adapters"

    def test_determine_profile_suite_special_case_shared(self):
        """Test shared maps to base profile."""
        result = TestProfileResolver.determine_profile(
            suite="shared",
            profile=None,
            target=None,
        )

        assert result == DockerProfiles.BASE

    def test_determine_profile_suite_special_case_cli(self):
        """Test cli maps to base profile."""
        result = TestProfileResolver.determine_profile(
            suite="cli",
            profile=None,
            target=None,
        )

        assert result == DockerProfiles.BASE

    def test_determine_profile_unknown_suite_defaults_base(self):
        """Test unknown suite defaults to base for safety."""
        result = TestProfileResolver.determine_profile(
            suite="unknown_suite_xyz",
            profile=None,
            target=None,
        )

        assert result == DockerProfiles.BASE

    def test_determine_profile_all_known_profiles(self):
        """Test all known profiles in registry are handled."""
        known_profiles = [
            "mcp",
            "adapters",
            "shell",
            "all",
            "generated",
            "python",
            "javascript",
            "java",
            "frameworks",
            "launch",
            "debug",
            "matrix",
        ]

        for known_profile in known_profiles:
            result = TestProfileResolver.determine_profile(
                suite=known_profile,
                profile=None,
                target=None,
            )
            # Special cases that map to base
            if known_profile in ("shared", "cli"):
                assert result == DockerProfiles.BASE
            else:
                assert result == known_profile

    def test_determine_profile_default_base(self):
        """Test defaults to base when no inputs provided."""
        result = TestProfileResolver.determine_profile(
            suite=None,
            profile=None,
            target=None,
        )

        assert result == DockerProfiles.BASE

    def test_determine_profile_priority_order_comprehensive(self):
        """Test complete priority chain works correctly."""
        # Explicit profile beats language detection
        result1 = TestProfileResolver.determine_profile(
            suite=None,
            profile="mcp",
            target=["frameworks/python/test.py"],
        )
        assert result1 == "mcp"

        # Language detection beats suite
        result2 = TestProfileResolver.determine_profile(
            suite="mcp",
            profile=None,
            target=["frameworks/javascript/test.py"],
        )
        assert result2 == Language.JAVASCRIPT.value

        # Suite beats default
        result3 = TestProfileResolver.determine_profile(
            suite="adapters",
            profile=None,
            target=None,
        )
        assert result3 == "adapters"

        # Default is base
        result4 = TestProfileResolver.determine_profile(
            suite=None,
            profile=None,
            target=None,
        )
        assert result4 == DockerProfiles.BASE

    def test_determine_profile_edge_case_empty_target_list(self):
        """Test empty target list doesn't crash."""
        result = TestProfileResolver.determine_profile(
            suite=None,
            profile=None,
            target=[],
        )

        assert result == DockerProfiles.BASE

    def test_determine_profile_edge_case_target_without_frameworks(self):
        """Test targets without frameworks/ path ignored for language detection."""
        result = TestProfileResolver.determine_profile(
            suite=None,
            profile=None,
            target=["src/tests/cli/test_command.py"],
        )

        assert result == DockerProfiles.BASE

    @patch("aidb_cli.managers.test.orchestrator.test_profile_resolver.logger")
    def test_determine_profile_logging(self, mock_logger):
        """Test debug logging occurs at each decision point."""
        # Test explicit profile logging
        TestProfileResolver.determine_profile(
            suite=None,
            profile="mcp",
            target=None,
        )
        # Verify debug logging was called
        assert mock_logger.debug.called

        # Test language detection logging
        mock_logger.reset_mock()
        TestProfileResolver.determine_profile(
            suite=None,
            profile=None,
            target=["frameworks/python/test.py"],
        )
        assert mock_logger.debug.called

        # Test suite mapping logging
        mock_logger.reset_mock()
        TestProfileResolver.determine_profile(
            suite="mcp",
            profile=None,
            target=None,
        )
        assert mock_logger.debug.called

        # Test default fallback logging
        mock_logger.reset_mock()
        TestProfileResolver.determine_profile(
            suite=None,
            profile=None,
            target=None,
        )
        assert mock_logger.debug.called
