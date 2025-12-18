"""Child session management for debug sessions.

This module provides functionality for creating and managing child debug sessions, used
by adapters that require multi-phase debugging through the DAP startDebugging reverse
request. Child sessions share their parent's DAP connection and adapter process.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast

from aidb.models import StartRequestType
from aidb.patterns import Obj
from aidb.session.event_bridge import EventBridge

if TYPE_CHECKING:
    from aidb.session import Session


class ChildSessionManager(Obj):
    """Manages the lifecycle of child debug sessions.

    This manager handles:
        - Creating child sessions from startDebugging requests
        - Setting up parent-child relationships
        - Managing child-specific DAP initialization
        - Coordinating with SessionRegistry
    """

    def __init__(
        self,
        ctx=None,
        event_bridge: EventBridge | None = None,
        on_child_created_callback: Callable[["Session"], None] | None = None,
    ):
        """Initialize the child session manager.

        Parameters
        ----------
        ctx : Context, optional
            The context for logging and debugging
        event_bridge : EventBridge, optional
            The event bridge for parent-child event synchronization. If not
            provided, a new one will be created.
        on_child_created_callback : Callable[[Session], None], optional
            Optional callback invoked immediately after child DAP initialization
            completes. Receives the child session as an argument. This allows
            external systems (e.g., MCP) to register event listeners before the
            child session hits any breakpoints.
        """
        super().__init__(ctx)

        from aidb.session.registry import SessionRegistry

        self.registry = SessionRegistry(ctx=self.ctx)

        # Initialize or use provided EventBridge
        self.event_bridge = event_bridge or EventBridge(ctx=self.ctx)

        # Store optional callback for child creation notification
        self._on_child_created_callback = on_child_created_callback

    async def create_child_session(
        self,
        parent: "Session",
        config: dict[str, Any],
    ) -> str:
        """Create a child debug session from a startDebugging request.

        Parameters
        ----------
        parent : Session
            The parent session requesting the child
        config : dict
            Configuration from the startDebugging reverse request, containing: -
            request: "launch" or "attach" - __pendingTargetId: Identifier for
            the child session - Other adapter-specific configuration

        Returns
        -------
        str
            The ID of the newly created child session

        Raises
        ------
        RuntimeError
            If child session creation fails
        """
        self.ctx.info(f"Creating child session for parent {parent.id}")
        self.ctx.debug(f"Child config keys: {list(config.keys())}")
        self.ctx.debug(
            f"Child __pendingTargetId: {config.get('__pendingTargetId', 'N/A')}",
        )

        # Extract key configuration and convert to enum
        request_str = config.get("request", "launch")
        start_request_type = (
            StartRequestType.ATTACH
            if request_str == "attach"
            else StartRequestType.LAUNCH
        )

        # Create child session with inherited configuration
        try:
            child = self._create_session_instance(parent, config)
            self._setup_parent_child_relationship(parent, child)
            self._register_with_registry(child, parent.id)

            await self.event_bridge.register_child(parent.id, child.id)
            self.ctx.debug(
                f"Registered child {child.id} with EventBridge for parent {parent.id}",
            )

            await self._start_child_session(child, start_request_type, config)

            self.ctx.info(f"Created child session {child.id} for parent {parent.id}")
            return child.id

        except Exception as e:
            self.ctx.error(f"Failed to create child session: {e}")
            msg = f"Child session creation failed: {e}"
            raise RuntimeError(msg) from e

    def _create_session_instance(
        self,
        parent: "Session",
        config: dict[str, Any],
    ) -> "Session":
        """Create the child Session instance with inherited configuration.

        Parameters
        ----------
        parent : Session
            The parent session
        config : dict
            Child session configuration

        Returns
        -------
        Session
            The newly created child session instance
        """
        from aidb.session import Session

        # Child inherits parent's target and language
        # For JavaScript, parent stores breakpoints in _pending_child_breakpoints
        # (parent sessions can't have breakpoints in vscode-js-debug)
        if hasattr(parent, "_pending_child_breakpoints"):
            breakpoints = parent._pending_child_breakpoints.copy()
        else:
            breakpoints = parent.breakpoints.copy() if parent.breakpoints else []

        child = Session(
            target=parent.target,
            language=parent.language,
            breakpoints=breakpoints,
            ctx=self.ctx,
            adapter_host=parent.adapter_host,
            adapter_port=parent.adapter_port,  # Share parent's adapter port
            parent_session_id=parent.id,  # Mark as child session
        )

        # Store the pending target ID from the startDebugging request
        if "__pendingTargetId" in config:
            child._pending_target_id = config["__pendingTargetId"]

        return child

    def _setup_parent_child_relationship(
        self,
        parent: "Session",
        child: "Session",
    ) -> None:
        """Set up the parent-child relationship between sessions.

        Parameters
        ----------
        parent : Session
            The parent session
        child : Session
            The child session
        """
        child.parent_session_id = parent.id
        parent.child_session_ids.append(child.id)

        self.ctx.info(
            f"Established parent-child relationship: {parent.id} -> {child.id}",
        )

    def _register_with_registry(self, child: "Session", parent_id: str) -> None:
        """Register the child session with the SessionRegistry.

        Parameters
        ----------
        child : Session
            The child session to register
        parent_id : str
            The parent session ID
        """
        self.registry.register_parent_child(parent_id, child.id)
        self.registry.set_active_child(parent_id, child.id)

    async def _start_child_session(
        self,
        child: "Session",
        start_request_type: StartRequestType,
        config: dict[str, Any],
    ) -> None:
        """Start the child session with appropriate DAP initialization.

        Parameters
        ----------
        child : Session
            The child session to start
        start_request_type : StartRequestType
            The type of start request (launch or attach)
        config : dict
            Configuration for the launch/attach request
        """
        if not child.parent_session_id:
            self.ctx.error(f"Child session {child.id} has no parent session ID")
            return

        # We've verified parent_session_id is not None above
        parent_id = cast("str", child.parent_session_id)
        parent = self.registry.get_session(parent_id)
        if not parent:
            # Debug: Check what sessions are registered
            all_sessions = self.registry.get_all_sessions()
            session_ids = [s.id for s in all_sessions]
            self.ctx.error(f"Registry has {len(all_sessions)} sessions: {session_ids}")
            self.ctx.error(f"Looking for parent: {parent_id}")
            msg = f"Parent session {parent_id} not found"
            raise RuntimeError(msg)

        # Use language-specific handler if available
        handler_method = f"_handle_{child.language}_child"
        self.ctx.info(
            f"Child language: {child.language}, looking for handler: {handler_method}",
        )
        if hasattr(self, handler_method):
            self.ctx.info(f"Found {handler_method}, calling it")
            getattr(self, handler_method)(child, parent, config)
        else:
            self.ctx.info(f"No specific handler for {child.language}, using default")
            # Default behavior for adapters without special handling
            self._handle_default_child(child, parent, config)

        # Perform child-specific DAP initialization
        await self._initialize_child_dap(child, start_request_type, config)

        # Mark child session as started after successful initialization
        child.state.set_initialized(True)
        child.started = True

        self.ctx.info(
            f"Started child session {child.id} with {start_request_type.value} request",
        )

    def _handle_default_child(
        self,
        child: "Session",
        parent: "Session",
        _config: dict[str, Any],
    ) -> None:
        """Handle default child session setup for most adapters.

        Most adapters share the parent's DAP connection and adapter process.

        Parameters
        ----------
        child : Session
            The child session being created
        parent : Session
            The parent session
        config : dict
            Configuration from startDebugging request
        """
        # Child sessions share parent's adapter process and DAP connection
        child._adapter_process = None
        # Child shares parent's adapter for status checks
        child.adapter = parent.adapter

        # Set up the reverse request callback for potential grandchildren
        if parent.connector._dap and parent.connector._dap._reverse_request_handler:
            parent.connector._dap.set_session_creation_callback(
                child._handle_child_session_request,
            )

    async def _initialize_child_dap(
        self,
        child: "Session",
        start_request_type: StartRequestType,
        config: dict[str, Any],
    ) -> None:
        """Initialize the child session's DAP connection.

        Parameters
        ----------
        child : Session
            The child session
        start_request_type : StartRequestType
            The type of start request (launch or attach)
        config : dict
            Configuration for initialization
        """
        self.ctx.info(
            f"Delegating child DAP initialization to {child.language} adapter",
        )
        # Ensure we have a non-None parent ID before registry lookup
        if child.parent_session_id is None:
            self.ctx.warning(
                f"Child session {child.id} has no parent_session_id; "
                "skipping child DAP initialization",
            )
            return
        parent_id_checked = cast("str", child.parent_session_id)
        parent = self.registry.get_session(parent_id_checked)
        if parent and parent.adapter:
            await parent.adapter.initialize_child_dap(child, start_request_type, config)
        else:
            self.ctx.warning(
                f"No parent adapter found for child session {child.id}, "
                "using default DAP sharing",
            )

        # Invoke callback immediately after child DAP initialization completes
        # This ensures external systems (e.g., MCP) can register event listeners
        # BEFORE the child hits any breakpoints
        if self._on_child_created_callback:
            self.ctx.info(
                f"Invoking on_child_created_callback for child session {child.id}",
            )
            try:
                self._on_child_created_callback(child)
                self.ctx.debug(
                    f"Successfully invoked on_child_created_callback for {child.id}",
                )
            except Exception as e:
                self.ctx.error(
                    f"Error in on_child_created_callback for {child.id}: {e}",
                )

    def _build_child_launch_args(
        self,
        child: "Session",
        config: dict[str, Any],
    ) -> dict[str, Any]:
        """Build launch arguments for child session.

        Parameters
        ----------
        child : Session
            The child session
        config : dict
            Configuration from startDebugging

        Returns
        -------
        dict
            Launch arguments for the child session
        """
        # Start with config from startDebugging
        launch_args = config.copy()

        # Ensure request type is set
        launch_args["request"] = "launch"

        # Let the adapter add language-specific configuration
        if hasattr(child, "adapter") and child.adapter:
            child.adapter.configure_child_launch(launch_args)

        return launch_args

    def _build_child_attach_args(
        self,
        _child: "Session",
        config: dict[str, Any],
    ) -> dict[str, Any]:
        """Build attach arguments for child session.

        Parameters
        ----------
        child : Session
            The child session
        config : dict
            Configuration from startDebugging

        Returns
        -------
        dict
            Attach arguments for the child session
        """
        # Start with config from startDebugging
        attach_args = config.copy()

        # Ensure request type is set
        attach_args["request"] = "attach"

        return attach_args
