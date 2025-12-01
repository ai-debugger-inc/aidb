"""Helper functions for tool definitions."""

from __future__ import annotations

from typing import Any

from aidb_mcp.utils import get_language_description, get_supported_languages


def create_language_param_schema() -> dict[str, Any]:
    """Create a dynamic language parameter schema for tool definitions.

    This generates a parameter schema that automatically includes all
    supported languages from the adapter registry.

    Returns
    -------
    Dict[str, Any]
        Schema definition for a language parameter
    """
    languages = get_supported_languages()

    if languages:
        return {
            "type": "string",
            "enum": languages,
            "description": get_language_description(),
        }
    # Fallback to simple string without enum validation
    return {
        "type": "string",
        "description": "Programming language",
    }


def create_framework_param_schema(language: str | None = None) -> dict[str, Any]:
    """Create a dynamic framework parameter schema.

    If a language is provided, this could query the adapter config
    for supported frameworks. Otherwise returns a generic schema.

    Parameters
    ----------
    language : str, optional
        Language to get frameworks for

    Returns
    -------
    Dict[str, Any]
        Schema definition for a framework parameter
    """
    if language:
        # In the future, we could query adapter config for frameworks
        # For now, return generic schema
        return {
            "type": "string",
            "description": f"Framework for {language} debugging",
        }
    return {
        "type": "string",
        "description": "Optional framework (pytest, jest, django, spring, etc.)",
    }
