"""Unit tests for VersionUpdateOrchestrator class."""

import sys
from pathlib import Path

import pytest

sys.path.insert(
    0,
    str(Path(__file__).parent.parent.parent.parent.parent / ".github" / "scripts"),
)

from _test_helpers import create_mock_versions_config
from version_management.orchestrator import SectionType, VersionUpdateOrchestrator


class TestVersionUpdateOrchestrator:
    """Test VersionUpdateOrchestrator functionality."""

    def test_init_creates_all_checkers(self, mock_checker_stack, tmp_path):
        """Verify orchestrator initializes all checker components."""
        config_file = tmp_path / "versions.json"
        config_file.touch()

        mock_checker_stack["loader"].load.return_value = {"version": "1.0.0"}

        orchestrator = VersionUpdateOrchestrator(config_file)

        assert orchestrator.config_path == config_file
        assert orchestrator.target_section == SectionType.ALL
        mock_checker_stack["loader"].load.assert_called_once_with(config_file)
        mock_checker_stack["infra_class"].assert_called_once()
        mock_checker_stack["adapter_class"].assert_called_once()
        mock_checker_stack["package_class"].assert_called_once()
        mock_checker_stack["validator_class"].assert_called_once()

    def test_check_all_updates_with_infrastructure_updates(
        self,
        mock_checker_stack,
        tmp_path,
    ):
        """Verify orchestrator aggregates infrastructure updates."""
        config_file = tmp_path / "versions.json"
        config_file.touch()

        mock_checker_stack["loader"].load.return_value = {"version": "1.0.0"}

        mock_checker_stack["infra"].check_updates.return_value = {
            "python": {"current": "3.11.0", "latest": "3.12.1"},
        }

        mock_checker_stack["adapter"].check_updates.return_value = {}
        mock_checker_stack["package"].check_pypi_updates.return_value = {}
        mock_checker_stack["package"].check_npm_updates.return_value = {}
        mock_checker_stack["validator"].validate.return_value = {"valid": True}

        orchestrator = VersionUpdateOrchestrator(config_file)
        updates = orchestrator.check_all_updates()

        assert "infrastructure" in updates
        assert updates["infrastructure"]["python"]["current"] == "3.11.0"
        assert updates["infrastructure"]["python"]["latest"] == "3.12.1"

    def test_check_all_updates_aggregates_all_sections(
        self,
        mock_checker_stack,
        tmp_path,
    ):
        """Verify orchestrator aggregates updates from all sections."""
        config_file = tmp_path / "versions.json"
        config_file.touch()

        mock_checker_stack["loader"].load.return_value = {"version": "1.0.0"}

        mock_checker_stack["infra"].check_updates.return_value = {
            "python": {"current": "3.11.0", "latest": "3.12.1"},
        }
        mock_checker_stack["adapter"].check_updates.return_value = {
            "javascript": {"current": "1.85.0", "latest": "1.86.0"},
        }
        mock_checker_stack["package"].check_pypi_updates.return_value = {
            "setuptools": {"current": "68.0.0", "latest": "69.0.0"},
        }
        mock_checker_stack["package"].check_npm_updates.return_value = {
            "typescript": {"current": "5.3.0", "latest": "5.3.3"},
        }
        mock_checker_stack["validator"].validate.return_value = {"valid": True}

        orchestrator = VersionUpdateOrchestrator(config_file)
        updates = orchestrator.check_all_updates()

        assert "infrastructure" in updates
        assert "adapters" in updates
        assert "global_packages_pip" in updates
        assert "global_packages_npm" in updates
        assert len(updates) == 4

    def test_empty_results_when_no_updates(
        self,
        mock_checker_stack,
        tmp_path,
    ):
        """Verify empty dict returned when no updates found."""
        config_file = tmp_path / "versions.json"
        config_file.touch()

        mock_checker_stack["loader"].load.return_value = {"version": "1.0.0"}

        mock_checker_stack["infra"].check_updates.return_value = {}
        mock_checker_stack["adapter"].check_updates.return_value = {}
        mock_checker_stack["package"].check_pypi_updates.return_value = {}
        mock_checker_stack["package"].check_npm_updates.return_value = {}
        mock_checker_stack["validator"].validate.return_value = {"valid": True}

        orchestrator = VersionUpdateOrchestrator(config_file)
        updates = orchestrator.check_all_updates()

        assert updates == {}

    def test_infrastructure_only_section(
        self,
        mock_checker_stack,
        tmp_path,
    ):
        """Verify infrastructure-only filtering."""
        config_file = tmp_path / "versions.json"
        config_file.touch()

        mock_checker_stack["loader"].load.return_value = {"version": "1.0.0"}

        mock_checker_stack["infra"].check_updates.return_value = {
            "python": {"current": "3.11.0", "latest": "3.12.1"},
        }
        mock_checker_stack["adapter"].check_updates.return_value = {
            "javascript": {"current": "1.85.0", "latest": "1.86.0"},
        }
        mock_checker_stack["package"].check_pypi_updates.return_value = {}
        mock_checker_stack["package"].check_npm_updates.return_value = {}
        mock_checker_stack["validator"].validate.return_value = {"valid": True}

        orchestrator = VersionUpdateOrchestrator(
            config_file,
            target_section=SectionType.INFRASTRUCTURE,
        )
        updates = orchestrator.check_all_updates()

        assert "infrastructure" in updates
        assert "adapters" not in updates

    def test_adapters_only_section(
        self,
        mock_checker_stack,
        tmp_path,
    ):
        """Verify adapters-only filtering."""
        config_file = tmp_path / "versions.json"
        config_file.touch()

        mock_checker_stack["loader"].load.return_value = {"version": "1.0.0"}

        mock_checker_stack["infra"].check_updates.return_value = {
            "python": {"current": "3.11.0", "latest": "3.12.1"},
        }
        mock_checker_stack["adapter"].check_updates.return_value = {
            "javascript": {"current": "1.85.0", "latest": "1.86.0"},
        }
        mock_checker_stack["package"].check_pypi_updates.return_value = {}
        mock_checker_stack["package"].check_npm_updates.return_value = {}
        mock_checker_stack["validator"].validate.return_value = {"valid": True}

        orchestrator = VersionUpdateOrchestrator(
            config_file,
            target_section=SectionType.ADAPTERS,
        )
        updates = orchestrator.check_all_updates()

        assert "adapters" in updates
        assert "infrastructure" not in updates

    def test_packages_always_run(
        self,
        mock_checker_stack,
        tmp_path,
    ):
        """Verify package checks run regardless of section filter."""
        config_file = tmp_path / "versions.json"
        config_file.touch()

        mock_checker_stack["loader"].load.return_value = {"version": "1.0.0"}

        mock_checker_stack["infra"].check_updates.return_value = {}
        mock_checker_stack["adapter"].check_updates.return_value = {}
        mock_checker_stack["package"].check_pypi_updates.return_value = {
            "pip": {"current": "23.0.0", "latest": "24.0.0"},
        }
        mock_checker_stack["package"].check_npm_updates.return_value = {}
        mock_checker_stack["validator"].validate.return_value = {"valid": True}

        orchestrator = VersionUpdateOrchestrator(
            config_file,
            target_section=SectionType.INFRASTRUCTURE,
        )
        updates = orchestrator.check_all_updates()

        # Packages still checked even with INFRASTRUCTURE filter
        assert "global_packages_pip" in updates

    def test_debugpy_validation_included(
        self,
        mock_checker_stack,
        tmp_path,
    ):
        """Verify debugpy validation results included when invalid or warnings
        present."""
        config_file = tmp_path / "versions.json"
        config_file.touch()

        mock_checker_stack["loader"].load.return_value = {"version": "1.0.0"}

        mock_checker_stack["infra"].check_updates.return_value = {}
        mock_checker_stack["adapter"].check_updates.return_value = {}
        mock_checker_stack["package"].check_pypi_updates.return_value = {}
        mock_checker_stack["package"].check_npm_updates.return_value = {}
        mock_checker_stack["validator"].validate.return_value = {
            "valid": False,
            "errors": ["Version mismatch"],
        }

        orchestrator = VersionUpdateOrchestrator(config_file)
        updates = orchestrator.check_all_updates()

        assert "debugpy_sync" in updates
        assert updates["debugpy_sync"]["valid"] is False

    def test_debugpy_warnings_included(
        self,
        mock_checker_stack,
        tmp_path,
    ):
        """Verify debugpy validation warnings included even when valid."""
        config_file = tmp_path / "versions.json"
        config_file.touch()

        mock_checker_stack["loader"].load.return_value = {"version": "1.0.0"}

        mock_checker_stack["infra"].check_updates.return_value = {}
        mock_checker_stack["adapter"].check_updates.return_value = {}
        mock_checker_stack["package"].check_pypi_updates.return_value = {}
        mock_checker_stack["package"].check_npm_updates.return_value = {}
        mock_checker_stack["validator"].validate.return_value = {
            "valid": True,
            "warnings": ["Minor version drift"],
        }

        orchestrator = VersionUpdateOrchestrator(config_file)
        updates = orchestrator.check_all_updates()

        assert "debugpy_sync" in updates
        assert updates["debugpy_sync"]["warnings"]

    def test_all_checkers_called(
        self,
        mock_checker_stack,
        tmp_path,
    ):
        """Verify all checker methods are invoked."""
        config_file = tmp_path / "versions.json"
        config_file.touch()

        mock_checker_stack["loader"].load.return_value = {"version": "1.0.0"}

        mock_checker_stack["infra"].check_updates.return_value = {}
        mock_checker_stack["adapter"].check_updates.return_value = {}
        mock_checker_stack["package"].check_pypi_updates.return_value = {}
        mock_checker_stack["package"].check_npm_updates.return_value = {}
        mock_checker_stack["validator"].validate.return_value = {"valid": True}

        orchestrator = VersionUpdateOrchestrator(config_file)
        orchestrator.check_all_updates()

        mock_checker_stack["infra"].check_updates.assert_called_once()
        mock_checker_stack["adapter"].check_updates.assert_called_once()
        mock_checker_stack["package"].check_pypi_updates.assert_called_once()
        mock_checker_stack["package"].check_npm_updates.assert_called_once()
        mock_checker_stack["validator"].validate.assert_called_once()

    def test_handles_checker_exceptions_gracefully(
        self,
        mock_checker_stack,
        tmp_path,
    ):
        """Verify orchestrator continues despite individual checker failures."""
        config_file = tmp_path / "versions.json"
        config_file.touch()

        mock_checker_stack["loader"].load.return_value = {"version": "1.0.0"}

        # Infrastructure checker raises exception
        mock_checker_stack["infra"].check_updates.side_effect = RuntimeError(
            "API error",
        )

        # But other checkers work fine
        mock_checker_stack["adapter"].check_updates.return_value = {
            "javascript": {"current": "1.85.0", "latest": "1.86.0"},
        }
        mock_checker_stack["package"].check_pypi_updates.return_value = {}
        mock_checker_stack["package"].check_npm_updates.return_value = {}
        mock_checker_stack["validator"].validate.return_value = {"valid": True}

        orchestrator = VersionUpdateOrchestrator(config_file)

        # Should continue and return results from other checkers
        results = orchestrator.check_all_updates()

        # Infrastructure failed, so not in results
        assert "infrastructure" not in results

        # But adapter updates still returned
        assert "adapters" in results
        assert results["adapters"]["javascript"]["latest"] == "1.86.0"

    def test_config_passed_to_all_checkers(
        self,
        mock_checker_stack,
        tmp_path,
    ):
        """Verify loaded config is passed to all checker instances."""
        config_file = tmp_path / "versions.json"
        config_file.touch()

        test_config = {"version": "1.0.0", "test_key": "test_value"}
        mock_checker_stack["loader"].load.return_value = test_config

        mock_checker_stack["infra"].check_updates.return_value = {}
        mock_checker_stack["adapter"].check_updates.return_value = {}
        mock_checker_stack["package"].check_pypi_updates.return_value = {}
        mock_checker_stack["package"].check_npm_updates.return_value = {}
        mock_checker_stack["validator"].validate.return_value = {"valid": True}

        VersionUpdateOrchestrator(config_file)

        # Verify all checkers received the loaded config
        mock_checker_stack["infra_class"].assert_called_once_with(test_config)
        mock_checker_stack["adapter_class"].assert_called_once_with(test_config)
        mock_checker_stack["package_class"].assert_called_once_with(test_config)

    def test_section_type_constants(
        self,
        mock_checker_stack,
        tmp_path,
    ):
        """Verify SectionType constants work correctly."""
        config_file = tmp_path / "versions.json"
        config_file.touch()

        mock_checker_stack["loader"].load.return_value = {"version": "1.0.0"}

        # Test all three section types
        for section_type in [
            SectionType.INFRASTRUCTURE,
            SectionType.ADAPTERS,
            SectionType.ALL,
        ]:
            orchestrator = VersionUpdateOrchestrator(
                config_file,
                target_section=section_type,
            )
            assert orchestrator.target_section == section_type
