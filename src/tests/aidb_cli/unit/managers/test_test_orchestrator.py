"""Unit tests for TestOrchestrator profile mapping logic."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from aidb_cli.managers.test.test_orchestrator import TestOrchestrator


@pytest.mark.unit
class TestProfileMapping:
    """Unit tests for TestOrchestrator._determine_docker_profile method."""

    @pytest.fixture
    def orchestrator(self, tmp_path):
        """Create a TestOrchestrator instance for testing.

        Parameters
        ----------
        tmp_path : Path
            Pytest temporary directory

        Returns
        -------
        TestOrchestrator
            Test orchestrator instance
        """
        mock_executor = Mock()
        repo_root = tmp_path / "repo"
        repo_root.mkdir(parents=True, exist_ok=True)

        return TestOrchestrator(
            repo_root=repo_root,
            command_executor=mock_executor,
        )

    def test_priority_1_explicit_profile_wins(self, orchestrator):
        """Test that explicit --profile flag has highest priority.

        Verifies that when an explicit profile is provided, it is used regardless of
        suite or target values.
        """
        profile = orchestrator._determine_docker_profile(
            suite=None,
            profile="base",
            target=None,
        )
        assert profile == "base"

        profile = orchestrator._determine_docker_profile(
            suite="mcp",
            profile="base",
            target=None,
        )
        assert profile == "base"

        profile = orchestrator._determine_docker_profile(
            suite="mcp",
            profile="adapters",
            target="some/test/path",
        )
        assert profile == "adapters"

    def test_priority_2_suite_mapping_mcp(self, orchestrator):
        """Test that 'mcp' suite maps to 'mcp' profile.

        Verifies that when no explicit profile is set, the suite mapping takes priority.
        """
        profile = orchestrator._determine_docker_profile(
            suite="mcp",
            profile=None,
            target=None,
        )
        assert profile == "mcp"

    def test_priority_2_suite_mapping_adapters(self, orchestrator):
        """Test that 'adapters' suite maps to 'adapters' profile.

        Verifies the suite-to-profile mapping for adapter tests.
        """
        profile = orchestrator._determine_docker_profile(
            suite="adapters",
            profile=None,
            target=None,
        )
        assert profile == "adapters"

    def test_priority_2_suite_mapping_shared(self, orchestrator):
        """Test that 'shared' suite maps to 'base' profile.

        Verifies that shared tests use the minimal base profile.
        """
        profile = orchestrator._determine_docker_profile(
            suite="shared",
            profile=None,
            target=None,
        )
        assert profile == "base"

    def test_priority_2_suite_mapping_generated(self, orchestrator):
        """Test that 'generated' suite maps to 'generated' profile.

        Verifies the suite-to-profile mapping for generated tests.
        """
        profile = orchestrator._determine_docker_profile(
            suite="generated",
            profile=None,
            target=None,
        )
        assert profile == "generated"

    def test_priority_2_suite_mapping_all(self, orchestrator):
        """Test that suite maps to corresponding profile.

        Verifies that the 'mcp' suite maps to the 'mcp' profile.
        """
        profile = orchestrator._determine_docker_profile(
            suite="mcp",
            profile=None,
            target=None,
        )
        assert profile == "mcp"

    def test_priority_3_default_to_base(self, orchestrator):
        """Test that default profile is 'base' when no suite or profile specified.

        Verifies that when neither suite nor profile is provided, the method defaults to
        the minimal 'base' profile.
        """
        profile = orchestrator._determine_docker_profile(
            suite=None,
            profile=None,
            target=None,
        )
        assert profile == "base"

    def test_all_known_suite_mappings(self, orchestrator):
        """Test all known suite-to-profile mappings are correct.

        Verifies that all documented suite mappings work as expected.
        """
        suite_mappings = {
            "mcp": "mcp",
            "adapters": "adapters",
            "shared": "base",
            "generated": "generated",
            "all": "all",
        }

        for suite, expected_profile in suite_mappings.items():
            profile = orchestrator._determine_docker_profile(
                suite=suite,
                profile=None,
                target=None,
            )
            assert profile == expected_profile, (
                f"Suite '{suite}' should map to profile '{expected_profile}'"
            )

    def test_unknown_suite_defaults_to_base(self, orchestrator):
        """Test that unknown suite names default to 'base' profile.

        Verifies that if a suite name is not recognized, the method falls back to the
        'base' profile.
        """
        profile = orchestrator._determine_docker_profile(
            suite="unknown_suite",
            profile=None,
            target=None,
        )
        assert profile == "base"

    def test_target_parameter_ignored_when_profile_set(self, orchestrator):
        """Test that target parameter doesn't affect explicit profile choice.

        Verifies that the target parameter is currently ignored in profile determination
        when an explicit profile is set.
        """
        profile = orchestrator._determine_docker_profile(
            suite=None,
            profile="mcp",
            target="some/specific/test.py",
        )
        assert profile == "mcp"

    def test_target_parameter_ignored_when_suite_set(self, orchestrator):
        """Test that target parameter doesn't affect suite mapping.

        Verifies that the target parameter is currently ignored in profile determination
        when a suite is set.
        """
        profile = orchestrator._determine_docker_profile(
            suite="adapters",
            profile=None,
            target="some/specific/test.py",
        )
        assert profile == "adapters"

    def test_explicit_profile_overrides_suite(self, orchestrator):
        """Test that explicit profile takes precedence over suite mapping.

        Verifies the priority order when both profile and suite are provided.
        """
        profile = orchestrator._determine_docker_profile(
            suite="mcp",
            profile="adapters",
            target=None,
        )
        assert profile == "adapters", "Explicit profile should override suite mapping"

        profile = orchestrator._determine_docker_profile(
            suite="adapters",
            profile="base",
            target=None,
        )
        assert profile == "base", "Explicit profile should override suite mapping"

    def test_case_sensitivity_of_suite_names(self, orchestrator):
        """Test that suite names are case-sensitive.

        Verifies that suite mapping is case-sensitive and uppercase suite names don't
        match.
        """
        profile = orchestrator._determine_docker_profile(
            suite="MCP",
            profile=None,
            target=None,
        )
        assert profile == "base", (
            "Uppercase suite name should not match, default to base"
        )

    def test_empty_string_suite_defaults_to_base(self, orchestrator):
        """Test that empty string suite defaults to base profile.

        Verifies that an empty string is treated as no suite.
        """
        profile = orchestrator._determine_docker_profile(
            suite="",
            profile=None,
            target=None,
        )
        assert profile == "base"

    def test_empty_string_profile_treated_as_none(self, orchestrator):
        """Test that empty string profile is treated as None.

        Verifies that an empty string profile doesn't override suite mapping.
        """
        profile = orchestrator._determine_docker_profile(
            suite="mcp",
            profile="",
            target=None,
        )
        # Empty string is falsy in Python, should fall through to suite mapping
        assert profile == "mcp"
