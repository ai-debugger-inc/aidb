"""Session lifecycle management for the API."""

import threading
from pathlib import Path
from typing import Any

from aidb.common import AidbContext
from aidb.common.errors import AidbError
from aidb.models.entities.breakpoint import BreakpointSpec
from aidb.patterns import Obj
from aidb.session import Session
from aidb.session.registry import SessionRegistry
from aidb_common.constants import Language

from .constants import MAX_CONCURRENT_SESSIONS
from .session_builder import SessionBuilder


class ResourceTracker:
    """Tracks resource allocations across all sessions.

    This class provides centralized tracking of all resources (ports, processes, etc.)
    allocated to sessions, enabling proper cleanup and leak detection.
    """

    def __init__(self, ctx: AidbContext | None = None):
        """Initialize the resource tracker.

        Parameters
        ----------
        ctx : AidbContext, optional
            Application context for logging
        """
        self.ctx = ctx
        self.lock = threading.RLock()
        # Track resources by session: {session_id: {resource_type: [resource_ids]}}
        self._session_resources: dict[str, dict[str, list[Any]]] = {}
        # Reverse lookup: {(resource_type, resource_id): session_id}
        self._resource_owners: dict[tuple[str, Any], str] = {}

    def track_resource(
        self,
        resource_type: str,
        resource_id: Any,
        session_id: str,
        _metadata: dict[str, Any] | None = None,
    ) -> None:
        """Track a resource allocation."""
        with self.lock:
            # Initialize session tracking if needed
            if session_id not in self._session_resources:
                self._session_resources[session_id] = {}
            if resource_type not in self._session_resources[session_id]:
                self._session_resources[session_id][resource_type] = []

            # Track the resource
            self._session_resources[session_id][resource_type].append(resource_id)
            self._resource_owners[(resource_type, resource_id)] = session_id

            if self.ctx:
                self.ctx.debug(
                    f"Tracked {resource_type} resource {resource_id} "
                    f"for session {session_id[:8]}",
                )

    def untrack_resource(self, resource_type: str, resource_id: Any) -> str | None:
        """Stop tracking a resource."""
        with self.lock:
            key = (resource_type, resource_id)
            session_id = self._resource_owners.pop(key, None)

            if session_id and session_id in self._session_resources:
                resources = self._session_resources[session_id].get(resource_type, [])
                if resource_id in resources:
                    resources.remove(resource_id)
                    if not resources:
                        del self._session_resources[session_id][resource_type]
                    if not self._session_resources[session_id]:
                        del self._session_resources[session_id]

            return session_id

    def get_session_resources(self, session_id: str) -> dict[str, list[Any]]:
        """Get all resources owned by a session."""
        with self.lock:
            return self._session_resources.get(session_id, {}).copy()

    def get_resource_owner(self, resource_type: str, resource_id: Any) -> str | None:
        """Get the session that owns a resource."""
        with self.lock:
            return self._resource_owners.get((resource_type, resource_id))

    def clear_session_resources(self, session_id: str) -> dict[str, int]:
        """Clear all resource tracking for a session."""
        with self.lock:
            resources = self._session_resources.pop(session_id, {})
            counts = {}

            # Clear reverse lookups
            for resource_type, resource_ids in resources.items():
                counts[resource_type] = len(resource_ids)
                for resource_id in resource_ids:
                    self._resource_owners.pop((resource_type, resource_id), None)

            return counts

    def get_all_resources(self) -> dict[str, dict[str, Any]]:
        """Get all tracked resources across all sessions."""
        with self.lock:
            return {sid: res.copy() for sid, res in self._session_resources.items()}

    def detect_leaks(self) -> dict[str, list[str]]:
        """Detect potential resource leaks.

        Returns
        -------
        Dict[str, List[str]]
            Sessions with potential leaks and their leaked resource types
        """
        leaks = {}
        with self.lock:
            for session_id, resources in self._session_resources.items():
                if resources:
                    # Session has resources but might be terminated
                    leaks[session_id] = list(resources.keys())
        return leaks


class SessionManager(Obj):
    """Manages session lifecycle and state for the Debug API.

    This class encapsulates all session management logic, including:
        - Session creation and destruction
        - Active session tracking
        - Child session resolution
        - Thread-safe session counting
        - Resource tracking and leak detection
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
        # Add resource tracking
        self._resource_tracker = ResourceTracker(ctx=self.ctx)

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
            # Track the session itself as a resource
            self._resource_tracker.track_resource("session", session.id, session.id)

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

            # Clear resource tracking for the session
            if session_id != "unknown":
                cleared = self._resource_tracker.clear_session_resources(session_id)
                if cleared:
                    self.ctx.debug(
                        f"Cleared resource tracking for session {session_id}: "
                        f"{cleared}",
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

    def track_session_resource(
        self,
        session_id: str,
        resource_type: str,
        resource_id: Any,
    ) -> None:
        """Track a resource allocation for a session.

        Parameters
        ----------
        session_id : str
            Session that owns the resource
        resource_type : str
            Type of resource (e.g., "port", "process")
        resource_id : Any
            Unique identifier for the resource
        """
        self._resource_tracker.track_resource(resource_type, resource_id, session_id)

    def get_session_resources(self, session_id: str) -> dict[str, list[Any]]:
        """Get all tracked resources for a session.

        Parameters
        ----------
        session_id : str
            Session to query

        Returns
        -------
        Dict[str, List[Any]]
            Resources by type owned by the session
        """
        return self._resource_tracker.get_session_resources(session_id)

    def detect_resource_leaks(self) -> dict[str, list[str]]:
        """Detect potential resource leaks across all sessions.

        Returns
        -------
        Dict[str, List[str]]
            Sessions with potential leaks and their leaked resource types
        """
        return self._resource_tracker.detect_leaks()

    def get_resource_summary(self) -> dict[str, Any]:
        """Get a summary of all tracked resources.

        Returns
        -------
        Dict[str, Any]
            Summary including:
            - active_sessions: count of active sessions
            - total_resources: count of all tracked resources
            - resources_by_session: detailed breakdown
            - potential_leaks: any detected resource leaks
        """
        with self.lock:
            all_resources = self._resource_tracker.get_all_resources()
            total_count = sum(
                sum(len(res_list) for res_list in resources.values())
                for resources in all_resources.values()
            )

            return {
                "active_sessions": self._active_sessions,
                "total_resources": total_count,
                "resources_by_session": all_resources,
                "potential_leaks": self._resource_tracker.detect_leaks(),
            }
