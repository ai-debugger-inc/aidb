"""Notification manager for MCP debugging events.

This module provides the core NotificationManager class that handles event queuing, rate
limiting, and notification delivery.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from aidb.common.constants import RECEIVE_POLL_TIMEOUT_S
from aidb_common.config import config
from aidb_common.patterns.singleton import Singleton
from aidb_logging import get_mcp_logger as get_logger

from ...core.constants import EventType

if TYPE_CHECKING:
    from collections.abc import Callable

logger = get_logger(__name__)


class NotificationManager(Singleton["NotificationManager"]):
    """Manage debugging event notifications for MCP with rate limiting."""

    MAX_QUEUE_SIZE = config.get_mcp_notification_queue_size()
    RATE_LIMIT_WINDOW = config.get_mcp_notification_cooldown()
    EVENT_TTL_SECONDS = config.get_mcp_event_ttl_seconds()
    AGGREGATION_WINDOW = config.get_mcp_event_batch_timeout()

    def __init__(self):
        """Initialize the notification manager with queue and rate limiting."""
        self._listeners: dict[str, list[Callable]] = {
            EventType.BREAKPOINT_HIT.value: [],
            EventType.EXCEPTION.value: [],
            EventType.SESSION_STATE_CHANGED.value: [],
            EventType.WATCH_CHANGED.value: [],
            EventType.THREAD_EVENT.value: [],
        }

        self._notification_queue: asyncio.Queue = asyncio.Queue(
            maxsize=self.MAX_QUEUE_SIZE,
        )
        self._dropped_count = 0
        self._total_processed = 0

        self._last_notification_time: dict[tuple[str, str], float] = {}
        self._rate_limit_violations = 0

        self._event_aggregation: dict[tuple[str, str], dict[str, Any]] = defaultdict(
            lambda: {"count": 0, "first_seen": None, "last_seen": None},
        )

        self._event_history: deque[tuple[float, str, dict[str, Any]]] = deque(
            maxlen=config.get_mcp_event_history_size(),
        )

        self._running = False
        self._task: asyncio.Task | None = None

    def register_listener(self, event_type: str, callback: Callable) -> None:
        """Register a listener for an event type.

        Parameters
        ----------
        event_type : str
            Type of event to listen for
        callback : Callable
            Callback function to invoke on event
        """
        if event_type in self._listeners:
            self._listeners[event_type].append(callback)
        else:
            logger.warning("Unknown event type: %s", event_type)

    def unregister_listener(self, event_type: str, callback: Callable) -> None:
        """Unregister a listener.

        Parameters
        ----------
        event_type : str
            Event type
        callback : Callable
            Callback to remove
        """
        if event_type in self._listeners:
            with contextlib.suppress(ValueError):
                self._listeners[event_type].remove(callback)

    async def emit(self, event_type: str, data: dict[str, Any]) -> None:
        """Emit a notification event with rate limiting and queue management.

        Parameters
        ----------
        event_type : str
            Type of event
        data : dict
            Event data
        """
        if event_type not in self._listeners:
            return

        current_time = time.time()

        session_id = data.get("session_id", "global")
        rate_limit_key = (session_id, event_type)

        last_time = self._last_notification_time.get(rate_limit_key, 0)
        if current_time - last_time < self.RATE_LIMIT_WINDOW:
            if event_type == EventType.BREAKPOINT_HIT.value:
                self._aggregate_event(rate_limit_key, data)
            self._rate_limit_violations += 1
            logger.debug(
                "Rate limited %s notification for session %s",
                event_type,
                session_id,
            )
            return

        if rate_limit_key in self._event_aggregation:
            agg_data = self._event_aggregation[rate_limit_key]
            if agg_data["count"] > 0:
                data["aggregated"] = True
                data["hit_count"] = agg_data["count"] + 1
                data["first_hit"] = agg_data["first_seen"]
                data["message"] = (
                    f"{data.get('message', '')} (hit {agg_data['count'] + 1} times)"
                )
                self._event_aggregation[rate_limit_key] = {
                    "count": 0,
                    "first_seen": None,
                    "last_seen": None,
                }

        data["timestamp"] = datetime.now(timezone.utc).isoformat()
        data["event_type"] = event_type
        data["event_time"] = current_time

        try:
            self._notification_queue.put_nowait((event_type, data))
            self._last_notification_time[rate_limit_key] = current_time

            self._event_history.append((current_time, event_type, data.copy()))

        except asyncio.QueueFull:
            self._dropped_count += 1
            logger.warning(
                "Notification queue full, dropped %s event. Total dropped: %s",
                event_type,
                self._dropped_count,
            )

            if event_type in [
                EventType.EXCEPTION.value,
                EventType.SESSION_STATE_CHANGED.value,
            ]:
                try:
                    old_event = self._notification_queue.get_nowait()
                    self._notification_queue.put_nowait((event_type, data))
                    logger.debug(
                        "Replaced %s with critical %s",
                        old_event[0],
                        event_type,
                    )
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass

    def _aggregate_event(
        self,
        rate_limit_key: tuple[str, str],
        data: dict[str, Any],
    ) -> None:
        """Aggregate repeated events for later batch notification.

        Parameters
        ----------
        rate_limit_key : tuple
            (session_id, event_type) key for aggregation
        data : dict
            Event data
        """
        agg = self._event_aggregation[rate_limit_key]
        agg["count"] += 1
        if agg["first_seen"] is None:
            agg["first_seen"] = data.get(
                "timestamp",
                datetime.now(timezone.utc).isoformat(),
            )
        agg["last_seen"] = data.get("timestamp", datetime.now(timezone.utc).isoformat())

    async def start(self) -> None:
        """Start the notification processor."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._process_notifications())

    async def stop(self) -> None:
        """Stop the notification processor."""
        self._running = False
        if self._task:
            await self._task
            self._task = None

    async def _process_notifications(self) -> None:
        """Process queued notifications with TTL checking."""
        while self._running:
            try:
                event_type, data = await asyncio.wait_for(
                    self._notification_queue.get(),
                    timeout=RECEIVE_POLL_TIMEOUT_S,
                )

                event_time = data.get("event_time", time.time())
                if time.time() - event_time > self.EVENT_TTL_SECONDS:
                    logger.debug(
                        "Skipping stale %s event (age: %.1fs)",
                        event_type,
                        time.time() - event_time,
                    )
                    continue

                self._total_processed += 1

                listener_count = len(self._listeners[event_type])
                if listener_count == 0:
                    logger.debug("No listeners for  event %s", event_type)
                    continue

                for callback in self._listeners[event_type]:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(data)
                        else:
                            callback(data)
                    except Exception as e:
                        logger.error("Error in notification callback: %s", e)

                if self._total_processed % 100 == 0:
                    logger.info(
                        "Notification stats: processed=%s, dropped=%s, rate_limited=%s",
                        self._total_processed,
                        self._dropped_count,
                        self._rate_limit_violations,
                    )

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error("Error processing notification: %s", e)

    def get_stats(self) -> dict[str, Any]:
        """Get notification manager statistics.

        Returns
        -------
        dict
            Statistics about notification processing
        """
        return {
            "total_processed": self._total_processed,
            "dropped_count": self._dropped_count,
            "rate_limit_violations": self._rate_limit_violations,
            "queue_size": self._notification_queue.qsize(),
            "max_queue_size": self.MAX_QUEUE_SIZE,
            "event_history_size": len(self._event_history),
        }

    def get_recent_events(self, count: int = 10) -> list[dict[str, Any]]:
        """Get recent events from history.

        Parameters
        ----------
        count : int
            Number of events to return

        Returns
        -------
        list
            Recent events
        """
        events = []
        for timestamp, event_type, data in list(self._event_history)[-count:]:
            events.append({"time": timestamp, "type": event_type, "data": data})
        return events

    def cleanup_session(self, session_id: str) -> None:
        """Clean up session-specific rate limiting and aggregation data.

        Parameters
        ----------
        session_id : str
            Session ID to clean up
        """
        keys_to_remove = [
            key for key in self._last_notification_time if key[0] == session_id
        ]
        for key in keys_to_remove:
            del self._last_notification_time[key]

        agg_keys_to_remove = [
            key for key in self._event_aggregation if key[0] == session_id
        ]
        for key in agg_keys_to_remove:
            del self._event_aggregation[key]

        logger.debug("Cleaned up notification data for session %s", session_id)
