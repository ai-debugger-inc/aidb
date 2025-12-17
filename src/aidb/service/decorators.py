"""Decorators for service layer operations."""

from __future__ import annotations

import functools
import re
from typing import TYPE_CHECKING, Any, TypeVar

from aidb.common.errors import AdapterCapabilityNotSupportedError

if TYPE_CHECKING:
    from collections.abc import Callable

T = TypeVar("T")


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
