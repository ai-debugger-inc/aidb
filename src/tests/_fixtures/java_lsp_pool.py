"""Test-specific Java JDT LS server pooling with pytest integration.

This module provides pytest fixtures for shared JDT LS across tests, avoiding the ~8-9
second startup penalty per test. Production code uses the pool in
src/aidb/adapters/lang/java/jdtls_pool.py instead.

Tests use this test-specific pool for isolation from production code changes and proper
pytest session management. The Java adapter will use the test pool when
AIDB_TEST_JAVA_LSP_POOL=1 is set (via the enable_java_lsp_pooling fixture).
"""

__all__ = [
    # Classes
    "JDTLSPool",
    # Fixtures
    "jdtls_pool",
    "java_test_workspace",
    "enable_java_lsp_pooling",
    # Functions
    "get_test_jdtls_pool",
]

import asyncio
import contextlib
import os
import tempfile
import threading
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from typing import Optional

import pytest

from aidb.adapters.lang.java.lsp.bridge_cleanup import terminate_bridge_process_safe
from aidb.adapters.lang.java.lsp.lsp_bridge import JavaLSPDAPBridge
from aidb.interfaces import IContext
from aidb.resources.process_tags import ProcessTags, ProcessType


class JDTLSPool:
    """Manages a shared JDT LS instance for test execution.

    This pool maintains a single JDT LS server process across multiple tests,
    using LSP workspace folders to isolate individual test workspaces.

    Attributes
    ----------
    bridge : JavaLSPDAPBridge | None
        The shared LSP-DAP bridge instance
    is_started : bool
        Whether the LSP server has been initialized
    lock : asyncio.Lock
        Lock for thread-safe access to the shared instance
    """

    def __init__(self, ctx: IContext | None = None):
        """Initialize the JDT LS pool.

        Parameters
        ----------
        ctx : IContext, optional
            Context for logging and storage
        """
        from aidb.common.context import AidbContext

        self.bridge: JavaLSPDAPBridge | None = None
        self.is_started = False
        self.lock = asyncio.Lock()
        self.ctx = ctx or AidbContext()
        self._test_workspaces: set[Path] = set()
        self._session_count = 0
        self._max_sessions_before_restart = (
            30  # Restart before hitting limits (conservative)
        )
        self._is_unhealthy = False
        # Background event loop to host pooled JDT LS across tests
        self._pool_loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: threading.Thread | None = None
        # Track loop id for diagnostics (does not drive logic)
        self._loop_id: int | None = None

    def _start_background_loop(self) -> None:
        """Start a dedicated background asyncio loop for the pooled bridge."""
        if self._pool_loop and self._loop_thread and self._loop_thread.is_alive():
            return

        loop = asyncio.new_event_loop()

        def _run() -> None:
            asyncio.set_event_loop(loop)
            loop.run_forever()

        thread = threading.Thread(target=_run, name="jdtls-pool-loop", daemon=True)
        thread.start()
        self._pool_loop = loop
        self._loop_thread = thread
        self._loop_id = id(loop)
        self.ctx.info(f"[POOL] Started background loop (id={self._loop_id}) for JDT LS")

    def _wrap_async_method(self, obj: object, name: str) -> None:
        """Wrap an async bound method so it runs on pool loop regardless of caller
        loop."""
        assert self._pool_loop is not None
        pool_loop = self._pool_loop  # Narrow type for closure
        orig = getattr(obj, name)

        async def _wrapper(*args, **kwargs):  # type: ignore[no-untyped-def]
            cfut = asyncio.run_coroutine_threadsafe(
                orig(*args, **kwargs),
                pool_loop,
            )
            return await asyncio.wrap_future(cfut)

        setattr(obj, name, _wrapper)

    async def get_or_start_bridge(
        self,
        jdtls_path: Path,
        java_debug_jar: Path,
        java_command: str = "java",
    ) -> JavaLSPDAPBridge:
        """Get existing bridge or start a new one if not running.

        Parameters
        ----------
        jdtls_path : Path
            Path to the Eclipse JDT LS installation directory
        java_debug_jar : Path
            Path to the java-debug-server plugin JAR
        java_command : str
            Java executable command, default "java"

        Returns
        -------
        JavaLSPDAPBridge
            The shared bridge instance
        """
        async with self.lock:
            # Ensure background loop exists
            self._start_background_loop()

            # Evaluate restart needs
            should_restart = (
                self._is_unhealthy
                or self._session_count >= self._max_sessions_before_restart
            )

            # Health/session based restart
            if should_restart and self.bridge:
                self.ctx.warning(
                    f"Restarting JDT LS pool (unhealthy={self._is_unhealthy}, "
                    f"sessions={self._session_count}/{self._max_sessions_before_restart})",
                )
                await self._stop_bridge()
                self.bridge = None
                self.is_started = False
                self._is_unhealthy = False
                self._session_count = 0

            if not self.is_started or self.bridge is None:
                self.ctx.info(
                    "Starting shared JDT LS instance for test pool on background loop",
                )

                assert self._pool_loop is not None

                async def _create_and_start():
                    bridge = JavaLSPDAPBridge(
                        jdtls_path=jdtls_path,
                        java_debug_jar=java_debug_jar,
                        java_command=java_command,
                        ctx=self.ctx,
                    )
                    bridge._is_pooled = True
                    base_workspace = Path(tempfile.mkdtemp(prefix="jdtls_pool_"))
                    pool_env = {ProcessTags.IS_POOL_RESOURCE: "true"}
                    await bridge.start(
                        project_root=base_workspace,
                        session_id="jdtls-pool-shared",
                        extra_env=pool_env,
                    )
                    return bridge

                cfut = asyncio.run_coroutine_threadsafe(
                    _create_and_start(),
                    self._pool_loop,
                )
                bridge: JavaLSPDAPBridge = await asyncio.wrap_future(cfut)

                # Wrap async methods to always run on background loop
                for name in (
                    "start_debug_session",
                    "attach_to_remote",
                    "resolve_classpath",
                    "register_workspace_folders",
                    "register_project",
                    "resolve_main_class",
                    "update_debug_settings",
                    "reset_dap_state",
                    "stop",
                    "cleanup_children",
                    "wait_for_project_import",
                ):
                    with contextlib.suppress(AttributeError):
                        self._wrap_async_method(bridge, name)

                self.bridge = bridge
                self.is_started = True
                self.ctx.info("JDT LS pool started successfully on background loop")

            # Increment session counter
            self._session_count += 1
            self.ctx.debug(f"JDT LS pool session count: {self._session_count}")

            return self.bridge

    def mark_unhealthy(self) -> None:
        """Mark the pool as unhealthy, forcing restart on next use."""
        self._is_unhealthy = True
        self.ctx.warning("JDT LS pool marked as unhealthy - will restart on next use")

    async def _stop_bridge(self) -> None:
        """Stop the current bridge and clean up resources."""
        if self.bridge:
            try:
                await self.bridge.stop()
            except Exception as e:
                self.ctx.warning(f"Error stopping bridge: {e}")

    def register_test_workspace(self, workspace: Path) -> None:
        """Register a test workspace for cleanup tracking.

        Parameters
        ----------
        workspace : Path
            Test workspace directory to track
        """
        self._test_workspaces.add(workspace)

    async def cleanup_test_workspace(self, workspace: Path) -> None:
        """Clean up a test workspace after test completion.

        This removes temporary files and resets LSP state for the workspace
        without tearing down the entire LSP server.

        Parameters
        ----------
        workspace : Path
            Test workspace directory to clean up
        """
        if workspace in self._test_workspaces:
            self._test_workspaces.remove(workspace)

        # Clean up filesystem
        if workspace.exists():
            import shutil

            try:
                shutil.rmtree(workspace)
                self.ctx.debug(f"Cleaned up test workspace: {workspace}")
            except Exception as e:
                self.ctx.warning(f"Failed to clean up workspace {workspace}: {e}")

    async def shutdown(self) -> None:
        """Shut down the shared JDT LS instance.

        Called at the end of the test session to clean up resources.
        """
        async with self.lock:
            if self.bridge:
                self.ctx.info("Shutting down shared JDT LS instance")
                try:
                    await self.bridge.stop()
                except Exception as e:
                    self.ctx.warning(f"Error stopping JDT LS pool: {e}")
                finally:
                    self.bridge = None
                    self.is_started = False

            # Clean up any remaining test workspaces
            for workspace in list(self._test_workspaces):
                await self.cleanup_test_workspace(workspace)


# Singleton pool instance for the test session
_pool: JDTLSPool | None = None


def get_test_jdtls_pool() -> JDTLSPool | None:
    """Get the test JDT LS pool if it exists.

    Returns
    -------
    JDTLSPool | None
        The test pool instance if available, None otherwise
    """
    return _pool


@pytest.fixture(scope="session")
def jdtls_pool(event_loop) -> Generator[JDTLSPool, None, None]:
    """Session-scoped fixture providing a shared JDT LS pool.

    This fixture creates a single JDT LS instance that is reused across
    all Java tests in the session, dramatically reducing test execution time.

    Parameters
    ----------
    event_loop : asyncio.AbstractEventLoop
        The event loop for the test session

    Returns
    -------
    JDTLSPool
        The shared JDT LS pool instance

    Notes
    -----
    The pool is automatically shut down at the end of the test session.
    """
    from aidb.common.context import AidbContext

    global _pool

    if _pool is None:
        ctx = AidbContext()
        _pool = JDTLSPool(ctx=ctx)
        ctx.info("Created JDT LS pool for test session")
        # Start a dedicated background loop at session setup
        _pool._start_background_loop()

    yield _pool

    # Cleanup at end of session
    if _pool and event_loop:
        event_loop.run_until_complete(_pool.shutdown())
        _pool = None


@pytest.fixture
async def java_test_workspace(jdtls_pool: JDTLSPool) -> AsyncGenerator[Path, None]:
    """Function-scoped fixture providing an isolated test workspace.

    Each test gets its own temporary workspace directory that is cleaned
    up after the test completes.

    Parameters
    ----------
    jdtls_pool : JDTLSPool
        The shared JDT LS pool

    Yields
    ------
    Path
        Temporary workspace directory for the test
    """
    workspace = Path(tempfile.mkdtemp(prefix="java_test_"))
    jdtls_pool.register_test_workspace(workspace)

    yield workspace

    # Cleanup after test
    await jdtls_pool.cleanup_test_workspace(workspace)


@pytest.fixture(scope="session", autouse=True)
def enable_java_lsp_pooling(jdtls_pool: JDTLSPool) -> None:
    """Enable Java LSP pooling for all tests in the session.

    This fixture runs automatically for all tests when the java_lsp_pool
    module is imported. It sets an environment variable that the Java
    adapter can check to use the shared pool instead of creating new
    LSP instances.

    Notes
    -----
    The Java adapter checks the AIDB_TEST_JAVA_LSP_POOL environment variable.
    If set to "1", it will use the shared pool from this module instead of
    creating new LSP bridge instances.
    """
    # Set environment variable to enable pooling
    os.environ["AIDB_TEST_JAVA_LSP_POOL"] = "1"

    # Touch the session-scoped pool fixture to ensure it initializes.
    # Without this, only get_test_jdtls_pool() is called from the adapter,
    # which returns None unless the jdtls_pool fixture has been constructed.
    # Forcing construction here guarantees a single shared JDT LS instance.
    _ = jdtls_pool
