"""Fixtures for generated test programs."""

__all__ = [
    # Core fixtures
    "generated_programs_manifest",
    "generated_program_factory",
    "scenario_id",
    # Re-exports from other fixture modules
    "docker_test_mode",
    "java_precompilation_manager",
    "java_session_pool",
]

import json
from pathlib import Path
from typing import Any

import pytest

# Import existing docker_test_mode from docker_simple (re-export for convenience)
from .docker_simple import docker_test_mode  # noqa: F401
from .java_precompilation import java_precompilation_manager  # noqa: F401
from .java_session_pool import java_session_pool  # noqa: F401

MANIFEST_PATH = (
    Path(__file__).parent.parent
    / "_assets"
    / "test_programs"
    / "generated"
    / "manifest.json"
)


@pytest.fixture(scope="session")
def generated_programs_manifest() -> dict[str, Any]:
    """Load manifest of generated test programs.

    Returns
    -------
    dict[str, Any]
        Manifest with scenarios, expected markers, file paths
    """
    with MANIFEST_PATH.open() as f:
        return json.load(f)


@pytest.fixture
def generated_program_factory(
    generated_programs_manifest: dict[str, Any],
    docker_test_mode: bool,
    java_precompilation_manager,
):
    """Factory to load generated test programs with Docker/local path support.

    For Java programs, uses precompiled .class files from session-scoped
    precompilation to eliminate per-test compilation overhead.

    Parameters
    ----------
    generated_programs_manifest : dict[str, Any]
        The loaded manifest
    docker_test_mode : bool
        Whether running in Docker
    java_precompilation_manager : JavaPrecompilationManager
        Session-scoped precompilation manager for Java programs

    Yields
    ------
    callable
        Function(scenario_id: str, language: str) -> dict[str, Any]

    Examples
    --------
    >>> program = generated_program_factory("basic_variables", "python")
    >>> program["path"]  # Path to test_program.py
    >>> program["markers"]  # Expected markers from manifest
    >>> program["scenario"]  # Full scenario metadata
    """

    def _load(scenario_id: str, language: str) -> dict[str, Any]:
        """Load a generated test program.

        Parameters
        ----------
        scenario_id : str
            Scenario ID (e.g., "basic_variables")
        language : str
            Language (python, javascript, java)

        Returns
        -------
        dict[str, Any]
            Program metadata with path, markers, scenario, language
        """
        scenario = generated_programs_manifest["scenarios"][scenario_id]

        # Docker vs local path resolution
        if docker_test_mode:
            # In Docker: /workspace/src/tests/_assets/...
            base = Path("/workspace/src/tests/_assets/test_programs/generated")
        else:
            # Local: relative to this file
            base = (
                Path(__file__).parent.parent / "_assets" / "test_programs" / "generated"
            )

        # Language-specific filename
        filenames = {
            "java": "TestProgram.java",
            "javascript": "test_program.js",
            "python": "test_program.py",
        }
        program_path = base / scenario_id / filenames[language]

        return {
            "path": program_path,
            "markers": scenario["expected_markers"][language],
            "scenario": scenario,
            "language": language,
        }

    return _load


@pytest.fixture(
    params=[
        "array_operations",
        "basic_exception",
        "basic_for_loop",
        "basic_variables",
        "basic_while_loop",
        "complex_expressions",
        "conditionals",
        "function_chain",
        "infinite_loop_with_counter",
        "large_array_operations",
        "nested_conditionals",
        "nested_loops",
        "recursive_stack_overflow",
        "simple_function",
        # Note: syntax_error_unclosed_bracket is excluded because it contains
        # intentional syntax errors and cannot be debugged. Error handling
        # scenarios require dedicated tests with appropriate expectations.
    ],
)
def scenario_id(request):
    """Parametrize tests across all scenarios.

    Use this to run a test against all scenarios.

    Examples
    --------
    >>> def test_scenario(scenario_id, language, generated_program_factory):
    >>>     program = generated_program_factory(scenario_id, language)
    >>>     # Test runs 15 times (once per scenario)

    Parameters
    ----------
    request : pytest.FixtureRequest
        Pytest request object

    Returns
    -------
    str
        Scenario ID
    """
    return request.param
