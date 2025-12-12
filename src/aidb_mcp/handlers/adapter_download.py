"""MCP handlers for adapter download operations."""

from __future__ import annotations

from typing import Any

from aidb.adapters.downloader import AdapterDownloader
from aidb_common.constants import Language
from aidb_common.discovery.adapters import get_supported_languages
from aidb_logging import get_mcp_logger as get_logger

from ..core.constants import AdapterAction, ParamName, ToolName
from ..core.exceptions import ErrorCode
from ..core.types import ErrorContext
from ..responses.adapter import (
    AdapterBulkDownloadResponse,
    AdapterDownloadResponse,
    AdapterListResponse,
)
from ..responses.errors import (
    ErrorResponse,
    InvalidParameterError,
    MissingParameterError,
)
from ..responses.helpers import internal_error, invalid_action

logger = get_logger(__name__)


async def _handle_adapter_download(args: dict[str, Any]) -> dict[str, Any]:
    """Handle adapter download for a specific language.

    Parameters
    ----------
    args : dict[str, Any]
        Tool arguments containing language, version, and force parameters

    Returns
    -------
    dict[str, Any]
        MCP response with download results
    """
    # Parameters are pre-validated by _validate_action_requirements()
    language = str(args.get(ParamName.LANGUAGE))  # Guaranteed to be valid and present
    version = args.get(ParamName.VERSION)
    force = bool(args.get(ParamName.FORCE, False))

    try:
        # Create downloader and perform download
        downloader = AdapterDownloader()
        result = downloader.download_adapter(language, version=version, force=force)

        if result.success:
            return AdapterDownloadResponse(
                language=result.language,
                path=result.path,
                status=result.status,
                message=result.message,
                version=result.extra.get("version")
                if result.extra and result.extra.get("version")
                else None,
            ).to_mcp_response()

        # Format error response with helpful context
        error_context = ErrorContext(
            language=language,
            download_url_attempted=True,
            manual_instructions_available=bool(result.instructions),
        )

        return ErrorResponse(
            summary=f"Failed to download {language} adapter",
            error_code=ErrorCode.AIDB_ADAPTER_DOWNLOAD_FAILED.value,
            error_message=result.message,
            context=error_context,
        ).to_mcp_response()

    except Exception as e:
        logger.exception(
            "Unexpected error downloading %s adapter: %s",
            language,
            e,
        )
        return internal_error(
            operation="download_adapter",
            exception=e,
            summary=f"Unexpected error downloading {language} adapter",
            context={"language": language},
        )


async def _handle_adapter_download_all(args: dict[str, Any]) -> dict[str, Any]:
    """Handle downloading all available adapters.

    Parameters
    ----------
    args : dict[str, Any]
        Tool arguments containing force parameter

    Returns
    -------
    dict[str, Any]
        MCP response with download results for all adapters
    """
    # Extract optional parameters
    force = bool(args.get("force", False))

    try:
        # Create downloader and perform downloads
        downloader = AdapterDownloader()
        results = downloader.download_all_adapters(force=force)

        # Process results
        success_count = 0
        error_count = 0
        adapter_results = {}

        for language, result in results.items():
            adapter_data = {
                "success": result.success,
                "status": result.status,
                "message": result.message,
            }

            if result.path:
                adapter_data["path"] = result.path
            if result.extra and result.extra.get("version"):
                adapter_data["version"] = result.extra["version"]
            if result.error:
                adapter_data["error"] = result.error
            if result.instructions:
                adapter_data["instructions"] = result.instructions

            adapter_results[language] = adapter_data

            if result.success:
                success_count += 1
            else:
                error_count += 1

        # Format overall response
        total_count = len(results)
        overall_success = success_count > 0

        if overall_success:
            return AdapterBulkDownloadResponse(
                adapters=adapter_results,
                successful=success_count,
                failed=error_count,
                total=total_count,
            ).to_mcp_response()
        return ErrorResponse(
            summary=f"Failed to download any adapters (0/{total_count})",
            error_code=ErrorCode.AIDB_ADAPTER_DOWNLOAD_FAILED.value,
            error_message="All adapter downloads failed",
            context=ErrorContext(
                operation="download_all_adapters",
                failed_count=error_count,
                total_count=total_count,
            ),
        ).to_mcp_response()

    except Exception as e:
        logger.exception("Unexpected error downloading all adapters: %s", e)
        return internal_error(
            operation="download_all_adapters",
            exception=e,
            summary="Unexpected error downloading adapters",
        )


async def _handle_adapter_list(_args: dict[str, Any]) -> dict[str, Any]:
    """Handle listing installed adapters.

    Parameters
    ----------
    _args : dict[str, Any]
        Tool arguments (none required for this operation)

    Returns
    -------
    dict[str, Any]
        MCP response with installed adapter information
    """
    try:
        # Create downloader and list installed adapters
        downloader = AdapterDownloader()
        installed = downloader.list_installed_adapters()

        if installed:
            # Format the installed adapters data
            adapter_info = {}
            for adapter_name, info in installed.items():
                adapter_info[adapter_name] = {
                    "version": info.get("version", "unknown"),
                    "path": info.get("path", "unknown"),
                    "installed": True,
                }

            return AdapterListResponse(
                adapters=adapter_info,
                total_installed=len(installed),
                install_directory=str(downloader.install_dir),
            ).to_mcp_response()

        # No adapters installed
        return AdapterListResponse(
            adapters={},
            total_installed=0,
            install_directory=str(downloader.install_dir),
            suggestions=[
                "Use adapter tool with action='download' and language parameter",
                "Use adapter tool with action='download_all' to install all adapters",
            ],
        ).to_mcp_response()

    except Exception as e:
        logger.exception("Unexpected error listing installed adapters: %s", e)
        return internal_error(
            operation="list_installed_adapters",
            exception=e,
            summary="Unexpected error listing adapters",
        )


def _validate_action_requirements(
    action: AdapterAction,
    args: dict[str, Any],
) -> dict[str, Any] | None:
    """Validate action-specific parameter requirements.

    Parameters
    ----------
    action : AdapterAction
        The action being performed
    args : dict[str, Any]
        Tool arguments

    Returns
    -------
    dict[str, Any] | None
        Error response dict if validation fails, None if valid
    """
    language = args.get(ParamName.LANGUAGE)

    if action == AdapterAction.DOWNLOAD:
        # DOWNLOAD action requires language parameter
        if not language:
            supported_languages = get_supported_languages()
            example_language = (
                supported_languages[0]
                if supported_languages
                else Language.JAVASCRIPT.value
            )

            return MissingParameterError(
                param_name="language",
                param_description=(
                    f"Programming language is required for download action. "
                    f"Available: {', '.join(supported_languages)}"
                ),
                example_value=example_language,
            ).to_mcp_response()

        # Validate language value
        supported_languages = get_supported_languages()
        if language not in supported_languages:
            return InvalidParameterError(
                parameter_name="language",
                expected_type=f"one of {supported_languages}",
                received_value=str(language),
            ).to_mcp_response()

    elif action == AdapterAction.LIST and language:
        # LIST action: validate language if provided (used as filter)
        supported_languages = get_supported_languages()
        if language not in supported_languages:
            return InvalidParameterError(
                parameter_name="language",
                expected_type=f"one of {supported_languages} (for filtering)",
                received_value=str(language),
            ).to_mcp_response()

    # DOWNLOAD_ALL action: language parameter is ignored (no validation needed)
    return None


async def handle_adapter_management(args: dict[str, Any]) -> dict[str, Any]:
    """Handle adapter management operations with action-based dispatch.

    This is the main entry point for the consolidated adapter management tool,
    supporting download, download_all, and list operations with proper validation
    and error handling following MCP standards.

    Parameters
    ----------
    args : dict[str, Any]
        Tool arguments containing action and action-specific parameters

    Returns
    -------
    dict[str, Any]
        MCP-formatted response with operation results
    """
    action_str = args.get(ParamName.ACTION, AdapterAction.LIST.value)
    logger.info(
        "Adapter management handler invoked",
        extra={
            "action": action_str,
            "default_action": AdapterAction.LIST.name,
            "tool": ToolName.ADAPTER,
        },
    )

    # Convert to enum
    try:
        action = AdapterAction(action_str)
    except ValueError:
        action = AdapterAction.LIST

    # Validate action-specific requirements
    validation_error = _validate_action_requirements(action, args)
    if validation_error:
        return validation_error

    try:
        # Dispatch to action handlers
        action_handlers = {
            AdapterAction.DOWNLOAD: _handle_adapter_download,
            AdapterAction.DOWNLOAD_ALL: _handle_adapter_download_all,
            AdapterAction.LIST: _handle_adapter_list,
        }

        handler = action_handlers.get(action)
        if handler:
            return await handler(args)

        valid_actions = [a.value for a in AdapterAction]
        return invalid_action(
            action=action.value,
            valid_actions=valid_actions,
            tool_name=ToolName.ADAPTER,
        )

    except Exception as e:
        logger.error("Adapter management failed: %s", e)
        action_str = action.value if hasattr(action, "value") else str(action)
        return internal_error(
            operation=f"adapter_{action_str}",
            exception=e,
        )


# Handler registry for adapter management tool
HANDLERS = {
    ToolName.ADAPTER: handle_adapter_management,
}
