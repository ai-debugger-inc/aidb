"""Parent-child session relationship management."""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Optional, cast

if TYPE_CHECKING:
    from aidb.interfaces import IContext
    from aidb.session import Session
from aidb.common.errors import AidbError
from aidb.models import SessionInfo
from aidb.session.registry import SessionRegistry


class SessionRelationshipsMixin:
    """Mixin for managing parent-child session relationships."""

    # Type hints for attributes from main Session class
    ctx: "IContext"
    parent_session_id: str | None
    child_session_ids: list[str]
    registry: Any
    language: str
    target: str
    adapter_kwargs: dict[str, Any]

    @property
    def is_child(self) -> bool:
        """Check if this is a child session.

        Returns
        -------
        bool
            True if this session has a parent session ID
        """
        return self.parent_session_id is not None

    async def create_child(
        self,
        config: dict[str, Any],
        on_child_created_callback: Callable[["Session"], None] | None = None,
    ) -> "Session":
        """Create a child debug session.

        Creates a new child session that inherits configuration from this
        parent session but can have its own debug context (e.g., for debugging
        a subprocess or new thread).

        Parameters
        ----------
        config : Dict[str, Any]
            Configuration for the child session, should include:
            - target_id: The target ID from the DAP process event
            - adapter specific configuration
        on_child_created_callback : Callable[[Session], None], optional
            Optional callback invoked immediately after child DAP initialization
            completes. Receives the child session as an argument.

        Returns
        -------
        Session
            The newly created child session

        Raises
        ------
        AidbError
            If child session creation fails
        """
        try:
            # Import here to avoid circular dependency
            from aidb.session.child_manager import ChildSessionManager

            # Create manager with context, optional event bridge, and callback
            manager = ChildSessionManager(
                ctx=self.ctx,
                event_bridge=None,
                on_child_created_callback=on_child_created_callback,
            )
            # create_child_session returns the child ID, not the session object
            # Cast self to Session since that's what the method expects
            child_session_id = await manager.create_child_session(
                cast("Session", self),
                config,
            )

            # Track the child session ID
            self.child_session_ids.append(child_session_id)

            self.ctx.debug(f"Parent session created child session {child_session_id}")

            # Get the actual child session from the registry
            registry = SessionRegistry(ctx=self.ctx)
            child_session = registry.get_session(child_session_id)
            if not child_session:
                msg = f"Failed to get child session {child_session_id}"
                raise RuntimeError(msg)

            return child_session

        except Exception as e:
            self.ctx.error(f"Failed to create child session: {e}")
            msg = f"Child session creation failed: {e}"
            raise AidbError(msg) from e

    async def _handle_child_session_request(self, config: dict[str, Any]) -> str:
        """Handle a request to create a child session.

        This is called when a DAP process event indicates a new debuggable
        process has been spawned.

        Parameters
        ----------
        config : Dict[str, Any]
            Configuration from the process event

        Returns
        -------
        str
            The ID of the created child session
        """
        self.ctx.debug(f"Handling child session request with config: {config}")

        # Get callback from session if available
        callback = getattr(self, "_on_child_created_callback", None)

        # Create the child session with optional callback
        child = await self.create_child(config, on_child_created_callback=callback)

        # Return the child session ID
        return child.id

    def get_child_sessions(self) -> list[SessionInfo]:
        """Get information about all child sessions.

        Returns
        -------
        List[SessionInfo]
            List of SessionInfo objects for all child sessions
        """
        child_infos = []
        for child_id in self.child_session_ids:
            child = self.registry.get_session(child_id)
            if child:
                child_infos.append(child.info())
        return child_infos

    def get_parent_session(self) -> Optional["Session"]:
        """Get the parent session if this is a child session.

        Returns
        -------
        Optional[Session]
            The parent session or None if this is not a child session
        """
        if not self.is_child or not self.parent_session_id:
            return None
        return self.registry.get_session(self.parent_session_id)
