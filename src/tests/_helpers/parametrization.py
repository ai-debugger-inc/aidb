"""Parametrization decorator utilities for common test patterns.

This module provides convenient decorator functions that wrap pytest.mark.parametrize
for common test parametrization scenarios.
"""

import functools
from collections.abc import Callable
from typing import Any, TypeVar, cast

import pytest

from aidb_common.constants import Language

F = TypeVar("F", bound=Callable[..., Any])


def parametrize_interfaces(func: F) -> F:
    """Parametrize test to run with MCP interface.

    This decorator applies pytest.mark.parametrize with the MCP interface type,
    using indirect=True for fixture injection.

    Note: The API interface was removed as part of the service layer refactor.
    All tests now run through MCP, which is the public interface for AI agents.

    Parameters
    ----------
    func : Callable
        Test function to parametrize

    Returns
    -------
    Callable
        Parametrized test function

    Examples
    --------
    >>> @parametrize_interfaces
    >>> async def test_something(debug_interface):
    >>>     # Runs with MCP interface
    >>>     pass
    """
    return pytest.mark.parametrize(
        "debug_interface",
        ["mcp"],
        indirect=True,
    )(func)


def parametrize_languages(languages: list[str] | None = None) -> Callable[[F], F]:
    """Parametrize test to run for specified languages.

    Parameters
    ----------
    languages : list[str], optional
        List of languages to test. If None, uses all supported languages
        (python, javascript, java)

    Returns
    -------
    Callable
        Decorator function

    Examples
    --------
    >>> @parametrize_languages()
    >>> async def test_all_languages(language):
    >>>     # Runs for python, javascript, java
    >>>     pass

    >>> @parametrize_languages(["python", "javascript"])
    >>> async def test_py_js(language):
    >>>     # Runs for python, javascript only
    >>>     pass
    """
    if languages is None:
        languages = [lang.value for lang in Language]

    def decorator(func: F) -> F:
        return pytest.mark.parametrize("language", languages)(func)

    return decorator


def parametrize_scenarios(*scenario_names: str) -> Callable[[F], F]:
    """Parametrize test to run for specified test scenarios.

    Parameters
    ----------
    *scenario_names : str
        Names of scenarios to test

    Returns
    -------
    Callable
        Decorator function

    Examples
    --------
    >>> @parametrize_scenarios("basic_variables", "control_flow")
    >>> async def test_scenarios(scenario_id):
    >>>     # Runs for basic_variables and control_flow scenarios
    >>>     pass
    """

    def decorator(func: F) -> F:
        return pytest.mark.parametrize("scenario_id", scenario_names)(func)

    return decorator


def parametrize_full_matrix(
    languages: list[str] | None = None,
    scenarios: list[str] | None = None,
) -> Callable[[F], F]:
    """Parametrize test for full combinatorial matrix.

    Runs test for all combinations of:
    - Interfaces (MCP, API)
    - Languages (specified or all)
    - Scenarios (specified or all from fixture)

    Parameters
    ----------
    languages : list[str], optional
        Languages to test. If None, uses default language fixture
    scenarios : list[str], optional
        Scenarios to test. If None, relies on scenario_id fixture

    Returns
    -------
    Callable
        Decorator function

    Examples
    --------
    >>> @parametrize_full_matrix(languages=["python"], scenarios=["basic_variables"])
    >>> async def test_matrix(debug_interface, language, scenario_id):
    >>>     # Runs 2 times: MCP+python+basic_variables, API+python+basic_variables
    >>>     pass
    """

    def decorator(func: F) -> F:
        # Apply interface parametrization
        decorated = parametrize_interfaces(func)

        # Apply language parametrization if specified
        if languages is not None:
            decorated = pytest.mark.parametrize("language", languages)(decorated)

        # Apply scenario parametrization if specified
        if scenarios is not None:
            decorated = pytest.mark.parametrize("scenario_id", scenarios)(decorated)

        return decorated

    return decorator


def parametrize_interface_language_pairs(
    pairs: list[tuple[str, str]],
) -> Callable[[F], F]:
    """Parametrize test for specific interface-language combinations.

    Useful for testing specific combinations that may have unique behavior.

    Parameters
    ----------
    pairs : list[tuple[str, str]]
        List of (interface, language) tuples

    Returns
    -------
    Callable
        Decorator function

    Examples
    --------
    >>> @parametrize_interface_language_pairs([
    >>>     ("mcp", "python"),
    >>>     ("api", "java"),
    >>> ])
    >>> async def test_pairs(debug_interface, language):
    >>>     # Runs only for specified combinations
    >>>     pass
    """

    def decorator(func: F) -> F:
        return pytest.mark.parametrize(
            ("debug_interface", "language"),
            pairs,
            indirect=["debug_interface"],
        )(func)

    return decorator


def skip_if_interface(interface_type: str, reason: str = "") -> Callable[[F], F]:
    """Skip test for a specific interface type.

    Parameters
    ----------
    interface_type : str
        Interface type to skip ("mcp" or "api")
    reason : str, optional
        Reason for skipping

    Returns
    -------
    Callable
        Decorator function

    Examples
    --------
    >>> @parametrize_interfaces
    >>> @skip_if_interface("mcp", reason="MCP not implemented yet")
    >>> async def test_feature(debug_interface):
    >>>     # Skips MCP, runs API
    >>>     pass
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Check if debug_interface fixture is present
            debug_interface = kwargs.get("debug_interface")

            if debug_interface is not None:
                # Get interface type name from class
                interface_name = debug_interface.__class__.__name__.lower()

                if interface_type in interface_name:
                    pytest.skip(reason or f"Skipping for {interface_type} interface")

            return func(*args, **kwargs)

        return cast("F", wrapper)

    return decorator


def skip_if_language(language: str, reason: str = "") -> Callable[[F], F]:
    """Skip test for a specific language.

    Parameters
    ----------
    language : str
        Language to skip
    reason : str, optional
        Reason for skipping

    Returns
    -------
    Callable
        Decorator function

    Examples
    --------
    >>> @parametrize_languages()
    >>> @skip_if_language("java", reason="Java not supported yet")
    >>> async def test_feature(language):
    >>>     # Skips Java, runs Python and JavaScript
    >>>     pass
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            test_language = kwargs.get("language")

            if test_language == language:
                pytest.skip(reason or f"Skipping for {language}")

            return func(*args, **kwargs)

        return cast("F", wrapper)

    return decorator


def require_adapter(language: str) -> Callable[[F], F]:
    """Skip test if debug adapter for language is not available.

    Parameters
    ----------
    language : str
        Language requiring adapter

    Returns
    -------
    Callable
        Decorator function

    Examples
    --------
    >>> @require_adapter("java")
    >>> async def test_java_debugging(debug_interface):
    >>>     # Skips if Java adapter not available
    >>>     pass
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # In the future, this could check for actual adapter availability
            # For now, it's a placeholder for the pattern
            return func(*args, **kwargs)

        return cast("F", wrapper)

    return decorator
