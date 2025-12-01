"""Fixtures for aidb_logging unit tests."""

import logging
from collections.abc import Generator

import pytest

# Re-export all unit fixtures for aidb_logging tests
from tests._fixtures.unit.conftest import *  # noqa: F401, F403


@pytest.fixture
def clean_logger(request) -> Generator[logging.Logger, None, None]:
    """Create a clean logger for testing.

    Yields
    ------
    logging.Logger
        Clean logger instance
    """
    logger_name = f"test.unit.{request.node.name}.{id(request)}"
    logger = logging.getLogger(logger_name)
    logger.handlers.clear()
    logger.filters.clear()
    logger.setLevel(logging.DEBUG)
    logger.propagate = True

    yield logger

    # Clean up
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)
    logger.filters.clear()
    logger.propagate = False
