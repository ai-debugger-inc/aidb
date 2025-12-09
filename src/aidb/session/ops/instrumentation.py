"""Instrumentation for step operations and DAP event tracking.

This module provides comprehensive metrics collection and logging for debugging session
operations, particularly focused on step operations (continue, step_into, step_out,
step_over) and their interaction with DAP events.
"""

import functools
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from aidb.dap.client.constants import EventType
from aidb.patterns import Obj

if TYPE_CHECKING:
    from aidb.dap.client.client import DAPClient


@dataclass
class StepMetrics(Obj):
    """Metrics for step operation logging.

    Captures comprehensive state information about DAP client and session at various
    phases of step operations.
    """

    operation: str  # "continue", "step_into", "step_out", "step_over", "wait"
    phase: str  # "pre", "clear", "wait", "result", "timeout", "start", "complete"

    # Event flags
    stopped_flag: bool = False
    terminated_flag: bool = False

    # Event ages (seconds since last signal)
    stopped_signal_age: float | None = None
    stopped_processed_age: float | None = None
    terminated_signal_age: float | None = None
    terminated_processed_age: float | None = None

    # Message timing
    last_message_age: float | None = None

    # AidbThread info
    current_thread_id: int | None = None
    current_thread_name: str | None = None
    receiver_thread_id: int | None = None
    receiver_thread_name: str | None = None

    # DAP state
    stop_reason: str | None = None
    target_thread_id: int | None = None
    current_dap_thread_id: int | None = None

    # Additional context
    timeout_value: float | None = None
    connection_diagnostics: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def capture(
        cls,
        dap_client: "DAPClient",
        operation: str,
        phase: str,
        target_thread_id: int | None = None,
        timeout: float | None = None,
    ) -> "StepMetrics":
        """Capture current metrics from DAP client.

        Parameters
        ----------
        dap_client : DAPClient
            The DAP client to capture metrics from
        operation : str
            The operation name (continue, step_into, wait, etc.)
        phase : str
            The phase of operation (pre, clear, wait, result, timeout)
        target_thread_id : int, optional
            Target thread ID for step operations
        timeout : float, optional
            Timeout value being used

        Returns
        -------
        StepMetrics
            Captured metrics instance
        """
        now = time.time()

        # Safe attribute access with defaults
        try:
            ep = dap_client.event_processor
            st = dap_client.state
        except (AttributeError, KeyError):
            # Return minimal metrics if client not fully initialized
            return cls(
                operation=operation,
                phase=phase,
                target_thread_id=target_thread_id,
                timeout_value=timeout,
            )

        # Helper to compute age safely
        def age(timestamp):
            return (now - timestamp) if timestamp else None

        # Safely extract event flags
        stopped_event_key = EventType.STOPPED.value
        terminated_event_key = EventType.TERMINATED.value
        try:
            default_event = threading.Event()
            stopped_received = ep._event_received.get(stopped_event_key, default_event)
            stopped_flag = stopped_received.is_set()
            terminated_flag = ep._event_received.get(
                terminated_event_key,
                threading.Event(),
            ).is_set()
        except (AttributeError, KeyError):
            stopped_flag = False
            terminated_flag = False

        # Safely extract timestamps
        try:
            event_walls = getattr(st, "event_last_signaled_wall", {})
            processed_walls = getattr(st, "event_last_processed_wall", {})

            stopped_signal_age = age(event_walls.get(stopped_event_key))
            stopped_processed_age = age(processed_walls.get(stopped_event_key))
            terminated_signal_age = age(event_walls.get(terminated_event_key))
            terminated_processed_age = age(processed_walls.get(terminated_event_key))
            last_message_age = age(getattr(st, "last_message_received_wall", None))
        except (AttributeError, KeyError):
            stopped_signal_age = None
            stopped_processed_age = None
            terminated_signal_age = None
            terminated_processed_age = None
            last_message_age = None

        # AidbThread information
        current_thread_id = threading.get_ident()
        current_thread_name = threading.current_thread().name
        receiver_thread_id = getattr(st, "receiver_thread_id", None)
        receiver_thread_name = getattr(st, "receiver_thread_name", None)

        # DAP state
        stop_reason = getattr(st, "stop_reason", None)
        current_dap_thread_id = getattr(st, "current_thread_id", None)

        return cls(
            operation=operation,
            phase=phase,
            stopped_flag=stopped_flag,
            terminated_flag=terminated_flag,
            stopped_signal_age=stopped_signal_age,
            stopped_processed_age=stopped_processed_age,
            terminated_signal_age=terminated_signal_age,
            terminated_processed_age=terminated_processed_age,
            last_message_age=last_message_age,
            current_thread_id=current_thread_id,
            current_thread_name=current_thread_name,
            receiver_thread_id=receiver_thread_id,
            receiver_thread_name=receiver_thread_name,
            stop_reason=stop_reason,
            target_thread_id=target_thread_id,
            current_dap_thread_id=current_dap_thread_id,
            timeout_value=timeout,
        )

    def to_debug_string(self) -> str:
        """Format metrics for debug logging.

        Returns
        -------
        str
            Formatted debug string tailored to the operation phase
        """
        # Format based on phase
        if self.phase == "pre":
            return (
                f"{self.operation} pre-clear: "
                f"stopped={self.stopped_flag} (age={self._format_age(self.stopped_signal_age)}s) "  # noqa: E501
                f"terminated={self.terminated_flag} (age={self._format_age(self.terminated_signal_age)}s) "  # noqa: E501
                f"stop_reason={self.stop_reason} "
                f"threads=[target:{self.target_thread_id}, current:{self.current_dap_thread_id}] "  # noqa: E501
                f"last_msg_age={self._format_age(self.last_message_age)}s "
                f"thr={self._format_thread(self.current_thread_id, self.current_thread_name)} "  # noqa: E501
                f"recv_thr={self._format_thread(self.receiver_thread_id, self.receiver_thread_name)}"  # noqa: E501
            )
        if self.phase == "clear":
            return f"{self.operation} post-clear: stopped={self.stopped_flag}"
        if self.phase == "wait":
            timeout_str = (
                f"{self.timeout_value:.2f}s" if self.timeout_value else "default"
            )
            return f"{self.operation} waiting: timeout={timeout_str}"
        if self.phase == "result":
            return (
                f"{self.operation} complete: "
                f"stop_reason={self.stop_reason} "
                f"stopped_age={self._format_age(self.stopped_signal_age)}s "
                f"terminated_age={self._format_age(self.terminated_signal_age)}s"
            )
        if self.phase == "timeout":
            return (
                f"{self.operation} TIMEOUT: "
                f"last_msg_age={self._format_age(self.last_message_age)}s "
                f"receiver={self._format_thread(self.receiver_thread_id, self.receiver_thread_name)} "  # noqa: E501
                f"stopped_flag={self.stopped_flag} terminated_flag={self.terminated_flag}"  # noqa: E501
            )
        if self.phase == "start":
            return (
                f"{self.operation} start: "
                f"stopped={self.stopped_flag} terminated={self.terminated_flag} "
                f"ages stopped={self._format_age(self.stopped_signal_age)}s "
                f"terminated={self._format_age(self.terminated_signal_age)}s"
            )
        if self.phase == "complete":
            return (
                f"{self.operation} complete: result={self.stop_reason} "
                f"stopped={self.stopped_flag} terminated={self.terminated_flag}"
            )
        return f"{self.operation} {self.phase}"

    def _format_age(self, age: float | None) -> str:
        """Format age value for display."""
        if age is None:
            return "None"
        return f"{age:.3f}"

    def _format_thread(
        self,
        thread_id: int | None,
        thread_name: str | None,
    ) -> str:
        """Format thread info for display."""
        if thread_id is None:
            return "None"
        if thread_name:
            return f"{thread_id}({thread_name})"
        return str(thread_id)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for structured logging."""
        return {
            "operation": self.operation,
            "phase": self.phase,
            "stopped_flag": self.stopped_flag,
            "terminated_flag": self.terminated_flag,
            "stopped_signal_age": self.stopped_signal_age,
            "stopped_processed_age": self.stopped_processed_age,
            "terminated_signal_age": self.terminated_signal_age,
            "terminated_processed_age": self.terminated_processed_age,
            "last_message_age": self.last_message_age,
            "stop_reason": self.stop_reason,
            "thread_info": {
                "current": self._format_thread(
                    self.current_thread_id,
                    self.current_thread_name,
                ),
                "receiver": self._format_thread(
                    self.receiver_thread_id,
                    self.receiver_thread_name,
                ),
                "target": self.target_thread_id,
                "dap_current": self.current_dap_thread_id,
            },
            "timeout": self.timeout_value,
            "connection_diagnostics": self.connection_diagnostics,
        }


def _extract_step_parameters(
    operation_name: str,
    args: tuple,
    kwargs: dict,
) -> tuple[Any, bool]:
    """Extract thread_id and wait_for_stop from arguments.

    Parameters
    ----------
    operation_name : str
        Name of the operation
    args : tuple
        Positional arguments
    kwargs : dict
        Keyword arguments

    Returns
    -------
    tuple[Any, bool]
        (thread_id, wait_for_stop)
    """
    if operation_name == "continue":
        # continue_ has (request, wait_for_stop=False)
        request = args[0] if args else kwargs.get("request")
        wait_for_stop = kwargs.get("wait_for_stop", False) if len(args) < 2 else args[1]
        thread_id = (
            getattr(request.arguments, "threadId", None)
            if request and hasattr(request, "arguments")
            else None
        )
    else:
        # step_* have (thread_id=None, wait_for_stop=True, **kwargs)
        thread_id = args[0] if args else kwargs.get("thread_id")
        wait_for_stop = kwargs.get("wait_for_stop", True) if len(args) < 2 else args[1]
    return thread_id, wait_for_stop


def _capture_metrics(
    self: Any,
    operation_name: str,
    phase: str,
    thread_id: Any,
    timeout: Any = None,
) -> None:
    """Capture and log metrics for a phase.

    Parameters
    ----------
    self : Any
        Instance with session.dap and ctx
    operation_name : str
        Name of the operation
    phase : str
        Phase name (pre, clear, wait, result, timeout)
    thread_id : Any
        Thread ID
    timeout : Any, optional
        Timeout value for wait phase
    """
    try:
        if phase == "wait" and timeout is not None:
            metrics = StepMetrics.capture(
                self.session.dap,
                operation_name,
                phase,
                thread_id,
                timeout,
            )
        else:
            metrics = StepMetrics.capture(
                self.session.dap,
                operation_name,
                phase,
                thread_id,
            )
        self.ctx.debug(metrics.to_debug_string())
    except (AttributeError, KeyError, TypeError) as e:
        self.ctx.debug(f"{phase.capitalize()}-metrics error in {operation_name}: {e}")


def _handle_timeout_metrics(
    self: Any,
    operation_name: str,
    thread_id: Any,
) -> None:
    """Handle timeout metrics with diagnostics.

    Parameters
    ----------
    self : Any
        Instance with session.dap and ctx
    operation_name : str
        Name of the operation
    thread_id : Any
        Thread ID
    """
    try:
        metrics = StepMetrics.capture(
            self.session.dap,
            operation_name,
            "timeout",
            thread_id,
        )

        # Add connection diagnostics
        try:
            diags = self.session.dap.get_connection_status()
            metrics.connection_diagnostics = diags
        except Exception as e:
            msg = f"Failed to get connection diagnostics for {operation_name}: {e}"
            self.ctx.debug(msg)

        self.ctx.debug(metrics.to_debug_string())

        if metrics.connection_diagnostics:
            self.ctx.debug(
                f"{operation_name} connection state: "
                f"receiver={metrics.connection_diagnostics.get('receiver_running')} "  # noqa: E501
                f"pending={metrics.connection_diagnostics.get('pending_requests')} "  # noqa: E501
                f"in_flight={metrics.connection_diagnostics.get('request_in_flight')}",  # noqa: E501
            )
    except (AttributeError, KeyError, TypeError) as e:
        self.ctx.debug(f"Timeout-metrics error in {operation_name}: {e}")


def instrument_step(operation_name: str):
    """Instrument step operations with metrics.

    This decorator handles the instrumentation for step operations like
    continue, step_into, step_out, and step_over. It works with methods that
    have specific signatures.

    Parameters
    ----------
    operation_name : str
        Name of the operation (continue, step_into, step_out, step_over)

    Returns
    -------
    callable
        Decorated function with instrumentation
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            # Extract parameters
            thread_id, wait_for_stop = _extract_step_parameters(
                operation_name,
                args,
                kwargs,
            )

            # Skip instrumentation if debug not enabled
            if not self.ctx.is_debug_enabled():
                return func(self, *args, **kwargs)

            if not wait_for_stop:
                # Minimal instrumentation for non-blocking operations
                self.ctx.debug(
                    f"{operation_name}: non-blocking call (thread_id={thread_id})",
                )
                return func(self, *args, **kwargs)

            # Pre-operation metrics
            _capture_metrics(self, operation_name, "pre", thread_id)

            # Clear stopped event (but not for continue operations)
            if operation_name != "continue":
                try:
                    self.session.dap.clear_event(EventType.STOPPED.value)
                    _capture_metrics(self, operation_name, "clear", thread_id)
                except (AttributeError, KeyError, TypeError) as e:
                    self.ctx.debug(f"Clear-metrics error in {operation_name}: {e}")

            # Log wait phase
            timeout = getattr(self.session.dap, "DEFAULT_WAIT_TIMEOUT", None)
            _capture_metrics(self, operation_name, "wait", thread_id, timeout)

            # Execute operation
            try:
                result = func(self, *args, **kwargs)

                # Post-operation metrics
                _capture_metrics(self, operation_name, "result", thread_id)

                return result

            except TimeoutError:
                # Timeout metrics with diagnostics
                _handle_timeout_metrics(self, operation_name, thread_id)
                raise

        return wrapper

    return decorator


def instrument_wait(func: Callable) -> Callable:
    """Instrument wait_for_stopped_or_terminated operations.

    Parameters
    ----------
    func : callable
        The wait function to instrument

    Returns
    -------
    callable
        Decorated function with wait-specific instrumentation
    """

    @functools.wraps(func)
    def wrapper(self, timeout: float | None = None):
        # Skip instrumentation if debug not enabled
        if not self.ctx.is_debug_enabled():
            return func(self, timeout=timeout)

        # Capture initial state
        try:
            metrics = StepMetrics.capture(self, "wait", "start", timeout=timeout)
            self.ctx.debug(f"Waiting for stop/terminate: {metrics.to_debug_string()}")
        except (AttributeError, KeyError, TypeError) as e:
            self.ctx.debug(f"Wait start metrics error: {e}")

        # Execute wait
        start_time = time.time()
        result = func(self, timeout=timeout)
        elapsed = time.time() - start_time

        # Log result
        try:
            metrics = StepMetrics.capture(self, "wait", "complete")
            self.ctx.debug(
                f"Wait result={result} (elapsed={elapsed:.3f}s): "
                f"{metrics.to_debug_string()}",
            )

            if result == "timeout":
                # Add timeout diagnostics
                try:
                    diags = self.get_connection_status()
                    self.ctx.debug(
                        f"Wait timeout diagnostics: "
                        f"receiver={diags.get('receiver_running')} "
                        f"pending={diags.get('pending_requests')} "
                        f"in_flight={diags.get('request_in_flight')}",
                    )
                except Exception as e:
                    msg = f"Failed to get timeout diagnostics: {e}"
                    self.ctx.debug(msg)
        except (AttributeError, KeyError, TypeError) as e:
            self.ctx.debug(f"Wait result metrics error: {e}")

        return result

    return wrapper
