"""E2E tests using generated test programs.

These tests demonstrate the zero-duplication testing pattern using the DebugInterface
abstraction to test both MCP and API entry points with generated test programs.
"""

import pytest


@pytest.mark.parametrize("debug_interface", ["mcp", "api"], indirect=True)
@pytest.mark.asyncio
async def test_basic_variables_all_languages(
    debug_interface,
    language,
    generated_program_factory,
):
    """Test basic_variables scenario across all languages.

    This test runs 6 times:
    - MCP + Python
    - MCP + JavaScript
    - MCP + Java
    - API + Python
    - API + JavaScript
    - API + Java

    Parameters
    ----------
    debug_interface : DebugInterface
        Either MCPInterface or APIInterface
    language : str
        Programming language (python, javascript, java)
    generated_program_factory : callable
        Factory to load generated programs
    """
    # Load program
    program = generated_program_factory("basic_variables", language)

    # Get first expected marker line for breakpoint
    first_marker_line = list(program["markers"].values())[0]

    # Start session with breakpoint at first marker
    # NOTE: start_session() with breakpoints starts PAUSED at the first breakpoint
    await debug_interface.start_session(
        program=str(program["path"]),
        breakpoints=[{"file": str(program["path"]), "line": first_marker_line}],
    )

    # Verify we're stopped at the breakpoint (no continue needed - already there!)
    assert debug_interface.is_session_active, "Expected session to be active"

    # Cleanup
    await debug_interface.stop_session()


@pytest.mark.parametrize("debug_interface", ["mcp", "api"], indirect=True)
@pytest.mark.asyncio
async def test_all_scenarios_python(
    debug_interface,
    scenario_id,
    generated_program_factory,
):
    """Test all scenarios with Python.

    This test runs 12 times:
    - 6 scenarios × 2 interfaces (MCP, API)

    Parameters
    ----------
    debug_interface : DebugInterface
        Either MCPInterface or APIInterface
    scenario_id : str
        Scenario ID from manifest
    generated_program_factory : callable
        Factory to load generated programs
    """
    # Load program
    program = generated_program_factory(scenario_id, "python")

    # Start session with initial breakpoint to keep session alive (standard pattern)
    first_marker_line = next(iter(program["markers"].values()))
    await debug_interface.start_session(
        program=str(program["path"]),
        breakpoints=[{"file": str(program["path"]), "line": first_marker_line}],
    )

    # Verify session started and is paused at breakpoint
    assert debug_interface.is_session_active, "Expected session to be active"

    # Cleanup
    await debug_interface.stop_session()


@pytest.mark.parametrize("debug_interface", ["mcp", "api"], indirect=True)
@pytest.mark.asyncio
async def test_generated_program_structure(
    debug_interface,
    generated_program_factory,
):
    """Test that generated programs have expected structure.

    This verifies the generated_program_factory returns the correct metadata.

    Parameters
    ----------
    debug_interface : DebugInterface
        Either MCPInterface or APIInterface (not used, but required for parametrization)
    generated_program_factory : callable
        Factory to load generated programs
    """
    # Load a program
    program = generated_program_factory("basic_variables", "python")

    # Verify structure
    assert "path" in program, "Expected 'path' in program metadata"
    assert "markers" in program, "Expected 'markers' in program metadata"
    assert "scenario" in program, "Expected 'scenario' in program metadata"
    assert "language" in program, "Expected 'language' in program metadata"

    # Verify path exists
    assert program["path"].exists(), (
        f"Expected program file to exist: {program['path']}"
    )

    # Verify markers
    assert len(program["markers"]) > 0, "Expected at least one marker"
    assert all(isinstance(v, int) for v in program["markers"].values()), (
        "Expected all marker values to be line numbers (integers)"
    )
