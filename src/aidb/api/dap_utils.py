"""DAP protocol utilities for request creation."""

from aidb.dap.protocol.bodies import (
    ContinueArguments,
    GotoArguments,
    PauseArguments,
)
from aidb.dap.protocol.requests import ContinueRequest, GotoRequest, PauseRequest

from .base import ValidationMixin


def resolve_thread_id(thread_id: int | None) -> int:
    """Resolve thread ID with default fallback.

    Parameters
    ----------
    thread_id : int, optional
        AidbThread ID or None for default

    Returns
    -------
    int
        Resolved thread ID
    """
    return ValidationMixin.validate_thread_id(thread_id)


def resolve_frame_id(frame_id: int | None) -> int:
    """Resolve frame ID with default fallback.

    Parameters
    ----------
    frame_id : int, optional
        Frame ID or None for default (top frame)

    Returns
    -------
    int
        Resolved frame ID
    """
    return ValidationMixin.validate_frame_id(frame_id)


def create_continue_request(
    thread_id: int | None = None,
    single_thread: bool = False,
) -> ContinueRequest:
    """Create a DAP continue request with defaults.

    Parameters
    ----------
    thread_id : int, optional
        AidbThread to continue, by default None (all threads)
    single_thread : bool
        Continue only specified thread, by default False

    Returns
    -------
    ContinueRequest
        Configured DAP continue request
    """
    resolved_thread_id = resolve_thread_id(thread_id)
    return ContinueRequest(
        seq=0,  # Will be set by the client
        arguments=ContinueArguments(
            threadId=resolved_thread_id,
            singleThread=single_thread if single_thread else None,
        ),
    )


def create_pause_request(thread_id: int | None = None) -> PauseRequest:
    """Create a DAP pause request with defaults.

    Parameters
    ----------
    thread_id : int, optional
        AidbThread to pause, by default None (uses default thread)

    Returns
    -------
    PauseRequest
        Configured DAP pause request
    """
    resolved_thread_id = resolve_thread_id(thread_id)
    return PauseRequest(seq=0, arguments=PauseArguments(threadId=resolved_thread_id))


def create_goto_request(target_id: int, thread_id: int | None = None) -> GotoRequest:
    """Create a DAP goto request with defaults.

    Parameters
    ----------
    target_id : int
        Target location ID
    thread_id : int, optional
        AidbThread to perform goto on, by default None (uses default thread)

    Returns
    -------
    GotoRequest
        Configured DAP goto request
    """
    resolved_thread_id = resolve_thread_id(thread_id)
    return GotoRequest(
        seq=0,  # Will be set by the client
        arguments=GotoArguments(threadId=resolved_thread_id, targetId=target_id),
    )
