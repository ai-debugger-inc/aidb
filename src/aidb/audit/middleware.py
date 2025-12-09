"""Audit middleware for automatic operation tracking."""

import contextvars
import functools
import inspect
import time
import traceback
from collections.abc import Callable
from typing import Any

from aidb.audit.events import AuditEvent, AuditLevel
from aidb.audit.logger import get_audit_logger
from aidb_logging import get_logger

logger = get_logger(__name__)


def audit_operation(
    component: str | None = None,
    operation: str | None = None,
    level: AuditLevel = AuditLevel.INFO,
    capture_params: bool = True,
    capture_result: bool = True,
    mask_sensitive: bool = True,
) -> Callable[..., Any]:
    """Audit method operations.

    Automatically captures operation context, parameters, results,
    and timing information for audit logging.

    Parameters
    ----------
    component : Optional[str]
        Component name (e.g., "api.operations"). If None, derived from class/module.
    operation : Optional[str]
        Operation name. If None, derived from method name.
    level : AuditLevel
        Default audit level for the operation
    capture_params : bool
        Whether to capture method parameters
    capture_result : bool
        Whether to capture method result
    mask_sensitive : bool
        Whether to mask sensitive data in parameters

    Returns
    -------
    Callable
        Decorated function with audit logging

    Examples
    --------
    >>> @audit_operation(component="api.operations")
    ... def continue_execution(self, thread_id: int):
    ...     # Implementation
    ...     pass
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        nonlocal component, operation

        if component is None:
            module = inspect.getmodule(func)
            component = module.__name__.replace("aidb.", "") if module else "unknown"

        if operation is None:
            operation = func.__name__

        is_async = inspect.iscoroutinefunction(func)

        if is_async:

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs) -> Any:
                audit_logger = get_audit_logger()
                if not audit_logger.is_enabled():
                    return await func(*args, **kwargs)

                return await _execute_with_audit(
                    func,
                    component,
                    operation,
                    level,
                    capture_params,
                    capture_result,
                    mask_sensitive,
                    *args,
                    **kwargs,
                )

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            audit_logger = get_audit_logger()
            if not audit_logger.is_enabled():
                return func(*args, **kwargs)

            return _execute_with_audit_sync(
                func,
                component,
                operation,
                level,
                capture_params,
                capture_result,
                mask_sensitive,
                *args,
                **kwargs,
            )

        return sync_wrapper

    return decorator


def _extract_session_metadata(event: AuditEvent, args: tuple[Any, ...]) -> None:
    """Extract session metadata from function arguments."""
    if args and hasattr(args[0], "session"):
        session = args[0].session
        if hasattr(session, "id"):
            event.session_id = session.id
        if hasattr(session, "language"):
            event.metadata["language"] = session.language
        if hasattr(session, "adapter_type"):
            event.metadata["adapter"] = session.adapter_type


def _capture_parameters(
    event: AuditEvent,
    func: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    mask_sensitive: bool = True,
) -> None:
    """Capture function parameters for audit logging."""
    try:
        sig = inspect.signature(func)
        bound_args = sig.bind(*args, **kwargs)
        bound_args.apply_defaults()

        params = {}
        for param_name, param_value in bound_args.arguments.items():
            if param_name != "self":
                if hasattr(param_value, "__dict__"):
                    params[param_name] = str(param_value)
                else:
                    params[param_name] = param_value

        event.parameters = params

        # Mask sensitive data if requested
        if mask_sensitive:
            event.mask_sensitive_data()

    except Exception as e:
        logger.debug("Failed to capture parameters for audit: %s", e)
        event.parameters = {"_capture_error": str(e)}


def _capture_result(event: AuditEvent, result: Any) -> None:
    """Capture function result for audit logging."""
    try:
        if hasattr(result, "to_dict"):
            event.result["value"] = result.to_dict()
        elif hasattr(result, "__dict__"):
            if hasattr(result, "success"):
                event.result["success"] = result.success
            if hasattr(result, "error"):
                event.result["error"] = result.error
            event.result["type"] = type(result).__name__
        else:
            event.result["value"] = result
    except Exception as e:
        logger.debug("Failed to capture result for audit: %s", e)
        event.result = {"_capture_error": str(e)}


def _handle_exception(event: AuditEvent, e: Exception) -> None:
    """Handle exception during audited function execution."""
    event.level = AuditLevel.ERROR
    event.error = str(e)
    event.result["success"] = False
    event.result["exception"] = type(e).__name__

    tb = traceback.format_exc()
    if len(tb) > 500:
        tb = tb[:500] + "... (truncated)"
    event.metadata["traceback"] = tb


def _execute_with_audit_common(
    func: Callable[..., Any],
    component: str,
    operation: str,
    level: AuditLevel,
    capture_params: bool,
    capture_result: bool,
    mask_sensitive: bool,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> tuple[AuditEvent, Callable[..., None]]:
    """Set up common audit logic and return teardown function."""
    audit_logger = get_audit_logger()
    start_time = time.perf_counter()

    event = AuditEvent(
        level=level,
        component=component,
        operation=operation,
    )

    _extract_session_metadata(event, args)

    if capture_params:
        _capture_parameters(event, func, args, kwargs, mask_sensitive)
        # Extract session_id from parameters if present
        if "session_id" in event.parameters and event.session_id is None:
            event.session_id = event.parameters["session_id"]

    def finalize_audit(
        result: Any = None,
        exception: Exception | None = None,
    ) -> None:
        if exception:
            _handle_exception(event, exception)
        elif capture_result and result is not None:
            _capture_result(event, result)

        if not exception:
            event.result["success"] = True

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        event.result["duration_ms"] = duration_ms

        try:
            audit_logger.log(event)
        except Exception as audit_error:
            logger.error("Failed to log audit event: %s", audit_error)

    return event, finalize_audit


def _execute_with_audit_sync(
    func: Callable[..., Any],
    component: str,
    operation: str,
    level: AuditLevel,
    capture_params: bool,
    capture_result: bool,
    mask_sensitive: bool,
    *args,
    **kwargs,
) -> Any:
    """Execute sync function with audit logging."""
    event, finalize_audit = _execute_with_audit_common(
        func,
        component,
        operation,
        level,
        capture_params,
        capture_result,
        mask_sensitive,
        args,
        kwargs,
    )

    try:
        result = func(*args, **kwargs)
        finalize_audit(result=result)
        return result
    except Exception as e:
        finalize_audit(exception=e)
        raise


async def _execute_with_audit(
    func: Callable[..., Any],
    component: str,
    operation: str,
    level: AuditLevel,
    capture_params: bool,
    capture_result: bool,
    mask_sensitive: bool,
    *args,
    **kwargs,
) -> Any:
    """Execute async function with audit logging."""
    event, finalize_audit = _execute_with_audit_common(
        func,
        component,
        operation,
        level,
        capture_params,
        capture_result,
        mask_sensitive,
        args,
        kwargs,
    )

    try:
        result = await func(*args, **kwargs)
        finalize_audit(result=result)
        return result
    except Exception as e:
        finalize_audit(exception=e)
        raise


_audit_context_metadata: contextvars.ContextVar[dict[str, Any] | None] = (
    contextvars.ContextVar("audit_context_metadata", default=None)
)


class AuditContext:
    """Context manager for audit operations with custom metadata.

    Allows adding temporary metadata to audit events within a context block.
    Uses contextvars for proper async/thread-local storage.

    Examples
    --------
    >>> with AuditContext(request_id="abc123", user="john.doe"):
    ...     # All audit events in this block will have the metadata
    ...     api.continue_execution(thread_id=1)

    >>> async with AuditContext(request_id="xyz789"):
    ...     await async_operation()
    """

    def __init__(
        self,
        component: str | None = None,
        operation: str | None = None,
        session_id: str | None = None,
        level: AuditLevel = AuditLevel.INFO,
        parameters: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize audit context.

        Parameters
        ----------
        component : Optional[str]
            Component name (e.g., "api.operations")
        operation : Optional[str]
            Operation name
        session_id : Optional[str]
            Session identifier
        level : AuditLevel
            Default audit level for the operation
        parameters : Optional[dict]
            Operation parameters
        metadata : Optional[dict]
            Additional metadata
        **kwargs
            Additional metadata to add to audit events within this context
        """
        self.component = component or "audit.context"
        self.operation = operation or "context_operation"
        self.session_id = session_id
        self.level = level
        self.parameters = parameters or {}
        self.metadata = metadata or {}
        self.metadata.update(kwargs)
        self.result: dict[str, Any] = {}
        self.error: str | None = None
        self.token: contextvars.Token[dict[str, Any] | None] | None = None
        self._start_time: float | None = None
        self._event: AuditEvent | None = None

    def __enter__(self) -> "AuditContext":
        """Enter context and set metadata."""
        current = (_audit_context_metadata.get() or {}).copy()
        current.update(self.metadata)
        self.token = _audit_context_metadata.set(current)

        # Start tracking the operation
        self._start_time = time.perf_counter()

        # Create the audit event
        self._event = AuditEvent(
            level=self.level,
            component=self.component,
            operation=self.operation,
            session_id=self.session_id,
            parameters=self.parameters.copy(),
            metadata=self.metadata.copy(),
        )

        return self

    async def __aenter__(self) -> "AuditContext":
        """Async enter context and set metadata."""
        return self.__enter__()

    def _handle_exception(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Handle exception information in the audit event.

        Parameters
        ----------
        exc_type : Any
            Exception type
        exc_val : Any
            Exception value
        exc_tb : Any
            Exception traceback
        """
        if not self._event:
            return

        self._event.level = AuditLevel.ERROR
        self._event.error = str(exc_val) if exc_val else f"{exc_type.__name__}"
        self._event.result["success"] = False

        if exc_tb:
            tb = traceback.format_tb(exc_tb)
            if tb:
                tb_str = "".join(tb)
                if len(tb_str) > 500:
                    tb_str = tb_str[:500] + "... (truncated)"
                self._event.metadata["traceback"] = tb_str

    def _handle_success(self) -> None:
        """Handle successful operation result."""
        if not self._event:
            return

        # Update with any results set during context
        self._event.result.update(self.result)
        if "success" not in self._event.result:
            self._event.result["success"] = True
        if self.error:
            self._event.error = self.error

    def _log_audit_event(self) -> None:
        """Log the audit event safely."""
        try:
            audit_logger = get_audit_logger()
            if audit_logger.is_enabled():
                audit_logger.log(self._event)
        except Exception as e:
            logger.error("Failed to log audit event: %s", e)

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context and restore previous metadata."""
        if self._event and self._start_time:
            # Calculate duration
            duration_ms = int((time.perf_counter() - self._start_time) * 1000)
            self._event.result["duration_ms"] = duration_ms

            # Handle exception or success
            if exc_type:
                self._handle_exception(exc_type, exc_val, exc_tb)
            else:
                self._handle_success()

            # Log the event
            self._log_audit_event()

        if self.token:
            _audit_context_metadata.reset(self.token)

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async exit context and restore previous metadata."""
        return self.__exit__(exc_type, exc_val, exc_tb)

    def set_result(self, result: dict[str, Any]) -> None:
        """Set the result of the operation.

        Parameters
        ----------
        result : dict
            Result data to record
        """
        self.result.update(result)

    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata to the context.

        Parameters
        ----------
        key : str
            Metadata key
        value : Any
            Metadata value
        """
        self.metadata[key] = value
        if self._event:
            self._event.metadata[key] = value

    @classmethod
    def get_metadata(cls) -> dict[str, Any]:
        """Get current context metadata.

        Returns
        -------
        dict
            Current metadata from all nested contexts
        """
        return (_audit_context_metadata.get() or {}).copy()
