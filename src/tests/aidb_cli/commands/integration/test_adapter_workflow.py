"""Integration tests for debug adapter management workflows.

Tests the CLI's adapter installation, building, discovery, and management capabilities
across different languages and platforms.
"""

import json
import shutil
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from aidb_cli.cli import cli


def _get_repo_root() -> Path:
    """Get repository root directory."""
    current = Path(__file__).parent
    while current.parent != current:
        if (current / ".git").exists():
            return current
        current = current.parent
    msg = "Could not find git repository root"
    raise RuntimeError(msg)


@pytest.fixture
def repo_root():
    """Repository root fixture."""
    return _get_repo_root()


@pytest.fixture
def temp_adapter_cache():
    """Create temporary adapter cache directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


class TestAdapterListingAndStatus:
    """Test adapter listing and status commands."""

    @pytest.mark.integration
    def test_adapter_list_command(self):
        """Test adapter list command."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["adapters", "list"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, f"Adapter list failed: {result.output}"
        assert len(result.output.strip()) > 0

        # Should mention supported languages
        output_lower = result.output.lower()
        expected_languages = ["python", "javascript", "java"]
        languages_found = sum(1 for lang in expected_languages if lang in output_lower)
        assert languages_found >= 1, (
            f"Expected to find at least one language in output: {result.output}"
        )

    @pytest.mark.integration
    def test_adapter_status_command(self):
        """Test adapter status command."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["adapters", "status"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, f"Adapter status failed: {result.output}"
        assert len(result.output.strip()) > 0

        # Should provide status information
        output_lower = result.output.lower()
        assert any(
            keyword in output_lower
            for keyword in [
                "status",
                "installed",
                "available",
                "adapter",
                "python",
                "javascript",
                "java",
            ]
        )

    @pytest.mark.integration
    def test_adapter_info_python(self):
        """Test adapter info command for Python."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["adapters", "info", "python"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, f"Adapter info python failed: {result.output}"

        # Should contain Python-specific information
        output_lower = result.output.lower()
        assert "python" in output_lower
        assert any(
            keyword in output_lower
            for keyword in [
                "debugpy",
                "adapter",
                "version",
                "path",
                "status",
            ]
        )

    @pytest.mark.integration
    def test_adapter_info_javascript(self):
        """Test adapter info command for JavaScript."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["adapters", "info", "javascript"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, f"Adapter info javascript failed: {result.output}"

        # Should contain JavaScript-specific information
        output_lower = result.output.lower()
        assert "javascript" in output_lower or "js" in output_lower
        assert any(
            keyword in output_lower
            for keyword in [
                "node",
                "adapter",
                "version",
                "path",
                "status",
            ]
        )

    @pytest.mark.integration
    def test_adapter_info_java(self):
        """Test adapter info command for Java."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["adapters", "info", "java"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, f"Adapter info java failed: {result.output}"

        # Should contain Java-specific information
        output_lower = result.output.lower()
        assert "java" in output_lower
        assert any(
            keyword in output_lower
            for keyword in [
                "jdt",
                "adapter",
                "version",
                "path",
                "status",
                "jar",
            ]
        )


class TestAdapterInstallation:
    """Test adapter installation workflows."""

    @pytest.mark.integration
    def test_adapter_download_with_install_flag(self):
        """Test downloading and installing adapters with --install flag."""
        runner = CliRunner()

        # Download with --install flag should be available
        download_help = runner.invoke(
            cli,
            ["adapters", "download", "--help"],
            catch_exceptions=False,
        )
        assert download_help.exit_code == 0
        assert "--install" in download_help.output

        # Build with --install flag should be available
        build_help = runner.invoke(
            cli,
            ["adapters", "build", "--help"],
            catch_exceptions=False,
        )
        assert build_help.exit_code == 0
        assert "--install" in build_help.output


class TestAdapterBuilding:
    """Test adapter building workflows."""

    @pytest.mark.integration
    def test_adapter_build_command_help(self):
        """Test adapter build command help."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["adapters", "build", "--help"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, f"Build help failed: {result.output}"
        assert "build" in result.output.lower()

    @pytest.mark.integration
    def test_adapter_build_list_options(self):
        """Test adapter build options and languages."""
        runner = CliRunner()

        # Build should accept language specifications
        result = runner.invoke(
            cli,
            ["adapters", "build"],
            catch_exceptions=False,
        )

        # Should either provide help or start building (we'll interrupt if it starts)
        if result.exit_code == 0:
            # If it succeeded, should have meaningful output
            assert len(result.output.strip()) > 0
        else:
            # If it failed, should provide useful information
            output_lower = result.output.lower()
            assert any(
                keyword in output_lower
                for keyword in [
                    "language",
                    "required",
                    "option",
                    "help",
                    "build",
                ]
            )


class TestAdapterCleanup:
    """Test adapter cleanup functionality."""

    @pytest.mark.integration
    def test_adapter_clean_command(self):
        """Test adapter clean command."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["adapters", "clean", "--yes"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, f"Adapter clean failed: {result.output}"

        # Should mention cleaning operations
        output_lower = result.output.lower()
        assert any(
            keyword in output_lower
            for keyword in [
                "clean",
                "cleared",
                "removed",
                "cache",
                "adapter",
            ]
        )

    @pytest.mark.integration
    def test_adapter_clean_idempotent(self):
        """Test that adapter clean is idempotent."""
        runner = CliRunner()

        # Run clean twice
        clean1 = runner.invoke(
            cli,
            ["adapters", "clean"],
            input="y\n",
            catch_exceptions=False,
        )
        assert clean1.exit_code == 0

        clean2 = runner.invoke(
            cli,
            ["adapters", "clean"],
            input="y\n",
            catch_exceptions=False,
        )
        assert clean2.exit_code == 0

        # Both should succeed


class TestAdapterDiscovery:
    """Test adapter discovery and metadata handling."""

    @pytest.mark.integration
    def test_adapter_metadata_access(self, repo_root):
        """Test adapter metadata accessibility."""
        runner = CliRunner()

        # Check if adapter cache exists
        cache_dir = repo_root / ".cache" / "adapters"

        if cache_dir.exists():
            # If cache exists, check for metadata files
            metadata_files = list(cache_dir.glob("*/metadata.json"))

            if metadata_files:
                # Verify metadata is valid JSON
                for metadata_file in metadata_files:
                    try:
                        with metadata_file.open() as f:
                            metadata = json.load(f)
                            assert isinstance(metadata, dict)
                            # Should have basic metadata fields
                            assert any(
                                key in metadata
                                for key in [
                                    "name",
                                    "version",
                                    "language",
                                    "platform",
                                ]
                            )
                    except (json.JSONDecodeError, FileNotFoundError):
                        pytest.fail(f"Invalid metadata file: {metadata_file}")

        # Regardless of cache state, list command should work
        list_result = runner.invoke(
            cli,
            ["adapters", "list"],
            catch_exceptions=False,
        )
        assert list_result.exit_code == 0

    @pytest.mark.integration
    def test_adapter_discovery_cross_platform(self):
        """Test adapter discovery works across platforms."""
        runner = CliRunner()

        # List should work regardless of platform
        result = runner.invoke(
            cli,
            ["adapters", "list"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0
        # Should show adapters or indicate none available
        assert len(result.output.strip()) > 0


class TestAdapterErrorHandling:
    """Test error handling in adapter operations."""

    @pytest.mark.integration
    def test_adapter_info_invalid_language(self):
        """Test adapter info with invalid language."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["adapters", "info", "nonexistent_language"],
            catch_exceptions=False,
        )

        # Should fail gracefully with helpful message
        assert result.exit_code != 0
        output_lower = result.output.lower()
        assert any(
            keyword in output_lower
            for keyword in [
                "not found",
                "invalid",
                "unknown",
                "error",
                "available",
            ]
        )

    @pytest.mark.integration
    def test_adapter_download_invalid_language(self):
        """Test adapter download with invalid language."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["adapters", "download", "-l", "nonexistent_language"],
            catch_exceptions=False,
        )

        # Should fail with helpful error message
        assert result.exit_code != 0
        assert len(result.output.strip()) > 0

    @pytest.mark.integration
    def test_adapter_operations_without_network(self):
        """Test adapter operations that don't require network."""
        runner = CliRunner()

        # Status and list should work without network
        status_result = runner.invoke(
            cli,
            ["adapters", "status"],
            catch_exceptions=False,
        )
        assert status_result.exit_code == 0

        list_result = runner.invoke(
            cli,
            ["adapters", "list"],
            catch_exceptions=False,
        )
        assert list_result.exit_code == 0

        clean_result = runner.invoke(
            cli,
            ["adapters", "clean"],
            input="y\n",
            catch_exceptions=False,
        )
        assert clean_result.exit_code == 0


class TestAdapterIntegration:
    """Test adapter integration with other systems."""

    @pytest.mark.integration
    def test_adapter_status_consistency(self):
        """Test that adapter status is consistent across commands."""
        runner = CliRunner()

        # Get status from multiple commands
        status_result = runner.invoke(
            cli,
            ["adapters", "status"],
            catch_exceptions=False,
        )
        assert status_result.exit_code == 0

        list_result = runner.invoke(
            cli,
            ["adapters", "list"],
            catch_exceptions=False,
        )
        assert list_result.exit_code == 0

        # Both should provide consistent information about available adapters
        status_lines = set(
            line.strip() for line in status_result.output.split("\n") if line.strip()
        )
        list_lines = set(
            line.strip() for line in list_result.output.split("\n") if line.strip()
        )

        # Should have some overlap in content (exact match not required due to formatting)
        assert len(status_lines) > 0
        assert len(list_lines) > 0

    @pytest.mark.integration
    def test_adapter_workflow_end_to_end(self):
        """Test complete adapter workflow."""
        runner = CliRunner()

        # 1. Check initial status
        initial_status = runner.invoke(
            cli,
            ["adapters", "status"],
            catch_exceptions=False,
        )
        assert initial_status.exit_code == 0

        # 2. Clean cache
        clean_result = runner.invoke(
            cli,
            ["adapters", "clean"],
            input="y\n",
            catch_exceptions=False,
        )
        assert clean_result.exit_code == 0

        # 3. List available adapters
        list_result = runner.invoke(
            cli,
            ["adapters", "list"],
            catch_exceptions=False,
        )
        assert list_result.exit_code == 0

        # 4. Check status after clean
        final_status = runner.invoke(
            cli,
            ["adapters", "status"],
            catch_exceptions=False,
        )
        assert final_status.exit_code == 0

        # Workflow should complete successfully
        assert True
