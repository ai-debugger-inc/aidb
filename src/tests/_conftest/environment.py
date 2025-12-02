"""Test environment setup and logging configuration.

This module provides functions for resolving environment templates and configuring
logging for the test suite.
"""

import logging
import os
from pathlib import Path


def resolve_env_template_early() -> None:
    """Resolve environment template before Settings can be cached.

    This ensures Settings singleton gets the correct values from the start. Must be
    called early in the conftest.py module import process.
    """
    env_template = Path(__file__).parent.parent / ".env.test"
    if not env_template.exists():
        return

    from aidb_common.env import apply_env_template_to_environ

    apply_env_template_to_environ(env_template, strict=False)


def configure_test_logging() -> None:
    """Configure comprehensive logging for tests using aidb_logging.

    Creates multiple log outputs:
    - Individual log files: aidb.log, mcp.log
    - Pytest propagation: for caplog integration
    """
    from aidb_logging import configure_logger
    from tests._helpers.constants import EnvVar, LogLevel

    # Get log level from environment
    log_level = os.getenv(
        EnvVar.AIDB_TEST_LOG_LEVEL.value,
        os.getenv(EnvVar.AIDB_LOG_LEVEL.value, LogLevel.WARNING.value),
    )

    # Configure AIDB loggers with standard profiles
    # These write to normal log files (aidb.log, mcp.log)
    configure_logger("aidb", profile="aidb", level=log_level)
    configure_logger("aidb_mcp", profile="mcp", level=log_level)
    configure_logger("tests", profile="aidb", level=log_level)

    # Enable propagation for pytest caplog integration
    for logger_name in ["aidb", "aidb_mcp", "tests"]:
        logger = logging.getLogger(logger_name)
        logger.propagate = True

    # Configure third-party loggers to be quieter
    for logger_name in ["asyncio", "urllib3", "docker"]:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.WARNING)

    # Suppress noisy orphan cleanup DEBUG logs - only show warnings and errors
    logging.getLogger("aidb.resources.orphan_cleanup").setLevel(logging.WARNING)
