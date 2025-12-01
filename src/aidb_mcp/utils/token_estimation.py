"""Token estimation utilities for performance monitoring.

Provides functions to estimate token consumption from response data. Supports both
tiktoken (accurate) and simple (chars/4) estimation methods.
"""

from __future__ import annotations

import json
from typing import Any

import tiktoken

from aidb_logging import get_mcp_logger as get_logger
from aidb_mcp.core.performance_types import TokenEstimationMethod

__all__ = [
    "estimate_tokens",
    "get_response_stats",
    "analyze_response_field_sizes",
    "get_top_context_consumers",
    "estimate_json_tokens",
    "truncate_to_token_limit",
]

logger = get_logger(__name__)


def _get_config():
    """Lazy config access to avoid circular imports.

    Returns
    -------
    PerformanceConfig
        Performance configuration
    """
    from aidb_mcp.core.config import get_config

    return get_config().performance


def estimate_tokens(
    text: str | None,
    method: TokenEstimationMethod | str | None = None,
) -> int | None:
    """Estimate token count for text.

    Parameters
    ----------
    text : str | None
        Text to estimate tokens for
    method : TokenEstimationMethod | str | None
        Estimation method to use, defaults to config

    Returns
    -------
    int | None
        Estimated token count, None if text is None or method is DISABLED
    """
    if text is None:
        return None

    # Resolve method from config if not provided
    if method is None:
        cfg = _get_config()
        method_str = cfg.token_estimation_method
    elif isinstance(method, TokenEstimationMethod):
        method_str = method.value
    else:
        method_str = method

    # Handle disabled
    if method_str == TokenEstimationMethod.DISABLED.value:
        return None

    # Use tiktoken for accurate estimation
    if method_str == TokenEstimationMethod.TIKTOKEN.value:
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))

    # Simple estimation: ~4 chars per token
    return len(text) // 4


def get_response_stats(response: dict[str, Any]) -> dict[str, int | None]:
    """Calculate comprehensive statistics for a response.

    Parameters
    ----------
    response : dict[str, Any]
        Response dictionary to analyze

    Returns
    -------
    dict[str, int | None]
        Statistics including:
        - response_chars: Character count
        - response_tokens: Estimated token count
        - response_size_bytes: Size in bytes
    """
    # Serialize to JSON to get what the agent actually sees
    json_str = json.dumps(response, separators=(",", ":"))

    return {
        "response_chars": len(json_str),
        "response_tokens": estimate_tokens(json_str),
        "response_size_bytes": len(json_str.encode("utf-8")),
    }


def analyze_response_field_sizes(response: dict[str, Any]) -> dict[str, dict[str, int]]:
    """Analyze token consumption by response field.

    Parameters
    ----------
    response : dict[str, Any]
        Response dictionary to analyze

    Returns
    -------
    dict[str, dict[str, int]]
        Field breakdown with chars, tokens, bytes for each field
    """
    breakdown = {}

    for key, value in response.items():
        if value is None:
            continue

        # Serialize field value
        field_json = json.dumps(value, separators=(",", ":"))

        breakdown[key] = {
            "chars": len(field_json),
            "tokens": estimate_tokens(field_json) or 0,
            "bytes": len(field_json.encode("utf-8")),
        }

    return breakdown


def get_top_context_consumers(
    responses: list[dict[str, Any]],
    top_n: int = 10,
) -> list[dict[str, Any]]:
    """Identify the largest responses by token count.

    Parameters
    ----------
    responses : list[dict[str, Any]]
        List of response dictionaries to analyze
    top_n : int, optional
        Number of top consumers to return, by default 10

    Returns
    -------
    list[dict[str, Any]]
        Top N responses sorted by token count, each with:
        - response: Original response dict
        - stats: Response statistics
        - field_breakdown: Field-level analysis
    """
    analyzed = []

    for response in responses:
        stats = get_response_stats(response)
        field_breakdown = analyze_response_field_sizes(response)

        analyzed.append(
            {
                "response": response,
                "stats": stats,
                "field_breakdown": field_breakdown,
            },
        )

    # Sort by token count (descending)
    analyzed.sort(key=lambda x: x["stats"]["response_tokens"] or 0, reverse=True)

    return analyzed[:top_n]


def estimate_json_tokens(data: Any) -> int | None:
    """Estimate tokens for any JSON-serializable data.

    Parameters
    ----------
    data : Any
        Data to estimate tokens for

    Returns
    -------
    int | None
        Estimated token count
    """
    try:
        json_str = json.dumps(data, separators=(",", ":"))
        return estimate_tokens(json_str)
    except Exception as e:
        logger.debug("Failed to estimate tokens for data: %s", e)
        return None


def truncate_to_token_limit(
    data: Any,
    max_tokens: int,
    method: TokenEstimationMethod | str | None = None,
) -> tuple[Any, bool]:
    """Truncate data to fit within token limit.

    Parameters
    ----------
    data : Any
        Data to truncate (string, dict, list, etc.)
    max_tokens : int
        Maximum tokens allowed
    method : TokenEstimationMethod | str | None
        Estimation method to use, defaults to config

    Returns
    -------
    tuple[Any, bool]
        (truncated_data, was_truncated)

    Notes
    -----
    This is a simple implementation. More sophisticated versions could:
    - Intelligently truncate lists/dicts
    - Preserve important fields
    - Add truncation indicators
    """
    if isinstance(data, str):
        current_tokens = estimate_tokens(data, method=method)
        if current_tokens is None or current_tokens <= max_tokens:
            return data, False

        # Estimate character budget (tokens * 4 for simple method)
        char_budget = max_tokens * 4
        truncated = data[:char_budget] + "..."
        return truncated, True

    if isinstance(data, (list, dict)):
        # Convert to JSON string for estimation
        json_str = json.dumps(data, separators=(",", ":"))
        current_tokens = estimate_tokens(json_str, method=method)

        if current_tokens is None or current_tokens <= max_tokens:
            return data, False

        # For collections, truncation is more complex
        # Return as-is for now, mark as truncated
        # Full implementation would intelligently reduce collection size
        return data, True

    # For other types, convert to string
    str_data = str(data)
    return truncate_to_token_limit(str_data, max_tokens, method)
