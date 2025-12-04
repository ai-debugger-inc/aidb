"""Session initialization handlers.

Handles the init tool which sets up debugging context without creating sessions.
"""

from __future__ import annotations

from typing import Any

from aidb.adapters.downloader import AdapterDownloader
from aidb_common.config.runtime import ConfigManager
from aidb_logging import get_mcp_logger as get_logger

from ...core import ToolName
from ...core.constants import DefaultValue, LaunchMode, ParamName
from ...core.decorators import mcp_tool
from ...responses.base import Response
from ...responses.errors import ErrorResponse, InitRequiredError
from ...responses.helpers import internal_error, invalid_parameter, missing_parameter
from ...starters.registry import StarterRegistry
from ...tools.validation import validate_language

logger = get_logger(__name__)

# Module-level tracking for init state
# This is global so init doesn't create sessions
_INIT_CONTEXT = {
    "initialized": False,
    "language": None,
    "framework": None,
    "mode": None,
}


def reset_init_context():
    """Reset the global init context.

    Used by tests for isolation.
    """
    global _INIT_CONTEXT
    _INIT_CONTEXT = {
        "initialized": False,
        "language": None,
        "framework": None,
        "mode": None,
    }


def _validate_initialization() -> dict[str, Any] | None:
    """Validate that initialization was called first.

    Returns
    -------
    dict, optional
        Error response if initialization not called, None if valid
    """
    if not _INIT_CONTEXT["initialized"]:
        return InitRequiredError(
            error_message=(
                "You must call init first to initialize the debugging "
                "context. This is a required step before starting any debug "
                "session."
            ),
            suggestions=[
                "Call init with your language and optionally framework",
                "Example: init(language='python', framework='pytest')",
                "Then use the session_start params from the init response",
            ],
        ).to_mcp_response()
    return None


async def _check_adapter_availability(language: str) -> dict[str, Any]:
    """Check if the debug adapter for the given language is available.

    Parameters
    ----------
    language : str
        The language to check adapter availability for

    Returns
    -------
    dict[str, Any]
        Adapter availability status and suggestions
    """
    try:
        downloader = AdapterDownloader()
        installed = downloader.list_installed_adapters()

        # Get supported languages from registry for validation
        from aidb.session.adapter_registry import AdapterRegistry

        registry = AdapterRegistry()
        supported_languages = registry.get_languages()

        # Simple mapping - language name equals adapter name
        adapter_name = (
            language.lower() if language.lower() in supported_languages else None
        )
        if not adapter_name:
            return {
                "available": False,
                "reason": "Unsupported language",
                "suggestions": [],
            }

        if adapter_name in installed:
            return {
                "available": True,
                "version": installed[adapter_name].get(
                    "version",
                    DefaultValue.VERSION_UNKNOWN,
                ),
                "path": installed[adapter_name].get("path", DefaultValue.PATH_UNKNOWN),
            }
        return {
            "available": False,
            "reason": f"{language.capitalize()} adapter not installed",
            "suggestions": [
                f"Use download_adapter tool with language='{language}'",
                "Use download_all_adapters tool to install all adapters",
            ],
        }

    except Exception as e:
        logger.warning(
            "Failed to check adapter availability for %s: %s",
            language,
            e,
        )
        return {
            "available": None,
            "reason": f"Could not check adapter status: {e}",
            "suggestions": [
                f"Try download_adapter tool with language='{language}'",
            ],
        }


@mcp_tool(
    require_session=False,
    include_after=False,
    record_history=False,
)
async def handle_init(args: dict[str, Any]) -> dict[str, Any]:
    """Handle init to set up debugging context using StarterRegistry."""
    try:
        # Language is required - don't use default
        language = args.get(ParamName.LANGUAGE)
        if not language:
            return missing_parameter(
                param_name="language",
                param_description=(
                    "Programming language to debug (python, javascript, java)"
                ),
                example_value="python",
            )

        # Validate language is supported
        try:
            validate_language(language)
        except ValueError as e:
            return invalid_parameter(
                param_name="language",
                expected_type="supported language (python, javascript, java)",
                received_value=language,
                error_message=str(e),
            )

        # Check adapter availability and provide download suggestions if needed
        adapter_status = await _check_adapter_availability(language)

        framework = args.get(ParamName.FRAMEWORK)
        mode = args.get(ParamName.MODE, LaunchMode.LAUNCH.value)
        workspace_root = args.get(ParamName.WORKSPACE_ROOT)
        workspace_roots = args.get(ParamName.WORKSPACE_ROOTS)
        launch_config_name = args.get(ParamName.LAUNCH_CONFIG_NAME)
        verbose = args.get(ParamName.VERBOSE, False)

        # Track init state globally
        _INIT_CONTEXT["initialized"] = True
        _INIT_CONTEXT["language"] = language
        _INIT_CONTEXT["framework"] = framework
        _INIT_CONTEXT["mode"] = mode

        # Get the appropriate starter for the language
        starter = StarterRegistry.get_starter(language)

        if not starter:
            # This shouldn't happen if validate_language passed, but handle it
            return ErrorResponse(
                error_code="NO_STARTER",
                error_message=f"No starter available for language: {language}",
                summary=f"Language {language} not properly configured",
            ).to_mcp_response()

        # Generate response using the starter
        starter_response = starter.generate_response(
            framework=framework,
            mode=mode,
            workspace_root=workspace_root,
            workspace_roots=workspace_roots,
            launch_config_name=launch_config_name,
            verbose=verbose,
        )

        # Extract next_steps from starter response to top level
        next_steps = starter_response.pop("next_steps", None)

        # In compact mode, filter to essential fields only
        config_mgr = ConfigManager()
        if not config_mgr.is_mcp_verbose():
            # Keep only essential fields for agents
            starter_response = {
                "language": starter_response.get("language"),
                "framework": starter_response.get("framework"),
                "ready": True,
            }

        # Create a response with the starter data and adapter status
        init_response = Response(
            summary=f"{language.capitalize()} debugging ready",
        )
        response_dict = init_response.to_mcp_response()

        # Put starter data in data field
        response_dict["data"] = starter_response

        # Add next_steps at top level (agents need session_start params)
        if next_steps:
            response_dict["next_steps"] = next_steps

        # Include adapter availability - in compact mode, just the boolean
        if config_mgr.is_mcp_verbose():
            response_dict["adapter_status"] = adapter_status
        else:
            response_dict["adapter_status"] = {
                "available": adapter_status.get("available", False),
            }

        # Add recommendations if adapter is not available
        if not adapter_status.get("available", False):
            response_dict["recommendations"] = adapter_status.get("suggestions", [])

        # No session_id - init doesn't create sessions
        return response_dict

    except Exception as e:
        logger.error("Debug start failed: %s", e)
        return internal_error(
            operation="init",
            exception=e,
            summary="Initialization failed",
        )


# Export handler functions
HANDLERS = {
    ToolName.INIT: handle_init,
}
