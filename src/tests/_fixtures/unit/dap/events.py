"""Mock DAP event processor for unit tests.

Provides mock implementations of EventProcessor for testing components that depend on
event processing.
"""

import asyncio
from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock

import pytest

from aidb.dap.protocol.base import Event


@pytest.fixture
def mock_event_processor() -> MagicMock:
    """Create a mock DAP event processor.

    The mock simulates the EventProcessor interface for testing
    components that need event processing capabilities.

    Returns
    -------
    MagicMock
        Mock event processor with subscription and event methods
    """
    processor = MagicMock()

    # Subscription methods
    processor.subscribe = MagicMock()
    processor.unsubscribe = MagicMock()

    # Event processing
    processor.process_event = MagicMock()

    # Event storage
    processor._last_events = {}
    processor._last_stopped_event = None
    processor._last_initialized_event = None
    processor._breakpoint_events = []

    # One-time listeners
    processor._terminated_listeners = []
    processor._stopped_listeners = []

    return processor


class MockEventProcessor:
    """Event processor mock with configurable event delivery.

    Use this when you need to simulate event arrival and verify
    that handlers are called correctly.

    Examples
    --------
    >>> processor = MockEventProcessor()
    >>> handler = MagicMock()
    >>> processor.subscribe("stopped", handler)
    >>> processor.emit_stopped(thread_id=1)
    >>> handler.assert_called_once()
    """

    def __init__(self) -> None:
        """Initialize the mock processor."""
        self._listeners: dict[str, list[Callable[[Event], None]]] = {}
        self._last_events: dict[str, Event] = {}
        self._event_signals: dict[str, asyncio.Event] = {}

    def subscribe(self, event_type: str, handler: Callable[[Event], None]) -> None:
        """Subscribe to an event type."""
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Callable[[Event], None]) -> None:
        """Unsubscribe from an event type."""
        if event_type in self._listeners:
            self._listeners[event_type] = [
                h for h in self._listeners[event_type] if h != handler
            ]

    def process_event(self, event: Event) -> None:
        """Process an incoming event."""
        event_type = event.event
        self._last_events[event_type] = event

        # Notify listeners
        for handler in self._listeners.get(event_type, []):
            handler(event)

        # Signal event arrival
        if event_type in self._event_signals:
            self._event_signals[event_type].set()

    def get_last_event(self, event_type: str) -> Event | None:
        """Get the last event of a specific type."""
        return self._last_events.get(event_type)

    async def wait_for_event(
        self,
        event_type: str,
        timeout: float = 5.0,
    ) -> Event | None:
        """Wait for an event of a specific type."""
        if event_type not in self._event_signals:
            self._event_signals[event_type] = asyncio.Event()

        try:
            await asyncio.wait_for(
                self._event_signals[event_type].wait(),
                timeout=timeout,
            )
            return self._last_events.get(event_type)
        except asyncio.TimeoutError:
            return None

    def emit_stopped(
        self,
        reason: str = "breakpoint",
        thread_id: int = 1,
    ) -> None:
        """Emit a stopped event for testing."""
        from tests._fixtures.unit.builders.dap_builders import DAPEventBuilder

        event = DAPEventBuilder.stopped_event(reason=reason, thread_id=thread_id)
        self.process_event(event)

    def emit_initialized(self) -> None:
        """Emit an initialized event for testing."""
        from tests._fixtures.unit.builders.dap_builders import DAPEventBuilder

        event = DAPEventBuilder.initialized_event()
        self.process_event(event)

    def emit_terminated(self) -> None:
        """Emit a terminated event for testing."""
        from tests._fixtures.unit.builders.dap_builders import DAPEventBuilder

        event = DAPEventBuilder.terminated_event()
        self.process_event(event)


@pytest.fixture
def mock_event_processor_full() -> MockEventProcessor:
    """Create a full-featured mock event processor.

    Returns
    -------
    MockEventProcessor
        Mock with subscription, event emission, and waiting capabilities
    """
    return MockEventProcessor()
