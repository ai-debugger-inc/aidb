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

    def test_priority_1_language_detection_from_target(self, orchestrator):
        """Test that language detection from target path has highest priority."""
        profile = orchestrator._determine_docker_profile(
            suite="mcp",
            target=["frameworks/python/test_something.py"],
        )
        assert profile == "python"

        profile = orchestrator._determine_docker_profile(
            suite="adapters",
            target=["frameworks/javascript/test_express.py"],
        )
        assert profile == "javascript"

    def test_priority_2_suite_mapping_mcp(self, orchestrator):
        """Test that 'mcp' suite maps to 'mcp' profile."""
        profile = orchestrator._determine_docker_profile(
            suite="mcp",
            target=None,
        )
        assert profile == "mcp"

    def test_priority_2_suite_mapping_adapters(self, orchestrator):
        """Test that 'adapters' suite maps to 'adapters' profile."""
        profile = orchestrator._determine_docker_profile(
            suite="adapters",
            target=None,
        )
        assert profile == "adapters"

    def test_priority_2_suite_mapping_shared(self, orchestrator):
        """Test that 'shared' suite maps to 'base' profile."""
        profile = orchestrator._determine_docker_profile(
            suite="shared",
            target=None,
        )
        assert profile == "base"

    def test_priority_2_suite_mapping_generated(self, orchestrator):
        """Test that 'generated' suite maps to 'generated' profile."""
        profile = orchestrator._determine_docker_profile(
            suite="generated",
            target=None,
        )
        assert profile == "generated"

    def test_priority_3_default_to_base(self, orchestrator):
        """Test that default profile is 'base' when no suite specified."""
        profile = orchestrator._determine_docker_profile(
            suite=None,
            target=None,
        )
        assert profile == "base"

    def test_all_known_suite_mappings(self, orchestrator):
        """Test all known suite-to-profile mappings are correct."""
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
                target=None,
            )
            assert profile == expected_profile, (
                f"Suite '{suite}' should map to profile '{expected_profile}'"
            )

    def test_unknown_suite_defaults_to_base(self, orchestrator):
        """Test that unknown suite names default to 'base' profile."""
        profile = orchestrator._determine_docker_profile(
            suite="unknown_suite",
            target=None,
        )
        assert profile == "base"

    def test_target_language_detection_beats_suite(self, orchestrator):
        """Test that target path language detection beats suite mapping."""
        profile = orchestrator._determine_docker_profile(
            suite="adapters",
            target=["frameworks/java/test_spring.py"],
        )
        assert profile == "java"

    def test_case_sensitivity_of_suite_names(self, orchestrator):
        """Test that suite names are case-sensitive."""
        profile = orchestrator._determine_docker_profile(
            suite="MCP",
            target=None,
        )
        assert profile == "base", (
            "Uppercase suite name should not match, default to base"
        )

    def test_empty_string_suite_defaults_to_base(self, orchestrator):
        """Test that empty string suite defaults to base profile."""
        profile = orchestrator._determine_docker_profile(
            suite="",
            target=None,
        )
        assert profile == "base"

    def test_empty_target_list(self, orchestrator):
        """Test that empty target list falls through to suite mapping."""
        profile = orchestrator._determine_docker_profile(
            suite="mcp",
            target=[],
        )
        assert profile == "mcp"
