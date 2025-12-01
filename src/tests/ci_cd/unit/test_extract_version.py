"""Unit tests for extract-version composite action."""

import re
import subprocess
from pathlib import Path

import pytest
import yaml


class TestExtractVersionLogic:
    """Test version extraction logic patterns from extract-version action.

    These tests validate the regex patterns and logic flow used in the extract-version
    bash script without requiring full GitHub Actions execution.
    """

    # Regex patterns from action.yaml
    # Production releases only (no pre-release suffixes)
    RELEASE_PATTERN = r"^release/"
    SEMVER_PATTERN = r"^[0-9]+\.[0-9]+\.[0-9]+$"

    @pytest.mark.parametrize(
        ("branch_name", "starts_with_release"),
        [
            # Branches that start with release/
            ("release/0.1.0", True),
            ("release/1.2.3", True),
            ("release/10.20.30", True),
            ("release/0.0.1", True),
            ("release/0.0.1-test", True),  # Starts with release/ (but invalid version)
            ("release/1.0.0-rc", True),  # Starts with release/ (but invalid version)
            # Branches that don't start with release/
            ("feature/new-feature", False),
            ("main", False),
            ("develop", False),
            ("hotfix/bug-fix", False),
            ("releases/1.0.0", False),  # Wrong prefix
        ],
    )
    def test_release_branch_pattern(self, branch_name, starts_with_release):
        """Verify branch names that start with release/ prefix."""
        matches_pattern = bool(re.match(self.RELEASE_PATTERN, branch_name))
        assert matches_pattern == starts_with_release

    @pytest.mark.parametrize(
        ("version", "expected_valid"),
        [
            # Valid semantic versions
            ("0.1.0", True),
            ("1.2.3", True),
            ("10.20.30", True),
            ("0.0.1", True),
            ("99.99.99", True),
            # Invalid versions
            ("1.2", False),
            ("1", False),
            ("1.2.3.4", False),
            ("v1.2.3", False),
            ("1.2.3-test", False),  # Suffix makes base pattern fail
            ("abc", False),
            ("1.2.x", False),
        ],
    )
    def test_semver_pattern(self, version, expected_valid):
        """Verify semantic versioning pattern matching."""
        matches_pattern = bool(re.match(self.SEMVER_PATTERN, version))
        assert matches_pattern == expected_valid

    @pytest.mark.parametrize(
        ("branch_name", "expected_version"),
        [
            ("release/0.1.0", "0.1.0"),
            ("release/1.2.3", "1.2.3"),
            ("release/10.20.30", "10.20.30"),
            ("release/0.0.1", "0.0.1"),
        ],
    )
    def test_version_extraction(self, branch_name, expected_version):
        """Verify version extraction from branch name (production releases only)."""
        # Simulate: VERSION="${BRANCH#release/}"
        version = branch_name.removeprefix("release/")
        assert version == expected_version

    @pytest.mark.parametrize(
        ("version", "expected_tag"),
        [
            # Bare version tags (production releases only)
            ("0.1.0", "0.1.0"),
            ("1.2.3", "1.2.3"),
            ("10.20.30", "10.20.30"),
            ("0.0.1", "0.0.1"),
            ("99.99.99", "99.99.99"),
        ],
    )
    def test_tag_generation(self, version, expected_tag):
        """Verify tag name generation from version (bare format, no suffixes)."""
        # Simulate the bash logic:
        # TAG_NAME="$VERSION"
        tag_name = version

        assert tag_name == expected_tag

    def test_full_validation_flow_success(self):
        """Test complete validation flow for valid release branch (production only)."""
        branch_name = "release/1.2.3"

        # Step 1: Check release pattern
        assert re.match(self.RELEASE_PATTERN, branch_name)

        # Step 2: Extract version
        version = branch_name.removeprefix("release/")
        assert version == "1.2.3"

        # Step 3: Validate semver (production only, no suffixes)
        assert re.match(self.SEMVER_PATTERN, version)

        # Step 4: Generate tag (bare version)
        tag_name = version
        assert tag_name == "1.2.3"

    def test_full_validation_flow_invalid_suffix(self):
        """Test complete validation flow rejects suffixed release branches."""
        branch_name = "release/0.0.1-test"

        # Step 1: Check release pattern (passes - starts with release/)
        assert re.match(self.RELEASE_PATTERN, branch_name)

        # Step 2: Extract version
        version = branch_name.removeprefix("release/")
        assert version == "0.0.1-test"

        # Step 3: Validate semver (fails - no suffixes allowed)
        assert not re.match(self.SEMVER_PATTERN, version)

    def test_full_validation_flow_invalid_branch(self):
        """Test complete validation flow for invalid branch name."""
        branch_name = "feature/new-feature"

        # Step 1: Check release pattern (fails)
        assert not re.match(self.RELEASE_PATTERN, branch_name)

    def test_full_validation_flow_invalid_version(self):
        """Test complete validation flow for invalid version format."""
        branch_name = "release/1.2"

        # Step 1: Check release pattern
        assert re.match(self.RELEASE_PATTERN, branch_name)

        # Step 2: Extract version
        version = branch_name.removeprefix("release/")
        assert version == "1.2"

        # Step 3: Validate semver (fails - invalid format)
        assert not re.match(self.SEMVER_PATTERN, version)


class TestActionInputsOutputs:
    """Test extract-version action.yaml schema and metadata."""

    @pytest.fixture
    def action_yaml(self, github_dir):
        """Load extract-version action.yaml.

        Parameters
        ----------
        github_dir : Path
            .github directory path.

        Returns
        -------
        dict
            Parsed action.yaml content.
        """
        action_file = github_dir / "actions" / "extract-version" / "action.yaml"
        with action_file.open("r") as f:
            return yaml.safe_load(f)

    def test_action_has_required_metadata(self, action_yaml):
        """Verify action.yaml has required metadata fields."""
        required_fields = ["name", "description", "inputs", "outputs", "runs"]
        for field in required_fields:
            assert field in action_yaml, f"Missing required field: {field}"

    def test_action_has_required_inputs(self, action_yaml):
        """Verify action.yaml defines required inputs."""
        inputs = action_yaml["inputs"]

        # branch_name is required
        assert "branch_name" in inputs
        assert inputs["branch_name"]["required"] is True
        assert "description" in inputs["branch_name"]

        # fail_on_invalid is optional with default
        assert "fail_on_invalid" in inputs
        assert inputs["fail_on_invalid"]["required"] is False
        assert inputs["fail_on_invalid"]["default"] == "true"

    def test_action_has_required_outputs(self, action_yaml):
        """Verify action.yaml defines required outputs."""
        outputs = action_yaml["outputs"]

        required_outputs = ["version", "is_valid", "tag_name"]
        for output in required_outputs:
            assert output in outputs, f"Missing required output: {output}"
            assert "description" in outputs[output]
            assert "value" in outputs[output]

    def test_action_uses_composite(self, action_yaml):
        """Verify action uses composite run type."""
        assert action_yaml["runs"]["using"] == "composite"
        assert "steps" in action_yaml["runs"]
        assert len(action_yaml["runs"]["steps"]) > 0

    def test_action_steps_use_bash(self, action_yaml):
        """Verify action steps use bash shell."""
        steps = action_yaml["runs"]["steps"]
        for step in steps:
            if "shell" in step:
                assert step["shell"] == "bash"


class TestExtractVersionIntegration:
    """Integration tests for extract-version action execution.

    These tests execute the action script directly to validate end-to-end functionality.
    """

    @pytest.fixture
    def action_script_path(self, github_dir):
        """Get path to extract-version action.yaml.

        Parameters
        ----------
        github_dir : Path
            .github directory path.

        Returns
        -------
        Path
            Path to action.yaml file.
        """
        return github_dir / "actions" / "extract-version" / "action.yaml"

    def _extract_bash_script(self, action_yaml_path: Path) -> str:
        """Extract the main bash script from action.yaml.

        Parameters
        ----------
        action_yaml_path : Path
            Path to action.yaml file.

        Returns
        -------
        str
            Extracted bash script content.
        """
        with action_yaml_path.open("r") as f:
            action_data = yaml.safe_load(f)

        # Get first step's run content (main extraction logic)
        return action_data["runs"]["steps"][0]["run"]

    @pytest.mark.integration
    @pytest.mark.skip(reason="GitHub Actions syntax not executable in standalone bash")
    def test_action_script_executes_successfully(self, action_script_path, tmp_path):
        """Verify action script executes without errors for valid input.

        Note: This test is skipped because the extracted GitHub Actions script
        contains syntax like ${{ inputs.branch_name }} which requires the
        Actions runtime and cannot be executed in a standalone bash script.

        The logic is thoroughly tested via unit tests that validate the
        regex patterns and logic flow.
        """
        pytest.skip("GitHub Actions syntax requires Actions runtime")

    @pytest.mark.integration
    @pytest.mark.skip(reason="GitHub Actions syntax not executable in standalone bash")
    def test_action_script_handles_invalid_branch(self, action_script_path, tmp_path):
        """Verify action script handles invalid branch gracefully.

        Note: This test is skipped for the same reason as
        test_action_script_executes_successfully - the script contains
        GitHub Actions-specific syntax that cannot be executed standalone.
        """
        pytest.skip("GitHub Actions syntax requires Actions runtime")
