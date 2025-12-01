# E2E Test Patterns

E2E tests validate complete workflows, exercising the full stack and catching integration bugs early.

______________________________________________________________________

## Base Class: BaseE2ETest

**Location:** `src/tests/_helpers/test_bases/base_e2e_test.py`

```python
from tests._helpers.test_bases.base_e2e_test import BaseE2ETest

class TestMyE2EScenario(BaseE2ETest):
    """Inherit from BaseE2ETest for E2E tests."""
    pass
```

**What you get:** Generated program support, marker-based testing, built-in assertion helpers.

______________________________________________________________________

## Pattern 1: Complete Workflow Test

```python
from tests._helpers.test_bases.base_e2e_test import BaseE2ETest
from tests._helpers.parametrization import parametrize_interfaces
import pytest

class TestCompleteSession(BaseE2ETest):
    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_complete_debugging_workflow(self, debug_interface, simple_program):
        """Test: start → bp → inspect → step → end."""
        # 1. Start
        session = await debug_interface.start_session(program=simple_program)
        assert session["status"] == "started"

        # 2. Set breakpoint
        bp = await debug_interface.set_breakpoint(file=simple_program, line=10)
        self.verify_bp.verify_breakpoint_verified(bp)

        # 3. Continue to breakpoint
        state = await debug_interface.continue_execution()
        self.verify_exec.verify_stopped(state, expected_reason="breakpoint")

        # 4. Inspect variables
        variables = await debug_interface.get_variables(scope="locals")
        assert variables["x"]["value"] == 10

        # 5. Step and complete
        await debug_interface.step_over()
        from tests._helpers.session_helpers import run_to_completion
        await run_to_completion(debug_interface)
        await debug_interface.stop_session()
```

______________________________________________________________________

## Pattern 2: Marker-Based Test (Multi-Language)

**Markers** map semantic locations across languages (Python line 5 = Java line 8).

```python
class TestGeneratedPrograms(BaseE2ETest):
    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_with_markers(self, debug_interface, generated_program_factory, language):
        program = generated_program_factory("basic_variables", language)

        # Use marker for breakpoint (language-independent)
        line = program["markers"]["var.init.x"]
        await debug_interface.set_breakpoint(file=program["path"], line=line)

        # Continue and verify
        state = await debug_interface.continue_execution()
        self.verify_exec.verify_stopped(state, expected_reason="breakpoint")
```

**Marker conventions:**

- `var.init.x` - Variable initialization
- `function.entry` - Function entry point
- `loop.start`, `loop.end` - Loop boundaries

______________________________________________________________________

## Pattern 3: MCP Response Validation

```python
class TestMCPResponses(BaseE2ETest):
    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_inspect_response(self, debug_interface, paused_program):
        response = await debug_interface.get_variables(scope="locals")

        # Structure
        assert "locals" in response

        # Content accuracy
        assert response["locals"]["x"]["value"] == 10

        # Efficiency (no bloat)
        assert len(response) <= 5  # No junk fields
```

______________________________________________________________________

## Working Examples to Study

**Framework Tests (E2E):**

- `src/tests/frameworks/python/flask/e2e/test_flask_debugging.py`
- `src/tests/frameworks/javascript/express/e2e/test_express_debugging.py`
- `src/tests/frameworks/java/springboot/e2e/test_springboot_debugging.py`

**Core API Tests:**

- `src/tests/aidb/api/e2e/test_launch_variable_resolution.py`
- `src/tests/aidb_shared/e2e/test_complex_workflows.py`

______________________________________________________________________

## Code Reuse

**Always use existing infrastructure:**

| Need            | Use                                                            |
| --------------- | -------------------------------------------------------------- |
| Base classes    | `BaseE2ETest`, `BaseIntegrationTest`, `FrameworkDebugTestBase` |
| Parametrization | `@parametrize_interfaces`, `@parametrize_languages`            |
| Assertions      | `self.verify_bp`, `self.verify_exec`, `MCPAssertions`          |
| Constants       | `StopReason`, `TestTimeouts`, `MCPTool`                        |

**Location:** `src/tests/_helpers/` and `src/tests/_fixtures/`

______________________________________________________________________

## Test Organization

```
src/tests/
├── aidb_shared/        # Language-agnostic debug fundamentals
│   ├── integration/    # Core debug operations
│   └── e2e/           # Complex workflows
├── aidb/              # Core API tests
├── aidb_mcp/          # MCP server tests
├── frameworks/        # Framework integration tests
│   ├── python/        # Flask, FastAPI, pytest
│   ├── javascript/    # Express, Jest
│   └── java/          # Spring Boot, JUnit
└── _helpers/          # Test infrastructure
```

______________________________________________________________________

## Generated Programs

**Location:** `src/tests/_assets/test_programs/generated/`

Programs are generated with semantic markers that map to the same logical location across languages.

```python
program = generated_program_factory("basic_variables", language)
# Returns: {"path": Path, "markers": {...}, "scenario": "basic_variables", "language": "python"}
```
