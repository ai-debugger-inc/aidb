"""DAP client protocol interfaces."""

from typing import TYPE_CHECKING, Optional, Protocol

if TYPE_CHECKING:
    from aidb.dap.protocol import Event, Request, Response


class IDAPClient(Protocol):
    """Protocol interface for DAP client.

    This interface allows components to interact with the DAP client without importing
    the concrete implementation.
    """

    @property
    def is_connected(self) -> bool:
        """Check if connected to DAP adapter."""
        ...

    async def connect(self, host: str, port: int) -> None:
        """Connect to DAP adapter."""
        ...

    async def disconnect(self) -> None:
        """Disconnect from DAP adapter."""
        ...

    async def send_request(
        self,
        request: "Request",
        timeout: float | None = None,
    ) -> "Response":
        """Send a request and wait for response."""
        ...

    def send_event(self, event: "Event") -> None:
        """Send an event (no response expected)."""
        ...

    async def wait_for_event(
        self,
        event_type: str,
        timeout: float | None = None,
    ) -> Optional["Event"]:
        """Wait for a specific event type."""
        ...
