"""Session registry for tracking all debug sessions.

This module provides a singleton registry for managing debug sessions, delegating child
management and cleanup to specialized managers.
"""

from typing import TYPE_CHECKING, Optional

from aidb.patterns import Obj
from aidb_common.patterns import Singleton

from .child_registry import ChildSessionRegistry
from .cleanup_manager import SessionCleanupManager

if TYPE_CHECKING:
    from aidb.interfaces import IContext
    from aidb.session import Session


class SessionRegistry(Singleton["SessionRegistry"], Obj):
    """Registry for tracking all debug sessions.

    This singleton class manages:
        - Registration and lookup of all active sessions
        - Delegation to child and cleanup managers
        - Session lifecycle coordination

    Attributes
    ----------
    _sessions : Dict[str, Session]
        All registered sessions by session ID
    _child_manager : ChildSessionRegistry
        Manager for parent-child relationships
    _cleanup_manager : SessionCleanupManager
        Manager for session cleanup operations
    """

    _initialized: bool

    def __init__(self, ctx: Optional["IContext"] = None):
        """Initialize the session registry.

        Parameters
        ----------
        ctx : AidbContext, optional
            Context for logging
        """
        # Only initialize once for singleton
        if hasattr(self, "_initialized") and self._initialized:
            # Update context if provided
            if ctx:
                self.ctx = ctx
            return

        super().__init__(ctx)
        # Add sync lock for thread-safe session registry operations
        import threading

        self.lock = threading.RLock()
        self._sessions: dict[str, Session] = {}
        self._child_manager = ChildSessionRegistry(ctx)
        self._cleanup_manager = SessionCleanupManager(ctx)
        self._initialized = True

    def register_session(self, session: "Session") -> None:
        """Register a session in the registry.

        Parameters
        ----------
        session : Session
            The session to register
        """
        with self.lock:
            self.ctx.debug(
                f"Registering session {session.id} (is_child={session.is_child})",
            )
            self._sessions[session.id] = session
            self.ctx.debug(
                f"Registered session {session.id} (language={session.language}). "
                f"Total sessions: {len(self._sessions)}",
            )

    def unregister_session(self, session_id: str) -> None:
        """Unregister a session from the registry.

        Parameters
        ----------
        session_id : str
            The ID of the session to unregister
        """
        with self.lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                self.ctx.debug(f"Unregistered session {session_id}")

    def get_session(self, session_id: str) -> Optional["Session"]:
        """Get a session by its ID.

        Parameters
        ----------
        session_id : str
            The session ID to look up

        Returns
        -------
        Session or None
            The session if found, None otherwise
        """
        with self.lock:
            return self._sessions.get(session_id)

    def get_all_sessions(self) -> list["Session"]:
        """Get all registered sessions.

        Returns
        -------
        List[Session]
            All currently registered sessions
        """
        with self.lock:
            return list(self._sessions.values())

    # ---------------------------
    # Child Management Delegation
    # ---------------------------

    def register_parent_child(self, parent_id: str, child_id: str) -> None:
        """Register a parent-child relationship between sessions.

        Parameters
        ----------
        parent_id : str
            The parent session ID
        child_id : str
            The child session ID
        """
        with self.lock:
            self._child_manager.register_parent_child(parent_id, child_id)

    def get_children(self, parent_id: str) -> list["Session"]:
        """Get all child sessions of a parent.

        Parameters
        ----------
        parent_id : str
            The parent session ID

        Returns
        -------
        List[Session]
            List of child sessions (empty if none)
        """
        with self.lock:
            return self._child_manager.get_children(parent_id, self._sessions)

    def set_active_child(self, parent_id: str, child_id: str) -> None:
        """Set the active child session for a parent.

        Parameters
        ----------
        parent_id : str
            The parent session ID
        child_id : str
            The child session ID to make active
        """
        with self.lock:
            self._child_manager.set_active_child(parent_id, child_id)

    def get_active_child(self, parent_id: str) -> str | None:
        """Get the active child session ID for a parent.

        Parameters
        ----------
        parent_id : str
            The parent session ID

        Returns
        -------
        str or None
            The active child session ID, or None if no active child
        """
        with self.lock:
            return self._child_manager.get_active_child(parent_id)

    def resolve_active_session(self, session: "Session") -> "Session":
        """Resolve the active session for operations.

        Parameters
        ----------
        session : Session
            The parent/root session

        Returns
        -------
        Session
            The active session (child if available, otherwise parent)
        """
        with self.lock:
            return self._child_manager.resolve_active_session(session, self._sessions)

    def get_active_session(self, language: str) -> Optional["Session"]:
        """Get the active session for a language.

        Parameters
        ----------
        language : str
            The language to find a session for

        Returns
        -------
        Session or None
            The most appropriate active session for the language
        """
        with self.lock:
            return self._child_manager.get_active_session_for_language(
                language,
                self._sessions,
            )

    # ---------------------------
    # Cleanup Management Delegation
    # ---------------------------

    async def cleanup_session(self, session_id: str) -> None:
        """Clean up a session and all its children.

        Parameters
        ----------
        session_id : str
            The session ID to clean up
        """
        with self.lock:
            await self._cleanup_manager.cleanup_session(
                session_id,
                self._sessions,
                self._child_manager,
            )

    async def cleanup_all(self) -> None:
        """Clean up all sessions in the registry.

        This is typically called during shutdown to ensure all debug sessions are
        properly terminated.
        """
        with self.lock:
            await self._cleanup_manager.cleanup_all(self._sessions, self._child_manager)
            self.ctx.debug("Session registry cleaned up")

    # ---------------------------
    # Utility Methods
    # ---------------------------

    def count_sessions(self) -> dict[str, int]:
        """Get counts of sessions by type.

        Returns
        -------
        Dict[str, int]
            Dictionary with counts of total, parent, and child sessions
        """
        with self.lock:
            total = len(self._sessions)
            children = sum(
                1
                for s in self._sessions.values()
                if hasattr(s, "is_child") and s.is_child
            )
            parents = total - children
            return {
                "total": total,
                "parents": parents,
                "children": children,
            }

    def get_sessions_by_language(self, language: str) -> list["Session"]:
        """Get all sessions for a specific language.

        Parameters
        ----------
        language : str
            The language to filter by

        Returns
        -------
        List[Session]
            Sessions matching the specified language
        """
        with self.lock:
            return [s for s in self._sessions.values() if s.language == language]

    def __repr__(self) -> str:
        """Return string representation of the registry state."""
        with self.lock:
            counts = self.count_sessions()
            return (
                f"<SessionRegistry: {counts['total']} sessions "
                f"({counts['parents']} parents, {counts['children']} children)>"
            )
