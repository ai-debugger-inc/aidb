"""Session-related response classes for MCP tools.

This module provides response classes for debugging session lifecycle operations:
- SessionStartResponse: For session initialization (launch/attach/remote)
- SessionStopResponse: For session termination
- SessionStatusResponse: For querying session state
- SessionListResponse: For listing active sessions

All responses include execution state and provide context-aware guidance based
on the current debugging context (breakpoints, entry point, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..core.constants import DetailedExecutionStatus, ResponseFieldName
from .base import Response
from .builders import CodeSnapshotBuilder, ExecutionStateBuilder
from .next_steps import (
    PAUSED_AT_BREAKPOINT_NEXT_STEPS,
    SESSION_START_NO_BREAKPOINTS_NEXT_STEPS,
    SESSION_START_WITH_BREAKPOINTS_NEXT_STEPS,
    SESSION_STOP_NEXT_STEPS,
)

if TYPE_CHECKING:
    from aidb.common.code_context import CodeContextResult


@dataclass
class SessionStartResponse(Response):
    """Response for successful session start.

    Provides comprehensive session initialization information including mode
    (launch/attach/remote), breakpoint status, and execution state. Always includes
    next_steps guidance as this is an entry point for debugging.

    Automatically infers execution status based on is_paused flag, providing appropriate
    next steps for the user's context.
    """

    session_id: str = ""
    mode: str = ""  # "launch", "attach", or "remote"
    language: str = ""
    target: str | None = None
    pid: int | None = None
    host: str | None = None
    port: int | None = None
    breakpoints_set: int = 0
    subscribed_events: list[str] = field(default_factory=list)
    workspace_root: str | None = None
    is_paused: bool = False
    default_changed: bool = False
    previous_default_session: str | None = None
    code_context: CodeContextResult | None = None
    location: str | None = None
    detailed_status: str | None = None
    stop_reason: str | None = None

    def _generate_summary(self) -> str:
        # Include session ID in base message
        short_id = self.session_id[:8] if self.session_id else "unknown"
        base_msg = f"Debug session {short_id} started in {self.mode} mode"

        details = []
        if self.default_changed:
            if self.previous_default_session:
                prev_short_id = self.previous_default_session[:8]
                details.append(f"set as default (was: {prev_short_id})")
            else:
                details.append("set as default session")

        if details:
            return f"{base_msg} ({', '.join(details)})"
        return base_msg

    def get_next_steps(self):
        """Get context-aware next steps after starting a session."""
        # If paused at a breakpoint, suggest debugging actions
        if self.is_paused:
            return PAUSED_AT_BREAKPOINT_NEXT_STEPS

        # If breakpoints were provided, use context-aware next steps
        if self.breakpoints_set > 0:
            return SESSION_START_WITH_BREAKPOINTS_NEXT_STEPS

        # No breakpoints provided - guide user to set them first
        return SESSION_START_NO_BREAKPOINTS_NEXT_STEPS

    def _infer_detailed_status(self) -> DetailedExecutionStatus:
        """Infer detailed execution status from session state.

        Returns
        -------
        DetailedExecutionStatus
            The inferred detailed status
        """
        if self.is_paused:
            return DetailedExecutionStatus.PAUSED
        return DetailedExecutionStatus.RUNNING

    def _customize_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """Customize session start response structure."""
        # Remove redundant state fields that duplicate execution_state
        response["data"].pop(ResponseFieldName.IS_PAUSED, None)
        response["data"].pop(ResponseFieldName.DETAILED_STATUS, None)
        response["data"].pop(ResponseFieldName.STOP_REASON, None)

        # Determine detailed status
        detailed_status = (
            DetailedExecutionStatus(self.detailed_status)
            if self.detailed_status
            else self._infer_detailed_status()
        )

        # Build execution state using builder
        execution_state = ExecutionStateBuilder.build(
            detailed_status=detailed_status,
            location=self.location,
            has_breakpoints=self.breakpoints_set > 0,
            stop_reason=None,
        )
        response["data"][ResponseFieldName.EXECUTION_STATE] = execution_state

        # Build code snapshot using builder
        code_snapshot = CodeSnapshotBuilder.build(
            code_context=self.code_context,
            location=self.location,
            fallback_target=self.target,
        )
        if code_snapshot:
            response["data"][ResponseFieldName.CODE_SNAPSHOT] = code_snapshot

        # Add display target
        if self.target:
            display_target = self.target
        elif self.pid:
            display_target = f"PID:{self.pid}"
        elif self.host and self.port:
            display_target = f"{self.host}:{self.port}"
        else:
            display_target = "unknown"
        response["data"]["target"] = display_target

        return response


@dataclass
class SessionStopResponse(Response):
    """Response for session stop operation."""

    session_id: str = ""
    terminated_reason: str | None = None
    cleanup_performed: bool = True

    def _generate_summary(self) -> str:
        if self.terminated_reason:
            return f"Debug session stopped: {self.terminated_reason}"
        return "Debug session stopped"

    def get_next_steps(self):
        """Get next steps after stopping a session."""
        return SESSION_STOP_NEXT_STEPS


@dataclass
class SessionRestartResponse(Response):
    """Response for session restart operation."""

    session_id: str = ""
    method: str = "emulated"
    kept_breakpoints: bool = True
    breakpoint_count: int = 0

    def _generate_summary(self) -> str:
        short_id = self.session_id[:8] if self.session_id else "unknown"
        method_text = "natively" if self.method == "native" else "via stop+start"
        bp_text = (
            f" with {self.breakpoint_count} breakpoints"
            if self.kept_breakpoints and self.breakpoint_count > 0
            else ""
        )
        return f"Session {short_id} restarted {method_text}{bp_text}"

    def get_next_steps(self):
        """Get next steps after restarting a session."""
        return SESSION_START_NO_BREAKPOINTS_NEXT_STEPS


@dataclass
class SessionStatusResponse(Response):
    """Response for session status query.

    Note: This response uses execution_state as the canonical source for
    session state information. The redundant top-level started/paused/terminated
    fields have been removed to eliminate duplication and cognitive load for agents.
    """

    session_id: str = ""
    language: str | None = None
    target: str | None = None
    current_location: str | None = None
    stopped_reason: str | None = None
    thread_count: int = 1
    breakpoint_count: int = 0
    # State tracking for internal use
    started: bool = False
    paused: bool = False
    terminated: bool = False

    def _generate_summary(self) -> str:
        if self.terminated:
            return "Session terminated"
        if self.paused:
            location_text = (
                f" at {self.current_location}" if self.current_location else ""
            )
            return f"Session paused{location_text}"
        if self.started:
            return "Session running"
        return "Session idle"

    def _infer_detailed_status(self) -> DetailedExecutionStatus:
        """Infer detailed execution status from session state.

        Returns
        -------
        DetailedExecutionStatus
            The inferred detailed status
        """
        if self.terminated:
            return DetailedExecutionStatus.TERMINATED
        if not self.started:
            return DetailedExecutionStatus.UNKNOWN
        if self.paused:
            return DetailedExecutionStatus.PAUSED
        return DetailedExecutionStatus.RUNNING

    def _customize_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """Customize session status response structure."""
        # Remove redundant state fields that were auto-extracted by base class
        # These are kept in dataclass for internal logic but should not
        # appear in response
        response["data"].pop("started", None)
        response["data"].pop("paused", None)
        response["data"].pop("terminated", None)

        # Add simple status field for quick reference
        if self.terminated:
            status = "terminated"
        elif not self.started:
            status = "idle"
        elif self.paused:
            status = "paused"
        else:
            status = "running"
        response["data"]["status"] = status

        # Build execution state using builder (canonical source of truth)
        detailed_status = self._infer_detailed_status()
        response["data"]["execution_state"] = ExecutionStateBuilder.build(
            detailed_status=detailed_status,
            location=self.current_location,
            has_breakpoints=self.breakpoint_count > 0,
            stop_reason=self.stopped_reason,
        )

        # Note: started/paused/terminated fields are NOT included in response data
        # to avoid redundancy. Agents should use execution_state as canonical source.

        return response


@dataclass
class SessionListResponse(Response):
    """Response for listing active sessions."""

    sessions: list[dict[str, Any]] = field(default_factory=list)

    def _generate_summary(self) -> str:
        count = len(self.sessions)
        if count == 0:
            return "No active sessions"
        if count == 1:
            return "1 active session"
        return f"{count} active sessions"

    def _customize_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """Customize session list response structure."""
        response["data"]["sessions"] = self.sessions
        response["data"]["count"] = len(self.sessions)
        return response
