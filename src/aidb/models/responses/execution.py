"""Execution-related response models."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..base import OperationResponse
from ..entities.session import ExecutionState, SessionStatus, StopReason

if TYPE_CHECKING:
    from aidb.dap.protocol.base import Response


@dataclass(frozen=True)
class AidbStopResponse(OperationResponse):
    """Response from stop operation."""

    stopped_session: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ExecutionStateResponse(OperationResponse):
    """Response from orchestration operations that return execution state.

    Used for step, continue, and status operations. Contains execution state information
    after event-driven orchestration that waits for DAP events to avoid race conditions
    with process termination.
    """

    execution_state: ExecutionState | None = None

    @classmethod
    def from_dap(cls, dap_response: "Response") -> "ExecutionStateResponse":
        """Create ExecutionStateResponse from DAP execution control response.

        This consolidates the mapper logic directly into the model.

        Parameters
        ----------
        dap_response : Response
            The DAP execution response to convert

        Returns
        -------
        ExecutionStateResponse
            The converted execution state response
        """
        from aidb.dap.protocol.responses import (
            ContinueResponse,
            GotoResponse,
            NextResponse,
            PauseResponse,
            StepInResponse,
            StepOutResponse,
        )

        # Determine execution state based on response type
        if isinstance(dap_response, PauseResponse):
            status = SessionStatus.PAUSED
            running = False
            paused = True
            stop_reason = StopReason.PAUSE
        elif isinstance(
            dap_response,
            ContinueResponse
            | GotoResponse
            | NextResponse
            | StepInResponse
            | StepOutResponse,
        ):
            # These indicate the debugger is running
            status = SessionStatus.RUNNING
            running = True
            paused = False
            stop_reason = None
        else:
            # Default state
            status = SessionStatus.RUNNING
            running = True
            paused = False
            stop_reason = None

        execution_state = ExecutionState(
            status=status,
            running=running,
            paused=paused,
            stop_reason=stop_reason,
            terminated=False,
        )

        # Extract base fields
        success = dap_response.success
        message = dap_response.message if hasattr(dap_response, "message") else None
        error_code = None
        if not success and hasattr(dap_response, "body"):
            body = dap_response.body
            if body and hasattr(body, "error"):
                error_code = (
                    body.error.get("id") if isinstance(body.error, dict) else None
                )

        return cls(
            execution_state=execution_state,
            success=success,
            message=message,
            error_code=error_code,
        )
