"""MCP server runtime application.

Defines the AidbMCPServer class and its handlers. Imports that pull in heavy subsystems
(tools, resources, notifications) are performed inside method bodies to reduce import-
time side effects.
"""

from __future__ import annotations

import asyncio
import json
from collections import deque
from typing import Any

from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    AnyUrl,
    CallToolResult,
    Resource,
    ResourceContents,
    TextContent,
    Tool,
)

from aidb.common.constants import (
    DEFAULT_WAIT_TIMEOUT_S,
    MCP_SERVER_TIMEOUT_S,
)
from aidb_logging import get_mcp_logger as get_logger
from aidb_mcp.core.constants import DebugURI, EventType
from aidb_mcp.core.performance import TraceSpan
from aidb_mcp.core.performance_types import SpanType
from aidb_mcp.server.runtime import get_runtime_config

# Provide a fallback for Python <3.11 ExceptionGroup
try:
    _ = ExceptionGroup  # type: ignore[has-type,used-before-def]
except NameError:  # pragma: no cover - legacy fallback

    class ExceptionGroupError(Exception):
        """Group multiple exceptions together (Python < 3.11 fallback)."""

        def __init__(self, message: str, exceptions: list[Exception]):
            super().__init__(message)
            self.exceptions = exceptions

    # Alias for compatibility with Python 3.11+ code paths
    ExceptionGroup = ExceptionGroupError  # type: ignore[misc,assignment]


logger = get_logger(__name__)


class AidbMCPServer:
    """MCP server for debugging."""

    def __init__(self) -> None:
        cfg = get_runtime_config()
        self.server: Server = Server(cfg.server_name)
        self._event_queue: deque[dict[str, Any]] = deque(
            maxlen=cfg.debug.event_queue_size,
        )
        # Ensure handlers are wired explicitly before registering server routes
        try:
            from aidb_mcp.server.wiring import wire_handlers

            wired = wire_handlers()
            logger.debug("MCP handlers wired", extra={"tool_count": len(wired)})
        except Exception as e:  # pragma: no cover - wiring is best-effort
            logger.debug("Handler wiring skipped: %s", e)
        self._register_handlers()

    async def _handle_list_tools(self) -> list[Tool]:
        from aidb_mcp.tools import get_all_tools

        tools = get_all_tools()
        logger.info("Listing  tools %s", len(tools))
        return tools

    async def _handle_call_tool(  # noqa: C901
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> CallToolResult:
        with TraceSpan(SpanType.MCP_CALL, f"call_tool.{name}") as span:
            if not name or not isinstance(name, str):
                logger.error("Invalid tool name provided: %s", name)
                error_response = {
                    "success": False,
                    "error": "Invalid tool name",
                    "tool": str(name) if name else "unknown",
                }
                # Default: compact JSON, use AIDB_MCP_VERBOSE=1 for pretty-print
                from aidb_common.config.runtime import ConfigManager

                config_mgr = ConfigManager()
                if config_mgr.is_mcp_verbose():
                    response_text = json.dumps(error_response, indent=2)
                else:
                    response_text = json.dumps(error_response, separators=(",", ":"))
                self._attach_response_stats(span, response_text)
                return CallToolResult(
                    content=[TextContent(type="text", text=response_text)],
                    isError=True,
                )

            if arguments is None:
                arguments = {}
            elif not isinstance(arguments, dict):
                logger.warning("Arguments not a dict, converting: %s", type(arguments))
                try:
                    if hasattr(arguments, "__iter__"):
                        arguments = dict(arguments)
                    else:
                        arguments = {}
                except Exception:
                    arguments = {}

            logger.info("Tool called: %s", name)
            logger.debug("Arguments: %s", arguments)

            # Get config manager for JSON formatting
            from aidb_common.config.runtime import ConfigManager

            config_mgr = ConfigManager()

            try:
                from aidb_mcp.tools import handle_tool

                result = await asyncio.wait_for(
                    handle_tool(name, arguments),
                    timeout=MCP_SERVER_TIMEOUT_S,
                )

                if not isinstance(result, dict):
                    logger.warning(
                        "Tool %s returned non-dict result: %s",
                        name,
                        type(result),
                    )
                    error_msg = f"Tool returned invalid response format: {type(result)}"
                    result = {
                        "success": False,
                        "error": error_msg,
                        "tool": name,
                    }

                try:
                    # Default: compact JSON for AI agents
                    # Use AIDB_MCP_VERBOSE=1 for human-readable pretty-print
                    if config_mgr.is_mcp_verbose():
                        response_text = json.dumps(result, indent=2, default=str)
                    else:
                        response_text = json.dumps(
                            result,
                            separators=(",", ":"),
                            default=str,
                        )
                except (TypeError, ValueError) as json_err:
                    logger.error(
                        "Failed to serialize tool response for %s: %s",
                        name,
                        json_err,
                    )
                    error_response = {
                        "success": False,
                        "error": f"Failed to serialize response: {str(json_err)}",
                        "tool": name,
                    }
                    # Default: compact JSON
                    if config_mgr.is_mcp_verbose():
                        response_text = json.dumps(error_response, indent=2)
                    else:
                        response_text = json.dumps(
                            error_response,
                            separators=(",", ":"),
                        )
                    self._attach_response_stats(span, response_text)
                    return CallToolResult(
                        content=[TextContent(type="text", text=response_text)],
                        isError=True,
                    )

                self._attach_response_stats(span, response_text)
                # Set isError based on success field in response
                is_error = not result.get("success", True)
                return CallToolResult(
                    content=[TextContent(type="text", text=response_text)],
                    isError=is_error,
                )

            except asyncio.TimeoutError:
                logger.error("Tool %s execution timed out", name)
                error_response = {
                    "success": False,
                    "error": "Tool execution timed out",
                    "tool": name,
                }
                # Default: compact JSON
                if config_mgr.is_mcp_verbose():
                    response_text = json.dumps(error_response, indent=2)
                else:
                    response_text = json.dumps(error_response, separators=(",", ":"))
                self._attach_response_stats(span, response_text)
                return CallToolResult(
                    content=[TextContent(type="text", text=response_text)],
                    isError=True,
                )
            except asyncio.CancelledError:
                logger.info("Tool %s execution was cancelled", name)
                error_response = {
                    "success": False,
                    "error": "Tool execution was cancelled",
                    "tool": name,
                }
                # Default: compact JSON
                if config_mgr.is_mcp_verbose():
                    response_text = json.dumps(error_response, indent=2)
                else:
                    response_text = json.dumps(error_response, separators=(",", ":"))
                self._attach_response_stats(span, response_text)
                return CallToolResult(
                    content=[TextContent(type="text", text=response_text)],
                    isError=True,
                )
            except Exception as e:  # pragma: no cover - defensive logging
                logger.exception("Error handling tool %s: %s", name, e)
                error_response = {
                    "success": False,
                    "error": str(e),
                    "tool": name,
                    "error_type": type(e).__name__,
                }
                # Default: compact JSON
                if config_mgr.is_mcp_verbose():
                    response_text = json.dumps(error_response, indent=2)
                else:
                    response_text = json.dumps(error_response, separators=(",", ":"))
                self._attach_response_stats(span, response_text)
                return CallToolResult(
                    content=[TextContent(type="text", text=response_text)],
                    isError=True,
                )

    async def _handle_list_resources(self) -> list[Resource]:
        from aidb_mcp.integrations.resources import get_all_resources

        resources = get_all_resources()
        logger.info("Listing  resources %s", len(resources))
        return resources

    async def _handle_read_resource(self, uri: str) -> ResourceContents:
        logger.info("Reading resource: %s", uri)
        try:
            from aidb_mcp.integrations.resources import read_resource

            return read_resource(uri)
        except Exception as e:  # pragma: no cover - defensive logging
            logger.error("Error reading resource %s: %s", uri, e)
            raise

    async def _handle_notification(self, event_data: dict[str, Any]) -> None:
        try:
            event_type = event_data.get("event_type", "debug_event")
            self._event_queue.append(event_data)
            await self._send_mcp_notification(event_data, event_type)

            msg = event_data.get("message", "No message")
            logger.info("Debug event (%s): %s", event_type, msg)
            logger.debug("Full event data for %s: %s", event_type, event_data)
        except Exception as e:  # pragma: no cover
            logger.error("Error handling debug event notification: %s", e)

    async def _send_mcp_notification(
        self,
        event_data: dict[str, Any],
        event_type: str,
    ) -> None:
        try:
            ctx = self.server.request_context
            if ctx and ctx.session:
                if "session_id" in event_data:
                    notification_uri = DebugURI.session_event(
                        event_data["session_id"],
                        event_type,
                    )
                else:
                    notification_uri = DebugURI.event(event_type)

                await ctx.session.send_resource_updated(AnyUrl(notification_uri))
                logger.debug(
                    "Sent MCP notification for %s: %s",
                    event_type,
                    notification_uri,
                )
        except LookupError:
            logger.debug("No MCP session context for %s notification", event_type)
        except Exception as notif_err:  # pragma: no cover
            logger.warning("Failed to send MCP notification: %s", notif_err)

    def _attach_response_stats(
        self,
        span: Any,
        response_text: str,
    ) -> None:
        """Attach response statistics to performance span.

        Parameters
        ----------
        span : PerformanceSpan | None
            Performance span to update (may be None if tracing disabled)
        response_text : str
            Serialized JSON response text
        """
        if span is None:
            return

        from aidb_mcp.utils.token_estimation import estimate_tokens

        # Calculate stats directly from the serialized text
        # (response_text is already JSON, don't double-serialize)
        span.response_chars = len(response_text)
        span.response_tokens = estimate_tokens(response_text)
        span.response_size_bytes = len(response_text.encode("utf-8"))

        if span.response_tokens is not None:
            logger.debug(
                "Response stats: %d chars, ~%d tokens",
                span.response_chars,
                span.response_tokens,
            )

    def _register_handlers(self) -> None:
        self.server.list_tools()(self._handle_list_tools)
        self.server.call_tool()(self._handle_call_tool)
        self.server.list_resources()(self._handle_list_resources)
        self.server.read_resource()(self._handle_read_resource)

        from aidb_mcp.integrations.notifications import get_notification_manager

        notification_manager = get_notification_manager()
        event_types = [
            EventType.BREAKPOINT_HIT.value,
            EventType.EXCEPTION.value,
            EventType.SESSION_STATE_CHANGED.value,
            EventType.WATCH_CHANGED.value,
            EventType.THREAD_EVENT.value,
        ]
        for event_type in event_types:
            notification_manager.register_listener(
                event_type,
                self._handle_notification,
            )

    def get_queued_events(self, count: int = 10) -> list[dict[str, Any]]:
        """Get recent queued events."""
        events = list(self._event_queue)
        if count > 0 and len(events) > count:
            return events[-count:]
        return events

    async def run(self) -> None:
        """Run the MCP server."""
        logger.info("Starting AIDB MCP Server v2")
        logger.info("Features: Tools, Resources, Notifications")
        cfg = get_runtime_config()
        logger.info("Server: %s v%s", cfg.server_name, cfg.server_version)

        from aidb_mcp.integrations.notifications import start_event_monitoring

        await start_event_monitoring()

        try:
            async with stdio_server() as (read_stream, write_stream):
                logger.info("stdio server connected, starting MCP protocol handler")
                try:
                    cfg = get_runtime_config()
                    await self.server.run(
                        read_stream,
                        write_stream,
                        InitializationOptions(
                            server_name=cfg.server_name,
                            server_version=cfg.server_version,
                            capabilities=self.server.get_capabilities(
                                notification_options=NotificationOptions(),
                                experimental_capabilities={},
                            ),
                        ),
                    )
                except ExceptionGroup as eg:
                    logger.info(
                        "Server task group encountered exceptions: %d",
                        len(eg.exceptions),
                    )
                    cancellation_errors = []
                    other_errors = []
                    for exc in eg.exceptions:
                        if isinstance(exc, asyncio.CancelledError):
                            cancellation_errors.append(exc)
                        else:
                            other_errors.append(exc)
                    if cancellation_errors:
                        logger.info(
                            "Found %d cancellation errors in task group",
                            len(cancellation_errors),
                        )
                    if other_errors:
                        logger.error(
                            "Found %d non-cancellation errors in task group",
                            len(other_errors),
                        )
                        for exc in other_errors:
                            logger.exception("Task group error: %s", exc)
                        msg = "Non-cancellation errors in task group"
                        raise ExceptionGroup(msg, other_errors) from eg
        except asyncio.CancelledError:
            logger.info("Server task cancelled")
        except Exception as e:  # pragma: no cover
            logger.exception("Server error: %s", e)
            raise
        finally:
            await self._cleanup()

    def _create_cleanup_tasks(self) -> list[asyncio.Task[Any]]:
        """Create cleanup tasks for event monitoring and debug sessions."""
        from aidb_mcp.integrations.notifications import stop_event_monitoring
        from aidb_mcp.session.manager import _DEBUG_SESSIONS

        tasks: list[asyncio.Task[Any]] = []
        tasks.append(asyncio.create_task(stop_event_monitoring()))

        for session_id in list(_DEBUG_SESSIONS.keys()):
            try:
                tasks.append(
                    asyncio.create_task(self._cleanup_session_safely(session_id)),
                )
            except Exception as e:  # pragma: no cover
                logger.warning(
                    "Error creating cleanup task for session %s: %s",
                    session_id,
                    e,
                )
        return tasks

    async def _cleanup(self) -> None:
        logger.info("Cleaning up AIDB MCP Server...")
        cleanup_tasks: list[asyncio.Task[Any]] = []
        try:
            cleanup_tasks = self._create_cleanup_tasks()
            if cleanup_tasks:
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*cleanup_tasks, return_exceptions=True),
                        timeout=DEFAULT_WAIT_TIMEOUT_S,
                    )
                    logger.info("All cleanup tasks completed")
                except asyncio.TimeoutError:
                    logger.warning("Cleanup tasks timed out, forcing shutdown")
                    for task in cleanup_tasks:
                        if not task.done():
                            task.cancel()
        except asyncio.CancelledError:
            logger.info("Server cleanup was cancelled")
            for task in cleanup_tasks:
                if not task.done():
                    task.cancel()
        except Exception as e:  # pragma: no cover
            logger.exception("Error during server cleanup: %s", e)
        logger.info("AIDB MCP Server cleanup complete")

    async def _cleanup_session_safely(self, session_id: str) -> None:
        """Clean up a debug session safely.

        NOTE: This runs cleanup synchronously in the current thread rather than
        using a thread executor. This is intentional - the cleanup_session function
        uses a threading.RLock that is also used by other code in the main thread.
        Running cleanup in a separate thread causes cross-thread lock contention
        and 10-second timeouts.

        The cleanup operation is typically fast (< 100ms), so briefly blocking
        the event loop is acceptable and avoids deadlock issues.
        """
        from aidb_mcp.session.manager import cleanup_session

        try:
            # Run cleanup synchronously to avoid cross-thread lock contention
            success = cleanup_session(session_id)
            if success:
                logger.info("Stopped debug session: %s", session_id)
            else:
                logger.warning("Failed to stop debug session: %s", session_id)
        except asyncio.CancelledError:
            logger.info("Cleanup cancelled for session: %s", session_id)
        except Exception as e:  # pragma: no cover
            logger.warning("Error stopping debug session %s: %s", session_id, e)
