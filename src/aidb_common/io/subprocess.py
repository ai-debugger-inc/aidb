"""Subprocess utility functions for AIDB."""

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aidb.interfaces.context import IContext


# Error message indicators for event loop mismatch detection
_EVENT_LOOP_ERROR_INDICATORS = (
    "attached to a different loop",
    "event loop is closed",
    "no running event loop",
)


def is_event_loop_error(error: Exception) -> bool:
    """Check if an exception is due to event loop mismatch or closure.

    These errors occur during pytest-xdist parallel test execution when async
    operations created on one worker's event loop are cleaned up on another.

    Parameters
    ----------
    error : Exception
        The exception to check

    Returns
    -------
    bool
        True if this is an event loop mismatch/closure error
    """
    error_msg = str(error).lower()
    return any(indicator in error_msg for indicator in _EVENT_LOOP_ERROR_INDICATORS)


async def close_subprocess_transports(
    process: asyncio.subprocess.Process | None,
    ctx: "IContext | None" = None,
    context_name: str = "Process",
) -> None:
    """Close all subprocess transports to prevent ResourceWarnings.

    When asyncio subprocesses terminate, their stdin/stdout/stderr transports
    remain in the event loop and must be explicitly closed to avoid
    ResourceWarnings on event loop closure.

    This function closes all three streams (stdin, stdout, stderr) in parallel
    for faster cleanup, typically reducing overhead from ~75ms to ~25ms.

    Parameters
    ----------
    process : asyncio.subprocess.Process | None
        The subprocess whose transports should be closed. If None, no-op.
    ctx : IContext, optional
        Context for logging. If None, no logging is performed.
    context_name : str
        Human-readable name for logging (e.g., "LSP client", "Adapter")

    Notes
    -----
    - This should be called after process.wait() or process.terminate()
    - Safe to call multiple times (checks is_closing())
    - Suppresses all exceptions during cleanup
    - Closes streams in parallel for performance

    Examples
    --------
    >>> proc = await asyncio.create_subprocess_exec("python", ...)
    >>> proc.terminate()
    >>> await proc.wait()
    >>> await close_subprocess_transports(proc, ctx, "Python adapter")
    """
    if not process:
        return

    async def close_stream(stream_name: str, stream) -> None:
        """Close a single stream transport."""
        if (
            stream
            and hasattr(stream, "is_closing")
            and hasattr(stream, "close")
            and hasattr(stream, "wait_closed")
            and not stream.is_closing()
        ):
            try:
                stream.close()
                await stream.wait_closed()
                if ctx:
                    ctx.debug(f"{context_name} {stream_name} transport closed")
            except Exception as e:
                if ctx:
                    ctx.debug(f"Error closing {stream_name} transport: {e}")

    # Close all streams in parallel for faster cleanup
    await asyncio.gather(
        close_stream("stdin", process.stdin),
        close_stream("stdout", process.stdout),
        close_stream("stderr", process.stderr),
        return_exceptions=True,
    )
