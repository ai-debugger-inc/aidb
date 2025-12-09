"""MCP utility functions.

This module re-exports adapter discovery utilities from the shared
``aidb_common.discovery.adapters`` module so that existing imports in MCP
handlers remain stable.
"""

from __future__ import annotations

from aidb_common.discovery.adapters import (
    get_adapter_capabilities,
    get_adapter_class,
    get_adapter_config,
    get_adapter_for_validation,
    get_default_language,
    get_file_extensions_for_language,
    get_hit_condition_examples,
    get_language_description,
    get_language_enum,
    get_language_from_file,
    get_popular_frameworks,
    get_supported_frameworks,
    get_supported_hit_conditions,
    get_supported_languages,
    is_language_supported,
    supports_hit_condition,
)

__all__ = [
    "get_adapter_capabilities",
    "get_adapter_class",
    "get_adapter_config",
    "get_adapter_for_validation",
    "get_default_language",
    "get_file_extensions_for_language",
    "get_hit_condition_examples",
    "get_language_description",
    "get_language_enum",
    "get_language_from_file",
    "get_popular_frameworks",
    "get_supported_frameworks",
    "get_supported_hit_conditions",
    "get_supported_languages",
    "is_language_supported",
    "supports_hit_condition",
]
