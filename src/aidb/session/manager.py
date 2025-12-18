"""Session lifecycle management."""

import threading
from pathlib import Path
from typing import Any

from aidb.common import AidbContext
from aidb.common.constants import MAX_CONCURRENT_SESSIONS
from aidb.common.errors import AidbError
from aidb.models.entities.breakpoint import BreakpointSpec
from aidb.patterns import Obj
from aidb.session.registry import SessionRegistry
from aidb.session.session_core import Session
from aidb_common.constants import Language

from .builder import SessionBuilder


class SessionManager(Obj):
    """Manages session lifecycle and state for the Debug API.

    This class encapsulates all session management logic, including:
        - Session creation and destruction
        - Active session tracking
        - Child session resolution
        - Thread-safe session counting
    """

    def __init__(self, ctx: AidbContext | None = None):
        """Initialize the SessionManager.

        Parameters
        ----------
        ctx : AidbContext, optional
            Application context
        """
        super().__init__(ctx)
        # Add sync lock for thread-safe session management
        self.lock = threading.RLock()
        self._active_sessions = 0
        self._current_session: Session | None = None
        self._registry = SessionRegistry(ctx=self.ctx)

    @property
    def active_sessions_count(self) -> int:
        """Get the count of active sessions.

        Returns
        -------
        int
            Number of active sessions
        """
        with self.lock:
            return self._active_sessions

    @property
    def current_session(self) -> Session | None:
        """Get the current session.

        Returns
        -------
        Session, optional
            The current session if one exists
        """
        with self.lock:
            return self._current_session

    def get_active_session(self) -> Session | None:
        """Get the active session for operations.

        For JavaScript and other languages that use child sessions, this returns
        the active child if one exists, otherwise the parent.

        Returns
        -------
        Session, optional
            The active session for operations
        """
        with self.lock:
            if not self._current_session:
                return None
            return self._registry.resolve_active_session(self._current_session)

    def create_session(
        self,
        target: str | None = None,
        language: str | None = None,
        breakpoints: list[BreakpointSpec] | BreakpointSpec | None = None,
        adapter_host: str = "localhost",
        adapter_port: int | None = None,
        host: str | None = None,
        port: int | None = None,
        pid: int | None = None,
        args: list[str] | None = None,
        launch_config_name: str | None = None,
        workspace_root: str | Path | None = None,
        timeout: int = 10000,
        project_name: str | None = None,
        **kwargs: Any,
    ) -> Session:
        """Create a new debug session.

        Parameters
        ----------
        target : str, optional
            The target file to debug
        language : str, optional
            Programming language
        breakpoints : Union[List[BreakpointSpec], BreakpointSpec], optional
            Initial breakpoints conforming to BreakpointSpec schema
        adapter_host : str, optional
            Host where the debug adapter runs
        adapter_port : int, optional
            Port where the debug adapter listens
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
            Timeout in milliseconds
        project_name : str, optional
            Name of the project being debugged
        ``**kwargs`` : Any
            Additional language-specific parameters

        Returns
        -------
        Session
            The created session

        Raises
        ------
        AidbError
            If session limit exceeded
        """
        # Check session limit
        with self.lock:
            if self._active_sessions >= MAX_CONCURRENT_SESSIONS:
                msg = (
                    f"Maximum concurrent sessions ({MAX_CONCURRENT_SESSIONS}) "
                    "exceeded. Please stop an existing session before starting "
                    "a new one."
                )
                raise AidbError(
                    msg,
                )

        # Build session using SessionBuilder
        builder = SessionBuilder(ctx=self.ctx)

        # Configure from launch.json if specified
        if launch_config_name:
            builder.with_launch_config(launch_config_name, workspace_root)

        # Configure target or attach mode
        if target:
            builder.with_target(target, args)
        elif pid or (host and port):
            builder.with_attach(host, port, pid)

        # Set remaining parameters
        if language:
            builder.with_language(language)

        builder.with_adapter(adapter_host, adapter_port)

        if breakpoints:
            builder.with_breakpoints(breakpoints, target)

        if project_name:
            builder.with_project(project_name)

        builder.with_timeout(timeout)

        builder.with_kwargs(**kwargs)

        # Debug logging for Java framework tests
        if language == Language.JAVA and kwargs:
            self.ctx.debug(
                f"Java create_session called with target={target}, kwargs={kwargs}",
            )

        # Build and track the session
        self.ctx.debug(
            f"Building session with target='{target}', language='{language}'",
        )
        session = builder.build()

        with self.lock:
            self._current_session = session
            self._active_sessions += 1

        self.ctx.info(
            f"Created session {session.id} - {self._active_sessions} total active",
        )
        return session

    def destroy_session(self) -> None:
        """Destroy the current session and clean up resources.

        This method safely decrements the active session count and clears the current
        session reference. It uses thread-safe locking to prevent race conditions during
        session cleanup.
        """
        with self.lock:
            session_id = (
                self._current_session.id if self._current_session else "unknown"
            )

            self._current_session = None
            self._active_sessions = max(0, self._active_sessions - 1)
            self.ctx.info(
                f"Destroyed session {session_id} - {self._active_sessions} remaining",
            )

    def get_launch_config(self, builder: SessionBuilder) -> Any | None:
        """Extract launch config from builder if present.

        Parameters
        ----------
        builder : SessionBuilder
            The session builder

        Returns
        -------
        Any, optional
            Launch config if present
        """
        if hasattr(builder, "_launch_config") and builder._launch_config:
            return builder._launch_config
        return None
