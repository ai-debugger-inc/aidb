"""Tests for base manager classes."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from aidb_cli.managers.base import BaseManager, BaseOrchestrator, BaseService


class TestBaseManager:
    """Test BaseManager functionality."""

    def teardown_method(self):
        """Reset singleton after each test."""
        BaseManager.reset()

    def test_singleton_pattern(self, tmp_path):
        """Test that BaseManager implements singleton pattern."""
        # Create two instances
        manager1 = BaseManager(repo_root=tmp_path)
        manager2 = BaseManager(repo_root=tmp_path)

        # Should be the same instance (via aidb_common.Singleton)
        assert manager1 is manager2
        assert manager1.repo_root == tmp_path
        assert manager2.repo_root == tmp_path

    def test_singleton_per_subclass(self, tmp_path):
        """Test that each subclass gets its own singleton."""

        class Manager1(BaseManager):
            pass

        class Manager2(BaseManager):
            pass

        m1_inst1 = Manager1(repo_root=tmp_path)
        m1_inst2 = Manager1(repo_root=tmp_path)
        m2_inst1 = Manager2(repo_root=tmp_path)

        # Same class instances should be identical
        assert m1_inst1 is m1_inst2
        # Different class instances should be different
        assert m1_inst1 is not m2_inst1

    def test_reset_singleton(self, tmp_path):
        """Test resetting singleton instance."""

        class TestManager(BaseManager):
            pass

        # Create instance
        manager1 = TestManager(repo_root=tmp_path)
        assert manager1.repo_root == tmp_path

        # Reset and create new instance
        TestManager.reset()
        manager2 = TestManager(repo_root=tmp_path)

        # Should be different instances after reset
        assert manager1 is not manager2
        assert manager2.repo_root == tmp_path

    def test_auto_detect_repo_root(self):
        """Test auto-detection of repo root."""
        with patch("aidb_cli.managers.base.manager.detect_repo_root") as mock_detect:
            mock_detect.return_value = Path("/test/repo")

            manager = BaseManager()

            assert manager.repo_root == Path("/test/repo")
            mock_detect.assert_called_once()


class TestBaseService:
    """Test BaseService functionality."""

    def test_service_initialization(self, tmp_path):
        """Test basic service initialization."""
        service = BaseService(repo_root=tmp_path)

        assert service.repo_root == tmp_path
        assert service._command_executor is None

    def test_command_executor_lazy_creation(self, tmp_path):
        """Test lazy creation of command executor."""
        service = BaseService(repo_root=tmp_path)

        with patch(
            "aidb_cli.services.command_executor.CommandExecutor",
        ) as mock_executor_class:
            mock_instance = Mock()
            mock_executor_class.return_value = mock_instance

            # Access command_executor property
            executor = service.command_executor

            assert executor is mock_instance
            mock_executor_class.assert_called_once_with(ctx=None)
            # Second access should return same instance
            executor2 = service.command_executor
            assert executor2 is mock_instance
            assert mock_executor_class.call_count == 1

    def test_service_with_provided_executor(self, tmp_path):
        """Test service with provided command executor."""
        mock_executor = Mock()
        service = BaseService(repo_root=tmp_path, command_executor=mock_executor)

        assert service.command_executor is mock_executor

    def test_logging_methods(self, tmp_path):
        """Test service logging methods."""
        service = BaseService(repo_root=tmp_path)

        # Mock the logger to verify calls
        with patch.object(service, "_logger") as mock_logger:
            service.log_debug("Debug %s", "message")
            service.log_info("Info %s", "message")
            service.log_warning("Warning %s", "message")
            service.log_error("Error %s", "message")

            # Verify logger was called with expected messages (lazy % formatting)
            mock_logger.debug.assert_called_once_with(
                "[%s] Debug %s",
                "BaseService",
                "message",
            )
            mock_logger.info.assert_called_once_with(
                "[%s] Info %s",
                "BaseService",
                "message",
            )
            mock_logger.warning.assert_called_once_with(
                "[%s] Warning %s",
                "BaseService",
                "message",
            )
            mock_logger.error.assert_called_once_with(
                "[%s] Error %s",
                "BaseService",
                "message",
            )

    def test_validate_paths(self, tmp_path):
        """Test path validation."""
        service = BaseService(repo_root=tmp_path)

        # Create test files
        existing_file = tmp_path / "exists.txt"
        existing_file.write_text("test")
        non_existing = tmp_path / "missing.txt"

        # Test validation
        assert service.validate_paths(existing_file) is True
        assert service.validate_paths(non_existing) is False
        assert service.validate_paths(existing_file, non_existing) is False

    def test_ensure_directory(self, tmp_path):
        """Test directory creation."""
        service = BaseService(repo_root=tmp_path)

        # Test creating new directory
        new_dir = tmp_path / "new" / "nested" / "dir"
        result = service.ensure_directory(new_dir)

        assert result == new_dir
        assert new_dir.exists()
        assert new_dir.is_dir()

        # Test with existing directory
        result2 = service.ensure_directory(new_dir)
        assert result2 == new_dir


class TestBaseOrchestrator:
    """Test BaseOrchestrator functionality."""

    def teardown_method(self):
        """Reset singleton after each test."""
        BaseOrchestrator.reset()

    def test_orchestrator_is_manager(self, tmp_path):
        """Test that orchestrator inherits from BaseManager."""
        orchestrator = BaseOrchestrator(repo_root=tmp_path)

        assert isinstance(orchestrator, BaseManager)
        assert orchestrator.repo_root == tmp_path
        # Orchestrator should have initialized successfully
        assert orchestrator._services == {}

    def test_service_registration(self, tmp_path):
        """Test registering services."""

        class TestService(BaseService):
            pass

        orchestrator = BaseOrchestrator(repo_root=tmp_path)
        service = orchestrator.register_service(TestService)

        assert isinstance(service, TestService)
        assert service.repo_root == tmp_path
        assert orchestrator.has_service(TestService)

    def test_service_retrieval(self, tmp_path):
        """Test getting registered services."""

        class TestService(BaseService):
            pass

        orchestrator = BaseOrchestrator(repo_root=tmp_path)
        registered = orchestrator.register_service(TestService)
        retrieved = orchestrator.get_service(TestService)

        assert registered is retrieved

    def test_service_not_registered(self, tmp_path):
        """Test getting unregistered service raises error."""

        class UnregisteredService(BaseService):
            pass

        orchestrator = BaseOrchestrator(repo_root=tmp_path)

        with pytest.raises(ValueError, match="not registered"):
            orchestrator.get_service(UnregisteredService)

    def test_service_singleton_within_orchestrator(self, tmp_path):
        """Test services are singletons within orchestrator."""

        class TestService(BaseService):
            pass

        orchestrator = BaseOrchestrator(repo_root=tmp_path)
        service1 = orchestrator.register_service(TestService)
        service2 = orchestrator.register_service(TestService)

        assert service1 is service2

    def test_cleanup_services(self, tmp_path):
        """Test cleanup of registered services."""

        class TestService(BaseService):
            def cleanup(self):
                self.cleaned = True

        orchestrator = BaseOrchestrator(repo_root=tmp_path)
        service = orchestrator.register_service(TestService)

        orchestrator.cleanup_services()
        assert service.cleaned

    def test_cleanup_services_error_handling(self, tmp_path):
        """Test cleanup handles service errors gracefully."""

        class FailingService(BaseService):
            def cleanup(self):
                msg = "Cleanup failed"
                raise ValueError(msg)

        orchestrator = BaseOrchestrator(repo_root=tmp_path)

        # Mock the logger to verify error logging
        with patch("aidb_cli.managers.base.orchestrator.logger") as mock_logger:
            orchestrator.register_service(FailingService)

            # Should not raise, but log error
            orchestrator.cleanup_services()

            # Verify error was logged
            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args[0]
            assert "Error cleaning up service" in call_args[0]
            assert "FailingService" in call_args[1]

    def test_execute_with_services(self, tmp_path):
        """Test workflow execution."""

        class TestOrchestrator(BaseOrchestrator):
            def test_workflow(self, value):
                return f"Executed: {value}"

        orchestrator = TestOrchestrator(repo_root=tmp_path)
        result = orchestrator.execute_with_services("test_workflow", "test_value")

        assert result == "Executed: test_value"

    def test_execute_missing_workflow(self, tmp_path):
        """Test executing non-existent workflow."""
        orchestrator = BaseOrchestrator(repo_root=tmp_path)

        with pytest.raises(AttributeError) as exc_info:
            orchestrator.execute_with_services("missing_workflow")

        assert "Workflow 'missing_workflow' not found" in str(exc_info.value)

    def test_orchestrator_with_command_executor(self, tmp_path):
        """Test orchestrator with provided command executor."""
        mock_executor = Mock()
        orchestrator = BaseOrchestrator(
            repo_root=tmp_path,
            command_executor=mock_executor,
        )

        assert orchestrator.command_executor is mock_executor

        # Services should get the same executor
        class TestService(BaseService):
            pass

        service = orchestrator.register_service(TestService)
        assert service.command_executor is mock_executor
