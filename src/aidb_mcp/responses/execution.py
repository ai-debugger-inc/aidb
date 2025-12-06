"""Execution-related response classes for MCP tools.

This module provides response classes for execution control operations including:
- ExecuteResponse: For run/continue operations
- StepResponse: For step over/into/out operations
- RunUntilResponse: For running to a specific location

All responses include execution state, code snapshots, and context-aware next steps.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from aidb.dap.client.constants import StopReason as DAPStopReason

from ..core.constants import DetailedExecutionStatus, ResponseFieldName, StopReason
from .base import Response
from .builders import CodeSnapshotBuilder, ExecutionStateBuilder
from .next_steps import (
    PAUSED_AT_BREAKPOINT_NEXT_STEPS,
    PAUSED_AT_EXCEPTION_NEXT_STEPS,
    PROGRAM_COMPLETED_NEXT_STEPS,
    STEP_COMPLETED_NEXT_STEPS,
)

if TYPE_CHECKING:
    from aidb.common.code_context import CodeContextResult


@dataclass
class ExecuteResponse(Response):
    """Response for execution operations (run/continue).

    Provides execution state information when a program is run or continued, including
    stop location, reason, and code context. Automatically infers detailed execution
    status and provides context-aware next steps.
    """

    action: str = ""  # "run", "continue", "jump"
    stopped: bool = False
    terminated: bool = False
    location: str | None = None
    stop_reason: str | None = None
    session_id: str | None = None
    code_context: CodeContextResult | None = None
    has_breakpoints: bool = False
    detailed_status: str | None = None
    program_output: list[dict[str, Any]] | None = None  # Logpoint/stdout/stderr output

    def _generate_summary(self) -> str:
        if self.terminated:
            return "Program execution completed"
        if self.stopped:
            base_message = ""
            if self.stop_reason == DAPStopReason.BREAKPOINT.value:
                location_text = f": {self.location}" if self.location else ""
                base_message = f"Stopped at breakpoint{location_text}"
            elif self.stop_reason == DAPStopReason.EXCEPTION.value:
                location_text = f" at {self.location}" if self.location else ""
                base_message = f"Exception occurred{location_text}"
            elif self.stop_reason == DAPStopReason.STEP.value:
                base_message = (
                    f"Stepped to {self.location}" if self.location else "Step completed"
                )
            else:
                base_message = (
                    f"Execution paused{f' at {self.location}' if self.location else ''}"
                )

            # Add code context if available
            if self.code_context and self.code_context[ResponseFieldName.FORMATTED]:
                formatted = self.code_context[ResponseFieldName.FORMATTED]
                return f"{base_message}\n\n{formatted}"
            return base_message
        return f"Execution {self.action} started"

    def get_next_steps(self):
        """Get next steps based on execution state."""
        if self.terminated:
            return PROGRAM_COMPLETED_NEXT_STEPS
        if self.stopped:
            if self.stop_reason == DAPStopReason.EXCEPTION.value:
                return PAUSED_AT_EXCEPTION_NEXT_STEPS
            return PAUSED_AT_BREAKPOINT_NEXT_STEPS
        return None

    def _infer_detailed_status(self) -> DetailedExecutionStatus:
        """Infer detailed execution status from current state.

        Returns
        -------
        DetailedExecutionStatus
            The inferred detailed status
        """
        if self.terminated:
            return DetailedExecutionStatus.TERMINATED
        if self.stopped:
            # Map stop reason to detailed status
            if self.stop_reason == DAPStopReason.BREAKPOINT.value:
                return DetailedExecutionStatus.STOPPED_AT_BREAKPOINT
            if self.stop_reason == DAPStopReason.EXCEPTION.value:
                return DetailedExecutionStatus.STOPPED_AT_EXCEPTION
            if self.stop_reason == DAPStopReason.STEP.value:
                return DetailedExecutionStatus.STOPPED_AFTER_STEP
            return DetailedExecutionStatus.PAUSED
        # Assume running if not stopped or terminated
        return DetailedExecutionStatus.RUNNING

    def _customize_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """Customize execute response with execution state and code context."""
        # Determine detailed status
        detailed_status = (
            DetailedExecutionStatus(self.detailed_status)
            if self.detailed_status
            else self._infer_detailed_status()
        )

        # Build execution state using builder
        response["data"][ResponseFieldName.EXECUTION_STATE] = (
            ExecutionStateBuilder.build(
                detailed_status=detailed_status,
                location=self.location,
                has_breakpoints=self.has_breakpoints,
                stop_reason=self.stop_reason,
            )
        )

        # Build code snapshot using builder
        code_snapshot = CodeSnapshotBuilder.build(
            code_context=self.code_context,
            location=self.location,
        )
        if code_snapshot:
            response["data"][ResponseFieldName.CODE_SNAPSHOT] = code_snapshot

        # Add program output if present (logpoints, stdout, stderr)
        if self.program_output:
            response["data"]["output"] = self.program_output

        return response


@dataclass
class StepResponse(Response):
    """Response for step operations."""

    action: str = ""  # "over", "into", "out"
    location: str | None = None
    stopped: bool = True
    stop_reason: str = "step"
    frame_info: dict[str, Any] | None = None
    session_id: str | None = None
    code_context: CodeContextResult | None = None
    has_breakpoints: bool = False
    detailed_status: str | None = None

    def _generate_summary(self) -> str:
        action_display = self.action.replace("_", " ")
        if self.location:
            base_message = f"Stepped {action_display} to {self.location}"
        else:
            base_message = f"Step {action_display} completed"

        # Add code context if available
        if self.code_context and self.code_context[ResponseFieldName.FORMATTED]:
            return f"{base_message}\n\n{self.code_context[ResponseFieldName.FORMATTED]}"
        return base_message

    def get_next_steps(self):
        """Get next steps after stepping."""
        return STEP_COMPLETED_NEXT_STEPS

    def _customize_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """Customize step response with execution state and frame information."""
        if self.frame_info:
            response["data"]["frame"] = self.frame_info

        # Determine detailed status
        # (step operations typically result in STOPPED_AFTER_STEP)
        detailed_status = (
            DetailedExecutionStatus(self.detailed_status)
            if self.detailed_status
            else DetailedExecutionStatus.STOPPED_AFTER_STEP
        )

        # Build execution state using builder
        response["data"][ResponseFieldName.EXECUTION_STATE] = (
            ExecutionStateBuilder.build(
                detailed_status=detailed_status,
                location=self.location,
                has_breakpoints=self.has_breakpoints,
                stop_reason=self.stop_reason,
            )
        )

        # Build code snapshot using builder
        code_snapshot = CodeSnapshotBuilder.build(
            code_context=self.code_context,
            location=self.location,
        )
        if code_snapshot:
            response["data"][ResponseFieldName.CODE_SNAPSHOT] = code_snapshot

        return response


@dataclass
class RunUntilResponse(Response):
    """Response for run_until operation."""

    target_location: str = ""
    reached_target: bool = True
    actual_location: str | None = None
    stop_reason: str | None = None
    session_id: str | None = None
    code_context: CodeContextResult | None = None
    has_breakpoints: bool = False
    detailed_status: str | None = None

    def _generate_summary(self) -> str:
        if self.reached_target:
            return f"Paused at {self.actual_location or self.target_location}"
        if self.stop_reason == StopReason.COMPLETED:
            return "Program completed without reaching target location"
        if self.stop_reason:
            return f"Stopped before target: {self.stop_reason}"
        return "Did not reach target location"

    def get_next_steps(self):
        """Get next steps based on continue result."""
        if self.reached_target:
            return PAUSED_AT_BREAKPOINT_NEXT_STEPS
        if self.stop_reason == StopReason.COMPLETED:
            return PROGRAM_COMPLETED_NEXT_STEPS
        return None

    def _infer_detailed_status(self) -> DetailedExecutionStatus:
        """Infer detailed execution status from current state.

        Returns
        -------
        DetailedExecutionStatus
            The inferred detailed status
        """
        if self.reached_target:
            return DetailedExecutionStatus.PAUSED
        if self.stop_reason == StopReason.COMPLETED:
            return DetailedExecutionStatus.TERMINATED
        return DetailedExecutionStatus.UNKNOWN

    def _customize_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """Customize run_until response with location details and execution state."""
        response["data"][ResponseFieldName.REACHED_TARGET] = self.reached_target

        if self.actual_location:
            response["data"][ResponseFieldName.CURRENT_LOCATION] = self.actual_location

        if self.stop_reason:
            response["data"][ResponseFieldName.STOP_REASON] = self.stop_reason

        # Determine detailed status
        detailed_status = (
            DetailedExecutionStatus(self.detailed_status)
            if self.detailed_status
            else self._infer_detailed_status()
        )

        # Build execution state using builder
        response["data"]["execution_state"] = ExecutionStateBuilder.build(
            detailed_status=detailed_status,
            location=self.actual_location,
            has_breakpoints=self.has_breakpoints,
            stop_reason=self.stop_reason,
        )

        # Build code snapshot using builder
        code_snapshot = CodeSnapshotBuilder.build(
            code_context=self.code_context,
            location=self.actual_location or self.target_location,
        )
        if code_snapshot:
            response["data"]["code_snapshot"] = code_snapshot

        return response
