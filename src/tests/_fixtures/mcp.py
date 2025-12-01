"""MCP-specific fixtures for testing AIDB MCP handlers.

This module provides fixtures for MCP session management and tool testing.
"""

__all__ = [
    # Core MCP fixtures
    "mcp_session",
    "mcp_tools",
    "mcp_notifications",
    "mcp_context",
    "mcp_workflow_runner",
    # Debug scenario fixtures
    "debug_session_context",
    "python_debug_scenario",
    "javascript_debug_scenario",
    "mcp_integration_test_context",
    # Assertion helpers
    "mcp_assertions",
    "MCPAssertions",
]

import json
import tempfile
import time
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, Optional

import pytest

from aidb_mcp.core.constants import ParamName
from tests._helpers.constants import (
    DebugPorts,
    Language,
    MCPResponseCode,
    StopReason,
)
from tests._helpers.ports import TestPortManager


@pytest.fixture
async def mcp_session() -> AsyncGenerator[dict[str, Any], None]:
    """Provide a mock MCP session for testing.

    Yields
    ------
    Dict[str, Any]
        Mock MCP session with tools and notifications
    """
    session_id = f"test_mcp_{time.time()}"

    session = {
        "id": session_id,
        "created_at": time.time(),
        "tools": {},
        "notifications": [],
        "state": "active",
        "context": {},
    }

    yield session

    # Cleanup
    session["state"] = "closed"


async def _mock_aidb_start(args: dict[str, Any]) -> dict[str, Any]:
    """Mock aidb_start handler."""
    language = args.get("language", Language.PYTHON.value)
    return {
        "code": MCPResponseCode.OK.value,
        "data": {
            "language": language,
            "framework": args.get("framework"),
            "next_call": {
                "tool": "aidb_session_start",
                "params": {
                    "language": language,
                    "target": args.get("target", "main.py"),
                    "workspace_root": args.get(
                        "workspace_root",
                        tempfile.gettempdir(),
                    ),
                },
            },
        },
    }


async def _mock_session_start(args: dict[str, Any]) -> dict[str, Any]:
    """Mock aidb_session_start handler."""
    session_id = f"session_{time.time()}"
    return {
        "code": MCPResponseCode.OK.value,
        "data": {
            "session_id": session_id,
            "language": args.get("language", Language.PYTHON.value),
            "status": "started",
            "port": DebugPorts.PYTHON,
            "capabilities": {
                "supportsConfigurationDoneRequest": True,
                "supportsConditionalBreakpoints": True,
                "supportsSetVariable": True,
            },
        },
    }


async def _mock_breakpoint(args: dict[str, Any]) -> dict[str, Any]:
    """Mock aidb_breakpoint handler."""
    action = args.get("action", "set")
    location = args.get("location", "file.py:1")

    if action == "set":
        return _breakpoint_set_response(location, args.get(ParamName.CONDITION))
    if action == "list":
        return _breakpoint_list_response()
    return {"code": MCPResponseCode.OK.value, "data": {"removed": True}}


def _breakpoint_set_response(location: str, condition: str | None) -> dict[str, Any]:
    """Create breakpoint set response."""
    return {
        "code": MCPResponseCode.OK.value,
        "data": {
            "breakpoint_id": f"bp_{time.time()}",
            "location": location,
            "verified": True,
            "condition": condition,
        },
    }


def _breakpoint_list_response() -> dict[str, Any]:
    """Create breakpoint list response."""
    return {
        "code": MCPResponseCode.OK.value,
        "data": {
            "breakpoints": [
                {"id": "bp_1", "location": "test.py:10", "verified": True},
            ],
        },
    }


async def _mock_execute(args: dict[str, Any]) -> dict[str, Any]:
    """Mock aidb_execute handler."""
    action = args.get("action", "continue")
    return {
        "code": MCPResponseCode.OK.value,
        "data": {
            "action": action,
            "stopped": False,
            "reason": None,
            "location": None,
        },
    }


async def _mock_step(args: dict[str, Any]) -> dict[str, Any]:
    """Mock aidb_step handler."""
    action = args.get("action", "over")
    return {
        "code": MCPResponseCode.OK.value,
        "data": {
            "action": action,
            "stopped": True,
            "reason": StopReason.STEP.value,
            "location": "test.py:11",
            "thread_id": 1,
        },
    }


async def _mock_inspect(args: dict[str, Any]) -> dict[str, Any]:
    """Mock aidb_inspect handler."""
    target = args.get("target", "locals")

    if target == "locals":
        return _inspect_locals_response()
    if target == "stack":
        return _inspect_stack_response()
    return {"success": True, "data": {"result": "mock_value"}}


def _inspect_locals_response() -> dict[str, Any]:
    """Create inspect locals response."""
    return {
        "code": MCPResponseCode.OK.value,
        "data": {
            "variables": {
                "x": {"value": "10", "type": "int"},
                "y": {"value": "20", "type": "int"},
                "result": {"value": "30", "type": "int"},
            },
        },
    }


def _inspect_stack_response() -> dict[str, Any]:
    """Create inspect stack response."""
    return {
        "code": MCPResponseCode.OK.value,
        "data": {
            "frames": [
                {"id": 0, "name": "main", "source": "test.py", "line": 10},
            ],
        },
    }


async def _mock_variable(args: dict[str, Any]) -> dict[str, Any]:
    """Mock aidb_variable handler."""
    action = args.get("action", "get")

    if action == "get":
        return _variable_get_response(args.get("expression", "x"))
    if action == "set":
        return _variable_set_response(args.get("name"), args.get("value"))
    return {"code": MCPResponseCode.OK.value, "data": {"patched": True}}


def _variable_get_response(expression: str) -> dict[str, Any]:
    """Create variable get response."""
    return {
        "code": MCPResponseCode.OK.value,
        "data": {
            "name": expression,
            "value": "42",
            "type": "int",
        },
    }


def _variable_set_response(name: str | None, value: Any) -> dict[str, Any]:
    """Create variable set response."""
    return {
        "code": MCPResponseCode.OK.value,
        "data": {
            "name": name,
            "value": value,
            "success": True,
        },
    }


async def _mock_session(args: dict[str, Any]) -> dict[str, Any]:
    """Mock aidb_session handler."""
    action = args.get("action", "status")

    if action == "status":
        return _session_status_response()
    if action == "list":
        return _session_list_response()
    return {"code": MCPResponseCode.OK.value, "data": {"success": True}}


def _session_status_response() -> dict[str, Any]:
    """Create session status response."""
    return {
        "code": MCPResponseCode.OK.value,
        "data": {
            "session_id": "test_session_123",
            "status": "running",
            "language": Language.PYTHON.value,
            "target": "test.py",
        },
    }


def _session_list_response() -> dict[str, Any]:
    """Create session list response."""
    return {
        "code": MCPResponseCode.OK.value,
        "data": {
            "sessions": [
                {
                    "id": "test_session_123",
                    "language": Language.PYTHON.value,
                    "status": "running",
                },
            ],
        },
    }


@pytest.fixture
def mcp_tools() -> dict[str, Any]:
    """Provide mock MCP tool handlers.

    Returns
    -------
    Dict[str, Any]
        Dictionary of mock tool handlers
    """
    return {
        "aidb_start": _mock_aidb_start,
        "aidb_session_start": _mock_session_start,
        "aidb_breakpoint": _mock_breakpoint,
        "aidb_execute": _mock_execute,
        "aidb_step": _mock_step,
        "aidb_inspect": _mock_inspect,
        "aidb_variable": _mock_variable,
        "aidb_session": _mock_session,
    }


@pytest.fixture
def mcp_notifications() -> list[dict[str, Any]]:
    """Provide a list to capture MCP notifications.

    Returns
    -------
    List[Dict[str, Any]]
        List to store notifications for verification
    """
    return []


@pytest.fixture
async def mcp_context(
    mcp_session: dict[str, Any],
    mcp_tools: dict[str, Any],
    mcp_notifications: list[dict[str, Any]],
) -> dict[str, Any]:
    """Provide a complete MCP testing context.

    Parameters
    ----------
    mcp_session : Dict[str, Any]
        MCP session fixture
    mcp_tools : Dict[str, Any]
        MCP tools fixture
    mcp_notifications : List[Dict[str, Any]]
        Notifications list fixture

    Yields
    ------
    Dict[str, Any]
        Complete MCP context for testing
    """
    context: dict[str, Any] = {
        "session": mcp_session,
        "tools": mcp_tools,
        "notifications": mcp_notifications,
        "call_history": [],
        "responses": {},
    }

    # Helper function to simulate tool calls
    async def call_tool(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        if tool_name not in mcp_tools:
            return {
                "code": MCPResponseCode.ERROR.value,
                "message": f"Unknown tool: {tool_name}",
            }

        # Record the call
        call_record = {"tool": tool_name, "args": args, "timestamp": time.time()}
        context["call_history"].append(call_record)

        # Execute the tool
        try:
            response = await mcp_tools[tool_name](args)
            context["responses"][len(context["call_history"]) - 1] = response
            return response
        except Exception as e:
            error_response = {"code": MCPResponseCode.ERROR.value, "message": str(e)}
            context["responses"][len(context["call_history"]) - 1] = error_response
            return error_response

    context["call_tool"] = call_tool

    return context


@pytest.fixture
def mcp_workflow_runner(mcp_context: dict[str, Any]):
    """Provide a workflow runner for testing MCP tool sequences.

    Parameters
    ----------
    mcp_context : Dict[str, Any]
        MCP context fixture

    Returns
    -------
    callable
        Workflow runner function
    """

    async def run_workflow(workflow: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Run a sequence of MCP tool calls.

        Parameters
        ----------
        workflow : List[Dict[str, Any]]
            List of tool calls with 'tool' and 'args' keys

        Returns
        -------
        List[Dict[str, Any]]
            List of responses from each tool call
        """
        responses = []

        for step in workflow:
            tool_name = step["tool"]
            args = step.get("args", {})

            response = await mcp_context["call_tool"](tool_name, args)
            responses.append(response)

            # Stop on error unless continue_on_error is set
            if response.get("code") != MCPResponseCode.OK.value and not step.get(
                "continue_on_error",
                False,
            ):
                break

        return responses

    return run_workflow


@pytest.fixture
async def debug_session_context() -> AsyncGenerator[dict[str, Any], None]:
    """Provide a context for testing complete debugging workflows.

    Yields
    ------
    Dict[str, Any]
        Debug workflow context with session and port management
    """
    session_id = f"debug_workflow_{time.time()}"

    # Create isolated port manager
    async with TestPortManager(session_id, base_range=45000) as port_manager:
        port = await port_manager.allocate_port(Language.PYTHON.value)

        context = {
            "session_id": session_id,
            "port": port,
            "port_manager": port_manager,
            "breakpoints": [],
            "variables": {},
            "current_location": None,
            "state": "starting",
        }

        yield context

        # Cleanup is handled by port_manager context


# Helper fixtures for common test scenarios


@pytest.fixture
def python_debug_scenario(temp_workspace: Path):
    """Provide a Python debugging scenario setup.

    Parameters
    ----------
    temp_workspace : Path
        Temporary workspace directory

    Returns
    -------
    Dict[str, Any]
        Python debugging scenario data
    """
    # Create test file
    test_file = temp_workspace / "debug_test.py"
    test_file.write_text(
        """
def calculate(a, b):
    result = a + b  # Line 3 - good for breakpoint
    return result

def main():
    x = 10
    y = 20
    total = calculate(x, y)  # Line 9 - good for stepping
    print(f"Total: {total}")
    return total

if __name__ == "__main__":
    main()
""",
    )

    # Create launch configuration
    vscode_dir = temp_workspace / ".vscode"
    vscode_dir.mkdir(exist_ok=True)
    launch_json = vscode_dir / "launch.json"
    launch_json.write_text(
        json.dumps(
            {
                "version": "0.2.0",
                "configurations": [
                    {
                        "name": "Debug Test",
                        "type": Language.PYTHON.value,
                        "request": "launch",
                        "program": str(test_file),
                        "console": "integratedTerminal",
                    },
                ],
            },
            indent=2,
        ),
    )

    return {
        "workspace": temp_workspace,
        "test_file": test_file,
        "launch_config": launch_json,
        "language": Language.PYTHON.value,
        "breakpoint_line": 3,
        "step_line": 9,
        "expected_variables": {"a": "10", "b": "20", "result": "30"},
    }


@pytest.fixture
def javascript_debug_scenario(temp_workspace: Path):
    """Provide a JavaScript debugging scenario setup.

    Parameters
    ----------
    temp_workspace : Path
        Temporary workspace directory

    Returns
    -------
    Dict[str, Any]
        JavaScript debugging scenario data
    """
    # Create test file
    test_file = temp_workspace / "debug_test.js"
    test_file.write_text(
        """
function calculate(a, b) {
    const result = a + b;  // Line 3 - good for breakpoint
    return result;
}

function main() {
    const x = 10;
    const y = 20;
    const total = calculate(x, y);  // Line 10 - good for stepping
    console.log(`Total: ${total}`);
    return total;
}

main();
""",
    )

    return {
        "workspace": temp_workspace,
        "test_file": test_file,
        "language": "javascript",
        "breakpoint_line": 3,
        "step_line": 10,
        "expected_variables": {"a": "10", "b": "20", "result": "30"},
    }


@pytest.fixture
async def mcp_integration_test_context(
    mcp_context: dict[str, Any],
    python_debug_scenario: dict[str, Any],
) -> dict[str, Any]:
    """Provide a complete integration test context for MCP + debugging.

    Parameters
    ----------
    mcp_context : Dict[str, Any]
        MCP context fixture
    python_debug_scenario : Dict[str, Any]
        Python debug scenario fixture

    Yields
    ------
    Dict[str, Any]
        Complete integration test context
    """
    context = {
        "mcp": mcp_context,
        "scenario": python_debug_scenario,
        "workflow_state": {
            "session_started": False,
            "breakpoints_set": [],
            "current_frame": None,
            "execution_stopped": False,
        },
    }

    # Helper methods
    async def start_debug_session():
        """Start a debugging session."""
        response = await mcp_context["call_tool"](
            "aidb_start",
            {
                "language": Language.PYTHON.value,
                "workspace_root": str(python_debug_scenario["workspace"]),
            },
        )

        if response.get("code") == MCPResponseCode.OK.value:
            next_call = response["data"]["next_call"]
            session_response = await mcp_context["call_tool"](
                next_call["tool"],
                next_call["params"],
            )
            context["workflow_state"]["session_started"] = True
            return session_response

        return response

    async def set_breakpoint(line: int, file_path: str | None = None):
        """Set a breakpoint."""
        if not file_path:
            file_path = str(python_debug_scenario["test_file"])

        location = f"{file_path}:{line}"
        response = await mcp_context["call_tool"](
            "aidb_breakpoint",
            {ParamName.ACTION: "set", ParamName.LOCATION: location},
        )

        if response.get("code") == MCPResponseCode.OK.value:
            context["workflow_state"]["breakpoints_set"].append(location)

        return response

    # Add helper methods to context with proper typing
    context["start_debug_session"] = start_debug_session  # type: ignore
    context["set_breakpoint"] = set_breakpoint  # type: ignore

    return context


# Assertion helpers for MCP testing


class MCPAssertions:
    """MCP-specific assertion helpers."""

    @staticmethod
    def assert_response_ok(response: dict[str, Any], message: str = "") -> None:
        """Assert MCP response is OK."""
        assert response.get("code") == MCPResponseCode.OK.value, (
            f"Expected OK response: {response.get('message', 'No message')}. {message}"
        )
        assert "data" in response, f"Response missing data field. {message}"

    @staticmethod
    def assert_response_error(
        response: dict[str, Any],
        expected_code: str | None = None,
    ) -> None:
        """Assert MCP response is an error."""
        assert response.get("code") != MCPResponseCode.OK.value, (
            "Expected error response but got OK"
        )
        if expected_code:
            assert response.get("code") == expected_code, (
                f"Expected error code {expected_code}, got {response.get('code')}"
            )

    @staticmethod
    def assert_tool_called(
        context: dict[str, Any],
        tool_name: str,
        **expected_args,
    ) -> None:
        """Assert a tool was called with expected arguments."""
        calls = context.get("call_history", [])

        for call in calls:
            if call["tool"] == tool_name:
                args = call["args"]
                if all(args.get(k) == v for k, v in expected_args.items()):
                    return

        msg = f"Tool {tool_name} not called with expected args: {expected_args}"
        raise AssertionError(
            msg,
        )

    @staticmethod
    def assert_workflow_successful(responses: list[dict[str, Any]]) -> None:
        """Assert all responses in a workflow are successful."""
        for i, response in enumerate(responses):
            assert response.get("code") == MCPResponseCode.OK.value, (
                f"Step {i} failed: {response.get('message', 'Unknown error')}"
            )


@pytest.fixture
def mcp_assertions():
    """Provide MCP assertion helpers.

    Returns
    -------
    MCPAssertions
        MCP assertion helper class
    """
    return MCPAssertions()
