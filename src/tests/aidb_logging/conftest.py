"""Root conftest for aidb_logging tests.

Provides common fixtures and test utilities for all aidb_logging tests.
"""

import logging
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from aidb_logging import clear_log_context, clear_request_id, clear_session_id


@pytest.fixture(autouse=True)
def cleanup_logging_context() -> Generator[None, None, None]:
    """Clean up logging context after each test.

    Yields
    ------
    None
        Control returns to test after setup
    """
    yield
    # Clean up context variables
    clear_session_id()
    clear_request_id()
    clear_log_context()


@pytest.fixture
def temp_log_file(tmp_path: Path) -> Path:
    """Create a temporary log file for testing.

    Parameters
    ----------
    tmp_path : Path
        Pytest tmp_path fixture

    Returns
    -------
    Path
        Path to temporary log file
    """
    return tmp_path / "test.log"


@pytest.fixture
def test_logger(temp_log_file: Path) -> Generator[logging.Logger, None, None]:
    """Create a test logger instance.

    Parameters
    ----------
    temp_log_file : Path
        Temporary log file path

    Returns
    -------
    logging.Logger
        Configured test logger
    """
    logger = logging.getLogger(f"test.{id(temp_log_file)}")
    logger.handlers.clear()
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    handler: logging.Handler = logging.FileHandler(temp_log_file)
    handler.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    yield logger

    # Clean up
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)
