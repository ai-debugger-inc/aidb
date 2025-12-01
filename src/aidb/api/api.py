"""Aidb debugging API."""

from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from aidb.adapters.base.vslaunch import BaseLaunchConfig, LaunchConfigurationManager
from aidb.audit.middleware import audit_operation
from aidb.common.errors import AidbError
from aidb.integrations.vscode import VSCodeIntegration
from aidb.models import AidbStopResponse, SessionInfo
from aidb.models.entities.breakpoint import BreakpointSpec
from aidb.patterns import Obj
from aidb.session import Session

from .constants import (
    DEFAULT_ADAPTER_HOST,
    DEFAULT_TIMEOUT_MS,
    TASK_STATUS_ERROR,
    TASK_STATUS_SUCCESS,
)
from .introspection import APIIntrospectionOperations
from .orchestration import APIOrchestrationOperations
from .session_builder import SessionBuilder
from .session_manager import SessionManager

if TYPE_CHECKING:
    from aidb.common import AidbContext


class DebugAPI(Obj):
    """Provide programmatic debugging API.

    All API methods are responsible for mapping user inputs to valid DAP request
    objects and delegating those responses to the appropriate session methods.

    Note
    ----
    All operations performed through this API are automatically audited when
    audit logging is enabled via the AIDB_AUDIT_LOG environment variable. See
    the audit logging documentation for configuration details.

    Attributes
    ----------
    introspection : APIIntrospectionOperations
        Introspection operations for debugging sessions (all audited)
    orchestration : APIOrchestrationOperations
        Orchestration operations for debugging sessions (all audited)
    """

    _introspection: APIIntrospectionOperations | None = None
    _orchestration: APIOrchestrationOperations | None = None

    @property
    def introspection(self) -> APIIntrospectionOperations:
        """Get introspection operations for debugging sessions.

        Raises
        ------
        AidbError
            If no active debug session exists
        """
        if self._introspection is None:
            msg = "No active debug session. Call start() first."
            raise AidbError(msg)
        return self._introspection

    @property
    def orchestration(self) -> APIOrchestrationOperations:
        """Get orchestration operations for debugging sessions.

        Raises
        ------
        AidbError
            If no active debug session exists
        """
        if self._orchestration is None:
            msg = "No active debug session. Call start() first."
            raise AidbError(msg)
        return self._orchestration

    def __init__(self, ctx: Optional["AidbContext"] = None):
        """Initialize the DebugAPI instance.

        Parameters
        ----------
        ctx : AidbContext, optional
            Application context
        """
        super().__init__(ctx)
        self._session_manager = SessionManager(ctx=ctx)
        self._launch_config: BaseLaunchConfig | None = None

    @property
    def session(self) -> Session | None:
        """Get the active session.

        For languages with child sessions (e.g., JavaScript), returns the active
        child if one exists. This ensures that all session state checks use the
        correct session.

        Returns
        -------
        Session, optional
            The active session (child if exists, otherwise parent)
        """
        return self.get_active_session()

    def get_active_session(self) -> Session | None:
        """Get the active session for operations.

        For JavaScript and other languages that use child sessions, this returns
        the active child if one exists, otherwise the parent. This ensures that
        breakpoints and other operations target the correct session.

        Returns
        -------
        Session, optional
            The active session for operations (child session if present,
            otherwise parent)
        """
        return self._session_manager.get_active_session()

    @property
    def started(self) -> bool:
        """Check whether the debug session has been started.

        Returns
        -------
        bool
            `True` if session has been started, `False` otherwise
        """
        if not self.session:
            return False
        return self.session.started

    @property
    def session_info(self) -> SessionInfo | None:
        """Get information about the active debug session.

        Returns
        -------
        SessionInfo, optional
            SessionInfo object for the active session, or `None` if no session
            exists
        """
        active_session = self.get_active_session()
        if active_session is not None:
            try:
                return active_session.info
            except Exception as e:
                self.ctx.warning(f"Failed to get session info: {e}")

        return None

    @audit_operation(component="api.lifecycle", operation="create_session")
    async def create_session(
        self,
        target: str | None = None,
        language: str | None = None,
        breakpoints: list[BreakpointSpec] | BreakpointSpec | None = None,
        adapter_host: str | None = DEFAULT_ADAPTER_HOST,
        adapter_port: int | None = None,
        # Attach parameters (host/port for remote, pid for local)
        host: str | None = None,
        port: int | None = None,
        pid: int | None = None,
        # Launch parameters
        args: list[str] | None = None,
        launch_config_name: str | None = None,
        workspace_root: str | Path | None = None,
        # Additional parameters
        timeout: int = DEFAULT_TIMEOUT_MS,
        project_name: str | None = None,
        **kwargs: Any,
    ) -> Session:
        """Create a debug session without starting it.

        This allows pre-registration of event handlers before the session
        begins. Call session.start() to begin debugging after setup.

        The mode (launch vs attach) is automatically determined based on
        parameters:
            - Provide 'target' to launch a new process
            - Provide 'pid' to attach to a local process
            - Provide 'host' and 'port' to attach to a remote process

        This operation is automatically audited when audit logging is enabled.

        Parameters
        ----------
        target : str, optional
            The target file to debug. Triggers launch mode when provided.
        language : str, optional
            Programming language. If None, inferred from target or defaults
        breakpoints : Union[List[BreakpointSpec], BreakpointSpec], optional
            Initial breakpoints conforming to BreakpointSpec schema in
            user-friendly formats
        adapter_host : str, optional
            Host where the debug adapter server runs, default "localhost"
        adapter_port : int, optional
            Port where the debug adapter server listens
        host : str, optional
            For attach mode: host of the target process
        port : int, optional
            For attach mode: port of the target process
        pid : int, optional
            For attach mode: process ID to attach to
        args : List[str], optional
            Command-line arguments for launch mode
        launch_config_name : str, optional
            Name of launch configuration to use
        workspace_root : Union[str, Path], optional
            Root directory of the workspace
        timeout : int, optional
            Timeout in milliseconds, default 10000
        project_name : str, optional
            Name of the project being debugged
        ``**kwargs`` : Any
            Additional language-specific parameters

        Returns
        -------
        Session
            The created but not started session. Call session.start() to begin
            debugging

        Raises
        ------
        AidbError
            If parameters are invalid or conflicting
        """
        # Delegate session creation to SessionManager
        session = await self._create_session_internal(
            target=target,
            language=language,
            breakpoints=breakpoints,
            adapter_host=adapter_host or DEFAULT_ADAPTER_HOST,
            adapter_port=adapter_port,
            host=host,
            port=port,
            pid=pid,
            args=args,
            launch_config_name=launch_config_name,
            workspace_root=workspace_root,
            timeout=timeout,
            project_name=project_name,
            **kwargs,
        )

        # Store launch config if applicable
        self._store_launch_config(launch_config_name, workspace_root)

        # Setup operation mixins
        self._setup_operation_mixins(session)

        return session

    @audit_operation(component="api.lifecycle", operation="stop")
    async def stop(self) -> AidbStopResponse:
        """Stop a debugging session.

        This operation is automatically audited when audit logging is enabled.
        The audit log will capture session termination details and cleanup
        status.

        Returns
        -------
        AidbStopResponse
            Response containing stop confirmation
        """
        if not self.session:
            msg = "No active session to stop. Call start() first."
            raise AidbError(msg)
        if self._orchestration is None:
            msg = "Orchestration not initialized. Call start() first."
            raise AidbError(msg)
        result = await self.orchestration.stop()

        # Handle postDebugTask if we have a launch config
        if self._launch_config and self._launch_config.postDebugTask:
            await self._execute_post_debug_task(self._launch_config.postDebugTask)

        # Properly destroy the session to release ports and cleanup resources
        if self.session:
            await self.session.destroy()

        # Clean up session reference
        self._session_manager.destroy_session()
        self._introspection = None
        self._orchestration = None
        self._launch_config = None
        return result

    @audit_operation(component="api.lifecycle", operation="start_from_launch_json")
    async def _execute_post_debug_task(self, task_name: str) -> None:
        """Execute a post-debug task through VS Code.

        Parameters
        ----------
        task_name : str
            Name of the task to execute
        """
        vscode = VSCodeIntegration()
        if vscode.detect_ide():
            if vscode.is_extension_installed() and await vscode.connect():
                self.ctx.info(f"Executing post-debug task: {task_name}")
                result = await vscode.execute_task(task_name)
                if not result.get(TASK_STATUS_SUCCESS):
                    error_msg = result.get(TASK_STATUS_ERROR)
                    self.ctx.warning(
                        f"Post-debug task '{task_name}' failed: {error_msg}",
                    )
                await vscode.disconnect()
            else:
                self.ctx.warning(
                    f"Could not connect to VS Code bridge. "
                    f"Post-debug task '{task_name}' will be skipped",
                )
        else:
            self.ctx.warning(
                f"VS Code not detected. Post-debug task '{task_name}' will be skipped",
            )

    async def _create_session_internal(
        self,
        target: str | None = None,
        language: str | None = None,
        breakpoints: list[BreakpointSpec] | BreakpointSpec | None = None,
        adapter_host: str = DEFAULT_ADAPTER_HOST,
        adapter_port: int | None = None,
        host: str | None = None,
        port: int | None = None,
        pid: int | None = None,
        args: list[str] | None = None,
        launch_config_name: str | None = None,
        workspace_root: str | Path | None = None,
        timeout: int = DEFAULT_TIMEOUT_MS,
        project_name: str | None = None,
        **kwargs: Any,
    ) -> Session:
        """Create session via SessionManager.

        Parameters
        ----------
        All parameters same as create_session

        Returns
        -------
        Session
            The created session
        """
        return self._session_manager.create_session(
            target=target,
            language=language,
            breakpoints=breakpoints,
            adapter_host=adapter_host,
            adapter_port=adapter_port,
            host=host,
            port=port,
            pid=pid,
            args=args,
            launch_config_name=launch_config_name,
            workspace_root=workspace_root,
            timeout=timeout,
            project_name=project_name,
            **kwargs,
        )

    def _store_launch_config(
        self,
        launch_config_name: str | None,
        workspace_root: str | Path | None,
    ) -> None:
        """Store launch configuration if applicable.

        Parameters
        ----------
        launch_config_name : str, optional
            Name of launch configuration
        workspace_root : Union[str, Path], optional
            Root directory of workspace
        """
        if launch_config_name:
            builder = SessionBuilder(ctx=self.ctx)
            builder.with_launch_config(launch_config_name, workspace_root)
            self._launch_config = self._session_manager.get_launch_config(builder)

    def _setup_operation_mixins(self, session: Session) -> None:
        """Set up operation mixins for the session.

        Parameters
        ----------
        session : Session
            The session to setup mixins for
        """
        self._introspection = APIIntrospectionOperations(session=session)
        self._orchestration = APIOrchestrationOperations(session=session)

    def list_launch_configurations(
        self,
        workspace_root: str | Path | None = None,
    ) -> list[dict[str, Any]]:
        """List available VS Code launch configurations.

        Parameters
        ----------
        workspace_root : Union[str, Path], optional
            Root directory containing .vscode/launch.json. Defaults to current
            directory

        Returns
        -------
        List[Dict[str, Any]]
            List of configuration summaries with name, type, and request fields
        """
        # Use only the new config system
        manager = LaunchConfigurationManager(workspace_root)

        return [
            {
                "name": config.name,
                "type": config.type,
                "request": config.request,
                "program": getattr(config, "program", None)
                or getattr(config, "module", None),
            }
            for config in manager.configurations
        ]
