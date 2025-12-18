"""Refactored core session implementation with focused components."""

import asyncio
import uuid
from typing import TYPE_CHECKING, Any, Union

if TYPE_CHECKING:
    from collections.abc import Callable

from aidb.common.errors import AidbError
from aidb.dap.client import DAPClient
from aidb.dap.client.public_events import StubPublicEventAPI
from aidb.dap.protocol.types import Capabilities
from aidb.models import (
    AidbBreakpoint,
    SessionInfo,
    SessionStatus,
    StartRequestType,
)
from aidb.patterns import Obj
from aidb_common.path import normalize_path

from .capabilities import CapabilityChecker
from .connector import SessionConnector
from .registry import SessionRegistry
from .resource import ResourceManager
from .session_breakpoints import SessionBreakpointsMixin
from .session_lifecycle import SessionLifecycleMixin
from .session_relationships import SessionRelationshipsMixin
from .state import SessionState

if TYPE_CHECKING:
    from aidb.dap.client.public_events import PublicEventAPI
    from aidb.dap.protocol.base import Request
    from aidb.interfaces.context import IContext


class Session(
    Obj,
    SessionBreakpointsMixin,
    SessionLifecycleMixin,
    SessionRelationshipsMixin,
):
    """Refactored core debug session implementation.

    This class is now a thin orchestration layer that delegates to focused
    components:
    - SessionState: Status and error management
    - SessionConnector: DAP connection management
    - CapabilityChecker: Capability checking
    - ResourceManager: Resource management
    - Mixins: Lifecycle, breakpoints, relationships
    """

    def __init__(
        self,
        ctx: "IContext",
        target: str,
        language: str,
        breakpoints: list[AidbBreakpoint] | None = None,
        adapter_host: str = "localhost",
        adapter_port: int | None = None,
        target_host: str = "localhost",
        target_port: int | None = None,
        args: list[str] | None = None,
        parent_session_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize a new debug session.

        Parameters
        ----------
        ctx : IContext
            Context object for logging and configuration
        target : str
            Target to debug (file path, process name, etc.)
        language : str
            Programming language of the target
        breakpoints : List[AidbBreakpoint], optional
            Initial breakpoints to set
        adapter_host : str, optional
            Host where the debug adapter server runs
        adapter_port : int, optional
            Port where the debug adapter server listens
        target_host : str, optional
            Host where the target process being debugged runs
        target_port : int, optional
            Port for target process communication if needed
        args : List[str], optional
            Command-line arguments for the debug session
        parent_session_id : str, optional
            ID of parent session if this is a child session
        ``**kwargs`` : Any
            Additional arguments for session initialization
        """
        super().__init__(ctx=ctx)
        self._id = str(uuid.uuid4())
        self.started = False

        # Parent-child relationship fields FIRST (needed by is_child property)
        self.parent_session_id = parent_session_id
        self.child_session_ids: list[str] = []

        # Initial breakpoints
        self.breakpoints = breakpoints or []
        bp_count = len(breakpoints or [])
        self.ctx.debug(
            f"Session.__init__: Received {bp_count} initial breakpoint(s) "
            f"for {language} session",
        )

        # Core attributes
        # Apply identifier vs file path heuristic using TargetClassifier
        if target:
            from aidb.adapters.base.target_classifier import TargetClassifier

            if TargetClassifier.is_file_path(target):
                self.target = normalize_path(target)
            else:
                # It's an identifier (class name, module, etc.) - keep as-is
                self.target = target
        else:
            self.target = target
        self.language = language
        self.adapter_host = adapter_host
        self.adapter_port = adapter_port
        self.target_host = target_host
        self.target_port = target_port
        self.args = args or []
        self.adapter_kwargs = kwargs

        # Extract start_request_type if provided
        self.start_request_type = kwargs.pop(
            "start_request_type",
            StartRequestType.LAUNCH,
        )

        # Extract on_child_created_callback if provided
        self._on_child_created_callback: Callable[[Any], None] | None = kwargs.pop(
            "on_child_created_callback",
            None,
        )

        # Child session specific attributes
        self._pending_target_id: str | None = None
        self._adapter_process: Any | None = None

        # Store raw DAP capabilities from adapter
        self._adapter_capabilities: Capabilities | None = None
        self._breakpoint_store: dict[int, AidbBreakpoint] = {}
        self._breakpoint_store_lock = asyncio.Lock()
        self._breakpoint_update_tasks: set[asyncio.Task] = set()
        self._launch_config: dict[str, Any] | None = None
        self._launch_args_override: dict[str, Any] | None = None

        # Event subscription and rebind tracking
        self._event_subscriptions: dict[str, Any] = {}
        self._last_rebind_times: dict[str, float] = {}

        # Initialize registry early (needed by connector)
        self.registry = SessionRegistry(ctx=self.ctx)

        # Initialize components
        self.state = SessionState(self, ctx=self.ctx)
        self.connector = SessionConnector(self, ctx=self.ctx)

        # These components access session attributes, so initialize after core
        # attributes are set
        self.resource = ResourceManager(session=self, ctx=self.ctx)
        self.capability_checker = CapabilityChecker(self)

        # Register this session
        self.registry.register_session(self)

        try:
            self._set_port()
            self._get_adapter()

            if not self.is_child:
                # Create stub events API - DAP client setup happens in start()
                self.connector.create_stub_events_api()

            # Initial breakpoints will be set after connection in start()
        except Exception as e:
            self.state.set_error(e)
            self.ctx.error(f"Failed to initialize session: {e}")
            # Unregister if initialization fails
            self.registry.unregister_session(self.id)
            msg = f"Session initialization failed: {e}"
            raise AidbError(msg) from e

        self.ctx.debug(f"Created new session with ID: {self.id}")

    def __repr__(self) -> str:
        """Return string representation of the session."""
        return (
            f"{self.__class__.__name__}(id={self.id}, target={self.target}, "
            f"language={self.language}, status={self.status.name})"
        )

    # ---------------------------
    # Core Properties (Delegated)
    # ---------------------------

    @property
    def id(self) -> str:
        """Get the unique session identifier."""
        return self._id

    @property
    def status(self) -> SessionStatus:
        """Get the current session status."""
        return self.state.get_status()

    @property
    def info(self) -> SessionInfo:
        """Get comprehensive session information."""
        return SessionInfo(
            id=self.id,
            target=self.target,
            language=self.language,
            status=self.status,
            host=self.adapter_host,
            port=self.adapter_port or 0,
        )

    def is_paused(self) -> bool:
        """Check if the session is currently paused at a breakpoint or step.

        This is the recommended method for checking session pause state. It checks
        the high-level session status which is updated when the session receives
        stopped events from the debug adapter.

        For low-level DAP client state checking (e.g., during initialization when
        child sessions may stop before full session setup), use ``is_dap_stopped()``.

        Returns
        -------
        bool
            True if the session is in PAUSED status, False otherwise
        """
        return self.state.is_paused()

    # ---------------------------
    # DAP Client Access
    # ---------------------------

    @property
    def dap(self) -> DAPClient:
        """Get the appropriate DAP client for debug operations."""
        return self.connector.get_dap_client()

    @dap.setter
    def dap(self, value: DAPClient | None) -> None:
        """Set the DAP client."""
        self.connector.set_dap_client(value)

    @property
    def events(self) -> Union["PublicEventAPI", StubPublicEventAPI]:
        """Get the public event subscription API."""
        return self.connector.get_events_api()

    def is_dap_stopped(self) -> bool:
        """Check if the DAP client reports stopped state (low-level).

        This checks the low-level DAP event processor state directly, which may
        differ from the high-level session status during initialization or
        teardown. Use this when you need to check the raw DAP state, such as:
        - JavaScript child sessions that stop before full initialization
        - Detecting stopped state during complex session transitions

        For most use cases, prefer ``is_paused()`` which checks the high-level
        session status.

        Returns
        -------
        bool
            True if DAP client reports stopped/paused state, False otherwise
        """
        try:
            return (
                hasattr(self, "connector")
                and self.connector
                and self.connector.has_dap_client()
                and self.dap.is_stopped
            )
        except Exception:
            return False

    # ---------------------------
    # Location Tracking
    # ---------------------------

    def get_current_location(self) -> tuple[str | None, int | None]:
        """Get the current execution location from DAP state.

        Returns the current file and line from the DAP event processor state.
        This provides a fast, cached view of the current location without
        making DAP requests.

        Returns
        -------
        tuple[str | None, int | None]
            (current_file, current_line) from DAP state, or (None, None)
            if not available
        """
        try:
            if (
                hasattr(self, "connector")
                and self.connector
                and self.connector.has_dap_client()
                and hasattr(self.dap, "_event_processor")
                and hasattr(self.dap._event_processor, "_state")
            ):
                state = self.dap._event_processor._state
                return state.current_file, state.current_line
        except Exception as e:
            self.ctx.debug(f"Could not get current location: {e}")
        return None, None

    # ---------------------------
    # Capability Management (Delegated)
    # ---------------------------

    def store_capabilities(self, capabilities: Capabilities) -> None:
        """Store the capabilities received from the debug adapter."""
        self._adapter_capabilities = capabilities
        self.ctx.debug(f"Stored adapter capabilities for session {self.id}")

    def get_capabilities(self) -> Capabilities | None:
        """Get the raw DAP capabilities from the adapter.

        Returns
        -------
        Optional[Capabilities]
            The adapter's DAP capabilities if available, None otherwise.
        """
        return self._adapter_capabilities

    @property
    def adapter_capabilities(self) -> Capabilities | None:
        """Direct access to raw adapter capabilities.

        Returns
        -------
        Optional[Capabilities]
            The adapter's DAP capabilities if available, None otherwise.
        """
        return self._adapter_capabilities

    def has_capability(self, capability_attr: str) -> bool:
        """Check if a specific capability is supported.

        Parameters
        ----------
        capability_attr : str
            The DAP capability attribute name (e.g., 'supportsConditionalBreakpoints')

        Returns
        -------
        bool
            True if the capability is supported, False otherwise.
        """
        if not self._adapter_capabilities:
            self.ctx.debug(
                f"No capabilities stored yet for session {self.id}, "
                f"checking for {capability_attr}",
            )
            return False
        return getattr(self._adapter_capabilities, capability_attr, False) is True

    # All supports_* methods now delegate to CapabilityChecker
    def supports_conditional_breakpoints(self) -> bool:
        """Check if conditional breakpoints are supported."""
        return self.capability_checker.supports_conditional_breakpoints()

    def supports_data_breakpoints(self) -> bool:
        """Check if data/watchpoint breakpoints are supported."""
        return self.capability_checker.supports_data_breakpoints()

    def supports_evaluate(self) -> bool:
        """Check if evaluate is supported (baseline - always True)."""
        return self.capability_checker.supports_evaluate()

    def supports_exception_info(self) -> bool:
        """Check if exception information requests are supported."""
        return self.capability_checker.supports_exception_info()

    def supports_function_breakpoints(self) -> bool:
        """Check if function breakpoints are supported."""
        return self.capability_checker.supports_function_breakpoints()

    def supports_goto(self) -> bool:
        """Check if jumping to locations is supported."""
        return self.capability_checker.supports_goto()

    def supports_hit_conditional_breakpoints(self) -> bool:
        """Check if hit count conditional breakpoints are supported."""
        return self.capability_checker.supports_hit_conditional_breakpoints()

    def supports_logpoints(self) -> bool:
        """Check if logpoints (non-breaking diagnostics) are supported."""
        return self.capability_checker.supports_logpoints()

    def supports_modules(self) -> bool:
        """Check if module inspection is supported."""
        return self.capability_checker.supports_modules()

    def supports_restart(self) -> bool:
        """Check if session restart is supported."""
        return self.capability_checker.supports_restart()

    def supports_set_expression(self) -> bool:
        """Check if set expression (complex assignments) is supported."""
        return self.capability_checker.supports_set_expression()

    def supports_set_variable(self) -> bool:
        """Check if variable modification is supported."""
        return self.capability_checker.supports_set_variable()

    def supports_step_back(self) -> bool:
        """Check if stepping backwards is supported."""
        return self.capability_checker.supports_step_back()

    def supports_terminate(self) -> bool:
        """Check if terminate request is supported."""
        return self.capability_checker.supports_terminate()

    # ---------------------------
    # Internal Setup Methods (Delegated)
    # ---------------------------

    def _set_port(self) -> None:
        """Set the port for the debug adapter server."""
        from aidb.resources.ports import PortRegistry

        try:
            self.ctx.debug(f"Port setup for language {self.language}")
            self.ctx.debug(f"Current adapter_port = {self.adapter_port}")

            registry = PortRegistry(session_id=self.id, ctx=self.ctx)

            if self.adapter_port is None:
                import asyncio

                try:
                    asyncio.get_running_loop()
                    self.ctx.debug("Deferring port acquisition to async start phase")
                    self.adapter_port = None
                except RuntimeError:
                    # Get adapter config for port settings
                    from aidb.session.adapter_registry import AdapterRegistry

                    adapter_registry = AdapterRegistry(ctx=self.ctx)
                    adapter_config = adapter_registry[self.language]

                    self.adapter_port = asyncio.run(
                        registry.acquire_port(
                            self.language,
                            default_port=adapter_config.default_dap_port,
                            fallback_ranges=adapter_config.fallback_port_ranges,
                        ),
                    )
                if self.adapter_port:
                    self.ctx.debug(f"Acquired port {self.adapter_port}")
            else:
                self.ctx.debug(f"Using existing port {self.adapter_port}")

        except Exception as e:
            self.ctx.error(f"Failed to set port: {e}")
            raise

    def _get_adapter(self) -> None:
        """Get the appropriate debug adapter for the session's language."""
        from aidb.session.adapter_registry import AdapterRegistry

        try:
            adapter_registry = AdapterRegistry(ctx=self.ctx)
            adapter_class = adapter_registry.get_adapter_class(self.language)
            adapter_config = adapter_registry.get_adapter_config(self.language)

            # Instantiate the adapter
            self.adapter = adapter_class(
                session=self,
                ctx=self.ctx,
                config=adapter_config,
                **self.adapter_kwargs,
            )

            # Propagate start_request_type to adapter config for initialization sequence
            self.adapter.config.dap_start_request_type = self.start_request_type
            self.ctx.debug(
                f"Got adapter for language {self.language}: {self.adapter} "
                f"(mode={self.start_request_type.value})",
            )
        except Exception as e:
            self.ctx.error(f"Failed to get adapter for language {self.language}: {e}")
            raise

    def _setup_dap_client(self) -> None:
        """Set up the DAP client for this session."""
        if self.adapter_port is None:
            msg = "adapter_port must be set before creating DAP client"
            raise ValueError(msg)

        # Delegate to connector
        self.connector.setup_dap_client(self.adapter_host, self.adapter_port)

    def _create_stub_events_api(self) -> None:
        """Create a stub events API for deferred sessions."""
        self.connector.create_stub_events_api()
        # Keep reference for compatibility
        self._stub_events = self.connector._stub_events
        self._pending_subscriptions = self.connector._pending_subscriptions

    async def _setup_child_dap_client(
        self,
        adapter_host: str,
        adapter_port: int,
    ) -> None:
        """Set up DAP client for a child session."""
        await self.connector.setup_child_dap_client(adapter_host, adapter_port)

    # ---------------------------
    # Public API Facade Methods
    # ---------------------------

    async def request(self, command: str, arguments: dict | None = None) -> Any:
        """Send a DAP request with command and arguments."""
        from aidb.dap.protocol.base import Request

        if not self.connector.has_dap_client():
            msg = f"Session {self.id} has no DAP client available"
            raise RuntimeError(msg)

        request = Request(seq=0, command=command, arguments=arguments or {})
        return await self.dap.send_request(request)

    async def send_request(self, request: "Request") -> Any:
        """Send a DAP request object."""
        if not self.connector.has_dap_client():
            msg = f"Session {self.id} has no DAP client available"
            raise RuntimeError(msg)

        return await self.dap.send_request(request)

    def get_output(self, clear: bool = True) -> list[dict[str, Any]]:
        """Get collected program output (logpoints, stdout, stderr).

        This method provides proper encapsulation of the DAP client's output
        buffer. Output is collected from DAP output events during program
        execution. Logpoint messages appear with category "console".

        Parameters
        ----------
        clear : bool
            If True (default), clears the buffer after retrieval to avoid
            returning duplicate output on subsequent calls.

        Returns
        -------
        list[dict[str, Any]]
            List of output entries, each with:
            - category: "console" (logpoints), "stdout", "stderr", etc.
            - output: The output text
            - timestamp: Unix timestamp when output was received
        """
        return self.connector.get_output(clear=clear)
