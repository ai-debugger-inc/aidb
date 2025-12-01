"""Factory functions for creating pre-configured mock objects."""

import asyncio
from typing import Any

from aidb_mcp.core.constants import ParamName
from tests._helpers.constants import Language
from tests._helpers.mocks.adapter_mocks import MockAdapter
from tests._helpers.mocks.dap_mocks import MockDAPClient
from tests._helpers.mocks.mcp_mocks import (
    MockMCPServer,
    MockNotificationHandler,
    MockToolHandler,
)
from tests._helpers.mocks.session_mocks import MockSessionManager


def create_successful_dap_client() -> MockDAPClient:
    """Create a DAP client that responds successfully to all commands.

    Returns
    -------
    MockDAPClient
        Pre-configured successful DAP client
    """
    client = MockDAPClient()

    # Add some realistic variable data
    client.variables[1] = [
        {"name": "x", "value": "10", "type": "int", "variablesReference": 0},
        {"name": "y", "value": "20", "type": "int", "variablesReference": 0},
    ]

    return client


def create_failing_dap_client() -> MockDAPClient:
    """Create a DAP client that fails on certain commands.

    Returns
    -------
    MockDAPClient
        Pre-configured failing DAP client
    """
    client = MockDAPClient()

    # Set up some failing commands
    client.set_error_response("launch", "Failed to launch debugger")
    client.set_error_response("setBreakpoints", "Breakpoint verification failed")

    return client


def create_python_adapter() -> MockAdapter:
    """Create a Python-specific mock adapter.

    Returns
    -------
    MockAdapter
        Pre-configured Python adapter
    """
    return MockAdapter(Language.PYTHON.value)


def create_session_manager_with_active_session() -> MockSessionManager:
    """Create a session manager with an active session.

    Returns
    -------
    MockSessionManager
        Session manager with pre-created active session
    """
    manager = MockSessionManager()
    session_id = "test_session_123"

    manager.create_session(session_id, language=Language.PYTHON.value, target="test.py")
    # Note: start_session is async, so caller needs to await it

    return manager


def create_mock_debugging_context() -> dict[str, Any]:
    """Create a complete mock debugging context.

    Returns
    -------
    Dict[str, Any]
        Complete debugging context with all mocks
    """
    dap_client = create_successful_dap_client()
    adapter = create_python_adapter()
    session_manager = MockSessionManager()

    # Create and start a session
    session_id = "test_session"
    session_manager.create_session(session_id, language=Language.PYTHON.value)

    return {
        "dap_client": dap_client,
        "adapter": adapter,
        "session_manager": session_manager,
        ParamName.SESSION_ID: session_id,
    }


def create_mock_mcp_server(
    with_default_tools: bool = True,
) -> MockMCPServer:
    """Create a mock MCP server with optional default tools.

    Parameters
    ----------
    with_default_tools : bool
        Whether to register default AIDB tools

    Returns
    -------
    MockMCPServer
        Configured mock server
    """
    server = MockMCPServer()

    if with_default_tools:
        # Register core AIDB tools
        server.register_tool(
            "aidb_init",
            "Initialize debugging context",
            {"type": "object", "properties": {"language": {"type": "string"}}},
        )
        server.register_tool(
            "aidb_session_start",
            "Start debug session",
            {
                "type": "object",
                "properties": {
                    "target": {"type": "string"},
                    "language": {"type": "string"},
                },
            },
        )
        server.register_tool(
            "aidb_session_stop",
            "Stop debug session",
            {
                "type": "object",
                "properties": {ParamName.SESSION_ID: {"type": "string"}},
            },
        )
        server.register_tool(
            "aidb_breakpoint_set",
            "Set breakpoint",
            {
                "type": "object",
                "properties": {
                    "file": {"type": "string"},
                    "line": {"type": "number"},
                },
            },
        )
        server.register_tool(
            "aidb_execution_continue",
            "Continue execution",
            {"type": "object", "properties": {}},
        )
        server.register_tool(
            "aidb_inspect",
            "Inspect variables",
            {
                "type": "object",
                "properties": {"target": {"type": "string"}},
            },
        )

    return server


def create_mock_mcp_context() -> dict[str, Any]:
    """Create a complete mock MCP context for testing.

    Returns
    -------
    Dict[str, Any]
        Complete MCP testing context
    """
    server = create_mock_mcp_server()
    notification_handler = MockNotificationHandler()
    tool_handler = MockToolHandler()

    # Wire up handlers - store task references to prevent GC
    _pending_tasks: list[asyncio.Task] = []

    def handle_stopped(params: dict[str, Any]) -> None:
        task = asyncio.create_task(notification_handler.handle("debug/stopped", params))
        _pending_tasks.append(task)

    def handle_continued(params: dict[str, Any]) -> None:
        task = asyncio.create_task(
            notification_handler.handle("debug/continued", params)
        )
        _pending_tasks.append(task)

    def handle_terminated(params: dict[str, Any]) -> None:
        task = asyncio.create_task(
            notification_handler.handle("debug/terminated", params)
        )
        _pending_tasks.append(task)

    server.subscribe_to_notification("debug/stopped", handle_stopped)
    server.subscribe_to_notification("debug/continued", handle_continued)
    server.subscribe_to_notification("debug/terminated", handle_terminated)

    return {
        "server": server,
        "notification_handler": notification_handler,
        "tool_handler": tool_handler,
    }
