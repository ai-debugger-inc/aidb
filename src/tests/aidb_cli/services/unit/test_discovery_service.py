"""Unit tests for TestDiscoveryService."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from aidb_cli.services.test.test_discovery_service import (
    TestDiscoveryService,
    TestSuiteMetadata,
)


class TestTestSuiteMetadata:
    """Test TestSuiteMetadata dataclass."""

    def test_metadata_creation(self):
        """Test creating metadata with required fields."""
        metadata = TestSuiteMetadata(
            name="cli",
            path=Path("/tests/aidb_cli"),
            languages=["python"],
            markers=["unit", "integration"],
            requires_docker=False,
            adapters_required=False,
            default_pattern="test_*.py",
        )

        assert metadata.name == "cli"
        assert metadata.languages == ["python"]
        assert metadata.dependencies == []

    def test_metadata_with_dependencies(self):
        """Test metadata with explicit dependencies."""
        metadata = TestSuiteMetadata(
            name="mcp",
            path=Path("/tests/aidb_mcp"),
            languages=["python", "javascript", "java"],
            markers=["unit", "integration", "multilang"],
            requires_docker=True,
            adapters_required=True,
            default_pattern="test_*.py",
            dependencies=["adapters"],
        )

        assert metadata.dependencies == ["adapters"]
        assert metadata.requires_docker is True


class TestTestDiscoveryService:
    """Test the TestDiscoveryService."""

    @pytest.fixture
    def mock_command_executor(self):
        """Create a mock command executor."""
        return Mock()

    @pytest.fixture
    def mock_version_manager(self):
        """Create a mock version manager."""
        with patch(
            "aidb_cli.services.test.test_discovery_service.VersionManager",
        ) as mock:
            version_manager = Mock()
            version_manager.versions = {
                "adapters": {
                    "python": "1.0.0",
                    "javascript": "1.0.0",
                    "java": "1.0.0",
                },
            }
            mock.return_value = version_manager
            yield mock

    @pytest.fixture
    def test_structure(self, tmp_path):
        """Create a test directory structure."""
        # Create test root
        test_root = tmp_path / "src" / "tests"
        test_root.mkdir(parents=True)

        # Create aidb_cli suite
        cli_dir = test_root / "aidb_cli"
        cli_dir.mkdir()
        (cli_dir / "test_commands.py").write_text("def test_foo(): pass")
        (cli_dir / "test_services.py").write_text(
            "@pytest.mark.unit\ndef test_bar(): pass",
        )

        # Create aidb_mcp suite
        mcp_dir = test_root / "aidb_mcp"
        mcp_dir.mkdir()
        (mcp_dir / "test_init.py").write_text(
            "@pytest.mark.unit\ndef test_init(): pass",
        )
        (mcp_dir / "test_session.py").write_text(
            "@pytest.mark.integration\ndef test_session(): pass",
        )

        # Create aidb_common suite
        common_dir = test_root / "aidb_common"
        common_dir.mkdir()
        (common_dir / "test_config.py").write_text("def test_config(): pass")

        # Create versions.yaml
        versions_yaml = tmp_path / "versions.yaml"
        versions_yaml.write_text(
            "adapters:\n  python: 1.0.0\n  javascript: 1.0.0\n  java: 1.0.0\n",
        )

        return tmp_path

    def test_service_initialization(
        self,
        test_structure,
        mock_command_executor,
        mock_version_manager,
    ):
        """Test service initialization loads suites."""
        service = TestDiscoveryService(
            repo_root=test_structure,
            command_executor=mock_command_executor,
        )

        assert service.test_root == test_structure / "src" / "tests"
        # Should have discovered suites + special suites
        suites = service.get_all_suites()
        assert len(suites) > 0

    def test_get_suite_metadata_existing(
        self,
        test_structure,
        mock_command_executor,
        mock_version_manager,
    ):
        """Test getting metadata for an existing suite."""
        service = TestDiscoveryService(
            repo_root=test_structure,
            command_executor=mock_command_executor,
        )

        metadata = service.get_suite_metadata("cli")
        assert metadata is not None
        assert metadata.name == "cli"
        assert metadata.languages == ["python"]

    def test_get_suite_metadata_nonexistent(
        self,
        test_structure,
        mock_command_executor,
        mock_version_manager,
    ):
        """Test getting metadata for non-existent suite."""
        service = TestDiscoveryService(
            repo_root=test_structure,
            command_executor=mock_command_executor,
        )

        metadata = service.get_suite_metadata("nonexistent")
        assert metadata is None

    def test_get_all_suites(
        self,
        test_structure,
        mock_command_executor,
        mock_version_manager,
    ):
        """Test getting all suite metadata."""
        service = TestDiscoveryService(
            repo_root=test_structure,
            command_executor=mock_command_executor,
        )

        suites = service.get_all_suites()
        assert isinstance(suites, dict)
        assert "cli" in suites
        assert "mcp" in suites
        # Special suites
        assert "unit" in suites
        assert "integration" in suites

    def test_mcp_suite_characteristics(
        self,
        test_structure,
        mock_command_executor,
        mock_version_manager,
    ):
        """Test MCP suite has correct characteristics (Python-only, no adapters)."""
        service = TestDiscoveryService(
            repo_root=test_structure,
            command_executor=mock_command_executor,
        )

        mcp_metadata = service.get_suite_metadata("mcp")
        assert mcp_metadata is not None
        assert mcp_metadata.adapters_required is False
        assert "python" in mcp_metadata.languages

    def test_discover_tests_all(
        self,
        test_structure,
        mock_command_executor,
        mock_version_manager,
    ):
        """Test discovering all tests."""
        service = TestDiscoveryService(
            repo_root=test_structure,
            command_executor=mock_command_executor,
        )

        discovered = service.discover_tests()
        assert isinstance(discovered, dict)
        assert len(discovered) > 0

    def test_discover_tests_specific_suite(
        self,
        test_structure,
        mock_command_executor,
        mock_version_manager,
    ):
        """Test discovering tests for a specific suite."""
        service = TestDiscoveryService(
            repo_root=test_structure,
            command_executor=mock_command_executor,
        )

        discovered = service.discover_tests(suite="cli")
        assert "cli" in discovered
        assert len(discovered["cli"]) > 0
        # Should only have cli suite
        assert len(discovered) == 1

    def test_discover_tests_with_pattern(
        self,
        test_structure,
        mock_command_executor,
        mock_version_manager,
    ):
        """Test discovering tests with custom pattern."""
        service = TestDiscoveryService(
            repo_root=test_structure,
            command_executor=mock_command_executor,
        )

        # Use a specific pattern
        discovered = service.discover_tests(suite="cli", pattern="test_commands.py")
        assert "cli" in discovered
        # Should only find the matching file
        matching_files = [f for f in discovered["cli"] if f.name == "test_commands.py"]
        assert len(matching_files) > 0

    def test_discover_tests_with_language_filter(
        self,
        test_structure,
        mock_command_executor,
        mock_version_manager,
    ):
        """Test discovering tests with language filter."""
        service = TestDiscoveryService(
            repo_root=test_structure,
            command_executor=mock_command_executor,
        )

        # MCP supports multiple languages, CLI only python
        discovered = service.discover_tests(language="python")
        assert "cli" in discovered  # CLI is python
        assert "mcp" in discovered  # MCP supports python

    def test_discover_tests_with_marker_filter(
        self,
        test_structure,
        mock_command_executor,
        mock_version_manager,
    ):
        """Test discovering tests with marker filter."""
        service = TestDiscoveryService(
            repo_root=test_structure,
            command_executor=mock_command_executor,
        )

        # Filter by unit marker
        discovered = service.discover_tests(suite="cli", marker="unit")
        if "cli" in discovered:
            # Should only find files with @pytest.mark.unit
            for test_file in discovered["cli"]:
                content = test_file.read_text()
                assert "pytest.mark.unit" in content or "mark.unit" in content

    def test_get_test_statistics(
        self,
        test_structure,
        mock_command_executor,
        mock_version_manager,
    ):
        """Test getting test statistics."""
        service = TestDiscoveryService(
            repo_root=test_structure,
            command_executor=mock_command_executor,
        )

        stats = service.get_test_statistics()
        assert "total_suites" in stats
        assert "total_files" in stats
        assert "suites" in stats
        assert stats["total_suites"] > 0
        assert stats["total_files"] > 0

    def test_get_test_statistics_specific_suite(
        self,
        test_structure,
        mock_command_executor,
        mock_version_manager,
    ):
        """Test getting statistics for a specific suite."""
        service = TestDiscoveryService(
            repo_root=test_structure,
            command_executor=mock_command_executor,
        )

        stats = service.get_test_statistics(suite="cli")
        assert stats["total_suites"] == 1
        assert "cli" in stats["suites"]
        assert "file_count" in stats["suites"]["cli"]

    def test_special_suite_unit(
        self,
        test_structure,
        mock_command_executor,
        mock_version_manager,
    ):
        """Test special 'unit' suite metadata."""
        service = TestDiscoveryService(
            repo_root=test_structure,
            command_executor=mock_command_executor,
        )

        unit_metadata = service.get_suite_metadata("unit")
        assert unit_metadata is not None
        assert unit_metadata.name == "unit"
        assert unit_metadata.requires_docker is False
        assert unit_metadata.adapters_required is False
        assert "unit" in unit_metadata.markers

    def test_special_suite_integration(
        self,
        test_structure,
        mock_command_executor,
        mock_version_manager,
    ):
        """Test special 'integration' suite metadata."""
        service = TestDiscoveryService(
            repo_root=test_structure,
            command_executor=mock_command_executor,
        )

        integration_metadata = service.get_suite_metadata("integration")
        assert integration_metadata is not None
        assert integration_metadata.name == "integration"
        assert integration_metadata.requires_docker is True
        assert integration_metadata.adapters_required is True
        assert "integration" in integration_metadata.markers

    def test_missing_test_root(self, tmp_path, mock_command_executor):
        """Test initialization with missing test root."""
        # Don't create src/tests directory
        service = TestDiscoveryService(
            repo_root=tmp_path,
            command_executor=mock_command_executor,
        )

        # Should not crash, but have no suites (except special ones might be registered)
        suites = service.get_all_suites()
        # At minimum should have special suites
        assert isinstance(suites, dict)

    def test_extract_test_languages_from_version_manager(
        self,
        tmp_path,
        mock_command_executor,
    ):
        """Test extracting test languages from version manager."""
        # Create versions.yaml with adapters
        versions_yaml = tmp_path / "versions.yaml"
        versions_yaml.write_text(
            "adapters:\n  python: 1.0.0\n  javascript: 1.0.0\n",
        )

        # Create minimal test structure
        test_root = tmp_path / "src" / "tests"
        test_root.mkdir(parents=True)

        with patch(
            "aidb_cli.services.test.test_discovery_service.VersionManager",
        ) as mock_vm:
            vm_instance = Mock()
            vm_instance.versions = {
                "adapters": {
                    "python": "1.0.0",
                    "javascript": "1.0.0",
                },
            }
            mock_vm.return_value = vm_instance

            service = TestDiscoveryService(
                repo_root=tmp_path,
                command_executor=mock_command_executor,
            )

            # Check that languages from version manager are used in special suites
            integration_metadata = service.get_suite_metadata("integration")
            assert integration_metadata is not None
            # Integration suite should exist but may have just python
            assert "python" in integration_metadata.languages

    def test_extract_test_languages_fallback(
        self,
        tmp_path,
        mock_command_executor,
    ):
        """Test fallback to default languages when version manager fails."""
        # Create minimal test structure
        test_root = tmp_path / "src" / "tests"
        test_root.mkdir(parents=True)

        with patch(
            "aidb_cli.services.test.test_discovery_service.VersionManager",
        ) as mock_vm:
            # Make version manager return instance with missing adapters key
            vm_instance = Mock()
            vm_instance.versions = {}  # No adapters key - will trigger fallback
            mock_vm.return_value = vm_instance

            service = TestDiscoveryService(
                repo_root=tmp_path,
                command_executor=mock_command_executor,
            )

            # Should fall back to SUPPORTED_LANGUAGES for special suites
            integration_metadata = service.get_suite_metadata("integration")
            assert integration_metadata is not None
            assert len(integration_metadata.languages) > 0

    def test_discover_suite_files(
        self,
        test_structure,
        mock_command_executor,
        mock_version_manager,
    ):
        """Test _discover_suite_files helper method."""
        service = TestDiscoveryService(
            repo_root=test_structure,
            command_executor=mock_command_executor,
        )

        cli_metadata = service.get_suite_metadata("cli")
        assert cli_metadata is not None

        files = service._discover_suite_files(cli_metadata)
        assert len(files) > 0
        # All files should be Python test files
        for f in files:
            assert f.name.startswith("test_")
            assert f.suffix == ".py"

    def test_filter_by_marker(
        self,
        test_structure,
        mock_command_executor,
        mock_version_manager,
    ):
        """Test _filter_by_marker helper method."""
        service = TestDiscoveryService(
            repo_root=test_structure,
            command_executor=mock_command_executor,
        )

        # Get all CLI test files
        cli_dir = test_structure / "src" / "tests" / "aidb_cli"
        test_files = list(cli_dir.glob("test_*.py"))

        # Filter by unit marker
        filtered = service._filter_by_marker(test_files, "unit")
        # Should only include test_services.py which has @pytest.mark.unit
        assert len(filtered) > 0
        for f in filtered:
            content = f.read_text()
            assert "pytest.mark.unit" in content or "mark.unit" in content
