"""Reusable mock objects for AIDB test suite.

This package provides mock implementations of DAP clients, adapters, sessions, MCP
servers, and other components for isolated testing.
"""

from tests._helpers.mocks.adapter_mocks import MockAdapter, MockProcess
from tests._helpers.mocks.dap_mocks import MockDAPClient
from tests._helpers.mocks.factories import (
    create_failing_dap_client,
    create_mock_debugging_context,
    create_mock_mcp_context,
    create_mock_mcp_server,
    create_python_adapter,
    create_session_manager_with_active_session,
    create_successful_dap_client,
)
from tests._helpers.mocks.mcp_mocks import (
    MockMCPServer,
    MockNotification,
    MockNotificationHandler,
    MockToolCall,
    MockToolHandler,
)
from tests._helpers.mocks.session_mocks import MockSessionManager

__all__ = [
    # DAP mocks
    "MockDAPClient",
    # Adapter mocks
    "MockAdapter",
    "MockProcess",
    # Session mocks
    "MockSessionManager",
    # MCP mocks
    "MockMCPServer",
    "MockToolCall",
    "MockNotification",
    "MockNotificationHandler",
    "MockToolHandler",
    # Factory functions
    "create_successful_dap_client",
    "create_failing_dap_client",
    "create_python_adapter",
    "create_session_manager_with_active_session",
    "create_mock_debugging_context",
    "create_mock_mcp_server",
    "create_mock_mcp_context",
]
