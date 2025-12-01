"""Unit tests for TestManager."""

import subprocess
from pathlib import Path
from unittest.mock import Mock, PropertyMock, patch

import pytest

from aidb.common.errors import AidbError
from aidb_cli.managers.test.test_manager import TestManager


class TestTestManager:
    """Test the TestManager."""

    @pytest.fixture
    def mock_command_executor(self):
        """Create a mock command executor."""
        executor = Mock()
        executor.execute = Mock(
            return_value=Mock(returncode=0, stdout="Docker 20.10.0"),
        )
        return executor

    @pytest.fixture
    def mock_build_manager(self):
        """Create a mock BuildManager."""
        manager = Mock()
        manager.get_supported_languages.return_value = ["python", "javascript", "java"]
        manager.find_adapter_source.return_value = Path("/fake/adapter")
        manager.check_adapters_built.return_value = (
            ["python", "javascript"],
            ["java"],
        )
        return manager

    @pytest.fixture
    @patch("aidb_cli.managers.test.test_manager.BuildManager")
    def manager(
        self,
        mock_build_class,
        tmp_path,
        mock_command_executor,
        mock_build_manager,
    ):
        """Create a TestManager instance."""
        mock_build_class.return_value = mock_build_manager

        # Create compose file
        compose_file = tmp_path / "src" / "tests" / "_docker" / "docker-compose.yaml"
        compose_file.parent.mkdir(parents=True)
        compose_file.write_text("version: '3.8'\n")

        with patch(
            "aidb_cli.managers.test.test_manager.TestManager._register_services",
        ):
            return TestManager(
                repo_root=tmp_path,
                command_executor=mock_command_executor,
            )

    def test_manager_initialization(self, tmp_path, mock_command_executor):
        """Test manager initialization."""
        with patch("aidb_cli.managers.test.test_manager.BuildManager"):
            with patch(
                "aidb_cli.managers.test.test_manager.TestManager._register_services",
            ):
                manager = TestManager(
                    repo_root=tmp_path,
                    command_executor=mock_command_executor,
                )

                assert manager.repo_root == tmp_path
                assert manager.command_executor == mock_command_executor
                assert manager.build_manager is not None

    @patch("aidb_cli.services.test.test_execution_service.TestExecutionService")
    def test_check_prerequisites_success(
        self,
        mock_service_class,
        manager,
        mock_command_executor,
    ):
        """Test check_prerequisites when all checks pass."""
        mock_service = Mock()
        mock_service.compose_file = (
            manager.repo_root / "src" / "tests" / "_docker" / "docker-compose.yaml"
        )
        mock_service_class.return_value = mock_service

        with patch.object(manager, "get_service", return_value=mock_service):
            result = manager.check_prerequisites()

            assert result is True
            mock_command_executor.execute.assert_called_once()

    @patch("aidb_cli.managers.test.test_manager.CliOutput")
    def test_check_prerequisites_docker_not_available(
        self,
        mock_output,
        manager,
        mock_command_executor,
    ):
        """Test check_prerequisites when Docker is not available."""
        mock_command_executor.execute.side_effect = FileNotFoundError()

        result = manager.check_prerequisites()

        assert result is False
        mock_output.plain.assert_called_once()
        assert "Docker is not installed" in str(mock_output.plain.call_args)

    @patch("aidb_cli.managers.test.test_manager.CliOutput")
    @patch("aidb_cli.services.test.test_execution_service.TestExecutionService")
    def test_check_prerequisites_compose_file_missing(
        self,
        mock_service_class,
        mock_output,
        manager,
        mock_command_executor,
    ):
        """Test check_prerequisites when compose file is missing."""
        mock_service = Mock()
        mock_service.compose_file = Path("/nonexistent/file.yaml")
        mock_service_class.return_value = mock_service

        with patch.object(manager, "get_service", return_value=mock_service):
            result = manager.check_prerequisites()

            assert result is False
            assert mock_output.plain.call_count == 1
            assert "Docker compose file not found" in str(mock_output.plain.call_args)

    def test_check_adapters_specific_languages(self, manager, mock_build_manager):
        """Test checking adapters for specific languages."""
        result = manager.check_adapters(["python", "javascript"])

        assert result == {"python": True, "javascript": True}
        assert mock_build_manager.find_adapter_source.call_count == 2

    def test_check_adapters_all_languages(self, manager, mock_build_manager):
        """Test checking adapters for all languages."""
        result = manager.check_adapters(["all"])

        assert "python" in result
        assert "javascript" in result
        assert "java" in result
        mock_build_manager.get_supported_languages.assert_called_once()

    def test_check_adapters_empty_list(self, manager, mock_build_manager):
        """Test checking adapters with empty list."""
        result = manager.check_adapters([])

        assert "python" in result
        mock_build_manager.get_supported_languages.assert_called_once()

    def test_check_adapters_missing_adapter(self, manager, mock_build_manager):
        """Test checking adapters when some are missing."""
        mock_build_manager.find_adapter_source.return_value = None

        result = manager.check_adapters(["missing_lang"])

        assert result == {"missing_lang": False}

    @patch("aidb_cli.services.test.test_execution_service.TestExecutionService")
    def test_build_docker_command(self, mock_service_class, manager):
        """Test building docker command."""
        mock_service = Mock()
        mock_service.build_docker_command.return_value = [
            "docker",
            "compose",
            "run",
            "test",
        ]
        mock_service_class.return_value = mock_service

        with patch.object(manager, "get_service", return_value=mock_service):
            result = manager.build_docker_command(
                profile="test",
                service="pytest",
                command="test",
                env_vars={"FOO": "bar"},
                build=True,
                detach=False,
            )

            assert result == ["docker", "compose", "run", "test"]
            mock_service.build_docker_command.assert_called_once_with(
                profile="test",
                service="pytest",
                command="test",
                env_vars={"FOO": "bar"},
                build=True,
                detach=False,
            )

    @patch("aidb_cli.services.test.test_reporting_service.TestReportingService")
    @patch("aidb_cli.services.test.test_execution_service.TestExecutionService")
    @patch.object(TestManager, "check_prerequisites", return_value=True)
    @patch.object(TestManager, "check_adapters", return_value={"python": True})
    def test_run_tests_success(
        self,
        mock_check_adapters,
        mock_check_prereqs,
        mock_exec_service_class,
        mock_report_service_class,
        manager,
    ):
        """Test running tests successfully."""
        mock_exec_service = Mock()
        mock_exec_service.prepare_test_environment.return_value = {"TEST": "value"}
        mock_exec_service.run_tests.return_value = 0
        mock_exec_service_class.return_value = mock_exec_service

        mock_report_service = Mock()
        mock_report_service_class.return_value = mock_report_service

        with patch.object(manager, "get_service") as mock_get_service:
            mock_get_service.side_effect = [mock_exec_service, mock_report_service]

            result = manager.run_tests(suite="cli", language="python")

            assert result == 0
            mock_exec_service.prepare_test_environment.assert_called_once()
            mock_exec_service.run_tests.assert_called_once()
            mock_report_service.start_suite.assert_called_once_with("cli")
            mock_report_service.record_result.assert_called_once_with(
                suite="cli",
                exit_code=0,
            )

    @patch.object(TestManager, "check_prerequisites", return_value=False)
    def test_run_tests_prerequisites_fail(self, mock_check_prereqs, manager):
        """Test running tests when prerequisites fail."""
        result = manager.run_tests(suite="cli")

        assert result == 1

    @patch("aidb_cli.managers.test.test_manager.click")
    @patch("aidb_cli.managers.test.test_manager.CliOutput")
    @patch("aidb_cli.services.test.test_reporting_service.TestReportingService")
    @patch("aidb_cli.services.test.test_execution_service.TestExecutionService")
    @patch.object(TestManager, "check_prerequisites", return_value=True)
    @patch.object(
        TestManager,
        "check_adapters",
        return_value={"python": False},
    )
    def test_run_tests_missing_adapters_confirm_no(
        self,
        mock_check_adapters,
        mock_check_prereqs,
        mock_exec_service_class,
        mock_report_service_class,
        mock_output,
        mock_click,
        manager,
    ):
        """Test running tests with missing adapters and user declines."""
        mock_click.confirm.return_value = False

        result = manager.run_tests(suite="adapters", language="python")

        assert result == 1
        mock_click.confirm.assert_called_once()
        mock_output.plain.assert_any_call(
            "   Run './dev-cli adapters build' to build them",
        )

    @patch("aidb_cli.managers.test.test_manager.click")
    @patch("aidb_cli.services.test.test_reporting_service.TestReportingService")
    @patch("aidb_cli.services.test.test_execution_service.TestExecutionService")
    @patch.object(TestManager, "check_prerequisites", return_value=True)
    @patch.object(
        TestManager,
        "check_adapters",
        return_value={"python": False},
    )
    def test_run_tests_missing_adapters_confirm_yes(
        self,
        mock_check_adapters,
        mock_check_prereqs,
        mock_exec_service_class,
        mock_report_service_class,
        mock_click,
        manager,
    ):
        """Test running tests with missing adapters and user confirms."""
        mock_click.confirm.return_value = True

        mock_exec_service = Mock()
        mock_exec_service.prepare_test_environment.return_value = {}
        mock_exec_service.run_tests.return_value = 0

        mock_report_service = Mock()

        with patch.object(manager, "get_service") as mock_get_service:
            mock_get_service.side_effect = [mock_exec_service, mock_report_service]

            result = manager.run_tests(suite="adapters", language="python")

            assert result == 0

    @patch("aidb_cli.services.test.test_reporting_service.TestReportingService")
    @patch("aidb_cli.services.test.test_execution_service.TestExecutionService")
    @patch.object(TestManager, "check_prerequisites", return_value=True)
    def test_run_tests_profile_auto_detection(
        self,
        mock_check_prereqs,
        mock_exec_service_class,
        mock_report_service_class,
        manager,
    ):
        """Test automatic profile detection based on suite."""
        mock_exec_service = Mock()
        mock_exec_service.prepare_test_environment.return_value = {}
        mock_exec_service.run_tests.return_value = 0

        mock_report_service = Mock()

        test_cases = [
            ("mcp", "mcp"),
            ("backend", "backend"),
            ("adapters", "adapters"),
            ("all", "all"),
            ("cli", "base"),
        ]

        for suite, expected_profile in test_cases:
            with patch.object(manager, "get_service") as mock_get_service:
                mock_get_service.side_effect = [mock_exec_service, mock_report_service]

                manager.run_tests(suite=suite, profile="auto")

                call_args = mock_exec_service.run_tests.call_args
                assert call_args[1]["profile"] == expected_profile

    @patch("aidb_cli.services.test.test_execution_service.TestExecutionService")
    def test_run_shell(self, mock_service_class, manager):
        """Test running interactive shell."""
        mock_service = Mock()
        mock_service.run_shell.return_value = 0

        with patch.object(manager, "get_service", return_value=mock_service):
            result = manager.run_shell(profile="test")

            assert result == 0
            mock_service.run_shell.assert_called_once_with("test")

    @patch("aidb_cli.services.test.test_execution_service.TestExecutionService")
    def test_clean(self, mock_service_class, manager):
        """Test cleaning test environment."""
        mock_service = Mock()
        mock_service.clean_test_environment.return_value = 0

        with patch.object(manager, "get_service", return_value=mock_service):
            result = manager.clean()

            assert result == 0
            mock_service.clean_test_environment.assert_called_once()

    @patch("aidb_cli.services.test.test_execution_service.TestExecutionService")
    def test_build_images(self, mock_service_class, manager):
        """Test building Docker images."""
        mock_service = Mock()
        mock_service.build_docker_images.return_value = 0

        with patch.object(manager, "get_service", return_value=mock_service):
            result = manager.build_images(profile="base", verbose=True)

            assert result == 0
            mock_service.build_docker_images.assert_called_once_with("base", True)

    @patch("aidb_cli.services.test.test_reporting_service.TestReportingService")
    @patch("aidb_cli.services.test.test_discovery_service.TestDiscoveryService")
    @patch("aidb_cli.services.test.test_execution_service.TestExecutionService")
    def test_get_test_status_full(
        self,
        mock_exec_service_class,
        mock_disc_service_class,
        mock_report_service_class,
        manager,
        mock_command_executor,
        mock_build_manager,
    ):
        """Test getting comprehensive test status."""
        mock_disc_service = Mock()
        mock_disc_service.get_test_statistics.return_value = {
            "total_tests": 100,
            "suites": ["cli", "mcp"],
        }

        mock_exec_service = Mock()
        mock_exec_service.compose_file = Path("/fake/compose.yaml")

        mock_report_service = Mock()
        mock_report_service.results = {"cli": Mock()}
        mock_aggregate = Mock()
        mock_aggregate.total_suites = 2
        mock_aggregate.total_tests = 100
        mock_aggregate.total_passed = 95
        mock_aggregate.total_failed = 5
        mock_aggregate.overall_success = False
        mock_report_service.aggregate_results.return_value = mock_aggregate

        with patch.object(manager, "get_service") as mock_get_service:

            def get_service_side_effect(service_class):
                if service_class.__name__ == "TestDiscoveryService":
                    return mock_disc_service
                if service_class.__name__ == "TestExecutionService":
                    return mock_exec_service
                if service_class.__name__ == "TestReportingService":
                    return mock_report_service
                return Mock()

            mock_get_service.side_effect = get_service_side_effect

            result = manager.get_test_status()

            assert result["docker_available"] is True
            assert "Docker" in result["docker_version"]
            assert result["adapters_built"]["python"] is True
            assert result["adapters_built"]["javascript"] is True
            assert result["adapters_built"]["java"] is False
            assert result["test_stats"]["total_tests"] == 100
            assert result["last_run"]["total_suites"] == 2
            assert result["last_run"]["overall_success"] is False

    @patch("aidb_cli.services.test.test_reporting_service.TestReportingService")
    @patch("aidb_cli.services.test.test_discovery_service.TestDiscoveryService")
    @patch("aidb_cli.services.test.test_execution_service.TestExecutionService")
    def test_get_test_status_docker_unavailable(
        self,
        mock_exec_service_class,
        mock_disc_service_class,
        mock_report_service_class,
        manager,
        mock_command_executor,
    ):
        """Test getting test status when Docker is unavailable."""
        mock_command_executor.execute.side_effect = OSError()

        mock_disc_service = Mock()
        mock_disc_service.get_test_statistics.return_value = {}

        mock_exec_service = Mock()
        mock_exec_service.compose_file = Path("/fake/compose.yaml")

        mock_report_service = Mock()
        mock_report_service.results = {}

        with patch.object(manager, "get_service") as mock_get_service:

            def get_service_side_effect(service_class):
                if service_class.__name__ == "TestDiscoveryService":
                    return mock_disc_service
                if service_class.__name__ == "TestExecutionService":
                    return mock_exec_service
                if service_class.__name__ == "TestReportingService":
                    return mock_report_service
                return Mock()

            mock_get_service.side_effect = get_service_side_effect

            result = manager.get_test_status()

            assert result["docker_available"] is False
            assert result["docker_version"] == ""

    @patch("aidb_cli.services.test.test_reporting_service.TestReportingService")
    @patch("aidb_cli.services.test.test_discovery_service.TestDiscoveryService")
    @patch("aidb_cli.services.test.test_execution_service.TestExecutionService")
    def test_get_test_status_adapter_check_failure(
        self,
        mock_exec_service_class,
        mock_disc_service_class,
        mock_report_service_class,
        manager,
        mock_command_executor,
        mock_build_manager,
    ):
        """Test getting test status when adapter check fails."""
        mock_build_manager.check_adapters_built.side_effect = OSError()

        mock_disc_service = Mock()
        mock_disc_service.get_test_statistics.return_value = {}

        mock_exec_service = Mock()
        mock_exec_service.compose_file = Path("/fake/compose.yaml")

        mock_report_service = Mock()
        mock_report_service.results = {}

        with patch.object(manager, "get_service") as mock_get_service:

            def get_service_side_effect(service_class):
                if service_class.__name__ == "TestDiscoveryService":
                    return mock_disc_service
                if service_class.__name__ == "TestExecutionService":
                    return mock_exec_service
                if service_class.__name__ == "TestReportingService":
                    return mock_report_service
                return Mock()

            mock_get_service.side_effect = get_service_side_effect

            result = manager.get_test_status()

            assert all(not built for built in result["adapters_built"].values())

    @patch("aidb_cli.services.test.test_reporting_service.TestReportingService")
    @patch("aidb_cli.services.test.test_discovery_service.TestDiscoveryService")
    @patch("aidb_cli.services.test.test_execution_service.TestExecutionService")
    def test_get_test_status_language_fallback(
        self,
        mock_exec_service_class,
        mock_disc_service_class,
        mock_report_service_class,
        manager,
        mock_command_executor,
        mock_build_manager,
    ):
        """Test getting test status with language fallback."""
        mock_build_manager.get_supported_languages.side_effect = Exception()

        mock_disc_service = Mock()
        mock_disc_service.get_test_statistics.return_value = {}

        mock_exec_service = Mock()
        mock_exec_service.compose_file = Path("/fake/compose.yaml")

        mock_report_service = Mock()
        mock_report_service.results = {}

        with patch.object(manager, "get_service") as mock_get_service:

            def get_service_side_effect(service_class):
                if service_class.__name__ == "TestDiscoveryService":
                    return mock_disc_service
                if service_class.__name__ == "TestExecutionService":
                    return mock_exec_service
                if service_class.__name__ == "TestReportingService":
                    return mock_report_service
                return Mock()

            mock_get_service.side_effect = get_service_side_effect

            result = manager.get_test_status()

            assert "adapters_built" in result
            assert all(
                lang in result["adapters_built"]
                for lang in ["python", "javascript", "java"]
            )
