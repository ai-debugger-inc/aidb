"""Variable and expression inspection for debugging."""

from __future__ import annotations

from typing import Any

from aidb_common.config.runtime import ConfigManager
from aidb_logging import get_mcp_logger as get_logger

from ...core import InspectTarget
from ...core.performance import timed
from ...core.response_limiter import ResponseLimiter
from ...core.serialization import to_jsonable

logger = get_logger(__name__)


def _format_variables_compact(
    variables: list[dict[str, Any]],
) -> dict[str, Any] | list[dict[str, Any]]:
    """Format variables in compact mode for agent consumption.

    Transforms list of DAP Variable dicts into a compact name->value mapping.
    In verbose mode, returns original list unchanged.

    Parameters
    ----------
    variables : list[dict[str, Any]]
        List of DAP Variable dicts with name, value, type, variablesReference, etc.

    Returns
    -------
    dict[str, Any] | list[dict[str, Any]]
        In compact mode: {"varName": {"v": "value", "t": "type", "varRef": N}, ...}
        In verbose mode: original list unchanged
    """
    if ConfigManager().is_mcp_verbose():
        return variables

    result = {}
    for var in variables:
        name = var.get("name", "unknown")
        compact_var: dict[str, Any] = {
            "v": var.get("value", ""),
            "t": var.get("type", ""),
        }
        # Include varRef only when > 0 (has children for drill-down)
        var_ref = var.get("variablesReference", 0)
        if var_ref:
            compact_var["varRef"] = var_ref
        result[name] = compact_var

    return result


@timed
async def inspect_locals(api) -> Any:
    """Inspect local variables."""
    logger.debug(
        "Inspecting local variables",
        extra={"target": InspectTarget.LOCALS.name},
    )
    try:
        result = await api.introspection.locals()
        variables_data = result.variables if hasattr(result, "variables") else result

        if hasattr(variables_data, "__len__"):
            var_count = len(variables_data) if variables_data else 0
            logger.info(
                "Retrieved %d local variables",
                var_count,
                extra={"variable_count": var_count, "target": "locals"},
            )
        else:
            logger.debug("Local variables result: %s", type(variables_data).__name__)

        jsonable_vars = to_jsonable(variables_data)

        if isinstance(jsonable_vars, list):
            limited_vars, was_truncated = ResponseLimiter.limit_variables(jsonable_vars)

            if was_truncated:
                logger.info(
                    "Truncated variables from %d to %d",
                    len(jsonable_vars),
                    len(limited_vars),
                    extra={
                        "total_variables": len(jsonable_vars),
                        "showing_variables": len(limited_vars),
                    },
                )
                return {
                    "variables": _format_variables_compact(limited_vars),
                    "truncated": True,
                    "total_variables": len(jsonable_vars),
                    "showing_variables": len(limited_vars),
                }

            return _format_variables_compact(limited_vars)

        return jsonable_vars
    except Exception as e:
        logger.warning(
            "Failed to inspect local variables: %s",
            e,
            extra={"error": str(e), "target": "locals"},
        )
        raise


@timed
async def inspect_globals(api) -> Any:
    """Inspect global variables."""
    logger.debug(
        "Inspecting global variables",
        extra={"target": InspectTarget.GLOBALS.name},
    )
    try:
        result = await api.introspection.globals()
        variables_data = result.variables if hasattr(result, "variables") else result

        if hasattr(variables_data, "__len__"):
            var_count = len(variables_data) if variables_data else 0
            logger.info(
                "Retrieved %d global variables",
                var_count,
                extra={"variable_count": var_count, "target": "globals"},
            )
        else:
            logger.debug("Global variables result: %s", type(variables_data).__name__)

        jsonable_vars = to_jsonable(variables_data)

        if isinstance(jsonable_vars, list):
            limited_vars, was_truncated = ResponseLimiter.limit_variables(jsonable_vars)

            if was_truncated:
                logger.info(
                    "Truncated global variables from %d to %d",
                    len(jsonable_vars),
                    len(limited_vars),
                    extra={
                        "total_variables": len(jsonable_vars),
                        "showing_variables": len(limited_vars),
                    },
                )
                return {
                    "variables": _format_variables_compact(limited_vars),
                    "truncated": True,
                    "total_variables": len(jsonable_vars),
                    "showing_variables": len(limited_vars),
                }

            return _format_variables_compact(limited_vars)

        return jsonable_vars
    except Exception as e:
        logger.warning(
            "Failed to inspect global variables: %s",
            e,
            extra={"error": str(e), "target": "globals"},
        )
        raise


@timed
async def inspect_expression(api, expression: str, frame_id: int | None) -> Any:
    """Evaluate a custom expression."""
    truncated_expr = expression[:100] if len(expression) > 100 else expression
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
        result = await api.introspection.evaluate(expression, frame_id=frame_id)

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
