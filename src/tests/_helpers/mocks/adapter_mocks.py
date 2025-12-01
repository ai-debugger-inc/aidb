"""Mock language adapters and processes for testing."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from tests._helpers.constants import DebugPorts, Language


class MockAdapter:
    """Mock language adapter for testing."""

    def __init__(self, language: str = Language.PYTHON.value):
        """Initialize mock adapter.

        Parameters
        ----------
        language : str
            Programming language this adapter supports
        """
        self.language = language
        self.name = f"mock_{language}_adapter"
        self.is_running = False
        self.process: MagicMock | None = None
        self.port = None

        # Configuration
        self.config = {
            Language.PYTHON.value: {
                "command": ["python", "-m", "debugpy"],
                "default_port": DebugPorts.PYTHON,
                "extensions": [".py"],
            },
            Language.JAVASCRIPT.value: {
                "command": ["node", "--inspect"],
                "default_port": DebugPorts.JAVASCRIPT,
                "extensions": [".js", ".mjs", ".ts"],
            },
            Language.JAVA.value: {
                "command": ["java", "-agentlib:jdwp"],
                "default_port": DebugPorts.JAVA,
                "extensions": [".java"],
            },
        }.get(
            language,
            {"command": ["unknown"], "default_port": 6000, "extensions": [".txt"]},
        )

        # Mock methods
        self.launch = AsyncMock(
            return_value={"success": True, "port": self.config["default_port"]},
        )
        self.attach = AsyncMock(return_value={"success": True})
        self.terminate = AsyncMock(return_value=True)
        self.get_configuration = MagicMock(return_value=self.config)

    async def start(self, target: str, **kwargs) -> dict[str, Any]:
        """Mock adapter start."""
        self.is_running = True
        self.port = kwargs.get("port", self.config["default_port"])

        # Simulate process
        self.process = MagicMock()
        self.process.pid = 12345
        self.process.returncode = None

        return {
            "success": True,
            "port": self.port,
            "pid": self.process.pid,
            "target": target,
        }

    async def stop(self) -> bool:
        """Mock adapter stop."""
        self.is_running = False
        if self.process:
            self.process.returncode = 0
        return True

    def is_alive(self) -> bool:
        """Check if adapter is running."""
        return self.is_running


class MockProcess:
    """Mock process for testing adapter launches."""

    def __init__(self, pid: int = 12345, returncode: int | None = None):
        """Initialize mock process.

        Parameters
        ----------
        pid : int
            Process ID
        returncode : int, optional
            Return code (None means still running)
        """
        self.pid = pid
        self.returncode = returncode
        self.stdout = AsyncMock()
        self.stderr = AsyncMock()

        # Mock stdout/stderr content
        self.stdout.read = AsyncMock(return_value=b"Mock stdout output")
        self.stderr.read = AsyncMock(return_value=b"Mock stderr output")

    def terminate(self) -> None:
        """Mock process termination."""
        if self.returncode is None:
            self.returncode = 0

    def kill(self) -> None:
        """Mock process kill."""
        if self.returncode is None:
            self.returncode = -9

    async def wait(self) -> int:
        """Mock process wait."""
        if self.returncode is None:
            # Simulate process ending
            await asyncio.sleep(0.1)
            self.returncode = 0
        return self.returncode

    async def communicate(self) -> tuple:
        """Mock process communication."""
        stdout = await self.stdout.read()
        stderr = await self.stderr.read()
        return (stdout, stderr)
