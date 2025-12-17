"""Session configuration handlers.

Handles config management operations like capabilities, env, adapters, etc.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aidb.adapters.downloader import AdapterDownloader
from aidb.common.capabilities import DAPCapability
from aidb_common.config import config
from aidb_common.constants import Language
from aidb_logging import get_mcp_logger as get_logger

from ...core import (
    ConfigAction,
    StepAction,
    ToolName,
)
from ...core.constants import AdapterStatus, DefaultValue, LaunchMode, ParamName
from ...core.decorators import mcp_tool
from ...core.exceptions import ErrorCode
from ...responses.base import Response
from ...responses.errors import ErrorResponse
from ...responses.helpers import internal_error, missing_parameter
from ...session import get_last_active_session
from ...utils import get_default_language

logger = get_logger(__name__)


async def _handle_config_capabilities(args: dict[str, Any]) -> dict[str, Any]:
    """Handle capabilities config action."""
    language = args.get(ParamName.LANGUAGE, get_default_language())

    # Get adapter capabilities from registry (always available)
    from ...utils import get_adapter_capabilities

    adapter_info = get_adapter_capabilities(language)

    # Try to get DAP capabilities from active session for more details
    session = get_last_active_session()
    adapter_caps = None
    if session and hasattr(session, "get_capabilities"):
        adapter_caps = session.get_capabilities()

    if adapter_caps:
        # Merge DAP capabilities with adapter registry info
        caps = _format_dap_capabilities(adapter_caps)
        # Add hit condition info from adapter registry
        caps.update(
            {
                "supported_hit_conditions": adapter_info.get(
                    "supported_hit_conditions",
                    [],
                ),
                "hit_condition_examples": adapter_info.get(
                    "hit_condition_examples",
                    [],
                ),
            },
        )
        response = Response(summary=f"Active session capabilities for {language}")
        response_dict = response.to_mcp_response()
        response_dict["data"]["language"] = language
        response_dict["data"]["capabilities"] = caps
        response_dict["data"]["available"] = True
        return response_dict

    # No active session, but we can still provide adapter registry info
    response = Response(
        summary=f"Adapter capabilities for {language} (no active session)",
    )
    response_dict = response.to_mcp_response()
    response_dict["data"]["language"] = language
    response_dict["data"]["capabilities"] = adapter_info
    response_dict["data"]["available"] = adapter_info.get("supported", False)
    response_dict["data"]["message"] = "Start a debug session for full DAP capabilities"
    return response_dict


async def _handle_config_env(_args: dict[str, Any]) -> dict[str, Any]:
    """Handle ENV config action."""
    env_vars = config.get_all_aidb_vars()
    response = Response(summary=f"Found {len(env_vars)} AIDB environment variables")
    response_dict = response.to_mcp_response()
    response_dict["data"]["environment"] = env_vars
    return response_dict


async def _handle_config_launch(_args: dict[str, Any]) -> dict[str, Any]:
    """Handle LAUNCH config action."""
    configs = _discover_launch_configs()
    response = Response(summary=f"Found {len(configs)} launch configurations")
    response_dict = response.to_mcp_response()
    response_dict["data"]["configurations"] = configs
    return response_dict


async def _handle_config_get(args: dict[str, Any]) -> dict[str, Any]:
    """Handle GET config action."""
    key = args.get(ParamName.KEY, "")
    if key:
        from aidb_common.env.reader import read_str

        value = read_str(key, "")
        response = Response(summary=f"Configuration value for '{key}'")
        response_dict = response.to_mcp_response()
        response_dict["data"]["key"] = key
        response_dict["data"]["value"] = value
        return response_dict

    # Show all configuration
    config_data = {
        "active_session": get_last_active_session(),
        "environment": config.get_all_aidb_vars(),
        "launch_configs": _discover_launch_configs(),
    }
    response = Response(summary="Current debugging configuration")
    response_dict = response.to_mcp_response()
    response_dict["data"] = config_data
    return response_dict


async def _handle_config_set(args: dict[str, Any]) -> dict[str, Any]:
    """Handle SET config action."""
    key = args.get(ParamName.KEY, "")
    value = args.get(ParamName.VALUE, "")
    if not key:
        return missing_parameter(ParamName.KEY, "Configuration key to set")
    if not value:
        return missing_parameter(ParamName.VALUE, "Configuration value to set")

    # Only allow setting AIDB_ environment variables for safety
    if not key.startswith("AIDB_"):
        return ErrorResponse(
            error_message=f"Only AIDB_ environment variables can be set, got: {key}",
            error_code=ErrorCode.AIDB_VALIDATION_INVALID_TYPE.value,
        ).to_mcp_response()

    config.set_env_var(key, value)
    response = Response(summary=f"Set {key} = {value}")
    response_dict = response.to_mcp_response()
    response_dict["data"]["key"] = key
    response_dict["data"]["value"] = value
    response_dict["data"]["set"] = True
    return response_dict


async def _handle_config_adapters(_args: dict[str, Any]) -> dict[str, Any]:
    """Handle ADAPTERS config action."""
    try:
        from aidb_common.discovery.adapters import get_supported_languages

        downloader = AdapterDownloader()
        installed = downloader.list_installed_adapters()

        adapter_status = {}
        # Get supported languages from utility
        supported_languages = get_supported_languages()

        for language in supported_languages:
            adapter_name = language.lower()
            if adapter_name in installed:
                adapter_status[language] = {
                    "installed": True,
                    "version": installed[adapter_name].get(
                        "version",
                        DefaultValue.VERSION_UNKNOWN,
                    ),
                    "path": installed[adapter_name].get(
                        "path",
                        DefaultValue.PATH_UNKNOWN,
                    ),
                    "status": AdapterStatus.READY.value,
                }
            else:
                adapter_status[language] = {
                    "installed": False,
                    "status": AdapterStatus.MISSING.value,
                    "suggestions": [
                        f"Use adapter tool: action='download', language='{language}'",
                    ],
                }

        total_adapters = len(adapter_status)
        installed_count = sum(
            1 for info in adapter_status.values() if info["installed"]
        )

        response = Response(
            summary=f"Adapters: {installed_count}/{total_adapters} installed",
        )
        response_dict = response.to_mcp_response()
        response_dict["data"]["adapters"] = adapter_status
        response_dict["data"]["summary"] = {
            "total": total_adapters,
            "installed": installed_count,
            "missing": total_adapters - installed_count,
            "install_directory": str(downloader.install_dir),
        }

        # Add quick actions if any adapters are missing
        if installed_count < total_adapters:
            response_dict["quick_actions"] = [
                "Use adapter tool: action='download_all' to install all",
                "Use adapter tool: action='list' for detailed status",
            ]

        return response_dict

    except Exception as e:
        logger.exception("Error checking adapter status: %s", e)
        return internal_error(
            operation="config_adapters",
            exception=e,
            summary="Failed to check adapter status",
        )


async def _handle_config_show(_args: dict[str, Any]) -> dict[str, Any]:
    """Handle SHOW/LIST config action."""
    session_id = get_last_active_session()
    config_data = {
        "active_session": session_id if session_id else None,
        "environment": config.get_all_aidb_vars(),
        "launch_configs": _discover_launch_configs(),
    }

    # Add session info if available
    if session_id:
        from ...session import get_or_create_session

        try:
            _, context = get_or_create_session(session_id)
            target = (
                context.session_info.target
                if context and context.session_info
                else None
            )
            session_info_dict = {
                "language": (
                    context.session_info.language
                    if context and context.session_info
                    else Language.PYTHON.value
                ),
                "mode": LaunchMode.LAUNCH.value,
            }
            if target:
                session_info_dict["target"] = target
            config_data["session_info"] = session_info_dict
        except Exception as e:
            msg = f"Failed to get session info for config: {e}"
            logger.debug(msg)

    response = Response(summary="Current debugging configuration")
    response_dict = response.to_mcp_response()
    response_dict["data"] = config_data
    return response_dict


def _get_breakpoint_capabilities(capabilities: Any) -> list[str]:
    """Extract breakpoint capabilities."""
    breakpoints = ["line"]  # Always support line breakpoints

    capability_map = {
        DAPCapability.CONDITIONAL_BREAKPOINTS: "conditional",
        DAPCapability.FUNCTION_BREAKPOINTS: "function",
        DAPCapability.LOG_POINTS: "logpoints",
        DAPCapability.DATA_BREAKPOINTS: "data",
        DAPCapability.INSTRUCTION_BREAKPOINTS: "instruction",
    }

    for attr, name in capability_map.items():
        if getattr(capabilities, attr, False):
            breakpoints.append(name)

    return breakpoints


def _get_stepping_capabilities(capabilities: Any) -> list[str]:
    """Extract stepping capabilities."""
    stepping = [
        StepAction.INTO.value,
        StepAction.OVER.value,
        StepAction.OUT.value,
    ]

    if getattr(capabilities, DAPCapability.STEP_BACK, False):
        stepping.append("back")
    if getattr(capabilities, DAPCapability.STEPPING_GRANULARITY, False):
        stepping.append("granular")

    return stepping


def _get_evaluation_capabilities(capabilities: Any) -> list[str]:
    """Extract evaluation capabilities."""
    evaluation = []

    capability_map = {
        DAPCapability.EVALUATE_FOR_HOVERS: "hover",
        DAPCapability.SET_VARIABLE: "set_variable",
        DAPCapability.SET_EXPRESSION: "set_expression",
        DAPCapability.COMPLETIONS: "completions",
    }

    for attr, name in capability_map.items():
        if getattr(capabilities, attr, False):
            evaluation.append(name)

    return evaluation


def _get_advanced_capabilities(capabilities: Any) -> list[str]:
    """Extract advanced capabilities."""
    advanced = []

    capability_map = {
        DAPCapability.RESTART: "restart",
        DAPCapability.TERMINATE: "terminate",
        DAPCapability.READ_MEMORY: "memory_read",
        DAPCapability.WRITE_MEMORY: "memory_write",
        DAPCapability.DISASSEMBLE: "disassemble",
        DAPCapability.MODULES: "modules",
    }

    for attr, name in capability_map.items():
        if getattr(capabilities, attr, False):
            advanced.append(name)

    return advanced


def _format_dap_capabilities(capabilities: Any) -> dict[str, Any]:
    """Format DAP Capabilities object into a more readable format."""
    result: dict[str, Any] = {
        "breakpoints": _get_breakpoint_capabilities(capabilities),
        "stepping": _get_stepping_capabilities(capabilities),
        "evaluation": _get_evaluation_capabilities(capabilities),
        "advanced": _get_advanced_capabilities(capabilities),
    }

    # Add raw capabilities for full transparency
    result["raw"] = {
        attr: getattr(capabilities, attr)
        for attr in dir(capabilities)
        if attr.startswith("supports") and not attr.startswith("_")
    }

    return result


def _discover_launch_configs() -> list[dict[str, Any]]:
    """Discover available launch configurations."""
    # Look for .vscode/launch.json
    launch_json_path = ".vscode/launch.json"
    if Path(launch_json_path).exists():
        # Would parse launch.json here
        return [{"name": "Found launch.json", "path": launch_json_path}]

    return [{"name": "No launch configurations found"}]


@mcp_tool(
    require_session=False,
    include_after=True,
    record_history=False,
)
async def handle_config_management(args: dict[str, Any]) -> dict[str, Any]:
    """Handle configuration and capabilities management."""
    from ..dispatch import dispatch_action

    action_handlers = {
        ConfigAction.CAPABILITIES: _handle_config_capabilities,
        ConfigAction.ENV: _handle_config_env,
        ConfigAction.LAUNCH: _handle_config_launch,
        ConfigAction.ADAPTERS: _handle_config_adapters,
        ConfigAction.GET: _handle_config_get,
        ConfigAction.SET: _handle_config_set,
        ConfigAction.SHOW: _handle_config_show,
        ConfigAction.LIST: _handle_config_show,  # LIST uses same handler as SHOW
    }

    handler, error, handler_args = dispatch_action(
        args,
        ConfigAction,
        action_handlers,
        default_action=ConfigAction.SHOW,
        tool_name=ToolName.CONFIG,
    )

    if error or handler is None:
        return error or internal_error(
            operation="config",
            exception="No handler found",
        )

    try:
        return await handler(*handler_args)
    except Exception as e:
        action = args.get(ParamName.ACTION, ConfigAction.SHOW.value)
        logger.error("Config management failed: %s", e)
        return internal_error(operation=f"config_{action}", exception=e)


# Export handler functions
HANDLERS = {
    ToolName.CONFIG: handle_config_management,
}
