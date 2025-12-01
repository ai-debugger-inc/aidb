# DebugInterface Abstraction

The cornerstone of AIDB's testing strategy - a unified API that works with both MCP tools and the direct API.

**Location:** `src/tests/_helpers/debug_interface/`

______________________________________________________________________

## Why This Matters

**Problem:** Two entry points (MCP Tools, Direct API) would require duplicate test suites.

**Solution:** One test validates both entry points automatically via `@parametrize_interfaces`.

```
Test Code (uses DebugInterface)
       │
   ┌───┴───┐
   ▼       ▼
APIInterface  MCPInterface
   │          │
   ▼          ▼
aidb API    aidb_mcp
```

______________________________________________________________________

## Usage Pattern

```python
from tests._helpers.parametrization import parametrize_interfaces

class TestBreakpoints(BaseE2ETest):
    @parametrize_interfaces  # Runs twice: MCP and API
    @pytest.mark.asyncio
    async def test_set_breakpoint(self, debug_interface, simple_program):
        """Works with BOTH MCP and API."""
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
- **API implementation:** `src/tests/_helpers/debug_interface/api_interface.py`
- **MCP implementation:** `src/tests/_helpers/debug_interface/mcp_interface.py`
- **Parametrization:** `src/tests/_helpers/parametrization.py`
