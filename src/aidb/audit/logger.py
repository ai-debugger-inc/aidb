"""Core audit logging implementation."""

import asyncio
import atexit
import contextlib
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import aiofiles  # type: ignore[import-untyped]

from aidb.audit.events import AuditEvent
from aidb.common import AidbContext
from aidb.common.constants import (
    AUDIT_FLUSH_TIMEOUT_S,
    AUDIT_INIT_TIMEOUT_S,
    AUDIT_INIT_TIMEOUT_TEST_S,
    AUDIT_MAX_PENDING_EVENTS,
    AUDIT_QUEUE_MAX_SIZE,
    AUDIT_SHUTDOWN_TIMEOUT_S,
    AUDIT_SINGLETON_RESET_TIMEOUT_S,
    AUDIT_WORKER_TIMEOUT_S,
)
from aidb_common.config import config
from aidb_logging import get_logger

if TYPE_CHECKING:
    from aiofiles.threadpool.text import (
        AsyncTextIOWrapper,  # type: ignore[import-untyped]
    )

logger = get_logger(__name__)


class AuditLogger:
    """Thread-safe singleton audit logger with async writes.

    Implements a lightweight, high-performance audit logging system
    with automatic log rotation and minimal overhead.

    Attributes
    ----------
    _instance : Optional[AuditLogger]
        Singleton instance
    _lock : threading.Lock
        Thread safety lock for singleton creation
    _queue : asyncio.Queue
        Async write queue for non-blocking operations
    _worker_task : Optional[asyncio.Task]
        Background task for processing queue
    _file_handle : Optional[IO]
        Current log file handle
    _current_size : int
        Current log file size in bytes
    _enabled : bool
        Whether audit logging is enabled
    _max_size_bytes : int
        Maximum log file size before rotation
    _log_path : Path
        Path to current log file
    _retention_days : int
        Number of days to retain rotated logs
    _shutdown : bool
        Flag to signal worker thread shutdown
    """

    _instance: Optional["AuditLogger"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "AuditLogger":
        """Create or return singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize audit logger.

        Audit logging provides comprehensive event logging for debugging and compliance.
        """
        if hasattr(self, "_initialized"):
            return
        self._initialized = True

        # Configuration from ConfigManager
        audit_requested = config.is_audit_enabled()
        self._max_size_mb = float(config.get_audit_log_size_mb())
        self._max_size_bytes = int(self._max_size_mb * 1024 * 1024)
        self._retention_days = config.get_audit_retention_days()

        # Check if audit logging is enabled via environment variable (opt-in)
        enabled_env = os.getenv("AIDB_AUDIT_ENABLED", "false").lower() == "true"
        self._enabled = audit_requested and enabled_env

        if self._enabled:
            logger.debug("Audit logging enabled via AIDB_AUDIT_ENABLED")
        elif audit_requested and not enabled_env:
            logger.debug(
                "Audit logging requested but not enabled. "
                "Set AIDB_AUDIT_ENABLED=true to enable audit logging.",
            )

        # Determine log path
        custom_path = config.get_audit_log_path()
        if custom_path:
            self._log_path = Path(custom_path)
        else:
            ctx = AidbContext()
            self._log_path = Path(ctx.get_storage_path("audit")) / "audit.log"

        # Create directory if needed
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize state
        self._worker_task: asyncio.Task[None] | None = None
        self._file_handle: AsyncTextIOWrapper | None = None
        self._current_size = 0
        self._shutdown = False
        self._write_lock = asyncio.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        # Create queue immediately (will be used across threads)
        self._queue: asyncio.Queue[AuditEvent | None] = asyncio.Queue(
            maxsize=AUDIT_QUEUE_MAX_SIZE,
        )
        self._init_complete = threading.Event()
        self._queue_empty_event: asyncio.Event | None = None

        # Start worker task if enabled
        if self._enabled:
            self._ensure_event_loop()
            # Register cleanup on exit
            atexit.register(self._cleanup_sync)

    @property
    def is_running(self) -> bool:
        """Check if the audit logger is running."""
        return self._worker_task is not None and not self._worker_task.done()

    def _ensure_event_loop(self) -> None:
        """Ensure we have an event loop and start the worker."""
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop, create one in a thread
            self._loop = asyncio.new_event_loop()
            self._thread = threading.Thread(
                target=self._run_event_loop,
                daemon=True,
                name="AuditLoggerLoop",
            )
            self._thread.start()

        # Schedule queue creation and worker start in the loop
        # Don't wait - let it initialize asynchronously
        asyncio.run_coroutine_threadsafe(self._init_async(), self._loop)

    def _run_event_loop(self) -> None:
        """Run the event loop in a background thread."""
        if self._loop is None:
            return
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    async def _init_async(self) -> None:
        """Initialize async components."""
        # Create async event for queue empty signaling
        self._queue_empty_event = asyncio.Event()
        # Initially set since queue starts empty
        self._queue_empty_event.set()
        await self._start_worker()
        # Signal that initialization is complete
        self._init_complete.set()

    async def _start_worker(self) -> None:
        """Start background worker task for async writes."""
        # Queue is already created in __init__

        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker_loop())
            logger.debug("Audit logger worker started, writing to %s", self._log_path)

    async def _worker_loop(self) -> None:
        """Background worker loop for processing audit events."""
        while not self._shutdown:
            try:
                # Wait for events with timeout to allow shutdown checks
                if self._queue is None:
                    break

                # Clear the empty event since we're waiting for items
                if self._queue_empty_event and self._queue.empty():
                    self._queue_empty_event.set()
                else:
                    if self._queue_empty_event:
                        self._queue_empty_event.clear()

                event = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=AUDIT_WORKER_TIMEOUT_S,
                )
                if event is None:  # Shutdown signal
                    break
                await self._write_event(event)

                # Signal if queue is now empty
                if self._queue_empty_event and self._queue.empty():
                    self._queue_empty_event.set()
            except asyncio.TimeoutError:
                # Timeout is normal - signal queue is empty
                if self._queue_empty_event and self._queue.empty():
                    self._queue_empty_event.set()
                continue
            except Exception as e:
                # Log but don't crash - audit failures should never break operations
                logger.exception("Audit worker error: %s", e)

    async def _write_event(self, event: AuditEvent) -> None:
        """Write event to log file with rotation handling.

        Parameters
        ----------
        event : AuditEvent
            Event to write
        """
        async with self._write_lock:
            try:
                # Open file if needed
                if self._file_handle is None:
                    await self._open_log_file()

                # Write event as JSON line
                json_line = event.to_json() + "\n"
                json_bytes = json_line.encode("utf-8")

                # Check if rotation needed
                if self._current_size + len(json_bytes) > self._max_size_bytes:
                    await self._rotate_log()
                    await self._open_log_file()

                # Write to file
                if self._file_handle is None:
                    msg = "File handle is None after open attempt"
                    raise RuntimeError(msg)

                await self._file_handle.write(json_line)
                await self._file_handle.flush()

                self._current_size += len(json_bytes)

            except Exception as e:
                logger.exception("Failed to write audit event: %s", e)

    async def _open_log_file(self) -> None:
        """Open or create the log file."""
        try:
            # Close existing handle
            if self._file_handle:
                await self._file_handle.close()

            # Open in append mode
            self._file_handle = await aiofiles.open(
                self._log_path,
                "a",
                encoding="utf-8",
            )

            # Get current size
            self._current_size = (
                self._log_path.stat().st_size if self._log_path.exists() else 0
            )

            # Set restrictive permissions (owner read/write only)
            if self._log_path.exists():
                Path(self._log_path).chmod(0o600)

        except Exception as e:
            logger.exception("Failed to open audit log file: %s", e)
            self._file_handle = None

    async def _rotate_log(self) -> None:
        """Rotate current log file and cleanup old files."""
        try:
            # Close current file
            if self._file_handle:
                # Flush before closing to ensure all writes complete
                with contextlib.suppress(Exception):
                    await self._file_handle.flush()
                await self._file_handle.close()
                self._file_handle = None

            # Rename with timestamp
            if self._log_path.exists():
                timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                rotated_path = self._log_path.parent / f"audit.log.{timestamp}"
                self._log_path.rename(rotated_path)
                logger.info("Rotated audit log to %s", rotated_path)

                # Cleanup old files
                await self._cleanup_old_logs()

        except Exception as e:
            logger.exception("Failed to rotate audit log: %s", e)

    async def _cleanup_old_logs(self) -> None:
        """Remove rotated logs older than retention period."""
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=self._retention_days)
            pattern = "audit.log.*"

            # Run file operations in executor to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._cleanup_old_logs_sync,
                cutoff,
                pattern,
            )

        except Exception as e:
            logger.exception("Failed to cleanup old audit logs: %s", e)

    def _cleanup_old_logs_sync(self, cutoff: datetime, pattern: str) -> None:
        """Synchronize helper for cleaning up old logs."""
        for old_file in self._log_path.parent.glob(pattern):
            # Skip the current log
            if old_file == self._log_path:
                continue

            # Check age
            if old_file.stat().st_mtime < cutoff.timestamp():
                old_file.unlink()
                logger.debug("Removed old audit log: %s", old_file)

    def log(self, event: AuditEvent) -> None:
        """Queue an audit event for logging.

        Parameters
        ----------
        event : AuditEvent
            Event to log
        """
        if not self._enabled:
            return

        try:
            # Ensure we have a loop
            if self._loop is None:
                self._ensure_event_loop()
                # Wait for initialization to complete
                # Use shorter timeout in test environments
                init_timeout = (
                    AUDIT_INIT_TIMEOUT_TEST_S
                    if os.getenv("PYTEST_CURRENT_TEST")
                    else AUDIT_INIT_TIMEOUT_S
                )
                if not self._init_complete.wait(timeout=init_timeout):
                    logger.warning("Audit logger initialization timeout")
                    return

            # Queue for async write
            try:
                if self._loop is not None and not self._loop.is_closed():
                    asyncio.run_coroutine_threadsafe(self._queue.put(event), self._loop)
                else:
                    logger.warning("Event loop not available for audit logging")
            except asyncio.QueueFull:
                logger.warning("Audit queue full, dropping event")

        except Exception as e:
            # Never fail due to audit logging
            logger.exception("Failed to queue audit event: %s", e)

    def flush(self) -> None:
        """Flush pending events to disk."""
        if not self._enabled or self._loop is None:
            return

        # Run async flush in the event loop
        future = asyncio.run_coroutine_threadsafe(self._flush_async(), self._loop)
        future.result(timeout=AUDIT_FLUSH_TIMEOUT_S)

    async def _flush_async(self) -> None:
        """Async helper for flushing."""
        if self._queue and self._queue_empty_event:
            # Wait for queue empty event with timeout
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(
                    self._queue_empty_event.wait(),
                    timeout=AUDIT_WORKER_TIMEOUT_S,
                )

        # Flush file
        async with self._write_lock:
            if self._file_handle:
                await self._file_handle.flush()

    def _cleanup_sync(self) -> None:
        """Synchronize cleanup for atexit handler."""
        if self._loop and self._enabled and not self._loop.is_closed():
            try:
                # Schedule async shutdown
                future = asyncio.run_coroutine_threadsafe(
                    self.shutdown(),
                    self._loop,
                )
                future.result(timeout=AUDIT_SHUTDOWN_TIMEOUT_S)
            except Exception as e:
                msg = f"Failed to shutdown audit logger cleanly: {e}"
                logger.warning(msg)

                # Stop the event loop
                with contextlib.suppress(RuntimeError):
                    # Loop already stopped or closed
                    self._loop.call_soon_threadsafe(self._loop.stop)

    async def shutdown(self) -> None:
        """Shutdown audit logger and flush pending events."""
        if self._shutdown:
            return

        logger.debug("Shutting down audit logger")
        self._shutdown = True

        if self._enabled and self._worker_task:
            # Signal shutdown - use put_nowait to avoid blocking on full queue
            if self._queue:
                try:
                    self._queue.put_nowait(None)
                except asyncio.QueueFull:
                    # Queue is full, worker will exit when it checks _shutdown flag
                    logger.debug("Queue full during shutdown, relying on shutdown flag")

            # Wait for worker to finish
            try:
                await asyncio.wait_for(
                    self._worker_task,
                    timeout=AUDIT_SHUTDOWN_TIMEOUT_S,
                )
            except asyncio.TimeoutError:
                logger.warning("Worker task timeout, cancelling")
                self._worker_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._worker_task

            # Process any remaining events (limit to prevent infinite loop)
            if self._queue:
                remaining_count = 0
                while (
                    not self._queue.empty()
                    and remaining_count < AUDIT_MAX_PENDING_EVENTS
                ):
                    try:
                        event = self._queue.get_nowait()
                        if event is not None:
                            await self._write_event(event)
                        remaining_count += 1
                    except asyncio.QueueEmpty:
                        break
                    except Exception:
                        break

            # Close file
            async with self._write_lock:
                if self._file_handle:
                    await self._file_handle.close()
                    self._file_handle = None

    def is_enabled(self) -> bool:
        """Check if audit logging is enabled.

        Returns
        -------
        bool
            True if audit logging is enabled
        """
        return self._enabled

    async def cleanup(self) -> None:
        """Clean up old rotated log files.

        This method removes rotated log files older than the retention period. It's
        useful for manual cleanup or scheduled maintenance.
        """
        if self._enabled:
            await self._cleanup_old_logs()

    @classmethod
    def _reset_singleton(cls) -> None:
        """Reset the singleton instance for testing.

        This method is intended for use in tests only to ensure clean state between test
        runs.
        """
        if cls._instance is not None:
            # Check if already shutting down to avoid deadlock
            if (
                not getattr(cls._instance, "_shutdown", False)
                and hasattr(cls._instance, "_loop")
                and cls._instance._loop
                and not cls._instance._loop.is_closed()
            ):
                # Try to shutdown cleanly
                try:
                    future = asyncio.run_coroutine_threadsafe(
                        cls._instance.shutdown(),
                        cls._instance._loop,
                    )
                    future.result(timeout=AUDIT_SINGLETON_RESET_TIMEOUT_S)
                except Exception as e:
                    msg = f"Failed to shutdown audit logger singleton: {e}"
                    logger.warning(msg)
            cls._instance = None


# Module-level convenience function
def get_audit_logger() -> AuditLogger:
    """Get the singleton audit logger instance.

    Returns
    -------
    AuditLogger
        The global audit logger
    """
    return AuditLogger()
