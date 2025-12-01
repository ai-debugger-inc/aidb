#!/usr/bin/env python
"""Example usage of the aidb_logging package."""

import time

from aidb_common.path import get_aidb_log_dir
from aidb_logging import (
    PerformanceLogger,
    SessionContext,
    get_aidb_logger,
    get_logger,
    get_mcp_logger,
    log_performance,
)


def example_aidb_profile():
    """Demonstrate aidb profile with CallerFilter."""
    print("\n=== AIDB Profile Example ===")
    logger = get_aidb_logger("example.aidb")

    logger.debug("Debug message from aidb")
    logger.info("Info message from aidb")
    logger.warning("Warning message from aidb")
    logger.error("Error message from aidb")

    # Check the log file
    log_file = get_aidb_log_dir() / "aidb.log"
    if log_file.exists():
        print(f"Log file created at: {log_file}")


def example_mcp_profile():
    """Demonstrate MCP profile with session context."""
    print("\n=== MCP Profile Example ===")
    logger = get_mcp_logger("example.mcp")

    # Without session context
    logger.info("Starting MCP operations")

    # With session context
    with SessionContext("debug-session-123"):
        logger.info("Processing debug session")
        logger.debug("Session details logged")
        logger.warning("Potential issue detected")


def example_performance_logging():
    """Demonstrate performance logging utilities."""
    print("\n=== Performance Logging Example ===")
    logger = get_logger("example.performance", level="DEBUG")

    # Using decorator
    @log_performance(operation="slow_calculation", slow_threshold_ms=50)
    def slow_function():
        """Demonstrate performance logging functionality."""
        time.sleep(0.1)
        return 42

    result = slow_function()
    print(f"Result: {result}")

    # Using context manager
    with PerformanceLogger(logger, "database_query", slow_threshold_ms=100):
        time.sleep(0.05)
        logger.debug("Query executed")


def main():
    """Run all examples."""
    print("=" * 60)
    print("AIDB Unified Logging System - Examples")
    print("=" * 60)

    example_aidb_profile()
    example_mcp_profile()
    example_performance_logging()

    print("\n" + "=" * 60)
    print("Examples completed! Check ~/.aidb/log/ for log files.")
    print("=" * 60)


if __name__ == "__main__":
    main()
