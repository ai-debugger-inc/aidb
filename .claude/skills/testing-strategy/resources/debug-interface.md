# DebugInterface Abstraction

A unified test interface for debugging operations through the MCP layer.

**Location:** `src/tests/_helpers/debug_interface/`

______________________________________________________________________

## Why This Matters

**Problem:** Tests need a consistent interface for debugging operations.

**Solution:** `MCPInterface` provides a test-friendly wrapper around MCP tools with `@parametrize_interfaces`.

```
Test Code (uses DebugInterface)
       │
       ▼
  MCPInterface
       │
       ▼
    aidb_mcp → DebugService → Session
```

Note: The direct API interface was removed as part of the service layer refactor.
All tests now run through MCP, which is the public interface for AI agents.

______________________________________________________________________

## Usage Pattern

```python
from tests._helpers.parametrization import parametrize_interfaces

class TestBreakpoints(BaseE2ETest):
    @parametrize_interfaces  # Runs with MCP interface
    @pytest.mark.asyncio
    async def test_set_breakpoint(self, debug_interface, simple_program):
        """Test breakpoint via MCP interface."""
        await debug_interface.start_session(program=simple_program)
        bp = await debug_interface.set_breakpoint(file=simple_program, line=5)
        self.verify_bp.verify_breakpoint_verified(bp)
        await debug_interface.stop_session()
```

______________________________________________________________________

## Core Interface Methods

```python
class DebugInterface(ABC):
    # Lifecycle
    async def initialize(self, language: str | None = None, **config)
    async def start_session(self, program: str | Path, **launch_args) -> dict
    async def stop_session()

    # Breakpoints
    async def set_breakpoint(self, file: str | Path, line: int, **kwargs) -> dict
    async def remove_breakpoint(self, breakpoint_id: str | int) -> bool
    async def list_breakpoints() -> list[dict]

    # Execution
    async def step_over() -> dict
    async def step_into() -> dict
    async def step_out() -> dict
    async def continue_execution() -> dict

    # Inspection
    async def get_state() -> dict
    async def get_variables(scope: str = "locals", frame: int = 0) -> dict
    async def get_stack_trace() -> list[dict]

    # Properties
    @property
    def is_session_active() -> bool
    @property
    def current_language() -> Language | None
```

______________________________________________________________________

## Shared Suite: Language-Agnostic Testing

The **shared suite** tests debug fundamentals across all languages using normalized, programmatically generated test programs.

**Location:** `src/tests/aidb_shared/` (integration/ + e2e/)

**Key Innovation:** Semantic markers that map identical logic to language-specific line numbers.

**What it tests:**

- Debug primitives (breakpoints, stepping, variables)
- Control flow across Python, JavaScript, Java
- Zero duplication: One test → 6 paths (2 interfaces × 3 languages)

```python
@parametrize_interfaces
@parametrize_languages
@pytest.mark.asyncio
async def test_breakpoint_hit(self, debug_interface, language, program):
    """Runs 6 times: (MCP, API) × (Python, JS, Java)"""
    line = program["markers"]["function.entry"]
    await debug_interface.set_breakpoint(file=program["path"], line=line)
    state = await debug_interface.continue_execution()
    assert state["stop_reason"] == "breakpoint"
```

______________________________________________________________________

## When to Use What

**Use Shared Suite when:**

- Testing core debug operations (breakpoint, step, inspect)
- Validating adapter behavior across languages
- Ensuring language parity

**Use Framework Tests when:**

- Testing framework-specific debugging (Django, Express, Spring)
- Validating launch.json configurations
- Testing real-world application patterns

**Use Launch Tests when:**

- Testing basic script/application launching
- Validating VS Code launch.json parsing
- Testing language-specific launch configurations

______________________________________________________________________

## Assertion Helpers

**Location:** `src/tests/_helpers/assertions/`

```python
# Breakpoint verification
self.verify_bp.verify_breakpoint_verified(bp)
self.verify_bp.verify_breakpoint_pending(bp)

# Execution verification
self.verify_exec.verify_stopped(state, expected_reason="breakpoint")
self.verify_exec.verify_completion(state)

# MCP response validation
MCPAssertions.assert_success(response)
MCPAssertions.assert_has_field(response, "data.locals")
```

______________________________________________________________________

## Implementation Files

- **Base interface:** `src/tests/_helpers/debug_interface/base.py`
- **MCP implementation:** `src/tests/_helpers/debug_interface/mcp_interface.py`
- **Parametrization:** `src/tests/_helpers/parametrization.py`
