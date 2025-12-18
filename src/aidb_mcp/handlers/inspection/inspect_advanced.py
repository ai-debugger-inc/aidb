"""Advanced inspection modes (all).

This module provides the 'all' inspection mode that gathers comprehensive debugging
information by reusing the individual inspection functions.
"""

from __future__ import annotations

from typing import Any

from aidb_logging import get_mcp_logger as get_logger

from ...core import InspectTarget
from ...core.performance import timed
from .inspect_execution import inspect_stack, inspect_threads
from .inspect_variables import inspect_globals, inspect_locals

logger = get_logger(__name__)


async def _safe_inspect(name: str, inspect_func, service) -> tuple[Any | None, bool]:
    """Safely call an inspection function, returning (result, success).

    Parameters
    ----------
    name : str
        Name of the inspection target for logging
    inspect_func : Callable
        The inspection function to call (e.g., inspect_locals)
    service
        The DebugService instance (Phase 2)

    Returns
    -------
    tuple[Any | None, bool]
        (result, success) where result is the inspection data or None on failure
    """
    try:
        result = await inspect_func(service)
        return result, True
    except Exception as e:
        logger.debug(
            "Failed to gather %s data: %s",
            name,
            e,
            extra={"data_type": name, "error": str(e)},
        )
        return None, False


@timed
async def inspect_all(service) -> dict[str, Any]:
    """Inspect all available information.

    Gathers comprehensive debugging information by calling the individual
    inspection functions. This reuses the existing helpers to avoid
    code duplication and ensure consistent formatting.

    Parameters
    ----------
    service
        The DebugService instance (Phase 2)

    Returns
    -------
    dict[str, Any]
        Dictionary with keys for each inspection category (locals, globals,
        stack, threads) containing the gathered data.
    """
    logger.debug(
        "Inspecting all available information",
        extra={"target": InspectTarget.ALL.name},
    )

    all_data: dict[str, Any] = {}
    gathered_count = 0
    failed_count = 0

    # Gather each category using the existing inspection functions
    # This reuses the specialized logic in each helper (e.g., frame limiting)
    inspection_targets = [
        ("locals", inspect_locals),
        ("globals", inspect_globals),
        ("stack", inspect_stack),
        ("threads", inspect_threads),
    ]

    for name, inspect_func in inspection_targets:
        data, success = await _safe_inspect(name, inspect_func, service)
        if success and data is not None:
            all_data[name] = data
            gathered_count += 1
        else:
            failed_count += 1

    logger.info(
        "Gathered all inspection data",
        extra={
            "target": "all",
            "gathered_count": gathered_count,
            "failed_count": failed_count,
            "total_categories": gathered_count + failed_count,
            "categories_available": list(all_data.keys()),
        },
    )

    return all_data
