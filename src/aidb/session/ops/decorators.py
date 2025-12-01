"""Decorators for session operations."""

import functools
import re
from collections.abc import Callable
from typing import Any, Protocol, TypeVar, cast

from aidb.common.errors import AdapterCapabilityNotSupportedError
from aidb.dap.client.retry import RetryConfig, RetryStrategy

T = TypeVar("T")


class RetryableFunction(Protocol):
    """Protocol for functions decorated with @retryable."""

    _retry_config: RetryConfig

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Call the decorated function."""
        msg = "Subclasses must implement this method"
        raise NotImplementedError(msg)


def retryable(
    max_attempts: int = 3,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL,
    initial_delay: float = 0.1,
    max_delay: float = 1.0,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Mark a session operation as retryable with specified configuration.

    This decorator indicates that an operation is idempotent and safe to retry
    on transient failures. The actual retry logic is implemented in the DAP
    client layer.

    Parameters
    ----------
    max_attempts : int
        Maximum number of attempts (including initial)
    strategy : RetryStrategy
        Retry strategy to use (exponential or linear backoff)
    initial_delay : float
        Initial delay between retries in seconds
    max_delay : float
        Maximum delay between retries in seconds

    Returns
    -------
    Callable
        Decorated function with retry metadata

    Examples
    --------
    >>> @retryable(max_attempts=5)
    ... def set_breakpoints(self, breakpoints):
    ...     # This operation is idempotent and safe to retry
    ...     return self.client.send_request(...)
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        # Store retry config as function attribute
        retryable_func = cast("RetryableFunction", func)
        retryable_func._retry_config = RetryConfig(
            max_attempts=max_attempts,
            strategy=strategy,
            initial_delay=initial_delay,
            max_delay=max_delay,
        )

        @functools.wraps(func)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> T:
            # The actual implementation just calls the original function
            # The retry logic is handled by checking for _retry_config
            # in the DAP client layer
            return func(self, *args, **kwargs)

        # Preserve the retry config on the wrapper
        retryable_wrapper = cast("RetryableFunction", wrapper)
        retryable_wrapper._retry_config = retryable_func._retry_config

        return cast("Callable[..., T]", wrapper)

    return decorator


def get_retry_config(func: Callable) -> RetryConfig | None:
    """Get retry configuration from a decorated function.

    Parameters
    ----------
    func : Callable
        Function to check for retry configuration

    Returns
    -------
    RetryConfig or None
        Retry configuration if function is decorated with @retryable
    """
    return getattr(func, "_retry_config", None)


def requires_capability(
    capability_attr: str,
    operation_name: str | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Ensure a debugging operation is only executed if the adapter supports it.

    This decorator checks if the debug adapter has a specific capability before
    allowing the operation to proceed. If the capability is not supported, it
    raises an AdapterCapabilityNotSupportedError error with a clear message.

    Parameters
    ----------
    capability_attr : str
        The capability attribute name from DAP Capabilities class
        (e.g., 'supportsSetVariable', 'supportsRestartRequest')
    operation_name : str, optional
        Human-readable name for the operation. If not provided, will be
        derived from the capability attribute name.

    Returns
    -------
    Callable
        Decorated function that checks capability before execution

    Raises
    ------
    AdapterCapabilityNotSupportedError
        If the adapter does not support the required capability

    Examples
    --------
    >>> @requires_capability('supportsSetVariable', 'variable modification')
    ... def set_variable(self, name, value, ref):
    ...     # Operation will only execute if adapter supports it
    ...     return self.client.send_request(...)

    >>> @requires_capability('supportsRestartRequest')
    ... def restart(self):
    ...     # Operation name will be derived as 'restart request'
    ...     return self.client.send_request(...)
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> T:
            # Check if the session has the required capability
            if not self.session.has_capability(capability_attr):
                # Derive operation name if not provided
                if operation_name:
                    op_name = operation_name
                else:
                    # Convert 'supportsSetVariable' -> 'set variable'
                    # Convert 'supportsRestartRequest' -> 'restart request'
                    op_name = (
                        capability_attr.replace("supports", "")
                        .replace("Request", " request")
                        .strip()
                    )
                    # Convert camelCase to spaces
                    op_name = re.sub(r"(?<!^)(?=[A-Z])", " ", op_name).lower()

                # Get the language from session for better error message
                language = getattr(self.session, "language", "current")

                msg = (
                    f"The {language} debug adapter does not support {op_name}. "
                    f"This is a limitation of the debug adapter, not the AI debugger."
                )
                raise AdapterCapabilityNotSupportedError(
                    msg,
                )

            # Execute the original function
            return func(self, *args, **kwargs)

        return wrapper

    return decorator
