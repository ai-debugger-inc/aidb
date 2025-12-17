"""Pytest configuration and fixtures for Java E2E launch tests."""

import os
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest


@pytest.fixture
async def debug_interface(
    request,
    temp_workspace: Path,
) -> AsyncGenerator:
    """Override debug_interface fixture to use Java language.

    This fixture ensures all Java E2E tests use the correct language setting
    for their debug interface.

    Parameters
    ----------
    request : FixtureRequest
        pytest request object
    temp_workspace : Path
        Temporary workspace directory

    Yields
    ------
    DebugInterface
        Debug interface configured for Java
    """
    from tests._helpers.debug_interface import MCPInterface

    # Enable Java auto-compilation for E2E tests
    os.environ["AIDB_JAVA_AUTO_COMPILE"] = "true"

    interface = MCPInterface(language="java")

    await interface.initialize(
        language="java",
        workspace_root=str(temp_workspace),
    )

    yield interface

    await interface.cleanup()
