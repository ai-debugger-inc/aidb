"""DAP component mocks for unit testing.

Provides mock implementations of DAP client components for testing at the component
level rather than full client integration.
"""

from tests._fixtures.unit.dap.events import mock_event_processor
from tests._fixtures.unit.dap.receiver import mock_receiver
from tests._fixtures.unit.dap.transport import mock_transport

__all__ = [
    "mock_transport",
    "mock_receiver",
    "mock_event_processor",
]
