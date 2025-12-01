"""Child session management for parent-child debugging relationships.

This module handles the management of parent-child session relationships, which are used
for multi-phase debugging scenarios (e.g., vscode-js-debug).
"""

from typing import TYPE_CHECKING, Optional

from aidb.models import SessionStatus
from aidb.patterns import Obj

if TYPE_CHECKING:
    from aidb.interfaces.context import IContext
    from aidb.session import Session


class ChildSessionRegistry(Obj):
    """Manages parent-child session relationships registry.

    This class handles:
        - Registration of parent-child relationships
        - Tracking active child sessions
        - Resolving the appropriate session for operations
        - Child session lookups and management

    Attributes
    ----------
    _parent_child_map : Dict[str, List[str]]
        Maps parent session IDs to lists of child session IDs
    _active_child_map : Dict[str, str]
        Maps parent session IDs to their active child session ID
    """

    def __init__(self, ctx: Optional["IContext"] = None):
        """Initialize the child session manager.

        Parameters
        ----------
        ctx : IContext, optional
            Context for logging
        """
        super().__init__(ctx)
        self._parent_child_map: dict[str, list[str]] = {}
        self._active_child_map: dict[str, str] = {}
        self._last_resolution: tuple[str, str] | None = None

    def register_parent_child(self, parent_id: str, child_id: str) -> None:
        """Register a parent-child relationship between sessions.

        Parameters
        ----------
        parent_id : str
            The parent session ID
        child_id : str
            The child session ID
        """
        if parent_id not in self._parent_child_map:
            self._parent_child_map[parent_id] = []
        self._parent_child_map[parent_id].append(child_id)
        self.ctx.info(f"Registered child session {child_id} under parent {parent_id}")

    def get_children(
        self,
        parent_id: str,
        sessions: dict[str, "Session"],
    ) -> list["Session"]:
        """Get all child sessions of a parent.

        Parameters
        ----------
        parent_id : str
            The parent session ID
        sessions : Dict[str, Session]
            All registered sessions

        Returns
        -------
        List[Session]
            List of child sessions (empty if none)
        """
        child_ids = self._parent_child_map.get(parent_id, [])
        children = []
        for child_id in child_ids:
            child = sessions.get(child_id)
            if child:
                children.append(child)
        return children

    def set_active_child(self, parent_id: str, child_id: str) -> None:
        """Set the active child session for a parent.

        This is critical for JavaScript debugging after startDebugging creates a
        child. All subsequent DAP operations should go to the child, not the
        parent.

        Parameters
        ----------
        parent_id : str
            The parent session ID
        child_id : str
            The child session ID to make active
        """
        self._active_child_map[parent_id] = child_id
        self.ctx.debug(f"Set active child for parent {parent_id} to child {child_id}")

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
        return self._active_child_map.get(parent_id)

    def resolve_active_session(
        self,
        session: "Session",
        sessions: dict[str, "Session"],
    ) -> "Session":
        """Resolve the active session for operations.

        For languages with child sessions (e.g., JavaScript), returns the active
        child if available, otherwise returns the parent session.

        Parameters
        ----------
        session : Session
            The parent/root session
        sessions : Dict[str, Session]
            All registered sessions

        Returns
        -------
        Session
            The active session (child if available, otherwise parent)
        """
        active_child_id = self._active_child_map.get(session.id)
        # Only log when resolution changes (avoid spam from repeated lookups)
        if active_child_id:
            active_child = sessions.get(active_child_id)
            if active_child:
                # Only log if this is a new resolution or changed
                cache_key = (session.id, active_child_id)
                cache_miss = (
                    not hasattr(self, "_last_resolution")
                    or self._last_resolution != cache_key
                )
                if cache_miss:
                    self.ctx.debug(
                        f"Resolved {session.id} -> child {active_child_id}",
                    )
                    self._last_resolution = cache_key
                return active_child
            self.ctx.warning(
                f"Active child {active_child_id} not found in sessions registry",
            )
        return session

    def get_active_session_for_language(
        self,
        language: str,
        sessions: dict[str, "Session"],
    ) -> Optional["Session"]:
        """Get the active session for a language, considering child sessions.

        For languages that use child sessions (e.g., JavaScript), returns the
        child session if available and paused, otherwise returns the parent.

        Parameters
        ----------
        language : str
            The language to find a session for
        sessions : Dict[str, Session]
            All registered sessions

        Returns
        -------
        Session or None
            The most appropriate active session for the language
        """
        for session in sessions.values():
            if session.language == language:
                # Check if there's an explicitly set active child
                if session.id in self._active_child_map:
                    active_child_id = self._active_child_map[session.id]
                    active_child = sessions.get(active_child_id)
                    if active_child:
                        self.ctx.debug(
                            f"Using active child session "
                            f"{active_child_id} for {language}",
                        )
                        return active_child

                # If this session has children, prefer an active child
                if session.id in self._parent_child_map:
                    for child_id in self._parent_child_map[session.id]:
                        child = sessions.get(child_id)
                        if child and child.status == SessionStatus.PAUSED:
                            self.ctx.debug(
                                f"Found active child session {child_id} for {language}",
                            )
                            return child
                # Return parent if no active children
                return session
        return None

    def get_child_ids(self, parent_id: str) -> list[str]:
        """Get all child session IDs for a parent.

        Parameters
        ----------
        parent_id : str
            The parent session ID

        Returns
        -------
        List[str]
            List of child session IDs (empty if none)
        """
        return self._parent_child_map.get(parent_id, [])

    def has_children(self, parent_id: str) -> bool:
        """Check if a session has any child sessions.

        Parameters
        ----------
        parent_id : str
            The parent session ID

        Returns
        -------
        bool
            True if the session has children, False otherwise
        """
        return (
            parent_id in self._parent_child_map
            and len(self._parent_child_map[parent_id]) > 0
        )

    def remove_parent_child_mapping(self, parent_id: str) -> None:
        """Remove parent-child mapping for a session.

        Parameters
        ----------
        parent_id : str
            The parent session ID
        """
        if parent_id in self._parent_child_map:
            del self._parent_child_map[parent_id]
        if parent_id in self._active_child_map:
            del self._active_child_map[parent_id]

    def clear(self) -> None:
        """Clear all parent-child mappings."""
        self._parent_child_map.clear()
        self._active_child_map.clear()
