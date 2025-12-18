"""Connection health monitoring for MCP debugging tools.

This module handles connection health checks, heartbeat monitoring, and automatic
recovery attempts for debug sessions.
"""

from __future__ import annotations

import asyncio
import time

from aidb_common.config import config
from aidb_logging import get_mcp_logger as get_logger

from .manager import (
    _DEBUG_SESSIONS,
    _SESSION_CONTEXTS,
    _state_lock,
)

logger = get_logger(__name__)

# Connection health monitoring
_last_heartbeat: float = 0
_heartbeat_interval: float = config.get_mcp_health_check_interval()
_connection_healthy: bool = False
_health_check_task: asyncio.Task | None = None


def check_connection_health(session_id: str | None = None) -> bool:
    """Check the health of debug connections.

    Parameters
    ----------
    session_id : str, optional
        Specific session to check. If None, checks all sessions.

    Returns
    -------
    bool
        True if connection(s) are healthy
    """
    global _last_heartbeat, _connection_healthy

    with _state_lock:
        current_time = time.time()

        # Check specific session or all sessions
        sessions_to_check = (
            {session_id: _DEBUG_SESSIONS.get(session_id)}
            if session_id
            else _DEBUG_SESSIONS.copy()
        )

        all_healthy = True
        for sid, service in sessions_to_check.items():
            if service and service.session.started:
                try:
                    # Try a simple operation to test connection
                    _ = service.session.info
                    _last_heartbeat = current_time
                except Exception as e:
                    logger.warning("Connection unhealthy for session %s: %s", sid, e)
                    all_healthy = False

        _connection_healthy = all_healthy
        return all_healthy


async def heartbeat_monitor():
    """Background task to monitor connection health."""
    while True:
        try:
            # Check all active sessions
            healthy = check_connection_health()

            if not healthy:
                logger.warning("Connection health check failed, attempting recovery...")
                # Try to recover each unhealthy session
                for session_id in list(_DEBUG_SESSIONS.keys()):
                    if not check_connection_health(session_id):
                        await attempt_recovery(session_id)

            await asyncio.sleep(_heartbeat_interval)

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Error in heartbeat monitor: %s", e)
            await asyncio.sleep(_heartbeat_interval)


async def attempt_recovery(session_id: str) -> bool:
    """Attempt to recover a lost connection.

    Parameters
    ----------
    session_id : str
        Session ID to recover

    Returns
    -------
    bool
        True if recovery successful
    """
    with _state_lock:
        context = _SESSION_CONTEXTS.get(session_id)
        if not context or not context.session_started:
            return False

        session_info = context.session_info
        if not session_info:
            return False

        service = _DEBUG_SESSIONS.get(session_id)
        if not service:
            return False

        try:
            # Try to reconnect to existing session
            if service.session and hasattr(service.session, "reconnect"):
                service.session.reconnect(session_info.id)
                return True
        except Exception as e:
            msg = f"Failed to reconnect to session {session_info.id}: {e}"
            logger.debug(msg)

        # If reconnection fails, mark session as dead
        context.session_started = False
        return False


def start_health_monitoring():
    """Start the connection health monitoring task."""
    global _health_check_task

    with _state_lock:
        if _health_check_task is None or _health_check_task.done():
            try:
                loop = asyncio.get_event_loop()
                _health_check_task = loop.create_task(heartbeat_monitor())
            except RuntimeError:
                # No event loop, will try again later
                pass


def stop_health_monitoring():
    """Stop the connection health monitoring task."""
    with _state_lock:
        if _health_check_task and not _health_check_task.done():
            _health_check_task.cancel()


def get_health_status() -> dict:
    """Get current health monitoring status.

    Returns
    -------
    dict
        Health status information
    """
    with _state_lock:
        return {
            "healthy": _connection_healthy,
            "last_heartbeat": _last_heartbeat,
            "heartbeat_interval": _heartbeat_interval,
            "monitoring_active": _health_check_task is not None
            and not _health_check_task.done(),
            "time_since_heartbeat": (
                time.time() - _last_heartbeat if _last_heartbeat > 0 else None
            ),
        }
