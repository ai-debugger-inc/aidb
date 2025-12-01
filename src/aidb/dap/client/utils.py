"""Utility functions for DAP client."""

from pathlib import Path
from typing import Any


def clean_dict(d: dict) -> dict:
    """Remove None values from a dict recursively.

    Also fixes Python name mangling for double-underscore attributes.

    Parameters
    ----------
    d : dict
        Dictionary to clean

    Returns
    -------
    dict
        Cleaned dictionary without None values
    """
    result = {}
    for k, v in d.items():
        # Fix Python name mangling (e.g., _AttachRequestArguments__restart ->
        # __restart)
        if k.startswith("_") and "__" in k:
            # Extract the actual field name after the class name prefix
            parts = k.split("__", 1)
            if len(parts) == 2:
                k = "__" + parts[1]  # Restore original double underscore

        if v is not None:
            if isinstance(v, dict):
                v = clean_dict(v)
            result[k] = v
    return result


def sanitize_for_json(obj: Any) -> Any:
    """Convert Path objects and other types for JSON serialization.

    Recursively converts Path objects to strings and handles nested structures.

    Parameters
    ----------
    obj : Any
        Object to sanitize

    Returns
    -------
    Any
        Sanitized object safe for JSON serialization
    """
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [sanitize_for_json(item) for item in obj]
    if hasattr(obj, "__dict__"):
        # Handle dataclasses and other objects with __dict__
        return sanitize_for_json(obj.__dict__)
    return obj
