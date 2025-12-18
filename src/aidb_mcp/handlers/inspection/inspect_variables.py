"""Variable and expression inspection for debugging."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aidb.common.constants import LOG_EXPRESSION_PREVIEW_LENGTH
from aidb_common.config.runtime import ConfigManager
from aidb_logging import get_mcp_logger as get_logger

from ...core import InspectTarget
from ...core.performance import timed
from ...core.serialization import to_jsonable

if TYPE_CHECKING:
    from aidb.models import AidbVariablesResponse

logger = get_logger(__name__)


def _format_variables_response(
    result: AidbVariablesResponse,
) -> dict[str, Any]:
    """Format variables response based on verbosity mode.

    Parameters
    ----------
    result : AidbVariablesResponse
        The variables response from the API

    Returns
    -------
    dict[str, Any]
        In compact mode: {"varName": {"v": "value", "t": "type", "varRef": N}, ...}
        In verbose mode: full serialized AidbVariablesResponse
    """
    if ConfigManager().is_mcp_verbose():
        return to_jsonable(result.variables)

    return result.to_compact()


@timed
async def inspect_locals(service) -> Any:
    """Inspect local variables."""
    logger.debug(
        "Inspecting local variables",
        extra={"target": InspectTarget.LOCALS.name},
    )
    try:
        # Phase 2: use service.variables.locals()
        result = await service.variables.locals()

        var_count = len(result.variables) if result.variables else 0
        logger.info(
            "Retrieved %d local variables",
            var_count,
            extra={"variable_count": var_count, "target": "locals"},
        )

        # Use model's to_compact() for clean formatting
        return _format_variables_response(result)
    except Exception as e:
        logger.warning(
            "Failed to inspect local variables: %s",
            e,
            extra={"error": str(e), "target": "locals"},
        )
        raise


@timed
async def inspect_globals(service) -> Any:
    """Inspect global variables."""
    logger.debug(
        "Inspecting global variables",
        extra={"target": InspectTarget.GLOBALS.name},
    )
    try:
        # Phase 2: use service.variables.globals()
        result = await service.variables.globals()

        var_count = len(result.variables) if result.variables else 0
        logger.info(
            "Retrieved %d global variables",
            var_count,
            extra={"variable_count": var_count, "target": "globals"},
        )

        # Use model's to_compact() for clean formatting
        return _format_variables_response(result)
    except Exception as e:
        logger.warning(
            "Failed to inspect global variables: %s",
            e,
            extra={"error": str(e), "target": "globals"},
        )
        raise


@timed
async def inspect_expression(service, expression: str, frame_id: int | None) -> Any:
    """Evaluate a custom expression."""
    truncated_expr = (
        expression[:LOG_EXPRESSION_PREVIEW_LENGTH]
        if len(expression) > LOG_EXPRESSION_PREVIEW_LENGTH
        else expression
    )
    logger.debug(
        "Evaluating custom expression",
        extra={
            "expression": truncated_expr,
            "expression_length": len(expression),
            "frame_id": frame_id,
            "target": InspectTarget.EXPRESSION.name,
        },
    )
    try:
        # Phase 2: use service.variables.evaluate()
        result = await service.variables.evaluate(expression, frame_id=frame_id)

        logger.info(
            "Expression evaluation completed",
            extra={
                "expression": truncated_expr,
                "frame_id": frame_id or 0,
                "result_type": type(result).__name__ if result is not None else "None",
                "has_result": result is not None,
            },
        )

        return to_jsonable(result)
    except Exception as e:
        logger.warning(
            "Expression evaluation failed: %s",
            e,
            extra={
                "expression": truncated_expr,
                "frame_id": frame_id,
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )
        raise
