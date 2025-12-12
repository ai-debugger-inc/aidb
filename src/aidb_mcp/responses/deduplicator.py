"""Response deduplication for token efficiency.

This module provides systematic removal of duplicate fields from MCP responses. Instead
of modifying 30+ response types individually, we post-process responses to remove
redundant data while preserving semantic meaning.
"""

from __future__ import annotations

from typing import Any

from aidb_common.config.runtime import ConfigManager
from aidb_mcp.core.constants import MCPResponseField, ResponseFieldName

__all__ = ["ResponseDeduplicator"]


class ResponseDeduplicator:
    """Removes redundant fields from MCP responses systematically."""

    # Field mapping: canonical field → fields to remove
    CANONICAL_FIELDS = {
        # Execution state - multiple representations of pause/stop status
        "execution_state_status": {
            "canonical": (
                f"{ResponseFieldName.EXECUTION_STATE}.{ResponseFieldName.STATUS}"
            ),
            "remove": [
                ResponseFieldName.IS_PAUSED,
                ResponseFieldName.STATE,
                ResponseFieldName.DETAILED_STATUS,
            ],
            "notes": "execution_state.status is authoritative",
        },
        # Execution state - stop reason duplication
        "stop_reason": {
            "canonical": (
                f"{ResponseFieldName.EXECUTION_STATE}.{ResponseFieldName.STOP_REASON}"
            ),
            "remove": [ResponseFieldName.STOP_REASON],  # Top-level duplicate
            "notes": "Keep only nested version for consistency",
        },
        # Session state - initial state duplication
        "initial_state_execution": {
            "canonical": ResponseFieldName.EXECUTION_STATE,
            "remove": [
                f"{ResponseFieldName.INITIAL_STATE}.{ResponseFieldName.EXECUTION_PAUSED}",
            ],
            "notes": "execution_state already captures this",
        },
        # Location - multiple representations
        "location": {
            "canonical": ResponseFieldName.LOCATION,
            "remove": [
                f"{ResponseFieldName.INITIAL_STATE}.{ResponseFieldName.CURRENT_LOCATION}",
            ],
            "notes": "Top-level location is sufficient",
        },
        # Variable metadata - expression duplication
        "variable_expression": {
            "canonical": ResponseFieldName.EXPRESSION,
            "remove": [f"{ResponseFieldName.RESULT}.{ResponseFieldName.EXPRESSION}"],
            "notes": "Top-level expression is sufficient",
        },
        # Code context - lines array duplicates formatted string
        "code_context_lines": {
            "canonical": (
                f"{ResponseFieldName.CODE_CONTEXT}.{ResponseFieldName.FORMATTED}"
            ),
            "remove": [
                f"{ResponseFieldName.CODE_CONTEXT}.{ResponseFieldName.LINES}",
            ],
            "notes": (
                "Lines array duplicates formatted string; "
                "keep formatted for readability"
            ),
            "savings": "~40-50% per code_context (300-400 chars)",
        },
        # Metadata removal - timestamps not needed in responses
        "timestamp_metadata": {
            "canonical": None,
            "remove": [
                ResponseFieldName.TIMESTAMP,
                ResponseFieldName.CREATED_AT,
            ],
            "notes": "Timestamp not needed in AI debugging responses",
        },
        # Metadata removal - internal tracking IDs not needed
        "internal_ids": {
            "canonical": None,
            "remove": [
                ResponseFieldName.CORRELATION_ID,
                ResponseFieldName.OPERATION_ID,
            ],
            "notes": "Internal tracking IDs not needed in responses",
        },
        # Metadata removal - operation type implied by tool call
        "operation_metadata": {
            "canonical": None,
            "remove": [
                ResponseFieldName.OPERATION,
                ResponseFieldName.VERSION,
            ],
            "notes": "Operation type implied by MCP tool name",
        },
    }

    # Fields to omit when null or empty
    OMIT_WHEN_EMPTY = {
        ResponseFieldName.CHILDREN: lambda val: val == {} or val == [],
        ResponseFieldName.ERROR: lambda val: val is None,
        ResponseFieldName.LOCALS: lambda val: val == {} or val == [],
        ResponseFieldName.MODULE: lambda val: val is None or val == "",
        ResponseFieldName.HAS_CHILDREN: lambda val: val is False,  # Omit when False
        ResponseFieldName.ID: lambda val: val == 0
        or val is None,  # Omit when 0 (no children to fetch)
    }

    @classmethod
    def deduplicate(cls, response: dict[str, Any]) -> dict[str, Any]:
        """Remove duplicate and empty fields from response.

        Parameters
        ----------
        response : dict
            The response dictionary to deduplicate

        Returns
        -------
        dict
            Deduplicated response

        Notes
        -----
        This method:
        1. Removes fields identified as duplicates
        2. Removes fields that are null/empty when appropriate
        3. Preserves semantic meaning (keeps meaningful nulls)
        """
        if ConfigManager().is_mcp_verbose():
            # Verbose mode - return as-is
            return response

        # Create a copy to avoid mutating original
        result = response.copy() if isinstance(response, dict) else response

        # Remove duplicate fields
        result = cls._remove_duplicates(result)

        # Remove empty fields
        return cls._remove_empty_fields(result)

    @classmethod
    def _remove_duplicates(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Remove fields that duplicate canonical fields.

        Parameters
        ----------
        data : dict
            Dictionary to process

        Returns
        -------
        dict
            Dictionary with duplicates removed
        """
        if not isinstance(data, dict):
            return data

        result = {}

        for key, value in data.items():
            if cls._should_remove_field(key, data):
                continue

            # Keep field, recursively process nested structures
            result[key] = cls._process_value(value)

        return result

    @classmethod
    def _should_remove_field(cls, key: str, data: dict[str, Any]) -> bool:
        """Check if a field should be removed based on CANONICAL_FIELDS.

        Parameters
        ----------
        key : str
            Field name to check
        data : dict
            Parent dictionary containing the field

        Returns
        -------
        bool
            True if field should be removed
        """
        for mapping in cls.CANONICAL_FIELDS.values():
            # Check simple key match
            if key in mapping["remove"]:
                canonical = mapping["canonical"]
                # If canonical is None, always remove (metadata cleanup)
                # Otherwise, only remove if canonical field exists
                if canonical is None or cls._has_field(data, canonical):
                    return True

            # Check nested path match
            if cls._matches_nested_path(key, data, mapping):
                return True

        return False

    @classmethod
    def _matches_nested_path(
        cls,
        key: str,
        data: dict[str, Any],
        mapping: dict[str, Any],
    ) -> bool:
        """Check if key matches a nested path pattern in mapping.

        Parameters
        ----------
        key : str
            Field name to check
        data : dict
            Parent dictionary
        mapping : dict
            CANONICAL_FIELDS mapping entry

        Returns
        -------
        bool
            True if matches nested path pattern
        """
        for remove_path in mapping["remove"]:
            if "." not in remove_path:
                continue

            parts = remove_path.split(".")
            if len(parts) == 2 and parts[1] == key:
                canonical = mapping["canonical"]
                # Skip if canonical is None (metadata removal)
                if canonical is None:
                    return True
                canonical_key = canonical.split(".")[-1]
                if canonical_key in data:
                    return True

        return False

    @classmethod
    def _process_value(cls, value: Any) -> Any:
        """Recursively process a value for deduplication.

        Parameters
        ----------
        value : Any
            Value to process

        Returns
        -------
        Any
            Processed value
        """
        if isinstance(value, dict):
            return cls._remove_duplicates(value)
        if isinstance(value, list):
            return [
                cls._remove_duplicates(item) if isinstance(item, dict) else item
                for item in value
            ]
        return value

    # Top-level keys that should always be preserved (MCP protocol requirement)
    PRESERVE_TOP_LEVEL_KEYS = {
        MCPResponseField.DATA,
        MCPResponseField.SUCCESS,
        MCPResponseField.SUMMARY,
    }

    @classmethod
    def _remove_empty_fields(
        cls,
        data: dict[str, Any],
        *,
        _is_top_level: bool = True,
    ) -> dict[str, Any]:
        """Remove fields that are null or empty when appropriate.

        Parameters
        ----------
        data : dict
            Dictionary to process
        _is_top_level : bool
            Internal flag to track recursion depth. Top-level required
            keys (data, success, summary) are preserved even if empty.

        Returns
        -------
        dict
            Dictionary with empty fields removed
        """
        if not isinstance(data, dict):
            return data

        result = {}

        for key, value in data.items():
            # Check if this field should be omitted when empty
            if key in cls.OMIT_WHEN_EMPTY:
                checker = cls.OMIT_WHEN_EMPTY[key]
                if checker(value):
                    # Omit this field
                    continue

            # Recursively process nested dicts
            if isinstance(value, dict):
                processed = cls._remove_empty_fields(value, _is_top_level=False)
                # Special case: Remove 'name' field if it duplicates the parent key
                # This happens in variable dicts like {"x": {"name": "x", ...}}
                if (
                    ResponseFieldName.NAME in processed
                    and processed.get(ResponseFieldName.NAME) == key
                ):
                    processed = {
                        k: v
                        for k, v in processed.items()
                        if k != ResponseFieldName.NAME
                    }
                # Preserve top-level required keys even if empty (MCP protocol)
                if _is_top_level and key in cls.PRESERVE_TOP_LEVEL_KEYS:
                    result[key] = processed if processed else {}
                elif processed:  # Only include non-empty dicts
                    result[key] = processed
            elif isinstance(value, list):
                result[key] = [  # type: ignore[assignment]
                    cls._remove_empty_fields(item, _is_top_level=False)
                    if isinstance(item, dict)
                    else item
                    for item in value
                ]
            else:
                result[key] = value

        return result

    @classmethod
    def _has_field(cls, data: dict[str, Any], path: str) -> bool:
        """Check if a nested field exists in the data.

        Parameters
        ----------
        data : dict
            Dictionary to check
        path : str
            Dot-separated path (e.g., "execution_state.status")

        Returns
        -------
        bool
            True if field exists
        """
        parts = path.split(".")
        current = data

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return False

        return True
