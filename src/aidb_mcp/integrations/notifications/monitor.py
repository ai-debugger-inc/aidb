"""Debug event monitor for automatic notification generation.

This module provides the DebugEventMonitor class that polls debug sessions for state
changes and events when event bridges are not available.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from aidb.common.constants import MEDIUM_SLEEP_S
from aidb_logging import get_mcp_logger as get_logger

from ...session.manager_shared import _state_lock
from .api import (
    notify_breakpoint_hit,
    notify_session_state_changed,
    notify_watch_changed,
)
from .manager import NotificationManager

if TYPE_CHECKING:
    from aidb import DebugService

logger = get_logger(__name__)


class DebugEventMonitor:
    """Monitors debug sessions for events to notify about."""

    def __init__(self):
        """Initialize the event monitor."""
        self._monitoring = False
        self._monitor_task: asyncio.Task | None = None
        self._session_states: dict[str, dict[str, Any]] = {}
        self._watch_values: dict[str, dict[str, Any]] = {}

    async def start_monitoring(self) -> None:
        """Start monitoring debug sessions for events."""
        if self._monitoring:
            return

        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())

        await NotificationManager().start()

    async def stop_monitoring(self) -> None:
        """Stop monitoring."""
        self._monitoring = False
        if self._monitor_task:
            await self._monitor_task
            self._monitor_task = None

        await NotificationManager().stop()

    async def _monitor_loop(self) -> None:
        """Run the main monitoring loop.

        Note: This is now a fallback mechanism. Sessions with event bridges
        registered will get direct notifications without polling.
        """
        while self._monitoring:
            try:
                await self._check_sessions()
                await asyncio.sleep(MEDIUM_SLEEP_S)
            except Exception as e:
                logger.error("Error in monitor loop: %s", e)

    async def _check_sessions(self) -> None:
        """Check all sessions for state changes and events."""
        from ...session.manager import _DEBUG_SESSIONS, _SESSION_CONTEXTS

        with _state_lock:
            for session_id, session_data in _DEBUG_SESSIONS.items():
                try:
                    context = _SESSION_CONTEXTS.get(session_id)
                    if (
                        context
                        and hasattr(context, "event_bridge")
                        and context.event_bridge
                    ):
                        continue

                    await self._check_session(session_id, session_data)
                except Exception as e:
                    logger.error("Error checking session %s: %s", session_id, e)

    async def _check_session(self, session_id: str, session_data: DebugService) -> None:
        """Check a single session for events.

        Parameters
        ----------
        session_id : str
            Session ID
        session_data : DebugService
            DebugService instance for the session
        """
        service = session_data

        from ...session.manager import _SESSION_CONTEXTS

        context = _SESSION_CONTEXTS.get(session_id)

        if not context or not service:
            return

        try:
            session = service.session
            if not session:
                return
            status = session.status
        except Exception:
            return

        current_state = str(status) if status else "unknown"

        prev_state = self._session_states.get(session_id, {}).get("state")
        if prev_state and prev_state != current_state:
            await notify_session_state_changed(
                session_id=session_id,
                old_state=prev_state,
                new_state=current_state,
                reason=getattr(status, "stop_reason", None),
            )

        if session_id not in self._session_states:
            self._session_states[session_id] = {}

        self._session_states[session_id]["state"] = current_state

        if (
            current_state == "paused"
            and hasattr(status, "stop_reason")
            and "breakpoint" in str(status.stop_reason).lower()
        ):
            position = getattr(status, "current_position", None)
            if position:
                location = f"{position.file}:{position.line}"

                last_bp = self._session_states[session_id].get("last_breakpoint")
                if last_bp != location:
                    await notify_breakpoint_hit(
                        session_id=session_id,
                        location=location,
                        thread_id=getattr(status, "thread_id", None),
                    )
                    self._session_states[session_id]["last_breakpoint"] = location

        if hasattr(context, "watches") and context.watches:
            await self._check_watches(session_id, service, context.watches)

    async def _check_watches(
        self,
        session_id: str,
        service: Any,
        watches: set,
    ) -> None:
        """Check watch expressions for changes.

        Parameters
        ----------
        session_id : str
            Session ID
        service : DebugService
            Debug service instance
        watches : set
            Set of watch expressions
        """
        if session_id not in self._watch_values:
            self._watch_values[session_id] = {}

        for expression in watches:
            try:
                result = await service.variables.evaluate(expression)
                if not result.success:
                    continue

                current_value = result.value

                if expression in self._watch_values[session_id]:
                    prev_value = self._watch_values[session_id][expression]
                    if prev_value != current_value:
                        await notify_watch_changed(
                            session_id=session_id,
                            expression=expression,
                            old_value=prev_value,
                            new_value=current_value,
                            value_type=result.type,
                        )

                self._watch_values[session_id][expression] = current_value

            except Exception as e:
                logger.debug("Error evaluating watch %s: %s", expression, e)


_event_monitor = DebugEventMonitor()


async def start_event_monitoring() -> None:
    """Start monitoring debug events."""
    await _event_monitor.start_monitoring()


async def stop_event_monitoring() -> None:
    """Stop monitoring debug events."""
    await _event_monitor.stop_monitoring()
