"""Root pytest configuration and shared fixtures for AIDB test suite.

This module serves as the pytest entry point and imports fixtures from modular
components in the _conftest package. Pytest hooks must remain here for discovery, but
they delegate to functions in the modular package.
"""

import sys
from pathlib import Path

import pytest

# Add src directory to path for imports
src_path = Path(__file__).parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Initialize environment before any other imports
# Imports intentionally after path setup for environment initialization
from tests._conftest.environment import (  # noqa: E402
    configure_test_logging,
    resolve_env_template_early,
)

# CRITICAL: Resolve environment template BEFORE any AIDB imports
resolve_env_template_early()

# Configure logging on import
configure_test_logging()

# Import marker functions for pytest hooks
# Imports intentionally after environment setup
from tests._conftest.cleanup import (  # noqa: E402
    cleanup_orphaned_processes,  # noqa: F401
    cleanup_ports,  # noqa: F401
    reset_global_state,  # noqa: F401
)
from tests._conftest.markers import (  # noqa: E402
    add_default_language_marker,
    add_location_based_markers,
    add_parametrization_markers,
    add_pattern_based_markers,
    check_marker_requirements,
    register_custom_markers,
)
from tests._conftest.session import (  # noqa: E402
    cleanup_jdtls_project_pool,  # noqa: F401
    deterministic_session_environment,  # noqa: F401
    event_loop,  # noqa: F401
    setup_test_environment,  # noqa: F401
)
from tests._conftest.utils import (  # noqa: E402
    benchmark,  # noqa: F401
    test_data_dir,  # noqa: F401
)
from tests._fixtures.base import *  # noqa: E402, F401, F403
from tests._fixtures.docker_simple import *  # noqa: E402, F401, F403
from tests._fixtures.generated_programs import *  # noqa: E402, F401, F403
from tests._fixtures.java_lsp_pool import *  # noqa: E402, F401, F403
from tests._fixtures.mcp import *  # noqa: E402, F401, F403

# ============================================================================
# PYTEST HOOKS
# These must remain in conftest.py for pytest discovery
# ============================================================================


def pytest_sessionstart(session):
    """Set up test environment before running any tests.

    This hook runs BEFORE any tests are collected or executed.
    """


def pytest_configure(config):
    """Configure pytest hooks and markers."""
    register_custom_markers(config)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Override exit code if all tests ultimately passed after reruns.

    pytest-rerunfailures returns exit code 1 when tests are rerun, even if they
    ultimately pass. This hook overrides that behavior to return 0 when all tests
    eventually succeed, allowing the test suite to report success for flaky tests
    that pass on retry.

    Parameters
    ----------
    session : pytest.Session
        The pytest session object
    exitstatus : int
        The current exit status from pytest
    """
    if exitstatus != 0:
        # Get the terminal reporter to check final test outcomes
        terminalreporter = session.config.pluginmanager.get_plugin("terminalreporter")
        if terminalreporter:
            stats = terminalreporter.stats
            # If no failures or errors in final outcomes, override to success
            if not stats.get("failed") and not stats.get("error"):
                session.exitstatus = 0


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test location."""
    for item in items:
        add_location_based_markers(item)
        add_parametrization_markers(item)
        add_default_language_marker(item)
        add_pattern_based_markers(item)
        check_marker_requirements(item)


def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--run-slow",
        action="store_true",
        default=False,
        help="Run slow tests",
    )
    parser.addoption(
        "--run-flaky",
        action="store_true",
        default=False,
        help="Run flaky tests",
    )
    parser.addoption(
        "--language",
        action="store",
        default=None,
        help="Run tests for specific language adapter",
    )
