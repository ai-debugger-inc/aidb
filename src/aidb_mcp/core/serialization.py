"""Serialization utilities for MCP server.

All DebugService responses (dataclasses or custom response models) are converted into
JSON-safe primitives here.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from aidb_logging import get_mcp_logger as get_logger

logger = get_logger(__name__)


def _to_primitive(obj: Any) -> Any:
    """Recursively convert objects to JSON-safe primitives.

    Handles:
    - dataclasses
    - lists / dicts
    - datetime -> ISO string
    - Enum -> name
    """
    if obj is None:
        return None

    if is_dataclass(obj) and not isinstance(obj, type):
        logger.debug(
            "Converting dataclass to primitive",
            extra={"dataclass_type": type(obj).__name__},
        )
        return _to_primitive(asdict(obj))

    if isinstance(obj, list):
        return [_to_primitive(i) for i in obj]

    if isinstance(obj, dict):
        return {k: _to_primitive(v) for k, v in obj.items()}

    if isinstance(obj, datetime):
        logger.debug(
            "Converting datetime to ISO string",
            extra={"datetime": obj.isoformat()},
        )
        return obj.isoformat()

    if isinstance(obj, Enum):
        logger.debug(
            "Converting enum to name",
            extra={
                "enum_type": type(obj).__name__,
                "enum_name": obj.name,
                "enum_value": obj.value,
            },
        )
        return obj.name

    return obj


def to_jsonable(obj: Any) -> Any:
    """Return a JSON-serializable representation of obj."""
    logger.debug(
        "Converting object to JSON-serializable format",
        extra={"object_type": type(obj).__name__},
    )
    return _to_primitive(obj)


def to_json_text(obj: Any, indent: int = 2) -> str:
    """Return a JSON string from any response-like object."""
    try:
        jsonable = to_jsonable(obj)
        result = json.dumps(jsonable, indent=indent, default=str)
        logger.debug(
            "Successfully serialized object to JSON",
            extra={"object_type": type(obj).__name__, "json_length": len(result)},
        )
        return result
    except Exception as e:
        logger.exception(
            "Failed to serialize object to JSON",
            extra={"object_type": type(obj).__name__, "error": str(e)},
        )
        raise
