"""Error classes for aidb.

This module defines custom exceptions for the AI Debugger (aidb) system. The
exception hierarchy uses a hybrid approach:

1. Custom exceptions (inherit from AidbError) for:
   - Domain-specific debugging errors
   - Cross-cutting concerns across modules
   - API boundary errors exposed to users
   - Recovery scenarios with specific handling logic

2. Built-in Python exceptions for:
   - Standard programming errors (ValueError, TypeError)
   - Common failure modes (FileNotFoundError, PermissionError)
   - Well-understood semantics matching Python idioms

Exception Hierarchy::

    AidbError (base)
    +-- Configuration & Setup
    |   +-- ConfigurationError - Debug config issues
    |   +-- AdapterNotFoundError - Adapter binary not located
    |   +-- VSCodeVariableError - Unresolvable VS Code variables
    +-- Connection & Protocol
    |   +-- DebugConnectionError - Connection failures
    |   +-- DAPProtocolError - DAP protocol violations
    |   +-- DebugTimeoutError - Operation timeouts
    +-- Adapter & Capabilities
    |   +-- DebugAdapterError - Adapter operational errors
    |   +-- AdapterCapabilityNotSupportedError - Missing features
    |   +-- UnsupportedOperationError - Unsupported operations
    +-- Session Management
    |   +-- DebugSessionLostError - Lost session recovery
    +-- Resource Management
    |   +-- ResourceError (base)
    |   +-- ResourceExhaustedError - Resource pool exhausted
    +-- Batch Operations
    |   +-- BatchOperationError - Multiple errors aggregated
    +-- Compilation
        +-- CompilationError - Source compilation failed
"""

from typing import Any


class AidbError(Exception):
    """Base exception class for all aidb-related errors.

    This is the root of the aidb exception hierarchy. All custom exceptions in
    the aidb system should inherit from this class to allow for consistent error
    handling at API boundaries.

    Attributes
    ----------
    message : str
        Human-readable error message
    error_code : str
        Machine-readable error code (class name by default)
    details : Dict[str, Any]
        Additional error context and debugging information
    recoverable : bool
        Whether this error might be recoverable with retry
    summary : str | None
        Brief user-friendly summary for display purposes

    Usage:
        Use this directly only for generic aidb errors that don't fit into more
        specific categories. Prefer specific subclasses when available.
    """

    def __init__(
        self,
        message: str = "",
        details: dict[str, Any] | None = None,
        error_code: str | None = None,
        recoverable: bool = False,
        summary: str | None = None,
    ):
        """Initialize AIDB error with message and optional details.

        Parameters
        ----------
        message : str
            Error message
        details : dict, optional
            Additional error details
        error_code : str, optional
            Error code identifier
        recoverable : bool
            Whether error is recoverable
        summary : str, optional
            Brief user-friendly summary for display
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        self.recoverable = recoverable
        self.summary = summary if summary is not None else message


# ==============================
# Configuration & Setup Errors
# ==============================


class ConfigurationError(AidbError):
    """Raised when there's an issue with the debugging configuration.

    This error indicates problems with debug launch configurations, including
    missing required fields, invalid values, or incompatible settings for the
    target language/environment.

    Usage:
        Raise when validating launch configurations, parsing launch.json, or
        detecting configuration incompatibilities.

    Example
    -------
    >>> if 'program' not in config and 'request' == 'launch':
    ...     raise ConfigurationError(
    ...         "Launch configuration missing required 'program' field"
    ...     )
    """


class AdapterNotFoundError(AidbError):
    """Raised when a debug adapter cannot be located.

    This error indicates that a required debug adapter binary could not be found
    in any of the standard locations (environment variables, home directory, etc.).
    The error includes searched locations and installation instructions.

    Usage:
        Raise when adapter binary lookup fails after checking all locations.

    Example
    -------
    >>> raise AdapterNotFoundError(
    ...     "javascript",
    ...     ["~/.aidb/adapters/javascript", "$AIDB_JAVASCRIPT_PATH"],
    ...     "Download from: https://github.com/ai-debugger-inc/aidb/releases"
    ... )
    """

    def __init__(self, language: str, searched_locations: list[str], instructions: str):
        """Initialize with language, searched locations, and installation instructions.

        Parameters
        ----------
        language : str
            The language/adapter that couldn't be found
        searched_locations : list[str]
            List of locations that were searched
        instructions : str
            Installation instructions for the adapter
        """
        self.language = language
        self.searched_locations = searched_locations
        message = self._format_message(language, searched_locations, instructions)
        super().__init__(message, summary=f"{language.capitalize()} adapter not found")

    def _format_message(
        self,
        language: str,
        searched_locations: list[str],
        instructions: str,
    ) -> str:
        """Format the error message with clear instructions.

        Parameters
        ----------
        language : str
            The language/adapter that couldn't be found
        searched_locations : list[str]
            List of locations that were searched
        instructions : str
            Installation instructions for the adapter

        Returns
        -------
        str
            Formatted error message
        """
        lines = [
            f"\n{language.capitalize()} debug adapter not found!",
            "\nSearched locations:",
        ]
        for location in searched_locations:
            lines.append(f"  • {location}")
        lines.append(f"\n{instructions}")
        return "\n".join(lines)


class VSCodeVariableError(AidbError):
    """Raised when VS Code variables cannot be resolved outside VS Code.

    This error occurs when launch configurations contain VS Code runtime
    variables like ${selectedText}, etc. that require the VS Code
    editor context to resolve. The error message should guide users to either
    use specific values or run the debugger from within VS Code.

    Usage:
        Raise when encountering unresolvable VS Code variables in launch
        configurations when running outside of VS Code environment.

    Example
    -------
    >>> if "${file}" in launch_config.program:
    ...     raise VSCodeVariableError(
    ...         "Variable '${file}' requires VS Code runtime context. "
    ...         "Please provide a specific file path instead."
    ...     )
    """


# ==============================
# Connection & Protocol Errors
# ==============================


class DebugConnectionError(AidbError):
    """Raised when a connection to a debug adapter or target process fails.

    This error indicates failures in establishing or maintaining connections to
    debug adapters, target processes, or remote debugging sessions. Renamed from
    ConnectionError to avoid conflict with Python's built-in.

    Usage:
        Raise when socket connections fail, adapters don't respond, or
        communication is interrupted.

    Example
    -------
    >>> if not socket.connect(adapter_port, timeout=30):
    ...     raise DebugConnectionError(
    ...         f"Failed to connect to adapter on port {adapter_port}"
    ...     )
    """


class DAPProtocolError(AidbError):
    """Raised when a DAP protocol error occurs.

    This error indicates violations of the Debug Adapter Protocol specification,
    including malformed messages, invalid sequences, or protocol state
    violations.

    Usage:
        Raise when DAP message parsing fails, required fields are missing, or
        protocol sequences are violated.

    Example
    -------
    >>> if 'seq' not in message:
    ...     raise DAPProtocolError(
    ...         "DAP message missing required 'seq' field"
    ...     )
    """


class DebugTimeoutError(AidbError):
    """Raised when a debugging operation times out.

    This error indicates that a debugging operation exceeded its time limit,
    such as waiting for adapter responses, breakpoint hits, or target state
    changes. Renamed from TimeoutError to avoid conflict with Python's built-in.

    Usage:
        Raise when operations don't complete within expected timeframes,
        particularly for operations that wait for external events.

    Example
    -------
    >>> if not wait_for_stopped(timeout=30):
    ...     raise DebugTimeoutError(
    ...         "Timeout waiting for breakpoint hit after 30 seconds"
    ...     )
    """


# ==============================
# Adapter & Capabilities Errors
# ==============================


class DebugAdapterError(AidbError):
    """Raised when the debug adapter encounters an error during operation.

    This error indicates operational failures within the debug adapter itself,
    such as internal errors, resource exhaustion, or unexpected states.

    Usage:
        Raise when the adapter reports internal errors or enters an
        unrecoverable state during debugging operations.

    Example
    -------
    >>> if adapter_response.success is False:
    ...     raise DebugAdapterError(
    ...         f"Adapter error: {adapter_response.message}"
    ...     )
    """


class AdapterCapabilityNotSupportedError(AidbError):
    """Raised when the adapter lacks the capability to handle the request.

    This error indicates that a requested debugging operation is not supported
    by the current debug adapter. Different language adapters have varying
    capabilities based on their underlying debug protocols.

    Usage:
        Raise when checking adapter capabilities before attempting operations
        that may not be universally supported (e.g., memory inspection,
        disassembly, hot reload).

    Example
    -------
    >>> if not adapter.supports_hot_reload:
    ...     raise AdapterCapabilityNotSupportedError(
    ...         f"{adapter.language} adapter does not support hot reload"
    ...     )
    """


class UnsupportedOperationError(AidbError):
    """Exception raised when an operation is not supported by the debug adapter.

    This error is raised when attempting to use a feature that the current
    debug adapter doesn't support, as indicated by its capabilities.

    Example
    -------
    >>> if not session.supports_logpoints():
    ...     raise UnsupportedOperationError(
    ...         "LogPoints are not supported by this debug adapter"
    ...     )
    """


class DebugSessionLostError(AidbError):
    """Raised when a debug session is lost and cannot be recovered.

    This occurs when trying to execute session commands (continue, step,
    evaluate, etc.) after the connection to the debug adapter has been lost. The
    session must be restarted from the beginning.

    Usage:
        Raise when detecting that the debug session has terminated unexpectedly
        and recovery attempts have failed. This is a terminal error requiring a
        new session.

    Example
    -------
    >>> if adapter.terminated and not self.can_recover():
    ...     raise DebugSessionLostError(
    ...         "Debug session terminated unexpectedly - restart required"
    ...     )
    """


# ==============================
# Compilation Errors
# ==============================


class CompilationError(AidbError):
    """Raised when source compilation fails.

    Example
    -------
    >>> raise CompilationError(
    ...     "Java compilation failed",
    ...     details={
    ...         "file": "Test.java",
    ...         "compiler_output": stderr,
    ...         "command": "javac Test.java"
    ...     }
    ... )
    """


# ==============================
# Resource Management Errors
# ==============================


class ResourceError(AidbError):
    """Base class for resource management errors.

    Attributes
    ----------
    resource_type : str
        Type of resource (port, process, session, etc.)
    resource_id : Any
        Identifier for the specific resource
    """

    def __init__(
        self,
        message: str,
        resource_type: str | None = None,
        resource_id: Any | None = None,
        **kwargs,
    ):
        """Initialize resource busy error.

        Parameters
        ----------
        message : str
            Error message
        resource_type : str, optional
            Type of busy resource
        resource_id : Any, optional
            Resource identifier
        **kwargs
            Additional error parameters
        """
        super().__init__(message, **kwargs)
        self.resource_type = resource_type
        self.resource_id = resource_id
        if resource_type:
            self.details["resource_type"] = resource_type
        if resource_id is not None:
            self.details["resource_id"] = resource_id


class ResourceExhaustedError(ResourceError):
    """Raised when a resource pool is exhausted.

    Example
    -------
    >>> raise ResourceExhaustedError(
    ...     "No available ports in range",
    ...     resource_type="port",
    ...     details={"attempted_ranges": [(5000, 5100), (9000, 9100)]}
    ... )
    """


# ==============================
# Batch Operation Errors
# ==============================


class BatchOperationError(AidbError):
    """Error that aggregates multiple errors from batch operations.

    Attributes
    ----------
    errors : List[Exception]
        Individual errors that occurred
    succeeded : List[Any]
        Items that succeeded (for partial failures)
    failed : List[Any]
        Items that failed
    """

    def __init__(
        self,
        message: str,
        errors: list[Exception] | None = None,
        succeeded: list[Any] | None = None,
        failed: list[Any] | None = None,
        **kwargs,
    ):
        """Initialize batch operation error.

        Parameters
        ----------
        message : str
            Error message
        errors : list[Exception], optional
            Individual errors from batch
        succeeded : list[Any], optional
            Items that succeeded
        failed : list[Any], optional
            Items that failed
        **kwargs
            Additional error parameters
        """
        super().__init__(message, **kwargs)
        self.errors = errors or []
        self.succeeded = succeeded or []
        self.failed = failed or []
        self.details.update(
            {
                "total_errors": len(self.errors),
                "succeeded_count": len(self.succeeded),
                "failed_count": len(self.failed),
            },
        )
        if self.errors:
            self.details["error_types"] = list(
                set(type(e).__name__ for e in self.errors),
            )

    def add_error(self, error: Exception, item: Any | None = None) -> None:
        """Add an error to the batch.

        Parameters
        ----------
        error : Exception
            The error that occurred
        item : Any, optional
            The item that caused the error
        """
        self.errors.append(error)
        if item is not None:
            self.failed.append(item)
        self.details["total_errors"] = len(self.errors)
        self.details["failed_count"] = len(self.failed)

    def has_errors(self) -> bool:
        """Check if any errors occurred."""
        return len(self.errors) > 0

    def get_error_summary(self) -> str:
        """Get a summary of all errors."""
        if not self.errors:
            return "No errors"

        error_counts: dict[str, int] = {}
        for error in self.errors:
            error_type = type(error).__name__
            error_counts[error_type] = error_counts.get(error_type, 0) + 1

        summary_parts = [
            f"{count} {error_type}" for error_type, count in error_counts.items()
        ]
        return f"Errors: {', '.join(summary_parts)}"
