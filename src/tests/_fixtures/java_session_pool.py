"""Test-only Java debug session pooling for faster test execution.

This module provides session-scoped fixtures that maintain a pool of reusable
Java debug sessions, avoiding the ~8-10 second session creation penalty per test.

IMPORTANT: This is TEST INFRASTRUCTURE ONLY and should never be used in production
MCP deployments. Production code maintains simple per-session instances.
"""

__all__ = [
    # Classes
    "JavaSessionPool",
    # Fixtures
    "java_session_pool",
    # Functions
    "get_java_session_pool",
]

import asyncio
import contextlib
from collections import deque
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

from aidb.service import DebugService
from aidb.session import Session


class JavaSessionPool:
    """Manages a pool of reusable Java debug sessions for test execution.

    This pool maintains pre-initialized debug sessions that can be checked out,
    used for testing, reset to clean state, and returned for reuse by other tests.

    Attributes
    ----------
    pool_size : int
        Maximum number of sessions to maintain in the pool
    available : deque[Session]
        Queue of available sessions ready for checkout
    in_use : dict[str, Session]
        Mapping of session IDs to sessions currently checked out
    lock : asyncio.Lock
        Lock for thread-safe pool access
    """

    def __init__(self, pool_size: int = 2):
        """Initialize the session pool.

        Parameters
        ----------
        pool_size : int
            Maximum number of sessions to maintain in pool (default: 2)
        """
        self.pool_size = pool_size
        self.available: deque[Session] = deque()
        self.in_use: dict[str, Session] = {}
        self.lock = asyncio.Lock()
        self._ctx = None
        self._warmup_complete = False

    def get_managed_session_ids(self) -> set[str]:
        """Get all session IDs currently managed by the pool.

        Returns
        -------
        set[str]
            Set of session IDs that are in the pool (available or in use)
        """
        session_ids = set()
        for session in self.available:
            session_ids.add(session.id)
        session_ids.update(self.in_use.keys())
        return session_ids

    async def warmup(
        self,
        ctx: Any,
        create_session_fn: Any,
    ) -> None:
        """Pre-warm the pool with initial sessions.

        Parameters
        ----------
        ctx : IContext
            Context for logging
        create_session_fn : Callable
            Async function that creates and initializes a new session
        """
        async with self.lock:
            if self._warmup_complete:
                ctx.debug("Session pool already warmed up, skipping")
                return

            self._ctx = ctx
            ctx.info(f"Warming up Java session pool with {self.pool_size} sessions")

            for i in range(self.pool_size):
                try:
                    session = await create_session_fn()
                    self.available.append(session)
                    ctx.info(
                        f"Pre-warmed session {i + 1}/{self.pool_size}: {session.id[:8]}",
                    )
                except Exception as e:
                    ctx.warning(f"Failed to pre-warm session {i + 1}: {e}")

            self._warmup_complete = True
            ctx.info(
                f"Session pool warmup complete: {len(self.available)} sessions ready",
            )

    async def checkout(
        self,
        create_session_fn: Any,
    ) -> Session:
        """Check out a session from the pool.

        If no sessions are available, creates a new one.

        Parameters
        ----------
        create_session_fn : Callable
            Async function that creates and initializes a new session

        Returns
        -------
        Session
            A ready-to-use debug session
        """
        async with self.lock:
            # Lazy initialize context if needed
            if self._ctx is None:
                from aidb.common.context import AidbContext

                self._ctx = AidbContext()

            # Try to get from pool
            if self.available:
                session = self.available.popleft()
                self.in_use[session.id] = session

                if self._ctx:
                    self._ctx.info(
                        f"♻️  REUSED pooled session {session.id[:8]} "
                        f"({len(self.available)} remaining in pool)",
                    )
                return session

            # Pool empty - create new session
            if self._ctx:
                self._ctx.info("⚙️  Pool empty, creating NEW session")

            session = await create_session_fn()
            self.in_use[session.id] = session
            return session

    async def return_session(self, session: Session) -> None:
        """Return a session to the pool after resetting its state.

        Parameters
        ----------
        session : Session
            Session to return to the pool
        """
        import time

        start_time = time.time()

        async with self.lock:
            # Remove from in-use tracking
            if session.id in self.in_use:
                del self.in_use[session.id]

            # Try to reset and return to pool
            try:
                reset_start = time.time()
                await self._reset_session_state(session)
                reset_time = time.time() - reset_start

                if self._ctx:
                    self._ctx.info(f"Session reset took {reset_time:.2f}s")

                # Only return to pool if under capacity
                if len(self.available) < self.pool_size:
                    self.available.append(session)
                    total_time = time.time() - start_time
                    if self._ctx:
                        self._ctx.info(
                            f"Returned session {session.id[:8]} to pool "
                            f"(total: {total_time:.2f}s, {len(self.available)} available)",
                        )
                else:
                    # Pool full - destroy excess session
                    if self._ctx:
                        self._ctx.info(
                            f"Pool full, destroying excess session {session.id[:8]}",
                        )
                    await self._destroy_session(session)

            except Exception as e:
                # Session corrupted - discard it
                if self._ctx:
                    self._ctx.warning(
                        f"Failed to reset session {session.id[:8]}, discarding: {e}",
                    )
                await self._destroy_session(session)

    async def _reset_session_state(self, session: Session) -> None:  # noqa: C901
        """Reset a session to clean state for reuse.

        This method clears all breakpoints, stops the debuggee if running,
        and resets session state flags while keeping the JDT LS alive.

        Parameters
        ----------
        session : Session
            Session to reset

        Raises
        ------
        Exception
            If session reset fails and session should be discarded
        """
        import time

        from aidb.models import SessionStatus

        if self._ctx:
            self._ctx.debug(f"Resetting session {session.id[:8]} state")

        # Check if session is already terminated - skip DAP operations if so
        is_terminated = session.status == SessionStatus.TERMINATED or (
            hasattr(session.dap, "is_terminated") and session.dap.is_terminated
        )

        if is_terminated:
            if self._ctx:
                self._ctx.info(
                    "Session already terminated, cannot reuse - will be destroyed",
                )
            # Raise error to trigger session destruction in return_session()
            msg = "Session is terminated and cannot be reused"
            raise RuntimeError(msg)
        # Create service for session operations
        service = DebugService(session)

        # 1. Clear all breakpoints
        try:
            bp_start = time.time()
            await service.breakpoints.clear_all()
            bp_time = time.time() - bp_start
            if self._ctx:
                self._ctx.info(f"  clear_breakpoints: {bp_time:.2f}s")
        except Exception as e:
            if self._ctx:
                self._ctx.warning(f"Failed to clear breakpoints: {e}")
            # Continue anyway - breakpoint clearing failure shouldn't discard session

        # 2. Stop the debuggee if running
        try:
            stop_start = time.time()
            if session.status != SessionStatus.TERMINATED:
                # Use the low-level terminate that doesn't destroy the session
                with contextlib.suppress(Exception):
                    await service.execution.terminate()
            stop_time = time.time() - stop_start
            if self._ctx:
                self._ctx.info(f"  stop debuggee: {stop_time:.2f}s")
        except Exception as e:
            if self._ctx:
                self._ctx.warning(f"Failed to stop debuggee: {e}")

        # 3. Reset session state flags
        try:
            state_start = time.time()
            # Clear breakpoint store
            if hasattr(session, "_breakpoint_store"):
                session._breakpoint_store.clear()

            # Reset stopped event flag if it exists
            if hasattr(session, "_stopped_event"):
                session._stopped_event.clear()

            # Clear any cached state
            if hasattr(session, "_event_subscriptions"):
                # Keep subscriptions but clear any cached state
                pass

            state_time = time.time() - state_start
            if self._ctx:
                self._ctx.info(f"  state reset: {state_time:.3f}s")

        except Exception as e:
            if self._ctx:
                self._ctx.error(f"Failed to reset session state: {e}")
            raise

        # 4. Verify DAP connection is still healthy (skip if already terminated)
        if not is_terminated:
            try:
                verify_start = time.time()
                if not session.dap:
                    msg = "DAP connection unavailable"
                    raise RuntimeError(msg)

                # Check if connection manager is available and connected
                if hasattr(session.dap, "_connection_manager"):
                    conn_mgr = session.dap._connection_manager
                    if (
                        hasattr(conn_mgr, "state")
                        and hasattr(conn_mgr.state, "connected")
                        and not conn_mgr.state.connected
                    ):
                        msg = "DAP connection not connected"
                        raise RuntimeError(msg)

                if hasattr(session.dap, "is_terminated") and session.dap.is_terminated:
                    msg = "DAP connection terminated"
                    raise RuntimeError(msg)

                verify_time = time.time() - verify_start
                if self._ctx:
                    self._ctx.info(f"  DAP verification: {verify_time:.3f}s")

            except Exception as e:
                if self._ctx:
                    self._ctx.error(f"DAP connection check failed: {e}")
                raise

    async def _destroy_session(self, session: Session) -> None:
        """Fully destroy a session.

        Parameters
        ----------
        session : Session
            Session to destroy
        """
        try:
            with contextlib.suppress(Exception):
                await session.destroy()
            if self._ctx:
                self._ctx.debug(f"Destroyed session {session.id[:8]}")
        except Exception as e:
            if self._ctx:
                self._ctx.warning(f"Error destroying session: {e}")

    async def shutdown(self) -> None:
        """Shut down the pool and clean up all sessions."""
        async with self.lock:
            if self._ctx:
                self._ctx.info(
                    f"Shutting down session pool "
                    f"({len(self.available)} available, {len(self.in_use)} in use)",
                )

            # Destroy all available sessions
            while self.available:
                session = self.available.popleft()
                await self._destroy_session(session)

            # Destroy any sessions still in use
            for session in list(self.in_use.values()):
                await self._destroy_session(session)
            self.in_use.clear()

            if self._ctx:
                self._ctx.info("Session pool shutdown complete")


# Global pool instance for the test session
_pool: JavaSessionPool | None = None


@pytest.fixture(scope="session")
def java_session_pool(event_loop) -> Generator[JavaSessionPool, None, None]:
    """Session-scoped fixture providing a shared Java session pool.

    This fixture creates a pool of reusable debug sessions that are shared
    across all Java tests in the session, dramatically reducing test execution time.

    Parameters
    ----------
    event_loop : asyncio.AbstractEventLoop
        The event loop for the test session

    Returns
    -------
    JavaSessionPool
        The shared session pool instance

    Notes
    -----
    The pool is automatically shut down at the end of the test session.
    Pool warmup happens lazily on first checkout to avoid blocking session startup.
    """
    from aidb.common.context import AidbContext

    global _pool

    if _pool is None:
        ctx = AidbContext()
        _pool = JavaSessionPool(pool_size=2)
        ctx.info("Created Java session pool for test session")

    yield _pool

    # Cleanup at end of session
    if _pool and event_loop:
        event_loop.run_until_complete(_pool.shutdown())
        _pool = None


def get_java_session_pool() -> JavaSessionPool | None:
    """Get the shared Java session pool.

    This function is called by test fixtures to access the session pool.

    Returns
    -------
    JavaSessionPool | None
        The shared pool instance if available, None otherwise
    """
    global _pool
    return _pool
