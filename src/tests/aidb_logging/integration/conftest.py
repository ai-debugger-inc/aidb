"""Fixtures for aidb_logging integration tests."""

import logging
from collections.abc import Generator
from pathlib import Path

import pytest

from aidb_logging.context import ContextManager


@pytest.fixture
def integration_log_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for integration test logs.

    Parameters
    ----------
    tmp_path : Path
        Pytest tmp_path fixture

    Returns
    -------
    Path
        Path to log directory
    """
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    return log_dir


@pytest.fixture(autouse=True)
def reset_logging() -> Generator[None, None, None]:
    """Reset logging configuration after each integration test.

    This ensures test isolation by clearing all handlers and resetting levels.
    """
    yield

    # Get all loggers and clean them up
    loggers = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
    loggers.append(logging.getLogger())  # Add root logger

    for logger in loggers:
        # Clear handlers
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)
        # Clear filters
        logger.filters.clear()
        # Reset level
        logger.setLevel(logging.NOTSET)

    # Reset ContextManager singleton to ensure isolation
    ContextManager.reset()
