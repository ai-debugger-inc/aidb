"""Shared DAP utilities for session operations and service components.

This module contains common DAP-related utilities that are shared between:
- BaseOperations (session ops layer) - uses caching wrapper
- BaseServiceComponent (service layer) - uses directly (stateless)
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Literal, cast

from aidb.common.constants import SHORT_SLEEP_S, STACK_TRACE_TIMEOUT_S
from aidb.common.errors import DebugTimeoutError
from aidb.dap.protocol.bodies import StackTraceArguments
from aidb.dap.protocol.requests import StackTraceRequest, ThreadsRequest

if TYPE_CHECKING:
    from aidb.dap.protocol.base import Response
    from aidb.dap.protocol.responses import StackTraceResponse, ThreadsResponse
    from aidb.interfaces import IContext
    from aidb.session import Session


def resolve_active_session(session: Session, ctx: IContext) -> Session:
    """Resolve the active session, handling child session routing.

    For languages with child sessions (e.g., JavaScript), the child session
    becomes the active session once it exists. All operations are routed to
    the child unconditionally.

    Parameters
    ----------
    session : Session
        The session to resolve
    ctx : IContext
        Application context for logging

    Returns
    -------
    Session
        The active session (child if exists, otherwise parent)
    """
    # If this is already a child, return as-is
    if session.is_child:
        return session

    # Check if adapter requires child session routing
    has_adapter = hasattr(session, "adapter") and session.adapter is not None
    requires_child = (
        has_adapter
        and hasattr(session.adapter, "requires_child_session_wait")
        and session.adapter.requires_child_session_wait
    )
    has_children = bool(session.child_session_ids)

    # For adapters requiring child sessions, always use child when it exists
    if has_adapter and requires_child and has_children:
        # Resolve to first child (JavaScript only has one)
        child_id = session.child_session_ids[0]
        child = session.registry.get_session(child_id)

        if child:
            ctx.debug(
                f"Resolved operation session {session.id} → child {child.id}",
            )
            return child

        # Child ID registered but session not found - shouldn't happen
        ctx.warning(
            f"Child session {child_id} registered but not found in registry",
        )

    return session


async def get_current_thread_id(session: Session, ctx: IContext) -> int:
    """Get the current active thread ID from DAP state or threads list.

    This is a stateless utility - it does not cache the result. Callers
    that need caching should implement it at their layer.

    Parameters
    ----------
    session : Session
        The session to query
    ctx : IContext
        Application context for logging

    Returns
    -------
    int
        The active thread ID

    Notes
    -----
    Resolution order:
    1. DAP client state (from stopped event)
    2. ThreadsRequest to get available threads
    3. Fallback to thread ID 1
    """
    # Check if the DAP client has a current thread ID from a stopped event
    if hasattr(session.dap, "_event_processor") and hasattr(
        session.dap._event_processor,
        "_state",
    ):
        dap_thread_id = session.dap._event_processor._state.current_thread_id
        if dap_thread_id is not None:
            ctx.debug(
                f"Using thread ID {dap_thread_id} from DAP client state",
            )
            return dap_thread_id

    # Try to get threads to find an active one
    try:
        ctx.debug("Attempting to get current threads...")
        request = ThreadsRequest(seq=0)
        response: Response = await session.dap.send_request(request)
        threads_response = cast("ThreadsResponse", response)
        threads_response.ensure_success()

        if threads_response.body and threads_response.body.threads:
            thread_count = len(threads_response.body.threads)
            ctx.debug(f"Found {thread_count} threads")
            first_thread = threads_response.body.threads[0]
            ctx.debug(
                f"Using thread ID {first_thread.id} (name: {first_thread.name})",
            )
            return first_thread.id
        ctx.warning("Threads response had no body or no threads")

    except Exception as e:
        ctx.warning(f"Failed to get threads: {type(e).__name__}: {e}")

    # Last resort: return 1 (common default for main thread)
    ctx.warning(
        "Using fallback thread ID 1 - thread tracking may be unreliable",
    )
    return 1


async def get_current_frame_id(
    session: Session,
    ctx: IContext,
    thread_id: int | None = None,
) -> int:
    """Get the current active frame ID for a thread.

    This is a stateless utility - it does not cache the result. Callers
    that need caching should implement it at their layer.

    Parameters
    ----------
    session : Session
        The session to query
    ctx : IContext
        Application context for logging
    thread_id : int, optional
        Thread ID to get frame for. If None, uses current thread.

    Returns
    -------
    int
        The active frame ID (top of stack)
    """
    if thread_id is None:
        thread_id = await get_current_thread_id(session, ctx)

    try:
        ctx.debug(f"Attempting to get stack trace for thread {thread_id}...")
        request = StackTraceRequest(
            seq=0,
            arguments=StackTraceArguments(threadId=thread_id),
        )

        response: Response = await session.dap.send_request(
            request,
            timeout=STACK_TRACE_TIMEOUT_S,
        )
        stack_response = cast("StackTraceResponse", response)
        stack_response.ensure_success()

        if stack_response.body and stack_response.body.stackFrames:
            frame_count = len(stack_response.body.stackFrames)
            ctx.debug(
                f"Found {frame_count} stack frames for thread {thread_id}",
            )
            top_frame = stack_response.body.stackFrames[0]
            ctx.debug(
                f"Using frame ID {top_frame.id} "
                f"(name: {top_frame.name}, line: {top_frame.line})",
            )
            return top_frame.id
        ctx.warning(
            f"Stack trace response for thread {thread_id} had no body or no frames",
        )

    except Exception as e:
        ctx.warning(
            f"Failed to get stack trace for thread "
            f"{thread_id}: {type(e).__name__}: {e}",
        )

    # Last resort: return 0 (common default for top frame)
    ctx.warning("Using fallback frame ID 0 - frame tracking may be unreliable")
    return 0


async def wait_for_stop_or_terminate(
    session: Session,
    _ctx: IContext,
    operation_name: str,
) -> Literal["stopped", "terminated", "timeout"]:
    """Wait for stopped or terminated using event subscription.

    Parameters
    ----------
    session : Session
        The session to wait on
    _ctx : IContext
        Application context (unused, kept for API consistency)
    operation_name : str
        Name of the operation for error messages

    Returns
    -------
    Literal["stopped", "terminated", "timeout"]
        The result of waiting

    Raises
    ------
    DebugTimeoutError
        If timeout occurs
    """
    if not hasattr(session.events, "wait_for_stopped_or_terminated_async"):
        await asyncio.sleep(SHORT_SLEEP_S)
        return "stopped"

    result = await session.events.wait_for_stopped_or_terminated_async(
        timeout=session.dap.DEFAULT_WAIT_TIMEOUT,
    )

    if result == "timeout":
        msg = f"Timeout waiting for stop after {operation_name}"
        raise DebugTimeoutError(msg)

    return cast("Literal['stopped', 'terminated', 'timeout']", result)
