"""Pattern analysis and debugging insights for context handler.

This module analyzes execution history to identify patterns and generate insights.
"""

from __future__ import annotations

from typing import Any

from aidb_logging import get_mcp_logger as get_logger

from ...core import ToolName

logger = get_logger(__name__)


def _calculate_success_rate(history: list) -> float:
    """Calculate success rate from execution history.

    Parameters
    ----------
    history : list
        List of execution history entries

    Returns
    -------
    float
        Success rate as percentage
    """
    if not history:
        return 100.0

    successful = sum(1 for entry in history if entry.get("result") == "success")
    return round((successful / len(history)) * 100, 1)


def _count_operations(history: list) -> dict[str, int]:
    """Count operations in recent history.

    Parameters
    ----------
    history : list
        List of execution history entries

    Returns
    -------
    Dict[str, int]
        Operation counts
    """
    operations = [entry.get("operation", "unknown") for entry in history[-10:]]
    operation_counts: dict[str, int] = {}
    for op in operations:
        operation_counts[op] = operation_counts.get(op, 0) + 1
    return operation_counts


def _identify_patterns(
    operation_counts: dict[str, int],
    history_length: int,
) -> list[str]:
    """Identify debugging patterns from operation counts.

    Parameters
    ----------
    operation_counts : Dict[str, int]
        Count of each operation type
    history_length : int
        Total history length

    Returns
    -------
    List[str]
        Identified patterns
    """
    patterns: list[str] = []

    if operation_counts.get(ToolName.STEP, 0) > 3:
        patterns.append("Heavy stepping detected - consider using breakpoints")

    inspect_count = operation_counts.get(ToolName.INSPECT, 0)
    step_count = operation_counts.get(ToolName.STEP, 0)
    if inspect_count > step_count:
        patterns.append("More inspection than stepping - good debugging practice")

    if operation_counts.get(ToolName.BREAKPOINT, 0) == 0 and history_length > 5:
        patterns.append("No breakpoints used - consider setting strategic breakpoints")

    return patterns


def _check_recent_errors(history: list) -> dict[str, Any]:
    """Check for recent errors in history.

    Parameters
    ----------
    history : list
        List of execution history entries

    Returns
    -------
    Dict[str, Any]
        Error analysis
    """
    recent_errors = [entry for entry in history[-5:] if entry.get("result") == "error"]
    if recent_errors:
        return {
            "recent_errors": len(recent_errors),
            "error_recovery_tip": (
                "Multiple recent errors detected - check session state"
            ),
        }
    return {}


def _generate_optimization_suggestions(
    operation_counts: dict[str, int],
    history_length: int,
) -> list[str]:
    """Generate optimization suggestions based on patterns.

    Parameters
    ----------
    operation_counts : Dict[str, int]
        Count of each operation type
    history_length : int
        Total history length

    Returns
    -------
    List[str]
        Optimization suggestions
    """
    suggestions: list[str] = []

    if operation_counts.get(ToolName.STEP, 0) > 5:
        suggestions.append("Consider using 'run_until' for faster navigation")

    if operation_counts.get(ToolName.INSPECT, 0) < 2 and history_length > 3:
        suggestions.append("Try inspecting variables to understand program state")

    return suggestions


def _analyze_execution_patterns(history: list) -> dict[str, Any]:
    """Analyze execution history for debugging patterns and insights.

    Parameters
    ----------
    history : list
        List of execution history entries

    Returns
    -------
    Dict[str, Any]
        Debugging insights and patterns
    """
    if not history or len(history) < 3:
        return {}

    insights: dict[str, Any] = {}

    operation_counts = _count_operations(history)

    if operation_counts:
        most_frequent = max(operation_counts.items(), key=lambda x: x[1])
        insights["most_frequent_operation"] = {
            "operation": most_frequent[0],
            "count": most_frequent[1],
        }

    patterns = _identify_patterns(operation_counts, len(history))
    if patterns:
        insights["patterns"] = patterns

    error_info = _check_recent_errors(history)
    insights.update(error_info)

    suggestions = _generate_optimization_suggestions(operation_counts, len(history))
    if suggestions:
        insights["optimization_suggestions"] = suggestions

    return insights
