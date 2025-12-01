"""Pytest configuration and fixtures for Java E2E launch tests."""

import os
import subprocess
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
    from tests._fixtures.base import DebugInterfaceType
    from tests._helpers.debug_interface import APIInterface, MCPInterface

    # Enable Java auto-compilation for E2E tests
    os.environ["AIDB_JAVA_AUTO_COMPILE"] = "true"

    interface_type = getattr(request, "param", DebugInterfaceType.API.value)

    if interface_type == DebugInterfaceType.MCP.value:
        interface = MCPInterface(language="java")
    elif interface_type == DebugInterfaceType.API.value:
        interface = APIInterface(language="java")
    else:
        valid = [t.value for t in DebugInterfaceType]
        msg = f"Unknown interface type: {interface_type}. Use {valid}"
        raise ValueError(msg)

    await interface.initialize(
        language="java",
        workspace_root=str(temp_workspace),
    )

    yield interface

    await interface.cleanup()
