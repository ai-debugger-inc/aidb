"""Shared adapter discovery utilities.

This package exposes a stable API for discovering adapters and their capabilities across
CLI and MCP components.
"""

from .adapters import (
    get_adapter_capabilities,
    get_adapter_for_validation,
    get_default_language,
    get_file_extensions_for_language,
    get_hit_condition_examples,
    get_language_description,
    get_language_enum,
    get_language_from_file,
    get_supported_hit_conditions,
    get_supported_languages,
    is_language_supported,
    supports_hit_condition,
)

__all__ = [
    "get_supported_languages",
    "get_language_description",
    "get_language_enum",
    "is_language_supported",
    "get_language_from_file",
    "get_file_extensions_for_language",
    "get_default_language",
    "get_supported_hit_conditions",
    "supports_hit_condition",
    "get_hit_condition_examples",
    "get_adapter_capabilities",
    "get_adapter_for_validation",
]
