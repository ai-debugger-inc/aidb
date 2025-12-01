"""Breakpoint-related response models."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..base import OperationResponse
from ..entities.breakpoint import AidbBreakpoint, BreakpointState
from ..entities.stack import SourceLocation

if TYPE_CHECKING:
    from aidb.dap.protocol.responses import (
        DataBreakpointInfoResponse,
        SetBreakpointsResponse,
        SetDataBreakpointsResponse,
        SetExceptionBreakpointsResponse,
        SetFunctionBreakpointsResponse,
    )


@dataclass
class AidbDataBreakpointsResponse:
    """Response model for data breakpoints (watchpoints).

    Attributes
    ----------
    breakpoints : Dict[int, AidbBreakpoint]
        Dictionary mapping breakpoint IDs to data breakpoints
    success : bool
        Whether the request was successful
    message : Optional[str]
        Error or status message
    """

    breakpoints: dict[int, AidbBreakpoint] = field(default_factory=dict)
    success: bool = True
    message: str | None = None

    @classmethod
    def from_dap(
        cls,
        dap_response: "SetDataBreakpointsResponse",
    ) -> "AidbDataBreakpointsResponse":
        """Create from DAP SetDataBreakpointsResponse.

        Parameters
        ----------
        dap_response : SetDataBreakpointsResponse
            The DAP response to convert

        Returns
        -------
        AidbDataBreakpointsResponse
            The converted response
        """
        breakpoints: dict[int, AidbBreakpoint] = {}
        if dap_response.body and dap_response.body.breakpoints:
            for idx, dap_bp in enumerate(dap_response.body.breakpoints):
                # Data breakpoints might not have an ID from DAP, use index
                bp_id = getattr(dap_bp, "id", idx)
                bp = AidbBreakpoint(
                    id=bp_id,
                    source_path="",  # Data breakpoints don't have a source path
                    line=0,  # Data breakpoints don't have a line
                    verified=getattr(dap_bp, "verified", True),
                    state=(
                        BreakpointState.VERIFIED
                        if getattr(dap_bp, "verified", True)
                        else BreakpointState.PENDING
                    ),
                    condition="",
                    hit_condition="",
                    log_message="",
                    message=getattr(dap_bp, "message", ""),
                    column=0,
                    # Store original data breakpoint info in message
                    data_id=getattr(dap_bp, "dataId", ""),
                    access_type=getattr(dap_bp, "accessType", ""),
                )
                breakpoints[bp_id] = bp

        return cls(
            breakpoints=breakpoints,
            success=dap_response.success,
            message=dap_response.message if not dap_response.success else None,
        )


@dataclass
class AidbExceptionBreakpointsResponse:
    """Response model for exception breakpoints.

    Attributes
    ----------
    breakpoints : Dict[int, AidbBreakpoint]
        Dictionary mapping breakpoint IDs to exception breakpoints
    success : bool
        Whether the request was successful
    message : Optional[str]
        Status or error message
    """

    breakpoints: dict[int, AidbBreakpoint] = field(default_factory=dict)
    success: bool = True
    message: str | None = None

    @classmethod
    def from_dap(
        cls,
        dap_response: "SetExceptionBreakpointsResponse",
    ) -> "AidbExceptionBreakpointsResponse":
        """Create from DAP SetExceptionBreakpointsResponse.

        Parameters
        ----------
        dap_response : SetExceptionBreakpointsResponse
            The DAP response to convert

        Returns
        -------
        AidbExceptionBreakpointsResponse
            The converted response
        """
        breakpoints: dict[int, AidbBreakpoint] = {}
        if dap_response.body and hasattr(dap_response.body, "breakpoints"):
            for idx, dap_bp in enumerate(dap_response.body.breakpoints or []):
                # Exception breakpoints might not have an ID from DAP, use index
                bp_id = getattr(dap_bp, "id", idx)
                bp = AidbBreakpoint(
                    id=bp_id,
                    source_path="",  # Exception breakpoints don't have a source path
                    line=0,  # Exception breakpoints don't have a line
                    verified=getattr(dap_bp, "verified", True),
                    state=(
                        BreakpointState.VERIFIED
                        if getattr(dap_bp, "verified", True)
                        else BreakpointState.PENDING
                    ),
                    condition=getattr(dap_bp, "condition", ""),
                    hit_condition="",
                    log_message="",
                    message=getattr(dap_bp, "message", ""),
                    column=0,
                )
                breakpoints[bp_id] = bp

        return cls(
            breakpoints=breakpoints,
            success=dap_response.success,
            message=dap_response.message if not dap_response.success else None,
        )


@dataclass
class AidbFunctionBreakpointsResponse:
    """Response model for function breakpoints.

    Attributes
    ----------
    breakpoints : Dict[int, AidbBreakpoint]
        Dictionary mapping breakpoint IDs to function breakpoints
    success : bool
        Whether the request was successful
    message : Optional[str]
        Error or status message
    """

    breakpoints: dict[int, AidbBreakpoint] = field(default_factory=dict)
    success: bool = True
    message: str | None = None

    @classmethod
    def from_dap(
        cls,
        dap_response: "SetFunctionBreakpointsResponse",
    ) -> "AidbFunctionBreakpointsResponse":
        """Create from DAP SetFunctionBreakpointsResponse.

        Parameters
        ----------
        dap_response : SetFunctionBreakpointsResponse
            The DAP response to convert

        Returns
        -------
        AidbFunctionBreakpointsResponse
            The converted response
        """
        breakpoints: dict[int, AidbBreakpoint] = {}
        if dap_response.body and dap_response.body.breakpoints:
            for dap_bp in dap_response.body.breakpoints:
                # Skip invalid breakpoints without an ID
                if not hasattr(dap_bp, "id") or dap_bp.id is None:
                    continue

                # Extract source location if available
                path = ""
                if hasattr(dap_bp, "source") and dap_bp.source:
                    if hasattr(dap_bp.source, "path"):
                        path = dap_bp.source.path or ""
                    elif hasattr(dap_bp.source, "name"):
                        path = dap_bp.source.name or ""

                line = (
                    dap_bp.line
                    if hasattr(dap_bp, "line") and dap_bp.line is not None
                    else 0
                )

                bp = AidbBreakpoint(
                    id=dap_bp.id,
                    source_path=path,
                    line=line,
                    verified=getattr(dap_bp, "verified", False),
                    state=(
                        BreakpointState.VERIFIED
                        if getattr(dap_bp, "verified", False)
                        else BreakpointState.PENDING
                    ),
                    condition=getattr(dap_bp, "condition", ""),
                    hit_condition=getattr(dap_bp, "hitCondition", ""),
                    log_message="",
                    message=getattr(dap_bp, "message", ""),
                    column=getattr(dap_bp, "column", 0),
                )
                breakpoints[dap_bp.id] = bp

        return cls(
            breakpoints=breakpoints,
            success=dap_response.success,
            message=dap_response.message if not dap_response.success else None,
        )


@dataclass
class AidbDataBreakpointInfoResponse:
    """Response model for data breakpoint info requests.

    Attributes
    ----------
    dataId : Optional[str]
        An identifier for the data breakpoint that can be used in setDataBreakpoints
    description : str
        A human-readable description of the data breakpoint
    accessTypes : Optional[List[str]]
        Possible access types for the data breakpoint (e.g., 'read', 'write')
    canPersist : Optional[bool]
        Whether this data breakpoint can be persisted across debug sessions
    success : bool
        Whether the request was successful
    message : Optional[str]
        Error message if the request failed
    """

    dataId: str | None = None
    description: str = ""
    accessTypes: list[str] | None = None
    canPersist: bool | None = None
    success: bool = True
    message: str | None = None

    @classmethod
    def from_dap(
        cls,
        dap_response: "DataBreakpointInfoResponse",
    ) -> "AidbDataBreakpointInfoResponse":
        """Create from DAP DataBreakpointInfoResponse.

        Parameters
        ----------
        dap_response : DataBreakpointInfoResponse
            The DAP response to convert

        Returns
        -------
        AidbDataBreakpointInfoResponse
            The converted response
        """
        if dap_response.body:
            access_types = None
            if dap_response.body.accessTypes:
                access_types = [str(at) for at in dap_response.body.accessTypes]

            return cls(
                dataId=dap_response.body.dataId,
                description=dap_response.body.description,
                accessTypes=access_types,
                canPersist=dap_response.body.canPersist,
                success=dap_response.success,
                message=dap_response.message if not dap_response.success else None,
            )
        return cls(
            success=dap_response.success,
            message=dap_response.message if not dap_response.success else None,
        )


@dataclass
class AidbBreakpointsResponse:
    """Response model for breakpoint operations.

    This model consolidates the mapper logic for converting DAP breakpoint responses to
    domain models.
    """

    breakpoints: dict[int, AidbBreakpoint] = field(default_factory=dict)
    success: bool = True
    message: str | None = None
    timestamp: float | None = None
    error_code: str | None = None

    @classmethod
    def from_dap(
        cls,
        dap_response: "SetBreakpointsResponse",
    ) -> "AidbBreakpointsResponse":
        """Create AidbBreakpointsResponse from DAP SetBreakpointsResponse.

        This consolidates the mapper logic directly into the model.

        Parameters
        ----------
        dap_response : SetBreakpointsResponse
            The DAP breakpoints response to convert

        Returns
        -------
        AidbBreakpointsResponse
            The converted breakpoints response
        """
        breakpoints: dict[int, AidbBreakpoint] = {}

        # Extract breakpoints from DAP response
        if dap_response.body and dap_response.body.breakpoints:
            for dap_bp in dap_response.body.breakpoints:
                # Skip invalid breakpoints without an ID
                if not hasattr(dap_bp, "id") or dap_bp.id is None:
                    continue

                # Extract source location
                path = ""
                if hasattr(dap_bp, "source") and dap_bp.source:
                    if hasattr(dap_bp.source, "path"):
                        path = dap_bp.source.path or ""
                    elif hasattr(dap_bp.source, "name"):
                        path = dap_bp.source.name or ""

                line = (
                    dap_bp.line
                    if hasattr(dap_bp, "line") and dap_bp.line is not None
                    else 0
                )
                column = dap_bp.column if hasattr(dap_bp, "column") else 0

                source_location = SourceLocation(
                    path=path,
                    line=line,
                    column=column,
                )

                # Determine breakpoint state
                state = BreakpointState.PENDING
                if hasattr(dap_bp, "verified"):
                    if dap_bp.verified:
                        state = BreakpointState.VERIFIED
                    else:
                        state = BreakpointState.PENDING

                # Create breakpoint
                bp = AidbBreakpoint(
                    id=dap_bp.id,
                    source_path=source_location.path,
                    line=line,
                    verified=dap_bp.verified if hasattr(dap_bp, "verified") else False,
                    state=state,
                    condition=getattr(dap_bp, "condition", None) or "",
                    hit_condition=getattr(dap_bp, "hitCondition", None) or "",
                    log_message=getattr(dap_bp, "logMessage", None) or "",
                    message=getattr(dap_bp, "message", None) or "",
                    column=getattr(dap_bp, "column", 0),
                )

                breakpoints[bp.id] = bp

        success, message, error_code = OperationResponse.extract_response_fields(
            dap_response,
        )

        return cls(
            breakpoints=breakpoints,
            success=success,
            message=message,
            error_code=error_code,
        )
