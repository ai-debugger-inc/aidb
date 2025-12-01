"""Pure pytest base classes for AIDB test suite."""

import asyncio
import contextlib
import logging
from pathlib import Path
from typing import Optional

import pytest

from aidb.common.context import AidbContext
from aidb.resources.ports import PortRegistry
from tests._helpers.constants import DebugPorts, Language, PortRanges
from tests._helpers.mixins import DebugSessionMixin, FileTestMixin, ValidationMixin


class PytestBase(FileTestMixin, ValidationMixin):
    """Base class for all pytest-style tests."""

    @pytest.fixture(autouse=True)
    def base_setup(self, tmp_path, caplog):
        """Automatic setup for all tests.

        Parameters
        ----------
        tmp_path : Path
            Pytest's temporary directory fixture
        caplog : LogCaptureFixture
            Pytest's log capture fixture
        """
        # Set up instance attributes
        self.temp_dir = tmp_path
        self.logger = logging.getLogger(self.__class__.__name__)
        self.caplog = caplog

        # Configure logging
        caplog.set_level(logging.DEBUG)

        return

        # Cleanup happens automatically with tmp_path


class PytestAsyncBase(PytestBase):
    """Base class for async pytest tests."""

    @pytest.fixture(autouse=True)
    def event_loop_setup(self, event_loop):
        """Set up event loop for async tests.

        Parameters
        ----------
        event_loop : asyncio.AbstractEventLoop
            Pytest-asyncio's event loop fixture
        """
        self.loop = event_loop
        return


class PytestIntegrationBase(PytestAsyncBase, DebugSessionMixin):
    """Base class for integration tests with pytest.

    Provides port management and debug session utilities.
    """

    @pytest.fixture(autouse=True)
    async def integration_setup(self):
        """Set up integration test environment."""
        # Initialize port registry
        self.ctx = AidbContext()
        self.port_registry = PortRegistry(ctx=self.ctx)

        # Track allocated resources
        self._allocated_ports: list[int] = []
        self._processes: list[asyncio.subprocess.Process] = []
        self._sessions: list[str] = []

        yield

        # Cleanup
        await self._cleanup_resources()

    async def _cleanup_resources(self):
        """Clean up allocated resources."""
        # Terminate processes
        for proc in self._processes:
            try:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    proc.kill()
            except Exception as e:
                # Process might already be dead or have other issues during cleanup
                logging.debug("Process cleanup failed: %s", e)

        # Release ports
        for port in self._allocated_ports:
            with contextlib.suppress(Exception):
                self.port_registry.release_port(port)

        # Clean up sessions
        for session_id in self._sessions:
            with contextlib.suppress(Exception):
                self.port_registry.release_session_ports(session_id)

    async def allocate_port(
        self,
        language: str = Language.PYTHON.value,
        session_id: str | None = None,
    ) -> int:
        """Allocate a port for testing.

        Parameters
        ----------
        language : str
            Language adapter requesting port
        session_id : str, optional
            Session ID for port allocation

        Returns
        -------
        int
            Allocated port number
        """
        try:
            lang_enum = Language(language)
            default_port = lang_enum.default_port
            fallback_ranges = getattr(PortRanges, lang_enum.name, PortRanges.DEFAULT)
        except ValueError:
            default_port = DebugPorts.PYTHON
            fallback_ranges = PortRanges.DEFAULT

        port = await self.port_registry.acquire_port(
            language=language,
            session_id=session_id or f"test_{id(self)}",
            default_port=default_port,
            fallback_ranges=fallback_ranges,
        )

        self._allocated_ports.append(port)
        if session_id:
            self._sessions.append(session_id)

        return port

    async def start_process(
        self,
        cmd: list[str],
        cwd: Path | None = None,
        env: dict | None = None,
    ) -> asyncio.subprocess.Process:
        """Start a process with tracking.

        Parameters
        ----------
        cmd : List[str]
            Command to execute
        cwd : Path, optional
            Working directory
        env : Dict, optional
            Environment variables

        Returns
        -------
        asyncio.subprocess.Process
            Started process
        """
        import os

        process_env = os.environ.copy()
        if env:
            process_env.update(env)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd or self.temp_dir,
            env=process_env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        self._processes.append(proc)
        return proc
