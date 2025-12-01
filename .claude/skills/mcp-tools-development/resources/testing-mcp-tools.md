# Testing MCP Tools

This guide covers best practices for testing MCP tools in AIDB, including E2E tests, integration tests, and the DebugInterface abstraction.

## Testing Philosophy

MCP tools require comprehensive testing to ensure:

1. **Correctness**: Tools return accurate data (line numbers, values, state)
1. **Structure**: Responses match MCP protocol expectations
1. **Content**: Data reflects actual debug state
1. **Efficiency**: Responses don't include bloat

**Priority:** E2E > Integration > Unit (highest ROI first)

## DebugInterface Abstraction

The `DebugInterface` abstraction allows tests to work with both direct API and MCP tools interchangeably.

### Location

```python
from tests._helpers.debug_interface import DebugInterface
```

The `DebugInterface` is located in `src/tests/_helpers/debug_interface/` (base class in `base.py`).

### Why Use DebugInterface?

1. **Flexibility**: Tests work with both API and MCP implementations
1. **Consistency**: Same test validates both paths
1. **Clarity**: Higher-level operations vs low-level API calls
1. **Coverage**: Ensures API and MCP stay in sync

### Basic Usage

```python
import pytest
from tests._helpers.debug_interface import DebugInterface


@pytest.mark.e2e
async def test_your_tool(debug_interface: DebugInterface):
    """Test tool with DebugInterface abstraction."""

    # Start session
    await debug_interface.start_session(
        target="test_app.py",
        breakpoints=[{"file": "test_app.py", "line": 10}],
    )

    # Continue to breakpoint
    await debug_interface.continue_execution()

    # Use your tool (works for both MCP and direct API)
    response = await debug_interface.call_tool(
        "aidb.your_tool",
        {"action": "your_action"},
    )

    # Validate response
    assert response["success"] is True
    assert "data" in response
```

### Parameterized Testing (MCP + Direct API)

Test both implementations automatically:

```python
@pytest.mark.e2e
@pytest.mark.parametrize("interface_type", ["mcp", "direct"])
async def test_step_operation(debug_interface: DebugInterface, interface_type: str):
    """Test stepping works via MCP and direct API."""

    # DebugInterface automatically routes to correct implementation
    await debug_interface.start_session(target="test_app.py")

    # Step (uses MCP or API based on interface_type fixture)
    response = await debug_interface.step("into")

    # Validate (same assertions for both)
    assert response["success"] is True
    assert "execution_state" in response["data"]
```

## E2E Test Patterns

### Pattern 1: Basic Tool Operation

Test the happy path for your tool:

```python
@pytest.mark.e2e
async def test_tool_basic_operation(debug_interface: DebugInterface):
    """Test basic tool operation."""
    # Setup
    await debug_interface.start_session(
        target="examples/simple_app.py",
        breakpoints=[{"file": "examples/simple_app.py", "line": 5}],
    )

    # Execute
    await debug_interface.continue_execution()
    response = await debug_interface.call_tool(
        "aidb.inspect",
        {"target": "locals"},
    )

    # Validate structure
    assert response["success"] is True
    assert "data" in response
    assert "locals" in response["data"]

    # Validate content accuracy
    assert isinstance(response["data"]["locals"], list)
    assert len(response["data"]["locals"]) > 0

    # Validate efficiency (no bloat)
    assert len(response["data"]) <= 3  # Only essential fields
```

### Pattern 2: Error Handling

Test tool behavior with invalid inputs:

```python
@pytest.mark.e2e
async def test_tool_invalid_action(debug_interface: DebugInterface):
    """Test tool error handling with invalid action."""
    await debug_interface.start_session(target="examples/simple_app.py")

    # Invalid action
    response = await debug_interface.call_tool(
        "aidb.your_tool",
        {"action": "invalid_action"},
    )

    # Should return error response
    assert response["success"] is False
    assert "error_code" in response
    assert "VALIDATION" in response["error_code"]
    assert "suggested_actions" in response  # User guidance
```

### Pattern 3: State Validation

Test tool behavior in different execution states:

```python
@pytest.mark.e2e
async def test_tool_requires_paused_state(debug_interface: DebugInterface):
    """Test tool that requires program to be paused."""
    await debug_interface.start_session(target="examples/simple_app.py")

    # Tool requires paused state but program is running
    response = await debug_interface.call_tool(
        "aidb.inspect",
        {"target": "locals"},
    )

    # Should return state error
    assert response["success"] is False
    assert "STATE" in response.get("error_code", "")
    assert "paused" in response.get("error_message", "").lower()
```

### Pattern 4: Multi-Step Workflow

Test tools in realistic debugging workflows:

```python
@pytest.mark.e2e
async def test_step_and_inspect_workflow(debug_interface: DebugInterface):
    """Test stepping and inspecting variables."""
    # Start session
    await debug_interface.start_session(
        target="examples/calculator.py",
        breakpoints=[{"file": "examples/calculator.py", "line": 10}],
    )

    # Continue to breakpoint
    await debug_interface.continue_execution()

    # Inspect initial state
    locals_response = await debug_interface.call_tool(
        "aidb.inspect",
        {"target": "locals"},
    )
    initial_vars = {v["name"]: v["value"] for v in locals_response["data"]["locals"]}

    # Step to next line
    await debug_interface.step("over")

    # Inspect updated state
    locals_response = await debug_interface.call_tool(
        "aidb.inspect",
        {"target": "locals"},
    )
    updated_vars = {v["name"]: v["value"] for v in locals_response["data"]["locals"]}

    # Validate state changed correctly
    assert initial_vars != updated_vars
    assert "result" in updated_vars  # New variable appeared
```

## MCP Response Validation

### Structure Validation

Ensure response matches MCP protocol:

```python
def validate_mcp_response_structure(response: dict) -> None:
    """Validate MCP response structure."""
    assert "success" in response, "Missing 'success' field"
    assert isinstance(response["success"], bool), "'success' must be boolean"

    if response["success"]:
        assert "data" in response, "Success response must have 'data'"
        assert "summary" in response, "Success response must have 'summary'"
    else:
        assert "error_code" in response, "Error response must have 'error_code'"
        assert "error_message" in response, "Error response must have 'error_message'"


@pytest.mark.e2e
async def test_response_structure(debug_interface: DebugInterface):
    """Test tool returns valid MCP response structure."""
    await debug_interface.start_session(target="examples/simple_app.py")

    response = await debug_interface.call_tool("aidb.session_status", {})

    # Validate structure
    validate_mcp_response_structure(response)
```

### Content Accuracy Validation

Verify response data reflects actual debug state:

```python
@pytest.mark.e2e
async def test_locals_content_accuracy(debug_interface: DebugInterface):
    """Test inspect.locals returns accurate variable values."""
    await debug_interface.start_session(
        target="examples/variables.py",
        breakpoints=[{"file": "examples/variables.py", "line": 15}],
    )
    await debug_interface.continue_execution()

    # Inspect locals
    response = await debug_interface.call_tool(
        "aidb.inspect",
        {"target": "locals"},
    )

    # Validate specific variables exist with correct values
    locals_dict = {v["name"]: v["value"] for v in response["data"]["locals"]}

    assert "x" in locals_dict, "Variable 'x' should exist"
    assert locals_dict["x"] == "10", f"Expected x=10, got {locals_dict['x']}"

    assert "message" in locals_dict, "Variable 'message' should exist"
    assert locals_dict["message"] == "'hello'", "Message should be 'hello'"
```

### Efficiency Validation (No Bloat)

Ensure responses don't include unnecessary data:

```python
@pytest.mark.e2e
async def test_response_efficiency(debug_interface: DebugInterface):
    """Test tool returns only necessary data (no bloat)."""
    await debug_interface.start_session(
        target="examples/simple_app.py",
        breakpoints=[{"file": "examples/simple_app.py", "line": 5}],
    )
    await debug_interface.continue_execution()

    response = await debug_interface.call_tool(
        "aidb.inspect",
        {"target": "locals"},
    )

    # Response should be focused
    data_keys = set(response["data"].keys())

    # Should have locals, maybe location
    assert len(data_keys) <= 3, f"Too many fields: {data_keys}"

    # Should NOT have unnecessary fields
    bloat_fields = {"globals", "timestamp", "correlation_id", "metadata"}
    assert not (data_keys & bloat_fields), f"Found bloat: {data_keys & bloat_fields}"
```

## Integration Tests

Integration tests focus on handler logic without full session setup.

### Testing Handlers Directly

**⚠️ CONCEPTUAL EXAMPLE** - Adapt to actual handler structure:

```python
import pytest
from aidb_mcp.handlers.inspection.state_inspection import handle_inspect


@pytest.mark.integration
async def test_inspect_handler_validation(mock_session_context):
    """Test inspect handler parameter validation."""
    # Missing required parameter
    response = await handle_inspect({
        "_api": mock_session_context.api,
        "_context": mock_session_context,
    })

    # Should return validation error
    assert response["success"] is False
    assert "VALIDATION" in response["error_code"]
```

### Testing Response Builders

```python
import pytest
from aidb_mcp.responses.builders import ExecutionStateBuilder
from aidb_mcp.core.constants import DetailedExecutionStatus


@pytest.mark.unit
def test_execution_state_builder():
    """Test ExecutionStateBuilder creates correct structure."""
    state = ExecutionStateBuilder.build(
        detailed_status=DetailedExecutionStatus.STOPPED_AT_BREAKPOINT,
        location="example.py:10",
        has_breakpoints=True,
        stop_reason="breakpoint",
    )

    assert state["status"] == "stopped"
    assert state["reason"] == "breakpoint"
    assert state["location"] == "example.py:10"
    assert state["has_breakpoints"] is True
```

## Test Organization

### Directory Structure

**⚠️ SIMPLIFIED EXAMPLE** - Actual structure is more detailed:

```
src/tests/
├── aidb_mcp/
│   ├── core/
│   │   ├── integration/
│   │   └── unit/
│   ├── handlers/
│   ├── responses/
│   ├── server/
│   └── utils/
└── _helpers/
    └── debug_interface/
        ├── base.py
        ├── api_interface.py
        └── mcp_interface.py
```

### Test Naming Conventions

- **E2E**: `test_<tool_name>_<scenario>` (e.g., `test_step_into_function`)
- **Integration**: `test_<component>_<behavior>` (e.g., `test_handler_validation`)
- **Unit**: `test_<function>_<case>` (e.g., `test_validate_action_invalid_enum`)

## Common Test Fixtures

### debug_interface Fixture

Automatically parameterized for MCP and direct API:

```python
@pytest.fixture
async def debug_interface(interface_type: str):
    """Provide DebugInterface for tests."""
    if interface_type == "mcp":
        interface = MCPDebugInterface()
    else:
        interface = DirectAPIDebugInterface()

    yield interface

    # Cleanup
    await interface.cleanup()
```

### Sample Applications

**⚠️ CONCEPTUAL EXAMPLES** - Create test programs as needed:

Example test programs for debugging workflows (adapt to your needs):

- Basic sequential execution program
- Function calls and variable tracking
- Control flow and loops
- Exception handling scenarios

See `src/tests/_assets/test_programs/` for actual test program examples.

## Best Practices

### DO

- **Test all three dimensions**: Structure, content accuracy, efficiency
- **Use DebugInterface**: Ensures MCP and API stay in sync
- **Test error paths**: Invalid inputs, wrong state, edge cases
- **Validate actual values**: Not just structure, but correct data
- **Check for bloat**: Responses should be minimal
- **Test workflows**: Multi-step realistic scenarios

### DON'T

- **Skip content validation**: Structure tests alone aren't enough
- **Ignore efficiency**: Bloated responses hurt agent performance
- **Test implementation details**: Focus on behavior, not internals
- **Mock unnecessarily**: Use real debug sessions when possible
- **Write flaky tests**: Ensure deterministic outcomes

## Debugging Failed Tests

### Enable Verbose Logging

```bash
AIDB_LOG_LEVEL=DEBUG AIDB_ADAPTER_TRACE=1 \
pytest src/tests/aidb_mcp/e2e/test_your_tool.py -v -s
```

### Inspect MCP Responses

```python
import json

@pytest.mark.e2e
async def test_debug_response(debug_interface: DebugInterface):
    """Debug test to inspect full response."""
    response = await debug_interface.call_tool("aidb.your_tool", {})

    # Print full response for debugging
    print(json.dumps(response, indent=2))

    # Add assertions after inspecting output
```

### Check Execution State

```python
@pytest.mark.e2e
async def test_debug_state(debug_interface: DebugInterface):
    """Debug test to check execution state."""
    await debug_interface.start_session(target="examples/simple_app.py")

    # Check state before operation
    status = await debug_interface.call_tool("aidb.session_status", {})
    print(f"Before: {status['data']['execution_state']}")

    # Perform operation
    await debug_interface.step("over")

    # Check state after operation
    status = await debug_interface.call_tool("aidb.session_status", {})
    print(f"After: {status['data']['execution_state']}")
```

## Summary

Testing MCP tools requires:

1. **DebugInterface abstraction** - Test MCP and API together
1. **Three-dimensional validation** - Structure + Content + Efficiency
1. **E2E-first approach** - Highest ROI testing
1. **Real debug sessions** - Avoid excessive mocking
1. **Content accuracy checks** - Verify actual values, not just structure

Always test the agent experience: Is the response accurate, clear, and minimal?
