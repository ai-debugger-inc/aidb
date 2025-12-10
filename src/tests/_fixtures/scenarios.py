"""Scenario-based fixtures for testing.

This module provides fixtures for generating complete test setups, consolidating test
file creation patterns that are currently repeated across multiple test files.
"""

__all__ = [
    # Scenario factory fixtures
    "debug_scenario_factory",
    "simple_breakpoint_scenario",
    "multi_breakpoint_scenario",
    "conditional_breakpoint_scenario",
    "error_scenario",
    "multi_file_scenario",
    "session_scenario_factory",
    "language_matrix_scenarios",
    "scenario_builder_factory",
    # Parametrized fixtures
    "language",
    "scenario_type",
    "with_breakpoints",
    # Standard scenarios
    "standard_test_scenarios",
]

from pathlib import Path
from typing import Any, Optional, Union

import pytest

from aidb_common.constants import SUPPORTED_LANGUAGES, Language
from tests._assets.test_content import get_test_content
from tests._helpers.session_manager import ScenarioBuilder, SessionManager


def _get_file_extension(language: str) -> str:
    """Get file extension for language.

    Parameters
    ----------
    language : str
        Programming language

    Returns
    -------
    str
        File extension
    """
    extensions = {
        "python": ".py",
        "javascript": ".js",
        "java": ".java",
    }
    return extensions.get(language, ".txt")


def _inject_errors(content: str, language: str) -> str:
    """Inject intentional errors into content for testing.

    Parameters
    ----------
    content : str
        Original content
    language : str
        Programming language

    Returns
    -------
    str
        Content with errors injected
    """
    error_injections = {
        "python": ("return", "retrun"),  # Typo
        "javascript": ("const", "cnst"),  # Typo
        "java": ("public", "publik"),  # Typo
    }

    if language in error_injections:
        original, replacement = error_injections[language]
        return content.replace(original, replacement)
    return content


def _create_test_file(
    temp_workspace: Path,
    fname: str,
    ext: str,
    language: str,
    scenario: str,
    with_errors: bool,
) -> Path:
    """Create a single test file.

    Parameters
    ----------
    temp_workspace : Path
        Workspace directory
    fname : str
        File name
    ext : str
        File extension
    language : str
        Programming language
    scenario : str
        Scenario type
    with_errors : bool
        Whether to inject errors

    Returns
    -------
    Path
        Created file path
    """
    if not fname.endswith(ext):
        fname += ext

    file_path = temp_workspace / fname
    content = get_test_content(language, scenario)

    if with_errors:
        content = _inject_errors(content, language)

    file_path.write_text(content)
    return file_path


def _create_multiple_files(
    temp_workspace: Path,
    language: str,
    scenario_type: str,
    ext: str,
    file_name: str | None,
    with_errors: bool,
) -> list[Path]:
    """Create multiple test files for a scenario.

    Parameters
    ----------
    temp_workspace : Path
        Workspace directory
    language : str
        Programming language
    scenario_type : str
        Type of scenario
    ext : str
        File extension
    file_name : str | None
        Custom file name
    with_errors : bool
        Whether to inject errors

    Returns
    -------
    list[Path]
        Created file paths
    """
    files = []
    scenarios = (
        ["calculate_function", "control_flow"]
        if scenario_type == "hello_world"
        else [scenario_type, "hello_world"]
    )

    for i, scenario in enumerate(scenarios):
        fname = f"test_{scenario}{ext}" if not file_name or i > 0 else file_name
        # Only inject errors in first file
        inject_errors = with_errors and i == 0
        file_path = _create_test_file(
            temp_workspace,
            fname,
            ext,
            language,
            scenario,
            inject_errors,
        )
        files.append(file_path)

    return files


def _process_breakpoints(
    breakpoints: list[int | str] | None,
    main_file: Path,
) -> list[str]:
    """Process breakpoint specifications.

    Parameters
    ----------
    breakpoints : list[int | str] | None
        Raw breakpoint specifications
    main_file : Path
        Main file path

    Returns
    -------
    list[str]
        Processed breakpoints
    """
    if not breakpoints:
        return []

    processed = []
    for bp in breakpoints:
        if isinstance(bp, int) or ":" not in str(bp):
            processed.append(f"{main_file}:{bp}")
        else:
            processed.append(str(bp))
    return processed


@pytest.fixture
def debug_scenario_factory(temp_workspace):
    """Create complete debug scenarios.

    This fixture consolidates the common pattern of:
    1. Creating test files with specific content
    2. Setting up breakpoints
    3. Configuring debug sessions

    Returns
    -------
    callable
        A factory function that creates debug scenarios
    """

    def create(
        language: str = "python",
        scenario_type: str = "hello_world",
        with_errors: bool = False,
        breakpoints: list[int | str] | None = None,
        multiple_files: bool = False,
        file_name: str | None = None,
    ) -> dict[str, Any]:
        """Create a debug scenario.

        Parameters
        ----------
        language : str
            Programming language (python, javascript, java)
        scenario_type : str
            Type of scenario from test_content.py
        with_errors : bool
            Whether to include intentional errors
        breakpoints : Optional[List[Union[int, str]]]
            Breakpoint locations
        multiple_files : bool
            Whether to create multiple test files
        file_name : Optional[str]
            Custom name for the test file

        Returns
        -------
        Dict[str, Any]
            Scenario data including:
            - files: List of created file paths
            - breakpoints: List of breakpoint specs
            - language: Language used
            - scenario: Scenario type
            - workspace: Workspace directory

        Raises
        ------
        ValueError
            If scenario_type is invalid or language is unsupported
        """
        # Validate scenario type exists
        try:
            # Try to get content to validate scenario exists
            _ = get_test_content(language, scenario_type)
        except (KeyError, ValueError) as e:
            msg = f"Unknown scenario: {scenario_type}. Error: {e}"
            raise ValueError(msg) from e

        # Get file extension
        ext = _get_file_extension(language)

        # Create files
        if multiple_files:
            files = _create_multiple_files(
                temp_workspace,
                language,
                scenario_type,
                ext,
                file_name,
                with_errors,
            )
        else:
            # Single file
            fname = file_name or f"test_{scenario_type}{ext}"
            file_path = _create_test_file(
                temp_workspace,
                fname,
                ext,
                language,
                scenario_type,
                with_errors,
            )
            files = [file_path]

        # Process breakpoints
        if not files:
            msg = "No files were created for the scenario"
            raise ValueError(msg)
        processed_breakpoints = _process_breakpoints(
            breakpoints,
            files[0],
        )

        return {
            "files": files,
            "breakpoints": processed_breakpoints,
            "language": language,
            "scenario": scenario_type,
            "workspace": temp_workspace,
            "with_errors": with_errors,
        }

    return create


@pytest.fixture
def simple_breakpoint_scenario(debug_scenario_factory):
    """Pre-configured scenario with a simple breakpoint."""

    def create(language: str = "python") -> dict[str, Any]:
        return debug_scenario_factory(
            language=language,
            scenario_type="calculate_function",
            breakpoints=[3],  # Breakpoint on function body
        )

    return create


@pytest.fixture
def multi_breakpoint_scenario(debug_scenario_factory):
    """Pre-configured scenario with multiple breakpoints."""

    def create(language: str = "python") -> dict[str, Any]:
        return debug_scenario_factory(
            language=language,
            scenario_type="control_flow",
            breakpoints=[3, 8, 12],  # Multiple breakpoints
        )

    return create


@pytest.fixture
def conditional_breakpoint_scenario(debug_scenario_factory):
    """Pre-configured scenario for conditional breakpoint testing."""

    def create(language: str = "python") -> dict[str, Any]:
        scenario = debug_scenario_factory(
            language=language,
            scenario_type="loop_function",
            breakpoints=[],  # Will add conditional breakpoints separately
        )
        # Add info about where conditional breakpoints can be set
        scenario["conditional_locations"] = {
            "loop_line": 3,  # Inside loop
            "condition_expr": "i > 5",  # Example condition
        }
        return scenario

    return create


@pytest.fixture
def error_scenario(debug_scenario_factory):
    """Pre-configured scenario with intentional errors."""

    def create(language: str = "python") -> dict[str, Any]:
        return debug_scenario_factory(
            language=language,
            scenario_type="exception_handling",
            with_errors=True,
            breakpoints=[2],  # Breakpoint before error
        )

    return create


@pytest.fixture
def multi_file_scenario(debug_scenario_factory):
    """Pre-configured scenario with multiple files."""

    def create(language: str = "python") -> dict[str, Any]:
        return debug_scenario_factory(
            language=language,
            scenario_type="calculate_function",
            multiple_files=True,
            breakpoints=[3, "test_control_flow.py:8"],  # Breakpoints in both files
        )

    return create


@pytest.fixture
def session_scenario_factory(call_tool, debug_scenario_factory):
    """Combine scenario creation with session management.

    This fixture provides a complete workflow:
    1. Creates test scenario
    2. Initializes debugging context
    3. Starts debug session
    4. Returns everything needed for testing
    """

    async def create(
        language: str = "python",
        scenario_type: str = "hello_world",
        auto_start: bool = True,
        **kwargs,
    ) -> dict[str, Any]:
        """Create scenario and optionally start session.

        Parameters
        ----------
        language : str
            Programming language
        scenario_type : str
            Scenario type
        auto_start : bool
            Whether to automatically start the debug session
        **kwargs
            Additional arguments passed to scenario factory

        Returns
        -------
        Dict[str, Any]
            Complete test setup including:
            - scenario: Created scenario data
            - session_manager: SessionManager instance
            - session_id: Session ID (if auto_start)
            - session_data: Session data (if auto_start)
        """
        # Create scenario
        scenario = debug_scenario_factory(
            language=language,
            scenario_type=scenario_type,
            **kwargs,
        )

        # Create session manager
        session_manager = SessionManager(call_tool)

        result = {
            "scenario": scenario,
            "session_manager": session_manager,
        }

        if auto_start:
            # Start session
            session_id, session_data = await session_manager.create_debug_session(
                language=language,
                scenario=scenario_type,
                temp_dir=scenario["workspace"],
                breakpoints=scenario["breakpoints"],
                file_name=scenario["files"][0].name if scenario["files"] else None,
            )

            result["session_id"] = session_id
            result["session_data"] = session_data

        return result

    return create


@pytest.fixture
def language_matrix_scenarios(debug_scenario_factory):
    """Create identical scenarios across all languages for matrix testing."""

    def create(scenario_type: str = "hello_world") -> dict[str, dict[str, Any]]:
        """Create the same scenario in all supported languages.

        Parameters
        ----------
        scenario_type : str
            Scenario type to create

        Returns
        -------
        Dict[str, Dict[str, Any]]
            Scenarios keyed by language
        """
        languages = SUPPORTED_LANGUAGES
        scenarios = {}

        for lang in languages:
            scenarios[lang] = debug_scenario_factory(
                language=lang,
                scenario_type=scenario_type,
                breakpoints=[3],  # Same breakpoint location
            )

        return scenarios

    return create


@pytest.fixture
def scenario_builder_factory(call_tool, temp_workspace):
    """Create ScenarioBuilder instances.

    This provides the fluent interface for building complex scenarios.
    """

    def create() -> ScenarioBuilder:
        """Create a new ScenarioBuilder.

        Returns
        -------
        ScenarioBuilder
            Builder instance configured with workspace
        """
        session_manager = SessionManager(call_tool)
        builder = ScenarioBuilder(session_manager)
        builder.in_directory(temp_workspace)
        return builder

    return create


# Parameterized fixtures for common test patterns


@pytest.fixture(params=[Language.PYTHON, Language.JAVASCRIPT, Language.JAVA])
def language(request):
    """Parameterized fixture for testing across languages."""
    return request.param.value


@pytest.fixture(
    params=["hello_world", "calculate_function", "control_flow", "exception_handling"],
)
def scenario_type(request):
    """Parameterized fixture for testing across scenario types."""
    return request.param


@pytest.fixture(params=[True, False])
def with_breakpoints(request):
    """Parameterized fixture for testing with/without breakpoints."""
    return request.param


@pytest.fixture
def standard_test_scenarios():
    """Provide standard test scenarios used across tests.

    Returns a dictionary of pre-configured scenarios that can be used to reduce
    duplication in test files.
    """
    return {
        "simple": {
            "scenario": "hello_world",
            "breakpoints": [],
        },
        "function": {
            "scenario": "calculate_function",
            "breakpoints": [3],
        },
        "control": {
            "scenario": "control_flow",
            "breakpoints": [3, 8],
        },
        "loop": {
            "scenario": "loop_function",
            "breakpoints": [3],
        },
        "exception": {
            "scenario": "exception_handling",
            "breakpoints": [2, 6],
        },
        "async": {
            "scenario": "async_function",
            "breakpoints": [3],
        },
        "class": {
            "scenario": "class_methods",
            "breakpoints": [5, 9],
        },
    }
