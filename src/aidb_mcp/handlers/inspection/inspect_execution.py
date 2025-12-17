"""Execution context inspection (stack frames, threads)."""

from __future__ import annotations

from typing import Any

from aidb_logging import get_mcp_logger as get_logger

from ...core import InspectTarget
from ...core.performance import timed
from ...core.response_limiter import ResponseLimiter
from ...core.serialization import to_jsonable

logger = get_logger(__name__)


def _remove_empty_locals(frames: Any) -> Any:
    """Remove empty locals field from stack frames.

    Parameters
    ----------
    frames : Any
        The frames data (list of dicts)

    Returns
    -------
    Any
        Frames with empty locals field removed
    """
    if isinstance(frames, list):
        for frame in frames:
            if isinstance(frame, dict) and "locals" in frame and not frame["locals"]:
                del frame["locals"]
    return frames


@timed
async def inspect_stack(service) -> Any:
    """Inspect call stack."""
    logger.debug(
        "Inspecting call stack",
        extra={"target": InspectTarget.STACK.name},
    )
    try:
        # Get current thread_id first, then call stack (Phase 2 service pattern)
        thread_id = await service.stack.get_current_thread_id()
        result = await service.stack.callstack(thread_id)
        frames_data = result.frames if hasattr(result, "frames") else result

        if hasattr(frames_data, "__len__"):
            frame_count = len(frames_data) if frames_data else 0
            logger.info(
                "Retrieved call stack with %d frames",
                frame_count,
                extra={"frame_count": frame_count, "target": "stack"},
            )
        else:
            logger.debug("Call stack result: %s", type(frames_data).__name__)

        jsonable_frames = to_jsonable(frames_data)
        jsonable_frames = _remove_empty_locals(jsonable_frames)

        if isinstance(jsonable_frames, list):
            limited_frames, was_truncated = ResponseLimiter.limit_stack_frames(
                jsonable_frames,
            )

            if was_truncated:
                logger.info(
                    "Truncated stack frames from %d to %d",
                    len(jsonable_frames),
                    len(limited_frames),
                    extra={
                        "total_frames": len(jsonable_frames),
                        "showing_frames": len(limited_frames),
                    },
                )
                return {
                    "frames": limited_frames,
                    "truncated": True,
                    "total_frames": len(jsonable_frames),
                    "showing_frames": len(limited_frames),
                }

            return limited_frames

        return jsonable_frames
    except Exception as e:
        logger.warning(
            "Failed to inspect call stack: %s",
            e,
            extra={"error": str(e), "target": "stack"},
        )
        raise


@timed
async def inspect_threads(service) -> Any:
    """Inspect threads."""
    logger.debug(
        "Inspecting threads",
        extra={"target": InspectTarget.THREADS.name},
    )
    try:
        # Phase 2: use service.stack.threads()
        result = await service.stack.threads()
        threads_data = result.threads if hasattr(result, "threads") else result
        current_thread = getattr(result, "current_thread_id", None)

        if hasattr(threads_data, "__len__"):
            thread_count = len(threads_data) if threads_data else 0
            logger.info(
                "Retrieved %d threads",
                thread_count,
                extra={"thread_count": thread_count, "target": "threads"},
            )
        else:
            logger.debug("Threads result: %s", type(threads_data).__name__)

        jsonable_threads = to_jsonable(threads_data)

        if isinstance(jsonable_threads, dict):
            limited_threads, was_truncated = ResponseLimiter.limit_threads(
                jsonable_threads,
                current_thread_id=current_thread,
            )

            if was_truncated:
                logger.info(
                    "Truncated threads from %d to %d",
                    len(jsonable_threads),
                    len(limited_threads),
                    extra={
                        "total_threads": len(jsonable_threads),
                        "showing_threads": len(limited_threads),
                    },
                )
                return {
                    "threads": limited_threads,
                    "truncated": True,
                    "total_threads": len(jsonable_threads),
                    "showing_threads": len(limited_threads),
                }

            return limited_threads

        return jsonable_threads
    except Exception as e:
        logger.warning(
            "Failed to inspect threads: %s",
            e,
            extra={"error": str(e), "target": "threads"},
        )
        raise
