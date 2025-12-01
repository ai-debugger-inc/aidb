"""Unit tests for TestSuiteService."""

from pathlib import Path
from unittest.mock import Mock, call, patch

import pytest

from aidb_cli.services.test.test_suite_service import TestSuiteService


class TestTestSuiteService:
    """Test the TestSuiteService."""

    @pytest.fixture
    def mock_command_executor(self):
        """Create a mock command executor."""
        executor = Mock()
        executor.execute = Mock()
        return executor

    @pytest.fixture
    def service(self, tmp_path, mock_command_executor):
        """Create service instance with mocks."""
        return TestSuiteService(
            repo_root=tmp_path,
            command_executor=mock_command_executor,
        )

    @pytest.fixture
    def mock_test_structure(self, tmp_path):
        """Create a mock test directory structure."""
        test_root = tmp_path / "src" / "tests"
        test_root.mkdir(parents=True)

        aidb_mcp = test_root / "aidb_mcp"
        aidb_mcp.mkdir()
        (aidb_mcp / "test_api.py").touch()
        (aidb_mcp / "test_tools.py").touch()
        api_dir = aidb_mcp / "api"
        api_dir.mkdir()
        (api_dir / "test_endpoints.py").touch()

        aidb_cli = test_root / "aidb_cli"
        aidb_cli.mkdir()
        (aidb_cli / "test_commands.py").touch()

        fixtures = test_root / "_fixtures"
        fixtures.mkdir()
        (fixtures / "base.py").touch()

        return test_root

    def test_initialization_sets_test_root(self, tmp_path, mock_command_executor):
        """Test that initialization sets test_root correctly."""
        service = TestSuiteService(
            repo_root=tmp_path,
            command_executor=mock_command_executor,
        )

        assert service.test_root == tmp_path / "src" / "tests"
        assert service.repo_root == tmp_path

    def test_initialization_inherits_from_base_service(
        self,
        tmp_path,
        mock_command_executor,
    ):
        """Test that service inherits from BaseService."""
        from aidb_cli.managers.base.service import BaseService

        service = TestSuiteService(
            repo_root=tmp_path,
            command_executor=mock_command_executor,
        )

        assert isinstance(service, BaseService)

    def test_list_suites_finds_all_aidb_suites(self, tmp_path, mock_test_structure):
        """Test list_suites finds all aidb_* directories."""
        service = TestSuiteService(repo_root=tmp_path)

        suites = service.list_suites()

        assert "mcp" in suites
        assert "cli" in suites
        assert len(suites) == 2

    def test_list_suites_excludes_non_aidb_directories(
        self,
        tmp_path,
        mock_test_structure,
    ):
        """Test list_suites excludes directories not starting with aidb_."""
        service = TestSuiteService(repo_root=tmp_path)

        suites = service.list_suites()

        assert "_fixtures" not in suites
        assert "fixtures" not in suites

    def test_list_suites_filters_specific_suite(self, tmp_path, mock_test_structure):
        """Test list_suites with specific suite filter."""
        service = TestSuiteService(repo_root=tmp_path)

        suites = service.list_suites(suite_filter="mcp")

        assert len(suites) == 1
        assert "mcp" in suites
        assert "cli" not in suites

    def test_list_suites_filter_none_returns_all_suites(
        self,
        tmp_path,
        mock_test_structure,
    ):
        """Test list_suites with suite_filter=None returns all suites."""
        service = TestSuiteService(repo_root=tmp_path)

        suites = service.list_suites(suite_filter=None)

        assert "mcp" in suites
        assert "cli" in suites

    def test_list_suites_counts_test_files_correctly(
        self,
        tmp_path,
        mock_test_structure,
    ):
        """Test list_suites counts test_*.py files correctly."""
        service = TestSuiteService(repo_root=tmp_path)

        suites = service.list_suites()

        assert suites["mcp"]["test_count"] == 3
        assert suites["cli"]["test_count"] == 1

    def test_list_suites_verbose_false_no_test_files(
        self,
        tmp_path,
        mock_test_structure,
    ):
        """Test list_suites with verbose=False does not include test_files."""
        service = TestSuiteService(repo_root=tmp_path)

        suites = service.list_suites(verbose=False)

        assert suites["mcp"]["test_files"] == []
        assert suites["cli"]["test_files"] == []

    def test_list_suites_verbose_true_includes_sample_test_files(
        self,
        tmp_path,
        mock_test_structure,
    ):
        """Test list_suites with verbose=True includes sample test_files."""
        service = TestSuiteService(repo_root=tmp_path)

        suites = service.list_suites(verbose=True)

        assert len(suites["mcp"]["test_files"]) > 0
        assert len(suites["mcp"]["test_files"]) <= 5
        assert any("test_" in f for f in suites["mcp"]["test_files"])

    def test_list_suites_verbose_limits_to_five_files(self, tmp_path):
        """Test list_suites verbose limits test_files to first 5."""
        from aidb_cli.services.test.suites import SuiteDefinition

        test_root = tmp_path / "src" / "tests"
        test_root.mkdir(parents=True)
        aidb_suite = test_root / "aidb_large"
        aidb_suite.mkdir()

        for i in range(10):
            (aidb_suite / f"test_file_{i:02d}.py").touch()

        service = TestSuiteService(repo_root=tmp_path)

        # Mock TestSuites.all() to include the "large" suite
        large_suite = SuiteDefinition(
            name="large",
            path="aidb_large",
            is_multilang=False,
            requires_docker=False,
            adapters_required=False,
            profile="base",
            description="Test suite for large tests",
        )

        with patch("aidb_cli.services.test.TestSuites.all", return_value=[large_suite]):
            suites = service.list_suites(verbose=True)

            assert len(suites["large"]["test_files"]) == 5

    def test_list_suites_handles_empty_tests_directory(self, tmp_path):
        """Test list_suites handles no suites found."""
        test_root = tmp_path / "src" / "tests"
        test_root.mkdir(parents=True)

        service = TestSuiteService(repo_root=tmp_path)

        suites = service.list_suites()

        assert len(suites) == 0

    def test_list_suites_returns_correct_path(self, tmp_path, mock_test_structure):
        """Test list_suites returns correct path for each suite."""
        service = TestSuiteService(repo_root=tmp_path)

        suites = service.list_suites()

        assert suites["mcp"]["path"] == str(
            tmp_path / "src" / "tests" / "aidb_mcp",
        )
        assert suites["cli"]["path"] == str(tmp_path / "src" / "tests" / "aidb_cli")

    @patch("aidb_cli.services.test.test_suite_service.get_marker_descriptions")
    @patch("aidb_cli.core.param_types.TestMarkerParamType")
    def test_list_markers_returns_all_markers(
        self,
        mock_marker_type,
        mock_get_descriptions,
        service,
    ):
        """Test list_markers returns all markers when no filter."""
        mock_instance = Mock()
        mock_instance._choices.return_value = ["unit", "integration", "e2e"]
        mock_marker_type.return_value = mock_instance

        mock_get_descriptions.return_value = {
            "unit": "Unit tests",
            "integration": "Integration tests",
            "e2e": "End-to-end tests",
        }

        markers = service.list_markers()

        assert len(markers) == 3
        assert markers["unit"] == "Unit tests"
        assert markers["integration"] == "Integration tests"
        assert markers["e2e"] == "End-to-end tests"

    @patch("aidb_cli.services.test.test_suite_service.get_marker_descriptions")
    @patch("aidb_cli.core.param_types.TestMarkerParamType")
    def test_list_markers_filters_specific_marker(
        self,
        mock_marker_type,
        mock_get_descriptions,
        service,
    ):
        """Test list_markers with marker_filter matches specific marker."""
        mock_instance = Mock()
        mock_instance._choices.return_value = ["unit", "integration", "e2e"]
        mock_marker_type.return_value = mock_instance

        mock_get_descriptions.return_value = {
            "unit": "Unit tests",
            "integration": "Integration tests",
            "e2e": "End-to-end tests",
        }

        markers = service.list_markers(marker_filter="unit")

        assert len(markers) == 1
        assert "unit" in markers
        assert "integration" not in markers

    @patch("aidb_cli.services.test.test_suite_service.get_marker_descriptions")
    @patch("aidb_cli.core.param_types.TestMarkerParamType")
    def test_list_markers_uses_custom_marker_fallback(
        self,
        mock_marker_type,
        mock_get_descriptions,
        service,
    ):
        """Test list_markers uses 'Custom marker' for unknown markers."""
        mock_instance = Mock()
        mock_instance._choices.return_value = ["custom_marker"]
        mock_marker_type.return_value = mock_instance

        mock_get_descriptions.return_value = {}

        markers = service.list_markers()

        assert markers["custom_marker"] == "Custom marker"

    def test_get_pattern_examples_returns_list_of_tuples(self, service):
        """Test get_pattern_examples returns list of (pattern, description) tuples."""
        examples = service.get_pattern_examples()

        assert isinstance(examples, list)
        assert all(isinstance(ex, tuple) and len(ex) == 2 for ex in examples)

    def test_get_pattern_examples_contains_expected_patterns(self, service):
        """Test get_pattern_examples includes expected common patterns."""
        examples = service.get_pattern_examples()

        patterns = [p[0] for p in examples]

        assert "test_payment*" in patterns
        assert "*_integration*" in patterns
        assert "not flaky" in patterns

    def test_find_matching_files_finds_files(self, tmp_path):
        """Test find_matching_files finds files matching pattern."""
        test_root = tmp_path / "src" / "tests"
        test_root.mkdir(parents=True)

        service = TestSuiteService(repo_root=tmp_path)

        mock_files = [
            test_root / "test_foo.py",
            test_root / "test_bar.py",
        ]

        with patch.object(Path, "rglob", return_value=mock_files):
            files = service.find_matching_files("test_*.py")

            assert len(files) == 2
            assert all(isinstance(f, Path) for f in files)

    def test_find_matching_files_suite_filter_limits_search(self, tmp_path):
        """Test find_matching_files with suite filter limits search to specific
        suite."""
        test_root = tmp_path / "src" / "tests"
        aidb_mcp = test_root / "aidb_mcp"
        aidb_mcp.mkdir(parents=True)

        service = TestSuiteService(repo_root=tmp_path)

        with patch.object(Path, "rglob", return_value=[]) as mock_rglob:
            service.find_matching_files("test_*.py", suite="mcp")

            mock_rglob.assert_called_once_with("test_*.py")

    def test_find_matching_files_respects_limit_parameter(self, tmp_path):
        """Test find_matching_files respects limit parameter."""
        test_root = tmp_path / "src" / "tests"
        test_root.mkdir(parents=True)

        service = TestSuiteService(repo_root=tmp_path)

        mock_files = [test_root / f"test_{i}.py" for i in range(20)]

        with patch.object(Path, "rglob", return_value=mock_files):
            files = service.find_matching_files("test_*.py", limit=5)

            assert len(files) == 5

    def test_find_matching_files_returns_empty_list_no_matches(
        self,
        tmp_path,
    ):
        """Test find_matching_files returns empty list if no matches."""
        test_root = tmp_path / "src" / "tests"
        test_root.mkdir(parents=True)

        service = TestSuiteService(repo_root=tmp_path)

        with patch.object(Path, "rglob", return_value=[]):
            files = service.find_matching_files("nonexistent_*.py")

            assert files == []

    def test_find_matching_files_returns_empty_if_path_not_exists(
        self,
        tmp_path,
    ):
        """Test find_matching_files returns empty list if search path doesn't exist."""
        service = TestSuiteService(repo_root=tmp_path)

        files = service.find_matching_files("test_*.py", suite="nonexistent")

        assert files == []

    @patch("aidb_cli.services.test.test_suite_service.CliOutput")
    @patch("aidb_cli.core.formatting.HeadingFormatter")
    def test_display_suites_outputs_correct_format(
        self,
        mock_formatter,
        mock_output,
        service,
    ):
        """Test display_suites outputs correct format."""
        suites = {
            "backend": {
                "path": "/path/to/backend",
                "test_count": 10,
                "test_files": [],
            },
            "cli": {
                "path": "/path/to/cli",
                "test_count": 5,
                "test_files": [],
            },
        }

        service.display_suites(suites, verbose=False)

        mock_formatter.section.assert_called_once()
        assert mock_output.success.call_count == 2
        mock_output.info.assert_called()

    @patch("aidb_cli.services.test.test_suite_service.CliOutput")
    @patch("aidb_cli.core.formatting.HeadingFormatter")
    def test_display_suites_verbose_shows_test_files(
        self,
        mock_formatter,
        mock_output,
        service,
    ):
        """Test display_suites with verbose shows test_files."""
        suites = {
            "backend": {
                "path": "/path/to/backend",
                "test_count": 10,
                "test_files": ["test_api.py", "test_models.py"],
            },
        }

        service.display_suites(suites, verbose=True)

        calls = [c for c in mock_output.info.call_args_list if "test_api.py" in str(c)]
        assert len(calls) > 0

    @patch("aidb_cli.services.test.test_suite_service.CliOutput")
    @patch("aidb_cli.core.formatting.HeadingFormatter")
    def test_display_suites_verbose_shows_remaining_count(
        self,
        mock_formatter,
        mock_output,
        service,
    ):
        """Test display_suites verbose shows remaining count when more than 5 files."""
        suites = {
            "backend": {
                "path": "/path/to/backend",
                "test_count": 10,
                "test_files": ["test_1.py", "test_2.py", "test_3.py"],
            },
        }

        service.display_suites(suites, verbose=True)

        calls = [c for c in mock_output.info.call_args_list if "and 7 more" in str(c)]
        assert len(calls) > 0

    @patch("aidb_cli.services.test.test_suite_service.CliOutput")
    def test_display_markers_formats_markers(
        self,
        mock_output,
        service,
    ):
        """Test display_markers formats markers correctly."""
        markers = {
            "unit": "Unit tests",
            "integration": "Integration tests",
        }

        service.display_markers(markers)

        # Verify CliOutput.plain called for each marker and info for total
        assert mock_output.plain.call_count == 2
        assert mock_output.info.call_count == 1  # Total count

    @patch("aidb_cli.services.test.test_suite_service.CliOutput")
    def test_display_pattern_examples_shows_examples(
        self,
        mock_output,
        service,
    ):
        """Test display_pattern_examples shows examples."""
        service.display_pattern_examples()

        # Verify CliOutput.info called multiple times for examples
        assert mock_output.info.call_count > 1

    @patch("aidb_cli.services.test.test_suite_service.CliOutput")
    def test_display_matching_files_with_results(
        self,
        mock_output,
        tmp_path,
    ):
        """Test display_matching_files outputs files when matches found."""
        test_root = tmp_path / "src" / "tests"
        test_root.mkdir(parents=True)
        test_file = test_root / "test_foo.py"
        test_file.touch()

        service = TestSuiteService(repo_root=tmp_path)

        files = [test_file]
        service.display_matching_files("test_*.py", files)

        # Verify CliOutput.info called for pattern and file info
        assert mock_output.info.call_count >= 2

    @patch("aidb_cli.services.test.test_suite_service.CliOutput")
    def test_display_matching_files_with_no_results(
        self,
        mock_output,
        service,
    ):
        """Test display_matching_files shows warning when no matches."""
        service.display_matching_files("test_*.py", [])

        # Verify warning called when no matches found
        mock_output.warning.assert_called_once()

    @patch("aidb_cli.services.test.test_suite_service.CliOutput")
    @patch("aidb_cli.core.formatting.HeadingFormatter")
    def test_display_matching_files_shows_total_when_limited(
        self,
        mock_formatter,
        mock_output,
        tmp_path,
    ):
        """Test display_matching_files shows total count when more than displayed."""
        test_root = tmp_path / "src" / "tests"
        test_root.mkdir(parents=True)
        test_file = test_root / "test_foo.py"
        test_file.touch()

        service = TestSuiteService(repo_root=tmp_path)

        files = [test_file]
        service.display_matching_files("test_*.py", files, total=10)

        calls = [c for c in mock_output.info.call_args_list if "and 9 more" in str(c)]
        assert len(calls) > 0
