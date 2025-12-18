"""Session lifecycle management and cleanup operations."""

from __future__ import annotations

import time
from typing import Any

from aidb_logging import (
    clear_session_id,
)
from aidb_logging import (
    get_mcp_logger as get_logger,
)
from aidb_logging import (
    get_session_id as get_session_id_from_context,
)

from ..core.config import get_config
from .manager_shared import (
    _DEBUG_SESSIONS,
    _DEFAULT_SESSION_ID,
    _SESSION_CONTEXTS,
    _state_lock,
)

logger = get_logger(__name__)

# Get configuration
config = get_config()


def _attempt_graceful_shutdown(
    service: Any,
    session_id: str,
    timeout: float,
    force: bool,
) -> bool:
    """Attempt graceful shutdown of a session.

    Parameters
    ----------
    service : DebugService
        Debug service instance
    session_id : str
        Session ID
    timeout : float
        Maximum time to wait
    force : bool
        If True, force cleanup on failure

    Returns
    -------
    bool
        True if shutdown succeeded or forced
    """
    logger.info("Attempting graceful shutdown of session %s", session_id)
    start_time = time.time()
    attempts = 0

    while attempts < config.session.max_retry_attempts:
        try:
            # Try to stop the session via the execution control
            import asyncio

            asyncio.get_event_loop().run_until_complete(service.execution.stop())
            logger.debug("Session stopped successfully %s", session_id)
            return True
        except Exception as e:
            attempts += 1
            elapsed = time.time() - start_time

            # Check timeout
            if elapsed >= timeout:
                if force:
                    logger.warning(
                        "Timeout stopping session %s, forcing cleanup: %s",
                        session_id,
                        e,
                    )
                    return True
                logger.error(
                    "Failed to stop session %s within timeout: %s",
                    session_id,
                    e,
                )
                return False

            # Check retry limit
            if attempts < config.session.max_retry_attempts:
                logger.debug(
                    "Retry %s/%s for session %s",
                    attempts,
                    config.session.max_retry_attempts,
                    session_id,
                )
                time.sleep(config.session.retry_delay)
            else:
                if force:
                    logger.warning(
                        "Max retries reached for session %s, forcing cleanup",
                        session_id,
                    )
                    return True
                logger.error(
                    "Failed to stop session %s after %s attempts",
                    session_id,
                    attempts,
                )
                return False

    return force  # Return True if force, False otherwise


def _cleanup_session_context(context: Any, session_id: str) -> None:
    """Clean up session context.

    Parameters
    ----------
    context : Any
        Session context object
    session_id : str
        Session ID
    """
    if context:
        # Clear any pending operations
        context.breakpoints_set.clear()
        context.variables_tracked.clear()
        logger.debug("Cleared session context for session %s", session_id)


def _cleanup_registries(
    session_id: str,
    force: bool,
) -> bool:
    """Clean up session from registries.

    Parameters
    ----------
    session_id : str
        Session ID
    force : bool
        If True, force cleanup despite errors

    Returns
    -------
    bool
        True if cleanup succeeded
    """
    global _DEFAULT_SESSION_ID

    try:
        # Remove from registries
        del _DEBUG_SESSIONS[session_id]
        if session_id in _SESSION_CONTEXTS:
            del _SESSION_CONTEXTS[session_id]

        # Reset default if this was it
        if session_id == _DEFAULT_SESSION_ID:
            _DEFAULT_SESSION_ID = None
            clear_session_id()

        # Clear session context if it was the current one
        if get_session_id_from_context() == session_id:
            clear_session_id()

        logger.info("Successfully cleaned up session: %s", session_id)
        return True

    except Exception as e:
        logger.error("Error during cleanup of session %s: %s", session_id, e)
        if force:
            logger.warning("Forcing cleanup despite errors")
            # Force remove from registries
            _DEBUG_SESSIONS.pop(session_id, None)
            _SESSION_CONTEXTS.pop(session_id, None)
            return True
        return False


def _force_cleanup_registries(session_id: str) -> None:
    """Force cleanup of session registries, ignoring all errors.

    Parameters
    ----------
    session_id : str
        Session ID to forcibly clean up
    """
    global _DEFAULT_SESSION_ID

    logger.warning("Forcing cleanup of session registries for: %s", session_id)

    try:
        # Force remove from registries
        _DEBUG_SESSIONS.pop(session_id, None)
        _SESSION_CONTEXTS.pop(session_id, None)

        # Reset default if this was it
        if session_id == _DEFAULT_SESSION_ID:
            _DEFAULT_SESSION_ID = None
            try:  # noqa: SIM105
                clear_session_id()
            except Exception:  # noqa: S110
                pass  # Ignore errors during session ID clearing

        # Clear session context if it was the current one
        try:
            if get_session_id_from_context() == session_id:
                clear_session_id()
        except Exception:  # noqa: S110
            pass  # Ignore errors during session ID clearing

        logger.warning("Force cleanup completed for session: %s", session_id)

    except Exception as e:
        logger.error(
            "Critical error during force cleanup for session %s: %s",
            session_id,
            e,
        )


def cleanup_session(
    session_id: str,
    timeout: float | None = None,
    force: bool = False,
) -> bool:
    """Clean up a specific session with timeout and retry logic.

    This function is designed to be atomic and cancellation-safe.

    Parameters
    ----------
    session_id : str
        Session ID to clean up
    timeout : float
        Maximum time to wait for cleanup (seconds)
    force : bool
        If True, force cleanup even if stop fails

    Returns
    -------
    bool
        True if session was cleaned up
    """
    # Use config value if timeout not specified
    if timeout is None:
        timeout = config.session.default_cleanup_timeout

    # Track cleanup state for atomicity
    cleanup_state = {
        "api_stopped": False,
        "context_cleaned": False,
        "registries_cleaned": False,
    }

    logger.debug(
        "[CLEANUP] cleanup_session session_id=%s, timeout=%s, force=%s",
        session_id,
        timeout,
        force,
    )

    try:
        with _state_lock:
            if session_id not in _DEBUG_SESSIONS:
                logger.debug("[CLEANUP] Session not found: %s", session_id)
                return False

            service = _DEBUG_SESSIONS[session_id]
            context = _SESSION_CONTEXTS.get(session_id)

            # Phase 1: Attempt graceful shutdown with timeout
            if service and service.session and service.session.started:
                try:
                    shutdown_success = _attempt_graceful_shutdown(
                        service,
                        session_id,
                        timeout,
                        force,
                    )
                    cleanup_state["session_stopped"] = shutdown_success
                    if not shutdown_success and not force:
                        logger.warning(
                            "Failed to stop session %s gracefully",
                            session_id,
                        )
                        return False
                except Exception as e:
                    logger.warning(
                        "Error during graceful shutdown for session %s: %s",
                        session_id,
                        e,
                    )
                    cleanup_state["api_stopped"] = force
                    if not force:
                        return False

            # Phase 2: Clean up session context (always safe)
            try:
                _cleanup_session_context(context, session_id)
                cleanup_state["context_cleaned"] = True
            except Exception as e:
                logger.warning(
                    "Error cleaning session context for %s: %s",
                    session_id,
                    e,
                )
                # Context cleanup failure is not critical, continue

            # Phase 3: Clean up registries atomically
            try:
                success = _cleanup_registries(session_id, force)
                cleanup_state["registries_cleaned"] = success

                if success:
                    logger.info("Successfully cleaned up session: %s", session_id)
                    return True
                logger.warning(
                    "Failed to cleanup registries for session: %s",
                    session_id,
                )
                return force  # Return True if forced, False otherwise

            except Exception as e:
                logger.error(
                    "Critical error during registry cleanup for session %s: %s",
                    session_id,
                    e,
                )
                cleanup_state["registries_cleaned"] = False
                if force:
                    # Force cleanup of registries on critical error
                    try:
                        _force_cleanup_registries(session_id)
                        cleanup_state["registries_cleaned"] = True
                        return True
                    except Exception as force_e:
                        logger.error(
                            "Failed to force cleanup session %s: %s",
                            session_id,
                            force_e,
                        )
                return False

    except Exception as e:
        logger.exception(
            "Unexpected error during session cleanup %s: %s",
            session_id,
            e,
        )
        # Log cleanup state for debugging
        logger.error("Cleanup state when error occurred: %s", cleanup_state)

        # Try force cleanup if force=True
        if force:
            try:
                _force_cleanup_registries(session_id)
                return True
            except Exception as force_e:
                logger.error(
                    "Failed to force cleanup after error for session %s: %s",
                    session_id,
                    force_e,
                )
        return False


async def cleanup_session_async(
    session_id: str,
    timeout: float | None = None,
    force: bool = False,
) -> bool:
    """Async version of cleanup_session.

    NOTE: This runs cleanup synchronously in the current thread rather than
    using a thread executor. This is intentional - the cleanup_session function
    uses a threading.RLock that is also used by other code in the main thread.
    Running cleanup in a separate thread causes cross-thread lock contention
    and 10-second timeouts.

    The cleanup operation is typically fast (< 100ms), so briefly blocking
    the event loop is acceptable and avoids deadlock issues.

    Parameters
    ----------
    session_id : str
        Session ID to clean up
    timeout : float
        Maximum time to wait for cleanup (seconds)
    force : bool
        If True, force cleanup even if stop fails

    Returns
    -------
    bool
        True if session was cleaned up
    """
    # Run cleanup synchronously in the same thread to avoid lock contention
    # The threading.RLock used by cleanup_session is also used by main thread code,
    # so running in a separate thread causes deadlocks
    return cleanup_session(session_id, timeout, force)


def cleanup_all_sessions():
    """Clean up all active sessions."""
    with _state_lock:
        session_ids = list(_DEBUG_SESSIONS.keys())
        for sid in session_ids:
            cleanup_session(sid)
