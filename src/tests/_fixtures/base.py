"""Core fixtures for AIDB test suite.

This module provides fundamental fixtures used across all test types.
"""

__all__ = [
    # Workspace fixtures
    "temp_workspace",
    "debug_session",
    # Mock fixtures
    "mock_adapter",
    "mock_dap_client",
    "mock_session_manager",
    # Utility fixtures
    "test_logger",
    "performance_tracker",
    "isolated_port_registry",
    "sample_launch_config",
    "create_launch_json",
    "env_vars",
    "assert_eventually",
    # Autouse fixtures
    "reset_singletons",
    "cleanup_async_tasks",
    # Logging fixtures
    "captured_logs",
    "isolated_logger",
    "log_context",
    "multi_logger_capture",
    "aidb_logs",
    "mcp_logs",
    "all_logs",
    "suppress_logs",
    "assert_logs",
    # Debug interface fixtures
    "debug_interface",
    "debug_interface_factory",
]

import asyncio
import contextlib
import json
import logging
import os
import tempfile
import time
from collections.abc import AsyncGenerator, Callable, Generator
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional
from unittest.mock import MagicMock, patch

import pytest

from aidb.common.context import AidbContext
from aidb.resources.ports import PortRegistry
from aidb.session import SessionManager
from aidb_common.io import is_event_loop_error
from aidb_logging import get_test_logger
from tests._fixtures.logging_fixtures import (
    aidb_logs,
    all_logs,
    assert_logs,
    captured_logs,
    isolated_logger,
    log_context,
    mcp_logs,
    multi_logger_capture,
    suppress_logs,
)
from tests._helpers.constants import (
    DebugInterfaceType,
    DebugPorts,
    EnvVar,
    Language,
    LogLevel,
    PortRanges,
)

if TYPE_CHECKING:
    # Only imported for typing to avoid runtime import cycles/cost
    from tests._helpers.debug_interface import DebugInterface

logger = get_test_logger(__name__)


@pytest.fixture
def temp_workspace() -> Generator[Path, None, None]:
    """Provide an isolated temporary directory with automatic cleanup.

    Yields
    ------
    Path
        Path to temporary directory
    """
    with tempfile.TemporaryDirectory(prefix="aidb_test_") as tmpdir:
        workspace = Path(tmpdir)

        # Create common subdirectories
        (workspace / "src").mkdir()
        (workspace / "tests").mkdir()
        (workspace / ".vscode").mkdir()

        yield workspace

        # Cleanup is automatic with TemporaryDirectory


@pytest.fixture
async def debug_session(temp_workspace: Path) -> AsyncGenerator[dict[str, Any], None]:
    """Provide a reusable debug session with auto-cleanup.

    Parameters
    ----------
    temp_workspace : Path
        Temporary workspace directory

    Yields
    ------
    Dict[str, Any]
        Session information including ID and session manager
    """
    session_manager = SessionManager()
    session_id = f"test_session_{time.time()}"

    # Create a simple test file
    test_file = temp_workspace / "test.py"
    test_file.write_text(
        """
def main():
    x = 1
    y = 2
    result = x + y  # Breakpoint here
    print(f"Result: {result}")
    return result

if __name__ == "__main__":
    main()
""",
    )

    session_info = {
        "id": session_id,
        "session_manager": session_manager,
        "workspace": temp_workspace,
        "test_file": test_file,
        "active": False,
    }

    yield session_info

    # Cleanup: Stop session if active
    if session_info.get("active") and session_info.get("session"):
        with contextlib.suppress(Exception):
            await session_info["session"].stop()


@pytest.fixture
def mock_adapter() -> MagicMock:
    """Provide a configurable mock adapter for testing.

    Returns
    -------
    MagicMock
        Mock adapter with common methods configured
    """
    adapter = MagicMock()

    # Configure common adapter methods
    adapter.name = "mock_adapter"
    adapter.language = Language.PYTHON.value
    adapter.get_configuration.return_value = {
        "default_port": DebugPorts.PYTHON,
        "fallback_ranges": PortRanges.PYTHON[:2],
        "command": ["python", "-m", "debugpy"],
        "adapter_type": "debugpy",
    }

    # Mock async methods
    async def mock_launch(*args, **kwargs):
        return {"success": True, "port": DebugPorts.PYTHON}

    async def mock_attach(*args, **kwargs):
        return {"success": True}

    adapter.launch = MagicMock(side_effect=mock_launch)
    adapter.attach = MagicMock(side_effect=mock_attach)
    adapter.terminate = MagicMock(return_value=None)

    return adapter


@pytest.fixture
def test_logger() -> logging.Logger:
    """Provide a configured logger for tests.

    Returns
    -------
    logging.Logger
        Configured test logger
    """
    logger = logging.getLogger("aidb_test")
    logger.setLevel(os.getenv(EnvVar.AIDB_LOG_LEVEL.value, LogLevel.INFO.value))

    # Add console handler if not present
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


@pytest.fixture
def performance_tracker() -> dict[str, Any]:
    """Provide timing and resource tracking for performance tests.

    Returns
    -------
    Dict[str, Any]
        Performance tracking utilities
    """
    tracker: dict[str, Any] = {"timings": {}, "memory": {}, "start_time": None}

    def start_timing(name: str):
        """Start timing an operation."""
        tracker["timings"][name] = {"start": time.time()}

    def end_timing(name: str):
        """End timing an operation."""
        if name in tracker["timings"]:
            tracker["timings"][name]["end"] = time.time()
            tracker["timings"][name]["duration"] = (
                tracker["timings"][name]["end"] - tracker["timings"][name]["start"]
            )

    def get_duration(name: str) -> float | None:
        """Get duration of a timed operation."""
        if name in tracker["timings"] and "duration" in tracker["timings"][name]:
            return tracker["timings"][name]["duration"]
        return None

    tracker["start_timing"] = start_timing
    tracker["end_timing"] = end_timing
    tracker["get_duration"] = get_duration

    return tracker


@pytest.fixture
def isolated_port_registry(temp_workspace: Path) -> Generator[PortRegistry, None, None]:
    """Provide an isolated PortRegistry for testing.

    Parameters
    ----------
    temp_workspace : Path
        Temporary workspace for registry files

    Yields
    ------
    PortRegistry
        Isolated port registry instance
    """
    # Create isolated context with temp storage
    with patch.object(AidbContext, "get_storage_path") as mock_storage:
        # Make storage use temp workspace
        def get_temp_storage(category: str, filename: str) -> Path:
            path = temp_workspace / ".aidb" / category
            path.mkdir(parents=True, exist_ok=True)
            return path / filename

        mock_storage.side_effect = get_temp_storage

        ctx = AidbContext()
        registry = PortRegistry(ctx=ctx)

        yield registry

        # Cleanup all allocated ports
        with contextlib.suppress(Exception):
            registry.cleanup_stale_allocations()


@pytest.fixture
def mock_dap_client() -> MagicMock:
    """Provide a mock DAP client for testing.

    Returns
    -------
    MagicMock
        Mock DAP client with common methods
    """
    client = MagicMock()

    # Configure common DAP client methods
    client.is_connected = False
    client.capabilities = {
        "supportsConfigurationDoneRequest": True,
        "supportsSetVariable": True,
        "supportsConditionalBreakpoints": True,
        "supportsHitConditionalBreakpoints": True,
        "supportsLogPoints": True,
    }

    # Mock request methods
    async def mock_request(command: str, args: dict | None = None):
        responses = {
            "initialize": {"capabilities": client.capabilities},
            "launch": {"success": True},
            "attach": {"success": True},
            "setBreakpoints": {"breakpoints": []},
            "configurationDone": {"success": True},
            "continue": {"allThreadsContinued": True},
            "next": {"success": True},
            "stepIn": {"success": True},
            "stepOut": {"success": True},
            "disconnect": {"success": True},
        }
        return responses.get(command, {"success": True})

    client.request = MagicMock(side_effect=mock_request)

    return client


@pytest.fixture
def sample_launch_config() -> dict[str, Any]:
    """Provide a sample VS Code launch configuration.

    Returns
    -------
    Dict[str, Any]
        Sample launch.json configuration
    """
    return {
        "version": "0.2.0",
        "configurations": [
            {
                "name": "Python: Current File",
                "type": "python",
                "request": "launch",
                "program": "${file}",
                "console": "integratedTerminal",
                "justMyCode": True,
            },
            {
                "name": "Python: Debug Tests",
                "type": "python",
                "request": "launch",
                "module": "pytest",
                "args": ["-xvs"],
                "console": "integratedTerminal",
                "justMyCode": False,
            },
            {
                "name": "Node: Current File",
                "type": "node",
                "request": "launch",
                "program": "${file}",
                "skipFiles": ["<node_internals>/**"],
                "console": "integratedTerminal",
            },
        ],
    }


@pytest.fixture
def create_launch_json(temp_workspace: Path):
    """Create launch.json files for testing.

    Parameters
    ----------
    temp_workspace : Path
        Workspace directory

    Returns
    -------
    callable
        Function to create launch.json with given config
    """

    def _create_launch_json(config: dict[str, Any] | None = None) -> Path:
        """Create a launch.json file.

        Parameters
        ----------
        config : Dict[str, Any], optional
            Launch configuration (uses default if not provided)

        Returns
        -------
        Path
            Path to created launch.json
        """
        vscode_dir = temp_workspace / ".vscode"
        vscode_dir.mkdir(exist_ok=True)

        launch_file = vscode_dir / "launch.json"

        if config is None:
            # Use a simple default config
            config = {
                "version": "0.2.0",
                "configurations": [
                    {
                        "name": "Debug",
                        "type": "python",
                        "request": "launch",
                        "program": "${file}",
                    },
                ],
            }

        launch_file.write_text(json.dumps(config, indent=2))
        return launch_file

    return _create_launch_json


@pytest.fixture
def env_vars() -> dict[str, str]:
    """Provide test environment variables.

    Returns
    -------
    Dict[str, str]
        Common test environment variables
    """
    return {
        EnvVar.AIDB_LOG_LEVEL.value: LogLevel.DEBUG.value,
        EnvVar.AIDB_ADAPTER_TRACE.value: "1",
        EnvVar.AIDB_TEST_MODE.value: "1",
        EnvVar.PYTHONDONTWRITEBYTECODE.value: "1",
        EnvVar.NODE_ENV.value: "test",
    }


@pytest.fixture
async def mock_session_manager() -> AsyncGenerator[SessionManager, None]:
    """Provide a mock SessionManager for testing.

    Yields
    ------
    SessionManager
        Mock session manager instance
    """
    with patch("aidb.session.session_manager.SessionManager") as mock_session_manager:
        manager = mock_session_manager.return_value

        # Configure mock methods
        manager.sessions = {}
        manager.create_session = MagicMock(return_value="test_session_123")
        manager.get_session = MagicMock(return_value=None)
        manager.stop_session = MagicMock(return_value=True)
        manager.list_sessions = MagicMock(return_value=[])

        yield manager


@pytest.fixture
def assert_eventually():
    """Provide an assertion helper for eventual conditions.

    Returns
    -------
    callable
        Function to assert eventual conditions
    """

    async def _assert_eventually(
        condition: Callable[[], bool],
        timeout: float = 5.0,
        interval: float = 0.1,
        message: str = "Condition not met within timeout",
    ):
        """Assert that a condition eventually becomes true.

        Parameters
        ----------
        condition : Callable[[], bool]
            Condition to check
        timeout : float
            Maximum wait time
        interval : float
            Check interval
        message : str
            Failure message
        """
        start = time.time()
        last_exception = None

        while time.time() - start < timeout:
            try:
                if asyncio.iscoroutinefunction(condition):
                    result = await condition()
                else:
                    result = condition()

                if result:
                    return
            except Exception as e:
                last_exception = e

            await asyncio.sleep(interval)

        if last_exception:
            msg = f"{message}: {last_exception}"
            raise AssertionError(msg)
        raise AssertionError(message)

    return _assert_eventually


# Autouse fixtures for common setup


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances between tests.

    This prevents test interference through shared singleton state.
    """
    # Clear singleton instances
    from aidb_common.patterns import Singleton

    # Store original instances
    original_instances = Singleton._instances.copy()

    yield

    # Restore original instances
    Singleton._instances = original_instances


@pytest.fixture(autouse=True)
def cleanup_async_tasks():
    """Ensure all async tasks are cleaned up after each test."""
    yield

    # Get all running tasks
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
    except RuntimeError:
        pass  # No event loop


# ============================================================================
# DebugInterface Fixture (for shared MCP/API tests)
# ============================================================================


def _extract_language_from_path(request: Any) -> str | None:
    """Extract language from framework test path.

    Detects language from test file path pattern /frameworks/{language}/.
    This enables automatic language detection for framework tests without
    requiring per-language fixture overrides.

    Parameters
    ----------
    request : FixtureRequest
        pytest request object

    Returns
    -------
    str | None
        Language name if detected from path, None otherwise

    Examples
    --------
    >>> # Test in /tests/frameworks/python/flask/test_foo.py
    >>> _extract_language_from_path(request)
    'python'

    >>> # Test in /tests/frameworks/javascript/jest/test_bar.py
    >>> _extract_language_from_path(request)
    'javascript'
    """
    from aidb_common.constants import SUPPORTED_LANGUAGES

    test_path_str = str(request.node.fspath)

    for lang in SUPPORTED_LANGUAGES:
        if f"/frameworks/{lang}/" in test_path_str:
            return lang

    return None


@pytest.fixture
async def debug_interface(
    request,
    temp_workspace: Path,
) -> AsyncGenerator["DebugInterface", None]:
    """Provide an MCP debug interface for testing.

    Scope: function - Each test gets fresh interface to avoid state leakage.

    Parameters
    ----------
    request : FixtureRequest
        pytest request object with params
    temp_workspace : Path
        Temporary workspace directory

    Yields
    ------
    DebugInterface
        MCPInterface instance

    Examples
    --------
    Use the interface in tests:

    >>> async def test_breakpoint(debug_interface):
    >>>     await debug_interface.initialize(language="python")
    >>>     # Test runs with MCP interface
    """
    from tests._helpers.debug_interface import MCPInterface

    # Get language with priority:
    # 1. From 'language' fixture (explicit parametrization)
    # 2. From test path (framework tests in /frameworks/{lang}/)
    # 3. From 'language' marker (backup)
    # 4. Default to "python"
    language = None

    # Check if 'language' fixture was used in test
    if "language" in request.fixturenames:
        language = request.getfixturevalue("language")

    # Fall back to path-based detection for framework tests
    if not language:
        language = _extract_language_from_path(request)

    # Fall back to marker if path detection didn't work
    if not language:
        language_marker = request.node.get_closest_marker("language")
        language = language_marker.args[0] if language_marker else "python"

    # Create MCP interface
    interface = MCPInterface(language=language)

    # Initialize the interface
    await interface.initialize(language=language, workspace_root=str(temp_workspace))

    yield interface

    # Cleanup with robust protection against event loop mismatches
    # These occur with pytest-xdist when fixture teardown runs on a different worker
    await _safe_cleanup_interface(interface, timeout=10.0)


async def _safe_cleanup_interface(
    interface,
    timeout: float = 10.0,
) -> None:
    """Clean up debug interface with event loop safety.

    This function handles event loop mismatches that occur during pytest-xdist
    parallel test execution, where async operations created on one worker's
    event loop may be cleaned up on another.

    Parameters
    ----------
    interface
        Debug interface to clean up
    timeout : float
        Maximum time to wait for cleanup
    """
    try:
        await asyncio.wait_for(interface.cleanup(), timeout=timeout)
    except asyncio.TimeoutError:
        logger.debug(
            "Debug interface cleanup timed out after %.1fs (non-fatal)", timeout
        )
    except RuntimeError as e:
        if is_event_loop_error(e):
            logger.debug("Event loop mismatch during cleanup: %s", e)
            # Try sync cleanup methods if available
            if hasattr(interface, "_sync_cleanup"):
                with contextlib.suppress(Exception):
                    interface._sync_cleanup()
        else:
            raise
    except Exception as e:  # noqa: S110 - cleanup should never fail tests
        logger.debug("Debug interface cleanup error (suppressed): %s", e)


@pytest.fixture
def debug_interface_factory(
    request,
    temp_workspace: Path,
) -> Generator[Callable[..., Any], None, None]:
    """Provide a factory for creating multiple debug interface instances.

    This fixture enables tests to create multiple concurrent debug sessions
    for testing session isolation and parallel session management.

    Parameters
    ----------
    request : FixtureRequest
        pytest request object
    temp_workspace : Path
        Temporary workspace directory

    Returns
    -------
    Callable
        Factory function that creates and initializes debug interface instances

    Examples
    --------
    Create multiple concurrent sessions:

    >>> async def test_concurrent_sessions(debug_interface_factory, language):
    >>>     session1 = await debug_interface_factory("mcp", language)
    >>>     session2 = await debug_interface_factory("mcp", language)
    >>>     # Both sessions are already initialized
    """
    from tests._helpers.debug_interface import MCPInterface

    created_interfaces = []

    async def _create_interface(
        interface_type: str = "mcp",
        language: str | None = None,
    ):
        """Create and initialize a debug interface instance.

        Parameters
        ----------
        interface_type : str
            Type of interface ("MCPInterface" or "mcp")
        language : str, optional
            Programming language (auto-detected from test if not provided)

        Returns
        -------
        DebugInterface
            Initialized MCPInterface instance
        """
        # Auto-detect language from test if not provided
        if language is None:
            if "language" in request.fixturenames:
                language = request.getfixturevalue("language")
            else:
                language_marker = request.node.get_closest_marker("language")
                language = language_marker.args[0] if language_marker else "python"

        # Normalize interface type (handle both class names and simple types)
        interface_type_lower = interface_type.lower()
        if "mcp" in interface_type_lower:
            interface = MCPInterface(language=language)
        else:
            valid = ["MCPInterface", "mcp"]
            msg = f"Unknown interface type: {interface_type}. Use {valid}"
            raise ValueError(msg)

        # Initialize the interface
        await interface.initialize(
            language=language,
            workspace_root=str(temp_workspace),
        )

        # Track for cleanup
        created_interfaces.append(interface)
        return interface

    yield _create_interface

    # Cleanup all created interfaces with event loop safety
    cleanup_timeout = 5.0

    async def cleanup_all():
        for interface in created_interfaces:
            await _safe_cleanup_interface(interface, timeout=cleanup_timeout)

    # Run cleanup - handle event loop unavailability gracefully
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            logger.debug("Event loop closed, skipping async cleanup")
        elif loop.is_running():
            # Schedule cleanup task - store reference to prevent GC
            cleanup_task = loop.create_task(cleanup_all())  # noqa: RUF006 - fire-and-forget cleanup
            del cleanup_task  # Explicitly discard reference
        else:
            # Run cleanup directly with overall timeout
            loop.run_until_complete(
                asyncio.wait_for(cleanup_all(), timeout=cleanup_timeout * 2)
            )
    except RuntimeError as e:
        logger.debug("Cleanup skipped (event loop unavailable): %s", e)
