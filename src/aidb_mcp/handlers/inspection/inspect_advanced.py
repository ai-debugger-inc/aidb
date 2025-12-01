"""Advanced inspection modes (all)."""

from __future__ import annotations

from typing import Any

from aidb_logging import get_mcp_logger as get_logger

from ...core import InspectTarget
from ...core.performance import timed
from ...core.serialization import to_jsonable

logger = get_logger(__name__)


@timed
async def inspect_all(api) -> dict[str, Any]:
    """Inspect all available information."""
    logger.debug(
        "Inspecting all available information",
        extra={"target": InspectTarget.ALL.name},
    )

    async def safe_gather(
        name: str,
        fetch_func,
        extract_attr: str | None = None,
    ):
        """Safely gather inspection data, returning None on failure."""
        try:
            logger.debug(
                "Gathering %s data",
                name,
                extra={"data_type": name, "extract_attr": extract_attr},
            )
            result = await fetch_func()
            if extract_attr and hasattr(result, extract_attr):
                extracted = getattr(result, extract_attr)
                logger.debug(
                    "Extracted %s from %s result",
                    extract_attr,
                    name,
                    extra={"data_type": name, "extracted_attr": extract_attr},
                )
                return to_jsonable(extracted)
            return to_jsonable(result)
        except Exception as e:
            logger.debug(
                "Failed to gather %s data: %s",
                name,
                e,
                extra={"data_type": name, "error": str(e)},
            )
            return None

    all_data = {}
    gathered_count = 0
    failed_count = 0

    locals_data = await safe_gather(
        "locals",
        api.introspection.locals,
        "variables",
    )
    if locals_data is not None:
        all_data["locals"] = locals_data
        gathered_count += 1
    else:
        failed_count += 1

    globals_data = await safe_gather(
        "globals",
        api.introspection.globals,
        "variables",
    )
    if globals_data is not None:
        all_data["globals"] = globals_data
        gathered_count += 1
    else:
        failed_count += 1

    stack_data = await safe_gather(
        "stack",
        api.introspection.callstack,
        "frames",
    )
    if stack_data is not None:
        all_data["stack"] = stack_data
        gathered_count += 1
    else:
        failed_count += 1

    threads_data = await safe_gather("threads", api.introspection.threads)
    if threads_data is not None:
        all_data["threads"] = threads_data
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
