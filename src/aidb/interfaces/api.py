"""Interface definitions for API layer components."""

from typing import TYPE_CHECKING, Any, Optional, Protocol

from aidb.models import SessionInfo

if TYPE_CHECKING:
    from aidb.interfaces.session import ISession


class IDebugAPI(Protocol):
    """Interface for the main Debug API."""

    async def create_session(
        self,
        target: str,
        language: str,
        **kwargs: Any,
    ) -> "ISession":
        """Create a new debug session."""
        ...

    async def get_session(self, session_id: str) -> Optional["ISession"]:
        """Get a session by ID."""
        ...

    async def list_sessions(self) -> list[SessionInfo]:
        """List all active sessions."""
        ...

    async def stop_session(self, session_id: str) -> bool:
        """Stop a debug session."""
        ...


class ISessionManager(Protocol):
    """Interface for session lifecycle management."""

    def create_session(self, target: str, language: str, **kwargs: Any) -> "ISession":
        """Create and register a new session."""
        ...

    def get_session(self, session_id: str) -> Optional["ISession"]:
        """Retrieve a session by ID."""
        ...

    def destroy_session(self, session_id: str) -> bool:
        """Destroy and unregister a session."""
        ...

    @property
    def active_sessions_count(self) -> int:
        """Get count of active sessions."""
        ...


class IResourceManager(Protocol):
    """Interface for resource management."""

    def register_process(self, proc: Any, use_process_group: bool = True) -> int:
        """Register a process with the resource manager."""
        ...

    def unregister_process(self, pid: int) -> None:
        """Unregister a process."""
        ...

    async def acquire_port(
        self,
        language: str,
        session_id: str,
        preferred: int | None = None,
    ) -> int:
        """Acquire a port for debug adapter."""
        ...

    def release_port(self, port: int) -> None:
        """Release a port back to the pool."""
        ...

    async def cleanup_resources(self) -> None:
        """Clean up all resources for the session."""
        ...


class ISessionBuilder(Protocol):
    """Interface for session building and configuration."""

    def build_session(self, target: str, language: str, **kwargs: Any) -> "ISession":
        """Build a configured session."""
        ...

    def validate_configuration(self, language: str, config: dict[str, Any]) -> bool:
        """Validate session configuration."""
        ...
