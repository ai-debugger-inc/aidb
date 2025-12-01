"""Utilities for discovering adapter capabilities from aidb core (shared).

This module provides utilities for querying the aidb adapter registry and capabilities
without requiring a full debug session. It is suitable for use by CLI and MCP
components.
"""

from __future__ import annotations

from typing import Any

from aidb_logging import get_mcp_logger as get_logger

logger = get_logger(__name__)


def get_supported_languages() -> list[str]:
    """Get list of all languages with registered adapters."""
    logger.debug("Querying adapter registry for supported languages")
    try:
        from aidb.session.adapter_registry import AdapterRegistry

        registry = AdapterRegistry()
        if hasattr(registry, "_configs"):
            languages = list(registry._configs.keys())
            result = [lang.lower() for lang in languages] if languages else []
            logger.info(
                "Retrieved supported languages from adapter registry",
                extra={"language_count": len(result), "languages": result},
            )
            return result
        logger.warning("Registry has no _configs attribute")
        return []
    except ImportError:
        logger.debug("AdapterRegistry not available - aidb core not imported")
        return []
    except Exception as e:
        logger.exception("Failed to access adapter registry", extra={"error": str(e)})
        return []


def get_language_description() -> str:
    """Generate a dynamic description string for language parameters."""
    logger.debug("Generating language description string")
    languages = get_supported_languages()
    if languages:
        lang_list = ", ".join(languages)
        description = f"Programming language ({lang_list})"
        logger.debug(
            "Generated language description with languages",
            extra={"description": description, "language_count": len(languages)},
        )
        return description
    logger.debug("Using generic language description - no languages available")
    return "Programming language"


def get_language_enum() -> list[str] | None:
    """Get language list for enum validation in tool schemas."""
    logger.debug("Getting language enum for tool schema validation")
    languages = get_supported_languages()
    return languages if languages else None


def is_language_supported(language: str) -> bool:
    """Check if a language has a registered adapter."""
    normalized = language.lower()
    supported = normalized in get_supported_languages()
    logger.debug(
        "Checked language support",
        extra={"language": language, "normalized": normalized, "supported": supported},
    )
    return supported


def get_language_from_file(filepath: str) -> str | None:
    """Determine the language for a file based on its extension."""
    logger.debug(
        "Resolving language for file %s",
        filepath,
        extra={"filepath": filepath},
    )
    try:
        from aidb.session.adapter_registry import AdapterRegistry

        language = AdapterRegistry.resolve_lang_for_target(filepath)
        result = language.lower() if language else None
        if result:
            logger.debug(
                "Resolved file language",
                extra={"filepath": filepath, "language": result},
            )
        else:
            logger.debug(
                "Could not resolve language for file",
                extra={"filepath": filepath},
            )
        return result
    except ImportError:
        logger.debug("AdapterRegistry not available for file language resolution")
        return None
    except Exception as e:
        logger.exception(
            "Failed to resolve language for file",
            extra={"filepath": filepath, "error": str(e)},
        )
        return None


def get_file_extensions_for_language(language: str) -> list[str]:
    """Get supported file extensions for a language."""
    logger.debug(
        "Getting file extensions for language %s",
        language,
        extra={"language": language},
    )
    try:
        from aidb.session.adapter_registry import AdapterRegistry

        registry = AdapterRegistry()
        config = registry.get_adapter_config(language.lower())
        if config and hasattr(config, "file_extensions"):
            extensions = config.file_extensions
            logger.debug(
                "Retrieved file extensions",
                extra={
                    "language": language,
                    "extension_count": len(extensions),
                    "extensions": extensions,
                },
            )
            return extensions
        logger.debug(
            "No file extensions found for language",
            extra={"language": language},
        )
        return []
    except Exception as e:
        logger.exception(
            "Failed to get file extensions",
            extra={"language": language, "error": str(e)},
        )
        return []


def get_default_language() -> str:
    """Get the default language to use when none is specified."""
    default = "python"
    logger.debug(
        "Using default language %s",
        default,
        extra={"default_language": default},
    )
    return default


def get_supported_hit_conditions(language: str) -> set[str]:
    """Get the set of supported hit condition modes for a language."""
    logger.debug(
        "Getting supported hit conditions %s",
        language,
        extra={"language": language},
    )
    try:
        from aidb.session.adapter_registry import AdapterRegistry

        registry = AdapterRegistry()
        config = registry.get_adapter_config(language.lower())
        if config and hasattr(config, "supported_hit_conditions"):
            mode_names = {mode.name for mode in config.supported_hit_conditions}
            logger.debug(
                "Retrieved hit condition modes",
                extra={
                    "language": language,
                    "mode_count": len(mode_names),
                    "modes": list(mode_names),
                },
            )
            return mode_names
        logger.debug(
            "No hit conditions found for language",
            extra={"language": language},
        )
        return set()
    except Exception as e:
        logger.exception(
            "Failed to get hit conditions",
            extra={"language": language, "error": str(e)},
        )
        return set()


def supports_hit_condition(language: str, expression: str) -> bool:
    """Check if an adapter supports a hit condition expression."""
    logger.debug(
        "Checking hit condition support",
        extra={"language": language, "expression": expression},
    )
    try:
        from aidb.session.adapter_registry import AdapterRegistry

        registry = AdapterRegistry()
        config = registry.get_adapter_config(language.lower())
        if config and hasattr(config, "supports_hit_condition"):
            supported = config.supports_hit_condition(expression)
            logger.debug(
                "Hit condition support checked",
                extra={
                    "language": language,
                    "expression": expression,
                    "supported": supported,
                },
            )
            return supported
        logger.debug(
            "No hit condition support method for language",
            extra={"language": language},
        )
        return False
    except Exception as e:
        logger.exception(
            "Failed to check hit condition support",
            extra={"language": language, "expression": expression, "error": str(e)},
        )
        return False


def get_hit_condition_examples(language: str) -> list[str]:
    """Get example hit conditions based on what the language adapter supports."""
    logger.debug(
        "Getting hit condition examples %s",
        language,
        extra={"language": language},
    )
    try:
        from aidb.models.entities.breakpoint import HitConditionMode
        from aidb.session.adapter_registry import AdapterRegistry

        registry = AdapterRegistry()
        config = registry.get_adapter_config(language.lower())
        if not config or not hasattr(config, "supported_hit_conditions"):
            logger.debug(
                "No hit condition support, using default example",
                extra={"language": language},
            )
            return ["'5' - exact hit count only"]

        examples: list[str] = []
        if HitConditionMode.EXACT in config.supported_hit_conditions:
            examples.append("'5' - break on 5th hit")
            logger.debug(
                "Added EXACT mode example",
                extra={"mode": HitConditionMode.EXACT.name},
            )
        if HitConditionMode.MODULO in config.supported_hit_conditions:
            examples.append("'%10' - break every 10th hit")
            logger.debug(
                "Added MODULO mode example",
                extra={"mode": HitConditionMode.MODULO.name},
            )
        if HitConditionMode.GREATER_THAN in config.supported_hit_conditions:
            examples.append("'>5' - break after 5 hits")
            logger.debug(
                "Added GREATER_THAN mode example",
                extra={"mode": HitConditionMode.GREATER_THAN.name},
            )
        if HitConditionMode.GREATER_EQUAL in config.supported_hit_conditions:
            examples.append("'>=5' - break on 5th hit and after")
            logger.debug(
                "Added GREATER_EQUAL mode example",
                extra={"mode": HitConditionMode.GREATER_EQUAL.name},
            )
        if HitConditionMode.LESS_THAN in config.supported_hit_conditions:
            examples.append("'<5' - break before 5th hit")
            logger.debug(
                "Added LESS_THAN mode example",
                extra={"mode": HitConditionMode.LESS_THAN.name},
            )
        if HitConditionMode.LESS_EQUAL in config.supported_hit_conditions:
            examples.append("'<=5' - break on hits 1-5")
            logger.debug(
                "Added LESS_EQUAL mode example",
                extra={"mode": HitConditionMode.LESS_EQUAL.name},
            )

        result = examples if examples else ["'5' - exact hit count only"]
        logger.info(
            "Generated hit condition examples",
            extra={"language": language, "example_count": len(result)},
        )
        return result
    except Exception as e:
        logger.exception(
            "Failed to get hit condition examples",
            extra={"language": language, "error": str(e)},
        )
        return ["'5' - exact hit count only"]


def get_adapter_capabilities(language: str) -> dict:
    """Get comprehensive capability information for a language adapter."""
    logger.debug(
        "Getting adapter capabilities %s",
        language,
        extra={"language": language},
    )
    try:
        from aidb.session.adapter_registry import AdapterRegistry

        registry = AdapterRegistry()
        config = registry.get_adapter_config(language.lower())
        if not config:
            logger.warning(
                "No adapter config found for language",
                extra={"language": language},
            )
            return {"supported": False, "language": language}

        supported_hit_conditions = list(get_supported_hit_conditions(language))
        file_extensions = list(getattr(config, "file_extensions", []))
        capabilities = {
            "supported": True,
            "language": language,
            "supports_conditional_breakpoints": getattr(
                config,
                "supports_conditional_breakpoints",
                False,
            ),
            "supports_logpoints": getattr(config, "supports_logpoints", False),
            "supports_data_breakpoints": getattr(
                config,
                "supports_data_breakpoints",
                False,
            ),
            "supports_function_breakpoints": getattr(
                config,
                "supports_function_breakpoints",
                False,
            ),
            "supported_hit_conditions": supported_hit_conditions,
            "hit_condition_examples": get_hit_condition_examples(language),
            "file_extensions": file_extensions,
        }
        logger.info(
            "Retrieved adapter capabilities",
            extra={
                "language": language,
                "supports_conditional": capabilities[
                    "supports_conditional_breakpoints"
                ],
                "supports_logpoints": capabilities["supports_logpoints"],
                "supports_data_breakpoints": capabilities["supports_data_breakpoints"],
                "supports_function_breakpoints": capabilities[
                    "supports_function_breakpoints"
                ],
                "hit_condition_count": len(supported_hit_conditions),
                "file_extension_count": len(file_extensions),
            },
        )
        return capabilities
    except Exception as e:
        logger.exception(
            "Failed to get adapter capabilities",
            extra={"language": language, "error": str(e)},
        )
        return {"supported": False, "language": language}


def get_adapter_for_validation(language: str) -> Any | None:
    """Get an adapter config wrapped in a simple object for validation purposes."""
    try:
        from aidb.session.adapter_registry import AdapterRegistry

        registry = AdapterRegistry()
        config = registry.get_adapter_config(language.lower())

        if config:

            class AdapterWrapper:
                def __init__(self, adapter_config):
                    self.config = adapter_config

                def validate_syntax(self, target: str):
                    from aidb.adapters.base.syntax_validator import SyntaxValidator

                    validator = SyntaxValidator.for_language(self.config.language)
                    if validator is None:
                        return True, None
                    return validator.validate(target)

            return AdapterWrapper(config)

        logger.warning(
            "No adapter config found for language",
            extra={"language": language},
        )
        return None
    except Exception as e:
        logger.warning(
            "Failed to get adapter for validation",
            extra={"language": language, "error": str(e)},
        )
        return None
