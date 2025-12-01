"""Session cleanup management for proper resource deallocation.

This module handles the cleanup of sessions and their resources, ensuring proper
termination and resource release.
"""

from typing import TYPE_CHECKING, Optional

from aidb.patterns import Obj

if TYPE_CHECKING:
    from aidb.interfaces.context import IContext
    from aidb.session import Session
    from aidb.session.child_registry import ChildSessionRegistry


class SessionCleanupManager(Obj):
    """Manages cleanup operations for debug sessions.

    This class handles:
        - Cleanup of individual sessions and their children
        - Cleanup of all sessions during shutdown
        - Proper resource deallocation
        - Error handling during cleanup

    Attributes
    ----------
    ctx : IContext
        Context for logging
    """

    def __init__(self, ctx: Optional["IContext"] = None):
        """Initialize the cleanup manager.

        Parameters
        ----------
        ctx : IContext, optional
            Context for logging
        """
        super().__init__(ctx)

    async def cleanup_session(
        self,
        session_id: str,
        sessions: dict[str, "Session"],
        child_manager: "ChildSessionRegistry",
    ) -> None:
        """Clean up a session and all its children.

        This method:
            1. Stops all child sessions first
            2. Removes child sessions from registry
            3. Cleans up parent-child mappings
            4. Removes the session itself

        Parameters
        ----------
        session_id : str
            The session ID to clean up
        sessions : Dict[str, Session]
            All registered sessions
        child_manager : ChildSessionManager
            Manager for parent-child relationships
        """
        # Clean up children first
        child_ids = child_manager.get_child_ids(session_id)
        if child_ids:
            self.ctx.debug(
                f"Cleaning up {len(child_ids)} child sessions for {session_id}",
            )
            # Copy list to avoid modification during iteration
            for child_id in child_ids[:]:
                child = sessions.get(child_id)
                if child:
                    try:
                        self.ctx.debug(f"Stopping child session {child_id}")
                        await child.destroy()
                    except Exception as e:
                        self.ctx.error(f"Error stopping child session {child_id}: {e}")
                    finally:
                        # Remove from registry
                        if child_id in sessions:
                            del sessions[child_id]

            # Remove parent-child mapping
            child_manager.remove_parent_child_mapping(session_id)

        # Clean up the session itself
        if session_id in sessions:
            session = sessions[session_id]
            try:
                self.ctx.debug(f"Stopping session {session_id}")
                await session.destroy()
            except Exception as e:
                self.ctx.error(f"Error stopping session {session_id}: {e}")
            finally:
                del sessions[session_id]

    async def cleanup_all(
        self,
        sessions: dict[str, "Session"],
        child_manager: "ChildSessionRegistry",
    ) -> None:
        """Clean up all sessions in the registry.

        This is typically called during shutdown to ensure all debug sessions
        are properly terminated.

        Parameters
        ----------
        sessions : Dict[str, Session]
            All registered sessions
        child_manager : ChildSessionManager
            Manager for parent-child relationships
        """
        # Get all parent sessions (those without a parent)
        parent_sessions = []
        for session_id, session in sessions.items():
            if (
                not hasattr(session, "parent_session_id")
                or session.parent_session_id is None
            ):
                parent_sessions.append(session_id)

        # Clean up parent sessions (which will clean up their children)
        for parent_id in parent_sessions:
            try:
                await self.cleanup_session(parent_id, sessions, child_manager)
            except Exception as e:
                self.ctx.error(f"Error during cleanup of session {parent_id}: {e}")

        # Clean up any remaining orphaned sessions
        remaining = list(sessions.keys())
        for session_id in remaining:
            try:
                await self.cleanup_session(session_id, sessions, child_manager)
            except Exception as e:
                self.ctx.error(
                    f"Error during cleanup of orphaned session {session_id}: {e}",
                )

        # Clear all mappings
        sessions.clear()
        child_manager.clear()
        self.ctx.debug("Session cleanup completed")

    async def cleanup_orphaned_children(
        self,
        sessions: dict[str, "Session"],
        child_manager: "ChildSessionRegistry",
    ) -> None:
        """Clean up orphaned child sessions.

        This method finds and cleans up child sessions whose parent
        no longer exists in the registry.

        Parameters
        ----------
        sessions : Dict[str, Session]
            All registered sessions
        child_manager : ChildSessionManager
            Manager for parent-child relationships
        """
        orphaned = []
        for session_id, session in sessions.items():
            if (
                hasattr(session, "parent_session_id")
                and session.parent_session_id
                and session.parent_session_id not in sessions
            ):
                # Check if parent exists
                orphaned.append(session_id)

        for orphan_id in orphaned:
            self.ctx.warning(f"Cleaning up orphaned child session {orphan_id}")
            try:
                await self.cleanup_session(orphan_id, sessions, child_manager)
            except Exception as e:
                self.ctx.error(f"Error cleaning up orphaned session {orphan_id}: {e}")

    def get_cleanup_order(
        self,
        sessions: dict[str, "Session"],
        child_manager: "ChildSessionRegistry",
    ) -> list[str]:
        """Get the optimal order for cleaning up sessions.

        Returns a list of session IDs in the order they should be
        cleaned up, with children before parents.

        Parameters
        ----------
        sessions : Dict[str, Session]
            All registered sessions
        child_manager : ChildSessionManager
            Manager for parent-child relationships

        Returns
        -------
        List[str]
            Session IDs in cleanup order
        """
        cleanup_order = []
        visited = set()

        def visit(session_id: str) -> None:
            if session_id in visited:
                return
            visited.add(session_id)

            # Visit children first
            for child_id in child_manager.get_child_ids(session_id):
                if child_id in sessions:
                    visit(child_id)

            cleanup_order.append(session_id)

        # Visit all sessions
        for session_id in sessions:
            visit(session_id)

        return cleanup_order
