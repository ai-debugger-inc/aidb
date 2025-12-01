"""Base orchestrator class for managing services."""

from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, TypeVar

from aidb_cli.managers.base.manager import BaseManager
from aidb_cli.managers.base.service import BaseService
from aidb_logging import get_cli_logger

if TYPE_CHECKING:
    from aidb_cli.services.command_executor import CommandExecutor

logger = get_cli_logger(__name__)

S = TypeVar("S", bound=BaseService)


class BaseOrchestrator(BaseManager):
    """Base orchestrator for coordinating multiple services.

    This class extends BaseManager to provide:
    - Service registration and management
    - Service lifecycle coordination
    - Dependency injection patterns
    - Orchestration workflows
    """

    def __init__(
        self,
        repo_root: Path | None = None,
        command_executor: Optional["CommandExecutor"] = None,
    ) -> None:
        """Initialize the base orchestrator.

        Parameters
        ----------
        repo_root : Path | None, optional
            Repository root directory
        command_executor : CommandExecutor | None, optional
            Command executor instance
        """
        self._command_executor = command_executor
        self._services: dict[type[BaseService], BaseService] = {}
        super().__init__(repo_root=repo_root)

    def _initialize(self) -> None:
        """Initialize orchestrator and register services.

        Subclasses should override to register their services.
        """
        self._register_services()

    def _register_services(self) -> None:
        """Register services for this orchestrator.

        Subclasses should override to register their specific services.

        Example
        -------
            self.register_service(MyService)
        """

    @property
    def command_executor(self) -> "CommandExecutor":
        """Get command executor instance, creating if necessary.

        Returns
        -------
        CommandExecutor
            Command executor instance
        """
        if self._command_executor is None:
            from aidb_cli.services.command_executor import CommandExecutor

            # Use Click context when available so streaming respects verbosity flags
            click_ctx = None
            try:
                import click

                click_ctx = click.get_current_context(silent=True)
            except Exception:
                click_ctx = None

            self._command_executor = CommandExecutor(ctx=click_ctx)
        return self._command_executor

    def register_service(
        self,
        service_class: type[S],
        **kwargs: Any,
    ) -> S:
        r"""Register a service with the orchestrator.

        Parameters
        ----------
        service_class : Type[S]
            Service class to instantiate
        **kwargs : Any
            Additional arguments for service initialization

        Returns
        -------
        S
            Instantiated service
        """
        if service_class in self._services:
            return self._services[service_class]  # type: ignore[return-value]

        service = service_class(
            repo_root=self.repo_root,
            command_executor=self.command_executor,
            **kwargs,
        )
        self._services[service_class] = service
        logger.debug(
            "Registered service %s in %s",
            service_class.__name__,
            self.__class__.__name__,
        )
        return service

    def get_service(self, service_class: type[S]) -> S:
        """Get a registered service.

        Parameters
        ----------
        service_class : Type[S]
            Service class to retrieve

        Returns
        -------
        S
            Service instance

        Raises
        ------
        ValueError
            If service is not registered
        """
        if service_class not in self._services:
            msg = (
                f"Service {service_class.__name__} not registered in "
                f"{self.__class__.__name__}"
            )
            raise ValueError(
                msg,
            )
        return self._services[service_class]  # type: ignore[return-value]

    def has_service(self, service_class: type[BaseService]) -> bool:
        """Check if a service is registered.

        Parameters
        ----------
        service_class : Type[BaseService]
            Service class to check

        Returns
        -------
        bool
            True if service is registered
        """
        return service_class in self._services

    def cleanup_services(self) -> None:
        """Cleanup all registered services.

        Calls cleanup() on each service in reverse registration order.
        """
        for service_class in reversed(list(self._services.keys())):
            service = self._services[service_class]
            try:
                service.cleanup()
                logger.debug("Cleaned up service %s", service_class.__name__)
            except Exception as e:  # Resilience: continue cleanup even if one fails
                logger.error(
                    "Error cleaning up service %s: %s",
                    service_class.__name__,
                    str(e),
                )

    @classmethod
    def reset(cls) -> None:
        """Reset the orchestrator and its services."""
        if cls in cls._instances:
            instance = cls._instances[cls]
            if hasattr(instance, "_services"):
                instance.cleanup_services()
                instance._services.clear()
        super().reset()

    def execute_with_services(
        self,
        workflow: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        r"""Execute a workflow with registered services.

        Parameters
        ----------
        workflow : str
            Name of workflow method to execute
        *args : Any
            Positional arguments for workflow
        **kwargs : Any
            Keyword arguments for workflow

        Returns
        -------
        Any
            Workflow result

        Raises
        ------
        AttributeError
            If workflow method doesn't exist
        """
        workflow_method = getattr(self, workflow, None)
        if workflow_method is None or not callable(workflow_method):
            msg = f"Workflow '{workflow}' not found in {self.__class__.__name__}"
            raise AttributeError(
                msg,
            )

        logger.debug("Executing workflow '%s' in %s", workflow, self.__class__.__name__)
        try:
            return workflow_method(*args, **kwargs)
        except Exception as e:
            logger.error("Error in workflow '%s': %s", workflow, str(e))
            raise
