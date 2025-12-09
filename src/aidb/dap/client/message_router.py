"""Message routing for DAP client.

This module handles incoming message dispatch to appropriate handlers.
"""

from typing import TYPE_CHECKING, Any, Optional

from aidb.common import AidbContext
from aidb.dap.protocol.base import Event
from aidb.patterns import Obj

from .constants import EventType

if TYPE_CHECKING:
    from aidb.interfaces import IContext

    from .events import EventProcessor
    from .request_handler import RequestHandler
    from .reverse_requests import ReverseRequestHandler


class MessageRouter(Obj):
    """Routes incoming DAP messages to appropriate handlers.

    This class handles:
    - Response message routing
    - Event message routing
    - Reverse request routing
    - Error handling for malformed messages
    """

    def __init__(
        self,
        ctx: Optional["IContext"] = None,
    ):
        """Initialize the message router.

        Parameters
        ----------
        ctx : IContext, optional
            Application context for logging
        """
        super().__init__(ctx or AidbContext())
        self._request_handler: RequestHandler | None = None
        self._event_processor: EventProcessor | None = None
        self._reverse_request_handler: ReverseRequestHandler | None = None

    def set_handlers(
        self,
        request_handler: Optional["RequestHandler"] = None,
        event_processor: Optional["EventProcessor"] = None,
        reverse_request_handler: Optional["ReverseRequestHandler"] = None,
    ) -> None:
        """Set handler references after initialization.

        Parameters
        ----------
        request_handler : RequestHandler, optional
            Handler for request/response processing
        event_processor : EventProcessor, optional
            Handler for event processing
        reverse_request_handler : ReverseRequestHandler, optional
            Handler for reverse requests from adapter
        """
        if request_handler:
            self._request_handler = request_handler
        if event_processor:
            self._event_processor = event_processor
        if reverse_request_handler:
            self._reverse_request_handler = reverse_request_handler

    async def process_message(self, message: dict[str, Any]) -> None:
        """Process a message received from the adapter.

        This is the main entry point called by the receiver thread for each message.
        Routes messages to appropriate handlers based on type.

        Parameters
        ----------
        message : dict
            The received message
        """
        msg_type = message.get("type")

        if msg_type == "response":
            await self._handle_response(message)
        elif msg_type == "event":
            self._handle_event(message)
        elif msg_type == "request":
            self._handle_reverse_request(message)
        else:
            self.ctx.warning(f"Unknown message type: {msg_type}")

    async def _handle_response(self, message: dict[str, Any]) -> None:
        """Handle a response message.

        Parameters
        ----------
        message : dict
            The response message
        """
        if not self._request_handler:
            self.ctx.error("No request handler available to process response")
            return

        await self._request_handler.handle_response(message)

    def _handle_event(self, message: dict[str, Any]) -> None:
        """Handle an event message.

        Parameters
        ----------
        message : dict
            The event message
        """
        if not self._event_processor:
            self.ctx.error("No event processor available to process event")
            return

        try:
            event = Event.from_dict(message)
            self._event_processor.process_event(event)

            # If the adapter reports termination, proactively clear any pending
            # requests so callers don't wait for full request timeouts.
            is_terminated = event.event == EventType.TERMINATED.value
            if is_terminated and self._request_handler is not None:
                try:
                    # Best effort: clear pending requests to return control quickly
                    # to any waiters instead of waiting on long timeouts.
                    # This does not close the transport; disconnect logic handles that.
                    import asyncio

                    asyncio.create_task(
                        self._request_handler.clear_all_pending_requests(),
                    )
                except Exception:
                    # Avoid raising from the router; termination should progress
                    pass

            # Note: Event forwarding to child sessions is handled via
            # subscription-based approach in EventBridge, not direct calls
        except Exception as e:
            self.ctx.error(f"Failed to process event: {e}")

    def _handle_reverse_request(self, message: dict[str, Any]) -> None:
        """Handle a reverse request from the adapter.

        Parameters
        ----------
        message : dict
            The reverse request message
        """
        if not self._reverse_request_handler:
            self.ctx.error("No reverse request handler available")
            return

        self._reverse_request_handler.handle_request(message)
