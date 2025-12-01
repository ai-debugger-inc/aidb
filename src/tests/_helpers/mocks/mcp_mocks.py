"""Mock MCP server and handlers for testing."""

import asyncio
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from aidb_mcp.core.constants import ParamName
from tests._helpers.constants import DebugPorts, Language


@dataclass
class MockToolCall:
    """Record of a tool call for testing."""

    name: str
    arguments: dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    response: dict[str, Any] | None = None
    error: str | None = None


@dataclass
class MockNotification:
    """Record of a notification for testing."""

    method: str
    params: dict[str, Any]
    timestamp: float = field(default_factory=time.time)


class MockMCPServer:
    """Mock MCP server for testing.

    This mock provides a full MCP server interface for testing tool handlers,
    notifications, and resource management without starting a real server.
    """

    def __init__(self, name: str = "test-mcp-server"):
        """Initialize mock MCP server.

        Parameters
        ----------
        name : str
            Server name
        """
        self.name = name
        self.is_running = False

        # Tool management
        self.tools: dict[str, dict[str, Any]] = {}
        self.tool_calls: list[MockToolCall] = []
        self.tool_responses: dict[str, Any] = {}
        self.tool_errors: dict[str, str] = {}

        # Notification management
        self.notifications: list[MockNotification] = []
        self.notification_subscriptions: dict[str, list[Callable]] = {}

        # Resource management
        self.resources: dict[str, dict[str, Any]] = {}
        self.resource_reads: list[str] = []

        # Prompt management
        self.prompts: dict[str, dict[str, Any]] = {}
        self.prompt_calls: list[str] = []

        # Session state
        self.session_state: dict[str, Any] = {
            "debug_session": None,
            "language": None,
            "workspace": None,
            "breakpoints": [],
            "variables": {},
            "stack_frames": [],
        }

        # Event queue for testing
        self.event_queue: deque[dict[str, Any]] = deque(maxlen=100)

    def register_tool(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
    ) -> None:
        """Register a tool with the server."""
        self.tools[name] = {
            "name": name,
            "description": description,
            "inputSchema": input_schema,
        }

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call a tool and return response."""
        call = MockToolCall(name=name, arguments=arguments)
        self.tool_calls.append(call)

        # Check for configured errors
        if name in self.tool_errors:
            call.error = self.tool_errors[name]
            raise Exception(self.tool_errors[name])

        # Return configured response or default
        if name in self.tool_responses:
            response = self.tool_responses[name]
        else:
            response = self._get_default_tool_response(name, arguments)

        call.response = response
        return response

    def _get_default_tool_response(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Get default response for a tool."""
        # Provide sensible defaults for common tools
        if name == "aidb_init":
            return {
                "success": True,
                ParamName.SESSION_ID: "mock_session_123",
                "language": arguments.get("language", Language.PYTHON.value),
                "examples": ["Example 1", "Example 2"],
            }
        if name == "aidb_session_start":
            lang = arguments.get("language", Language.PYTHON.value)
            port = (
                Language(lang).default_port
                if lang in [language.value for language in Language]
                else DebugPorts.PYTHON
            )
            return {
                "success": True,
                ParamName.SESSION_ID: "mock_session_123",
                "port": port,
                "adapter": f"mock_{lang}_adapter",
            }
        if name == "aidb_session_stop":
            return {
                "success": True,
                ParamName.SESSION_ID: arguments.get(ParamName.SESSION_ID),
            }
        if name == "aidb_breakpoint_set":
            return {
                "success": True,
                "breakpoints": [
                    {"id": 1, "line": arguments.get("line", 10), "verified": True},
                ],
            }
        if name == "aidb_execution_continue":
            return {"success": True, "continued": True}
        if name == "aidb_execution_step":
            return {"success": True, "step_type": arguments.get("step_type", "into")}
        if name == "aidb_inspect":
            return {
                "success": True,
                "data": {
                    "variables": [
                        {"name": "x", "value": "10", "type": "int"},
                        {"name": "y", "value": "20", "type": "int"},
                    ],
                },
            }
        return {"success": True, "tool": name, "arguments": arguments}

    def set_tool_response(self, name: str, response: dict[str, Any]) -> None:
        """Configure a custom response for a tool."""
        self.tool_responses[name] = response

    def set_tool_error(self, name: str, error: str) -> None:
        """Configure a tool to raise an error."""
        self.tool_errors[name] = error

    async def send_notification(self, method: str, params: dict[str, Any]) -> None:
        """Send a notification."""
        notification = MockNotification(method=method, params=params)
        self.notifications.append(notification)

        # Trigger subscribed handlers
        if method in self.notification_subscriptions:
            for handler in self.notification_subscriptions[method]:
                await handler(params)

        # Add to event queue
        self.event_queue.append(
            {"type": "notification", "method": method, "params": params},
        )

    def subscribe_to_notification(
        self,
        method: str,
        handler: Callable[[dict[str, Any]], None],
    ) -> None:
        """Subscribe to notifications."""
        if method not in self.notification_subscriptions:
            self.notification_subscriptions[method] = []
        self.notification_subscriptions[method].append(handler)

    def register_resource(
        self,
        uri: str,
        name: str,
        description: str,
        content: str,
    ) -> None:
        """Register a resource."""
        self.resources[uri] = {
            "uri": uri,
            "name": name,
            "description": description,
            "content": content,
        }

    def read_resource(self, uri: str) -> str | None:
        """Read a resource."""
        self.resource_reads.append(uri)
        resource = self.resources.get(uri)
        return resource["content"] if resource else None

    def register_prompt(
        self,
        name: str,
        description: str,
        arguments: list[dict[str, Any]],
    ) -> None:
        """Register a prompt."""
        self.prompts[name] = {
            "name": name,
            "description": description,
            "arguments": arguments,
        }

    def was_tool_called(self, name: str, **expected_args) -> bool:
        """Check if a tool was called with expected arguments."""
        for call in self.tool_calls:
            if call.name == name and all(
                call.arguments.get(k) == v for k, v in expected_args.items()
            ):
                return True
        return False

    def get_tool_calls(self, name: str | None = None) -> list[MockToolCall]:
        """Get tool calls, optionally filtered by name."""
        if name:
            return [c for c in self.tool_calls if c.name == name]
        return self.tool_calls

    def get_notifications(self, method: str | None = None) -> list[MockNotification]:
        """Get notifications, optionally filtered by method."""
        if method:
            return [n for n in self.notifications if n.method == method]
        return self.notifications

    def reset(self) -> None:
        """Reset the mock server to initial state."""
        self.tool_calls.clear()
        self.tool_responses.clear()
        self.tool_errors.clear()
        self.notifications.clear()
        self.resource_reads.clear()
        self.prompt_calls.clear()
        self.event_queue.clear()
        self.session_state = {
            "debug_session": None,
            "language": None,
            "workspace": None,
            "breakpoints": [],
            "variables": {},
            "stack_frames": [],
        }


class MockNotificationHandler:
    """Mock handler for MCP notifications."""

    def __init__(self):
        """Initialize mock notification handler."""
        self.received_notifications: list[MockNotification] = []
        self.handlers: dict[str, Callable] = {}

    async def handle(self, method: str, params: dict[str, Any]) -> None:
        """Handle a notification."""
        notification = MockNotification(method=method, params=params)
        self.received_notifications.append(notification)

        # Call registered handler if exists
        if method in self.handlers:
            await self.handlers[method](params)

    def register_handler(self, method: str, handler: Callable) -> None:
        """Register a handler for a notification method."""
        self.handlers[method] = handler

    def was_notified(self, method: str, **expected_params) -> bool:
        """Check if a notification was received."""
        for notification in self.received_notifications:
            if notification.method == method and all(
                notification.params.get(k) == v for k, v in expected_params.items()
            ):
                return True
        return False

    def get_notifications_for_method(self, method: str) -> list[MockNotification]:
        """Get all notifications for a method."""
        return [n for n in self.received_notifications if n.method == method]

    def reset(self) -> None:
        """Reset the handler."""
        self.received_notifications.clear()


class MockToolHandler:
    """Mock handler for MCP tools."""

    def __init__(self):
        """Initialize mock tool handler."""
        self.tools: dict[str, dict[str, Any]] = {}
        self.call_history: list[MockToolCall] = []
        self.responses: dict[str, Any] = {}
        self.errors: dict[str, str] = {}

    def register_tool(
        self,
        name: str,
        handler: Callable,
        description: str = "",
        input_schema: dict[str, Any] | None = None,
    ) -> None:
        """Register a tool."""
        self.tools[name] = {
            "name": name,
            "handler": handler,
            "description": description,
            "inputSchema": input_schema or {},
        }

    async def handle_tool_call(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle a tool call."""
        call = MockToolCall(name=name, arguments=arguments)
        self.call_history.append(call)

        # Check for configured error
        if name in self.errors:
            call.error = self.errors[name]
            raise Exception(self.errors[name])

        # Check for configured response
        if name in self.responses:
            response = self.responses[name]
        elif name in self.tools:
            # Call the registered handler
            handler = self.tools[name]["handler"]
            response = (
                await handler(arguments)
                if asyncio.iscoroutinefunction(handler)
                else handler(arguments)
            )
        else:
            response = {"error": f"Unknown tool: {name}"}

        call.response = response
        return response

    def set_response(self, name: str, response: dict[str, Any]) -> None:
        """Set a fixed response for a tool."""
        self.responses[name] = response

    def set_error(self, name: str, error: str) -> None:
        """Set an error for a tool."""
        self.errors[name] = error

    def was_called(self, name: str, **expected_args) -> bool:
        """Check if a tool was called."""
        for call in self.call_history:
            if call.name == name and all(
                call.arguments.get(k) == v for k, v in expected_args.items()
            ):
                return True
        return False

    def get_calls(self, name: str | None = None) -> list[MockToolCall]:
        """Get tool calls."""
        if name:
            return [c for c in self.call_history if c.name == name]
        return self.call_history

    def reset(self) -> None:
        """Reset the handler."""
        self.call_history.clear()
        self.responses.clear()
        self.errors.clear()
