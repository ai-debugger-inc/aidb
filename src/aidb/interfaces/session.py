"""Session protocol interfaces."""

from typing import TYPE_CHECKING, Any, Optional, Protocol

if TYPE_CHECKING:
    from aidb.common import AidbContext
    from aidb.dap.protocol.types import Capabilities
    from aidb.interfaces.dap import IDAPClient
    from aidb.models import SessionInfo
    from aidb.models import SessionStatus as SessionState


class ISession(Protocol):
    """Protocol interface for debug sessions.

    This interface allows adapters to reference session functionality without creating
    circular dependencies.
    """

    # Core properties
    id: str
    language: str
    adapter_type: str
    state: "SessionState"
    capabilities: Optional["Capabilities"]
    target: str
    adapter_port: int | None
    parent_session_id: str | None
    child_session_ids: list[str]
    breakpoints: list[Any]
    adapter: Any
    dap: "IDAPClient"
    debug: Any
    _pending_target_id: str | None
    _adapter_process: Any
    _launch_args_override: dict[str, Any] | None

    # Context and resource management
    @property
    def ctx(self) -> "AidbContext":
        """Get the session context."""
        ...

    @property
    def resource(self) -> Optional["ISessionResource"]:
        """Get the session resource manager."""
        ...

    # Session info
    def get_session_info(self) -> "SessionInfo":
        """Get current session information."""
        ...

    # State management
    async def set_state(self, state: "SessionState") -> None:
        """Update session state."""
        ...

    # Capability management
    def set_capabilities(self, capabilities: "Capabilities") -> None:
        """Set adapter capabilities."""
        ...

    def has_capability(self, capability: str) -> bool:
        """Check if session has a capability."""
        ...

    def _setup_child_dap_client(self, *args: Any, **kwargs: Any) -> Any:
        """Set up child DAP client."""
        ...


class ISessionResource(Protocol):
    """Protocol interface for session resource management."""

    def register_process(self, proc: Any) -> None:
        """Register a process with the resource manager."""
        ...

    def register_port(self, port: int) -> None:
        """Register a port with the resource manager."""
        ...

    async def acquire_port(self, start_port: int = 0) -> int:
        """Acquire a port for the session."""
        ...

    def release_port(self, port: int) -> None:
        """Release a port back to the pool."""
        ...

    async def cleanup(self) -> None:
        """Clean up all registered resources."""
        ...
