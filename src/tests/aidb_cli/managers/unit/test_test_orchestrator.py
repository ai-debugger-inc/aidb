"""Unit tests for TestOrchestrator."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from aidb_cli.managers.test.test_orchestrator import TestOrchestrator


class TestTestOrchestrator:
    """Test the TestOrchestrator."""

    @pytest.fixture
    def mock_command_executor(self):
        """Create a mock command executor."""
        executor = Mock()
        executor.execute = Mock()
        return executor

    @pytest.fixture
    def mock_ctx(self):
        """Create a mock Click context."""
        ctx = Mock()
        ctx.obj = Mock()
        ctx.obj.resolved_env = {"TEST": "value"}
        return ctx

    @pytest.fixture
    @patch("aidb_cli.managers.test.test_orchestrator.TestManager._register_services")
    def orchestrator(
        self,
        mock_register,
        tmp_path,
        mock_command_executor,
        mock_ctx,
    ):
        """Create orchestrator instance with mocks."""
        return TestOrchestrator(
            repo_root=tmp_path,
            command_executor=mock_command_executor,
            ctx=mock_ctx,
        )

    def test_initialization(self, tmp_path, mock_command_executor, mock_ctx):
        """Test orchestrator initialization."""
        with patch(
            "aidb_cli.managers.test.test_orchestrator.TestManager._register_services",
        ):
            orch = TestOrchestrator(
                repo_root=tmp_path,
                command_executor=mock_command_executor,
                ctx=mock_ctx,
            )

            assert orch.repo_root == tmp_path
            assert orch.ctx is mock_ctx
            assert orch._test_results == {}
            assert orch._docker_orchestrator is None

    @patch("aidb_cli.managers.test.test_orchestrator.DockerOrchestrator")
    def test_docker_orchestrator_lazy_creation(
        self,
        mock_docker_class,
        orchestrator,
    ):
        """Test Docker orchestrator is lazily created."""
        mock_docker = Mock()
        mock_docker_class.return_value = mock_docker

        # Access property - should create orchestrator
        docker = orchestrator.docker_orchestrator

        assert docker is mock_docker
        assert orchestrator._docker_orchestrator is docker

    def test_coordinator_lazy_creation(self, orchestrator):
        """Test coordinator is lazily created."""
        coordinator = orchestrator.coordinator

        assert coordinator is not None
        assert orchestrator._coordinator is coordinator

    def test_discovery_service_lazy_creation(self, orchestrator):
        """Test discovery service is lazily created."""
        discovery = orchestrator.discovery_service

        assert discovery is not None
        assert orchestrator._discovery_service is discovery

    def test_get_suite_metadata(self, orchestrator):
        """Test getting suite metadata."""
        mock_metadata = Mock()
        mock_discovery = Mock()
        mock_discovery.get_suite_metadata.return_value = mock_metadata

        orchestrator._discovery_service = mock_discovery

        metadata = orchestrator.get_suite_metadata("test_suite")

        assert metadata is mock_metadata
        mock_discovery.get_suite_metadata.assert_called_once_with("test_suite")

    @patch("aidb_cli.managers.test.test_orchestrator.CliOutput")
    def test_validate_prerequisites_no_metadata(
        self,
        mock_output,
        orchestrator,
    ):
        """Test prerequisite validation with no metadata."""
        mock_discovery = Mock()
        mock_discovery.get_suite_metadata.return_value = None
        orchestrator._discovery_service = mock_discovery

        result = orchestrator.validate_prerequisites("unknown_suite")

        assert result is True  # Allows running anyway

    @patch("aidb_cli.managers.test.test_orchestrator.CliOutput")
    def test_validate_prerequisites_docker_required(
        self,
        mock_output,
        orchestrator,
    ):
        """Test prerequisite validation when Docker is required."""
        mock_metadata = Mock()
        mock_metadata.requires_docker = True
        mock_metadata.adapters_required = False

        mock_discovery = Mock()
        mock_discovery.get_suite_metadata.return_value = mock_metadata
        orchestrator._discovery_service = mock_discovery

        with patch.object(
            orchestrator,
            "check_prerequisites",
            return_value=True,
        ):
            result = orchestrator.validate_prerequisites("test_suite")

            assert result is True

    @patch("aidb_cli.managers.test.test_orchestrator.CliOutput")
    def test_validate_prerequisites_adapters_required_missing(
        self,
        mock_output,
        orchestrator,
    ):
        """Test prerequisite validation when adapters are missing."""
        mock_metadata = Mock()
        mock_metadata.requires_docker = False
        mock_metadata.adapters_required = True

        mock_discovery = Mock()
        mock_discovery.get_suite_metadata.return_value = mock_metadata
        orchestrator._discovery_service = mock_discovery

        orchestrator.build_manager = Mock()
        orchestrator.build_manager.check_adapters_built.return_value = (
            ["python"],
            ["javascript"],
        )

        result = orchestrator.validate_prerequisites("test_suite")

        assert result is False

    @patch("aidb_cli.managers.test.test_orchestrator.CliOutput")
    def test_validate_prerequisites_adapters_available(
        self,
        mock_output,
        orchestrator,
    ):
        """Test prerequisite validation when all adapters are available."""
        mock_metadata = Mock()
        mock_metadata.requires_docker = False
        mock_metadata.adapters_required = True

        mock_discovery = Mock()
        mock_discovery.get_suite_metadata.return_value = mock_metadata
        orchestrator._discovery_service = mock_discovery

        orchestrator.build_manager = Mock()
        orchestrator.build_manager.check_adapters_built.return_value = (
            ["python", "javascript"],
            [],
        )

        result = orchestrator.validate_prerequisites("test_suite")

        assert result is True

    def test_should_use_docker_no_metadata(self, orchestrator):
        """Test Docker usage decision with no metadata."""
        mock_discovery = Mock()
        mock_discovery.get_suite_metadata.return_value = None
        orchestrator._discovery_service = mock_discovery

        result = orchestrator._should_use_docker("test_suite", None, None)

        assert result is False

    def test_should_use_docker_adapters_suite(self, orchestrator):
        """Test Docker usage decision for adapters suite."""
        # Need mock metadata since get_suite_metadata is called
        mock_metadata = Mock()
        mock_metadata.requires_docker = False
        mock_discovery = Mock()
        mock_discovery.get_suite_metadata.return_value = mock_metadata
        orchestrator._discovery_service = mock_discovery

        result = orchestrator._should_use_docker("adapters", None, None)

        assert result is True

    def test_should_use_docker_mcp_multilang(self, orchestrator):
        """Test Docker usage decision for MCP with non-Python language."""
        # Need mock metadata since get_suite_metadata is called
        mock_metadata = Mock()
        mock_metadata.requires_docker = False
        mock_discovery = Mock()
        mock_discovery.get_suite_metadata.return_value = mock_metadata
        orchestrator._discovery_service = mock_discovery

        result = orchestrator._should_use_docker("mcp", "javascript", None)

        assert result is True

    def test_should_use_docker_mcp_python(self, orchestrator):
        """Test Docker usage decision for MCP with Python."""
        result = orchestrator._should_use_docker("mcp", "python", None)

        assert result is False

    def test_should_use_docker_requires_docker(self, orchestrator):
        """Test Docker usage decision when metadata requires Docker."""
        mock_metadata = Mock()
        mock_metadata.requires_docker = True

        mock_discovery = Mock()
        mock_discovery.get_suite_metadata.return_value = mock_metadata
        orchestrator._discovery_service = mock_discovery

        result = orchestrator._should_use_docker("test_suite", None, None)

        assert result is True

    @patch("aidb_cli.managers.test.test_orchestrator.CliOutput")
    def test_run_local_tests(self, mock_output, orchestrator, tmp_path):
        """Test running tests locally."""
        mock_execution = Mock()
        mock_execution.run_local_tests.return_value = 0

        with patch.object(orchestrator, "get_service", return_value=mock_execution):
            exit_code = orchestrator._run_local_tests("test_suite", ["-v"])

            assert exit_code == 0
            mock_execution.run_local_tests.assert_called_once()

    def test_aggregate_results(self, orchestrator):
        """Test aggregating test results."""
        mock_reporting = Mock()
        mock_aggregated = {"total": 100, "passed": 95}
        mock_reporting.aggregate_results.return_value = mock_aggregated

        with patch.object(orchestrator, "get_service", return_value=mock_reporting):
            results = orchestrator.aggregate_results({"suite1": 0, "suite2": 0})

            assert results == mock_aggregated

    def test_get_test_statistics(self, orchestrator):
        """Test getting test statistics."""
        mock_reporting = Mock()
        mock_stats = {"total_tests": 100}
        mock_reporting.generate_statistics.return_value = mock_stats

        mock_discovery = Mock()
        mock_discovery.get_all_suites.return_value = []
        orchestrator._discovery_service = mock_discovery

        with patch.object(orchestrator, "get_service", return_value=mock_reporting):
            stats = orchestrator.get_test_statistics()

            assert stats == mock_stats

    @patch("aidb_cli.managers.test.test_orchestrator.CliOutput")
    def test_run_docker_tests_environment_startup_failure(
        self,
        mock_output,
        orchestrator,
    ):
        """Test Docker test run with environment startup failure."""
        mock_docker_orch = Mock()
        mock_docker_orch.start_test_environment.return_value = False
        orchestrator._docker_orchestrator = mock_docker_orch

        exit_code = orchestrator._run_docker_tests(
            suite="test",
            languages=["python"],
            markers=None,
            pattern=None,
            target=None,
            parallel=None,
            coverage=False,
            verbose=False,
            failfast=False,
            last_failed=False,
            build=False,
            timeout=None,
            no_cleanup=False,
        )

        assert exit_code == 1
