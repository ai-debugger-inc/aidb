"""Conftest utilities and fixtures package.

This package contains modular components of the test configuration that have been
split from the main conftest.py for better maintainability. The main conftest.py
imports from these modules to maintain pytest's fixture discovery requirements.

Modules
-------
markers
    Test marker registration and application functions
environment
    Environment setup and logging configuration
session
    Session-scoped fixtures (event loop, environment setup)
cleanup
    Autouse cleanup fixtures (processes, ports, global state)
utils
    Utility fixtures (test_data_dir, benchmark)
"""

from tests._conftest.cleanup import (
    cleanup_orphaned_processes,
    cleanup_ports,
    reset_global_state,
)
from tests._conftest.environment import (
    configure_test_logging,
    resolve_env_template_early,
)
from tests._conftest.markers import (
    add_default_language_marker,
    add_location_based_markers,
    add_parametrization_markers,
    add_pattern_based_markers,
    check_marker_requirements,
    register_custom_markers,
)
from tests._conftest.session import (
    cleanup_jdtls_project_pool,
    deterministic_session_environment,
    event_loop,
    setup_test_environment,
)
from tests._conftest.utils import benchmark, test_data_dir

__all__ = [
    # Markers
    "register_custom_markers",
    "add_location_based_markers",
    "add_parametrization_markers",
    "add_default_language_marker",
    "add_pattern_based_markers",
    "check_marker_requirements",
    # Environment
    "resolve_env_template_early",
    "configure_test_logging",
    # Session fixtures
    "event_loop",
    "setup_test_environment",
    "deterministic_session_environment",
    "cleanup_jdtls_project_pool",
    # Cleanup fixtures
    "cleanup_orphaned_processes",
    "cleanup_ports",
    "reset_global_state",
    # Utils
    "test_data_dir",
    "benchmark",
]
