"""Background message receiver for DAP client."""

import asyncio
import contextlib
import time
from typing import TYPE_CHECKING, Optional

from aidb.common.constants import MAX_CONSECUTIVE_FAILURES, SHORT_SLEEP_S
from aidb.common.errors import DebugConnectionError

if TYPE_CHECKING:
    from aidb.interfaces.context import IContext

    from .client import DAPClient


class MessageReceiver:
    """Background task that receives messages from the DAP adapter.

    This class runs as an asyncio task and continuously receives messages from
    the transport layer, passing them to the client for processing.

    Key features: - Runs as background asyncio task - Handles connection errors
    gracefully - Can be stopped cleanly - No direct request sending (clean
    architecture!)
    """

    def __init__(self, client: "DAPClient", ctx: Optional["IContext"] = None):
        """Initialize message receiver.

        Parameters
        ----------
        client : DAPClient
            The DAP client to send messages to
        ctx : IContext, optional
            Application context for logging
        """
        self._client = client
        self._ctx = ctx or client.ctx
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._running = False
        self._stopping = False  # Flag to indicate intentional shutdown

    async def start(self) -> None:
        """Start the receiver task."""
        if self._running:
            self._ctx.warning("Receiver already running")
            return

        self._stop_event.clear()
        self._running = True

        self._task = asyncio.create_task(self._receive_loop(), name="DAP-Receiver")

        self._ctx.debug("Message receiver started")

    async def stop(self, timeout: float = 2.0) -> None:
        """Stop the receiver task.

        Parameters
        ----------
        timeout : float
            Maximum time to wait for task to stop
        """
        if not self._running:
            return

        self._ctx.debug("Stopping message receiver...")
        self._stopping = True  # Mark as intentionally stopping
        self._stop_event.set()

        if self._task and not self._task.done():
            try:
                await asyncio.wait_for(self._task, timeout=timeout)
            except asyncio.TimeoutError:
                self._ctx.warning("Receiver task did not stop cleanly")
                self._task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._task

        self._running = False
        self._ctx.debug("Message receiver stopped")

    def _record_task_info(self) -> None:
        """Record receiver task information for debugging."""
        try:
            st = self._client.state
            current_task = asyncio.current_task()
            st.receiver_task_name = (
                current_task.get_name() if current_task else "unknown"
            )
        except Exception as e:
            msg = f"Failed to get current task name for receiver: {e}"
            self._ctx.debug(msg)

    def _capture_receive_timing(self) -> None:
        """Capture timing instrumentation for received message."""
        try:
            t_wall = time.time()
            t_ns = time.perf_counter_ns()
            current_task = asyncio.current_task()
            tname = current_task.get_name() if current_task else "unknown"
            prev_ns = self._client.state.last_message_received_mono_ns
            since_prev_ms = (
                (t_ns - prev_ns) / 1_000_000.0 if prev_ns is not None else None
            )
            self._client.state.last_message_received_wall = t_wall
            self._client.state.last_message_received_mono_ns = t_ns
            self._client.state.receiver_task_name = tname
            # Log timing at TRACE level (performance profiling detail)
            if since_prev_ms is not None:
                self._ctx.trace(
                    f"RECEIVER: ts={t_wall:.6f} task={tname} "
                    f"since_prev_ms={since_prev_ms:.3f}",
                )
            else:
                self._ctx.trace(
                    f"RECEIVER: ts={t_wall:.6f} task={tname} first_msg",
                )
        except Exception as e:
            msg = f"Failed to capture receive timing instrumentation: {e}"
            self._ctx.debug(msg)

    def _log_received_message(self, message: dict) -> None:
        """Log information about received message.

        Parameters
        ----------
        message : dict
            The received message to log
        """
        msg_type = message.get("type", "unknown")
        if msg_type == "event":
            event_name = message.get("event", "unknown")
            self._ctx.info(f"RECEIVER: Got event: {event_name}")
        elif msg_type == "response":
            cmd = message.get("command", "unknown")
            self._ctx.info(f"RECEIVER: Got response for: {cmd}")

    def _handle_connection_error(self, e: DebugConnectionError) -> bool:
        """Handle connection errors during message receiving.

        Parameters
        ----------
        e : DebugConnectionError
            The connection error to handle

        Returns
        -------
        bool
            True if should break from loop, False to continue
        """
        if self._stopping:
            # Expected during shutdown - just debug log
            self._ctx.debug(f"Connection closed during shutdown: {e}")
            return True
        if "timeout" in str(e).lower():
            # Just a timeout, continue
            return False
        # Connection closed (may be normal or unexpected)
        self._ctx.info(f"Connection closed in receiver: {e}")
        self._client.state.connected = False
        return True

    async def _handle_general_error(self, e: Exception) -> bool:
        """Handle general exceptions in the receive loop.

        Parameters
        ----------
        e : Exception
            The exception to handle

        Returns
        -------
        bool
            True if should break from loop, False to continue
        """
        if self._stopping:
            # Expected during shutdown
            self._ctx.debug(f"Exception during shutdown (expected): {e}")
            return True

        # Unexpected error - log but continue
        self._ctx.error(f"Unexpected error in receiver loop: {e}")

        # If we get too many errors, stop
        self._client.state.consecutive_failures += 1
        if self._client.state.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            self._ctx.error("Too many consecutive failures, stopping receiver")
            return True

        # Brief pause before retry
        await asyncio.sleep(SHORT_SLEEP_S)
        return False

    async def _process_single_iteration(self, loop_count: int) -> bool:  # noqa: ARG002
        """Process a single iteration of the receive loop.

        Parameters
        ----------
        loop_count : int
            The current loop iteration number

        Returns
        -------
        bool
            True if should continue loop, False to stop
        """
        # Check stop event FIRST - before any I/O operations
        # This allows clean exit when stop() is called before transport disconnect
        if self._stop_event.is_set():
            self._ctx.debug("Stop event set, exiting receiver loop")
            return False

        # Check if we're still connected
        if not self._client.transport.is_connected():
            self._ctx.debug("Transport disconnected, stopping receiver")
            return False

        try:
            message = await self._client.transport.receive_message()

            # Capture timing and log message
            self._capture_receive_timing()
            self._log_received_message(message)

            # Process the message
            await self._handle_message(message)

            # Check if session has terminated AFTER processing the message
            # This ensures we process the terminate response before stopping
            if self._client.is_terminated:
                self._ctx.debug("Session terminated, stopping receiver")
                return False

            return True

        except DebugConnectionError as e:
            should_break = self._handle_connection_error(e)
            return not should_break

    async def _receive_loop(self) -> None:
        """Run the main receive loop in background task."""
        self._ctx.debug("Receiver loop started")
        self._record_task_info()
        loop_count = 0

        try:
            while not self._stop_event.is_set():
                loop_count += 1
                if loop_count % 10 == 0:
                    self._ctx.debug(f"Receiver loop iteration {loop_count}")

                try:
                    should_continue = await self._process_single_iteration(loop_count)
                    if not should_continue:
                        break

                except Exception as e:
                    should_break = await self._handle_general_error(e)
                    if should_break:
                        break

        except asyncio.CancelledError:
            # Expected during cleanup - don't re-raise, exit cleanly
            self._ctx.debug("Receiver loop cancelled")
        finally:
            self._ctx.debug("Receiver loop ended")
            self._running = False
            self._stopping = False  # Reset for potential reuse

    async def _handle_message(self, message: dict) -> None:
        """Handle a received message.

        Parameters
        ----------
        message : dict
            The received message
        """
        try:
            # Pass to client for processing
            await self._client.process_message(message)

            # Reset failure count on success
            self._client.state.consecutive_failures = 0

        except Exception as e:
            self._ctx.error(f"Error processing message: {e}")

    @property
    def is_running(self) -> bool:
        """Check if receiver is running."""
        return self._running and self._task is not None and not self._task.done()


async def start_receiver(client: "DAPClient") -> MessageReceiver:
    """Start a message receiver for the given client.

    This is a convenience function to create and start a receiver.

    Parameters
    ----------
    client : DAPClient
        The client to receive messages for

    Returns
    -------
    MessageReceiver
        The started receiver
    """
    # Extract underlying AidbContext if client.ctx is PrefixedLogger
    ctx = client.ctx.ctx if hasattr(client.ctx, "ctx") else client.ctx
    receiver = MessageReceiver(client, ctx)
    await receiver.start()

    # Store reference in client for cleanup
    client._receiver = receiver

    return receiver
