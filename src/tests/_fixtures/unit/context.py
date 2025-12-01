"""Mock context fixtures for unit tests.

Provides mock implementations of AidbContext for unit testing without requiring the full
logging/singleton infrastructure.
"""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_ctx() -> MagicMock:
    """Standard mock context for unit tests.

    Provides all AidbContext methods as MagicMocks, matching the
    real interface in `aidb.common.context.AidbContext`.

    Returns
    -------
    MagicMock
        Mock context with logging and storage methods
    """
    ctx = MagicMock()

    # Logging methods
    ctx.trace = MagicMock()
    ctx.debug = MagicMock()
    ctx.info = MagicMock()
    ctx.warning = MagicMock()
    ctx.error = MagicMock()
    ctx.critical = MagicMock()

    # Utility methods
    ctx.is_debug_enabled = MagicMock(return_value=True)
    ctx.state_dir = MagicMock(return_value="/tmp/aidb-test")
    ctx.get_storage_path = MagicMock(
        side_effect=lambda component, file=None: (
            f"/tmp/aidb-test/{component}/{file}"
            if file
            else f"/tmp/aidb-test/{component}"
        )
    )
    ctx.create_child = MagicMock(return_value=ctx)

    # Logger for direct access
    ctx.logger = MagicMock()

    return ctx


@pytest.fixture
def null_ctx() -> MagicMock:
    """Minimal context that does nothing.

    Use this when context is required but not relevant to the test.

    Returns
    -------
    MagicMock
        Minimal mock context
    """
    return MagicMock()


@pytest.fixture
def tmp_storage(tmp_path: Path) -> Path:
    """Temporary storage directory for tests.

    Creates a temporary aidb directory structure for tests
    that need real file operations.

    Parameters
    ----------
    tmp_path : Path
        pytest's temporary path fixture

    Returns
    -------
    Path
        Path to temporary aidb storage directory
    """
    storage = tmp_path / "aidb"
    storage.mkdir()
    return storage


@pytest.fixture
def mock_ctx_with_storage(tmp_storage: Path) -> MagicMock:
    """Mock context with real temporary storage paths.

    Combines the mock context with actual filesystem paths
    for tests that need to write files.

    Parameters
    ----------
    tmp_storage : Path
        Temporary storage directory

    Returns
    -------
    MagicMock
        Mock context with real storage paths
    """
    ctx = MagicMock()

    # Logging methods
    ctx.trace = MagicMock()
    ctx.debug = MagicMock()
    ctx.info = MagicMock()
    ctx.warning = MagicMock()
    ctx.error = MagicMock()
    ctx.critical = MagicMock()

    # Real storage paths
    ctx.is_debug_enabled = MagicMock(return_value=True)
    ctx.state_dir = MagicMock(return_value=str(tmp_storage))

    def get_storage_path(component: str, file: str | None = None) -> str:
        component_dir = tmp_storage / component
        component_dir.mkdir(parents=True, exist_ok=True)
        if file:
            return str(component_dir / file)
        return str(component_dir)

    ctx.get_storage_path = MagicMock(side_effect=get_storage_path)
    ctx.create_child = MagicMock(return_value=ctx)
    ctx.logger = MagicMock()

    return ctx


def assert_error_logged(mock_ctx: MagicMock, message_contains: str) -> None:
    """Assert that an error was logged containing the given message.

    Parameters
    ----------
    mock_ctx : MagicMock
        Mock context to check
    message_contains : str
        Substring that should appear in logged error

    Raises
    ------
    AssertionError
        If no matching error was logged
    """
    calls = mock_ctx.error.call_args_list
    messages = [str(call) for call in calls]
    assert any(message_contains in m for m in messages), (
        f"Expected error containing '{message_contains}' but got: {messages}"
    )


def assert_warning_logged(mock_ctx: MagicMock, message_contains: str) -> None:
    """Assert that a warning was logged containing the given message.

    Parameters
    ----------
    mock_ctx : MagicMock
        Mock context to check
    message_contains : str
        Substring that should appear in logged warning

    Raises
    ------
    AssertionError
        If no matching warning was logged
    """
    calls = mock_ctx.warning.call_args_list
    messages = [str(call) for call in calls]
    assert any(message_contains in m for m in messages), (
        f"Expected warning containing '{message_contains}' but got: {messages}"
    )
