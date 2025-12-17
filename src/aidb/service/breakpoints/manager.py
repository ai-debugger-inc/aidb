"""Breakpoint management service operations."""

from typing import TYPE_CHECKING

from aidb.dap.protocol.bodies import (
    DataBreakpointInfoArguments,
    SetBreakpointsArguments,
    SetDataBreakpointsArguments,
    SetFunctionBreakpointsArguments,
)
from aidb.dap.protocol.requests import (
    DataBreakpointInfoRequest,
    SetBreakpointsRequest,
    SetDataBreakpointsRequest,
    SetExceptionBreakpointsRequest,
    SetFunctionBreakpointsRequest,
)
from aidb.dap.protocol.responses import (
    DataBreakpointInfoResponse,
    SetBreakpointsResponse,
    SetDataBreakpointsResponse,
    SetExceptionBreakpointsResponse,
    SetFunctionBreakpointsResponse,
)
from aidb.dap.protocol.types import Source, SourceBreakpoint
from aidb.models import (
    AidbBreakpointsResponse,
    AidbDataBreakpointInfoResponse,
    AidbDataBreakpointsResponse,
    AidbExceptionBreakpointsResponse,
    AidbFunctionBreakpointsResponse,
)
from aidb.models.entities.breakpoint import HitConditionMode
from aidb_common.discovery.adapters import (
    get_supported_hit_conditions,
    supports_hit_condition,
)
from aidb_common.path import normalize_path

from ..base import BaseServiceComponent

if TYPE_CHECKING:
    from aidb.interfaces import IContext
    from aidb.session import Session


class BreakpointService(BaseServiceComponent):
    """Breakpoint management service operations.

    Provides methods for setting, removing, and managing breakpoints of all types:
    source breakpoints, function breakpoints, data breakpoints, and exception
    breakpoints.
    """

    def __init__(self, session: "Session", ctx: "IContext | None" = None) -> None:
        """Initialize breakpoint service.

        Parameters
        ----------
        session : Session
            Debug session instance
        ctx : IContext, optional
            Application context
        """
        super().__init__(session, ctx)

    def _validate_breakpoint_lines(
        self,
        request: SetBreakpointsRequest,
    ) -> dict[int, int]:
        """Validate breakpoint line numbers and track invalid ones.

        Parameters
        ----------
        request : SetBreakpointsRequest
            DAP request containing breakpoints to validate

        Returns
        -------
        dict[int, int]
            Maps breakpoint index to requested line number for invalid lines
        """
        requested_lines: dict[int, int] = {}
        if not (
            request.arguments
            and request.arguments.source
            and request.arguments.breakpoints
        ):
            return requested_lines

        source_path = request.arguments.source.path
        if not source_path:
            return requested_lines

        try:
            from pathlib import Path

            file_path = Path(source_path)
            if not (file_path.exists() and file_path.is_file()):
                return requested_lines

            with file_path.open(encoding="utf-8", errors="ignore") as f:  # noqa: ASYNC230
                line_count = sum(1 for _ in f)

            for idx, bp in enumerate(request.arguments.breakpoints):
                if bp.line < 1 or bp.line > line_count:
                    requested_lines[idx] = bp.line
                    self.ctx.warning(
                        f"Breakpoint line {bp.line} is out of range "
                        f"(file has {line_count} lines): {source_path}",
                    )
        except Exception as e:
            self.ctx.debug(f"Failed to validate breakpoint line numbers: {e}")

        return requested_lines

    async def set(  # noqa: C901
        self,
        request: SetBreakpointsRequest,
    ) -> AidbBreakpointsResponse:
        """Set breakpoints using DAP protocol request.

        Parameters
        ----------
        request : SetBreakpointsRequest
            DAP request containing source file and breakpoint specifications

        Returns
        -------
        AidbBreakpointsResponse
            Response containing successfully set breakpoints

        Raises
        ------
        ValueError
            If a hit condition is not supported by the adapter
        """
        # Validate hit conditions if adapter config is available
        if hasattr(self.session, "adapter_config") and request.arguments:
            config = self.session.adapter_config
            if request.arguments.breakpoints:
                for bp in request.arguments.breakpoints:
                    if bp.hitCondition and not config.supports_hit_condition(
                        bp.hitCondition,
                    ):
                        try:
                            mode, _ = HitConditionMode.parse(bp.hitCondition)
                            supported = [
                                m.name for m in config.supported_hit_conditions
                            ]
                            msg = (
                                f"Hit condition '{bp.hitCondition}' "
                                f"(mode: {mode.name}) not supported by "
                                f"{config.language} adapter. "
                                f"Supported modes: {', '.join(supported)}"
                            )
                            raise ValueError(msg)
                        except ValueError as e:
                            if "Invalid hit condition format" in str(e):
                                msg = (
                                    f"Invalid hit condition format: "
                                    f"'{bp.hitCondition}'. "
                                    f"Valid formats: '5', '%5', '>5', '>=5', '<5', "
                                    f"'<=5', '==5'"
                                )
                                raise ValueError(msg) from e
                            raise

        requested_lines = self._validate_breakpoint_lines(request)

        breakpoints_response = await self._send_and_ensure(
            request,
            SetBreakpointsResponse,
        )

        # Fix debugpy quirk: mark invalid breakpoints as unverified
        if (
            requested_lines
            and breakpoints_response.body
            and breakpoints_response.body.breakpoints
        ):
            for idx, bp in enumerate(breakpoints_response.body.breakpoints):
                if idx in requested_lines:
                    requested_line = requested_lines[idx]
                    bp.verified = False
                    if not bp.message:
                        bp.message = f"Line {requested_line} is out of range"

        if breakpoints_response.body and breakpoints_response.body.breakpoints:
            for bp in breakpoints_response.body.breakpoints:
                if not bp.verified:
                    line = bp.line if bp.line else "unknown"
                    msg = bp.message or "not an executable line"
                    self.ctx.warning(
                        f"Breakpoint at line {line} could not be verified: {msg}",
                    )

        mapped = AidbBreakpointsResponse.from_dap(breakpoints_response, request)

        # Update session-scoped breakpoint store
        source_path = (
            request.arguments.source.path
            if request.arguments and request.arguments.source
            else None
        )
        try:
            breakpoint_list = list(mapped.breakpoints.values())
            if source_path:
                await self.session._update_breakpoints_from_response(
                    source_path,
                    breakpoint_list,
                )
        except Exception as e:
            self.ctx.error(f"Failed to update breakpoint store: {e}", exc_info=True)

        return mapped

    async def clear(
        self,
        source_path: str | None = None,
        clear_all: bool = False,
    ) -> AidbBreakpointsResponse:
        """Clear breakpoints for a specific source file or all files.

        Parameters
        ----------
        source_path : str, optional
            Path to the source file to clear breakpoints from
        clear_all : bool, optional
            If True, clear all breakpoints from all files

        Returns
        -------
        AidbBreakpointsResponse
            Response confirming breakpoints have been cleared
        """
        if clear_all is True:
            source_files = set()
            if hasattr(self.session, "_breakpoint_store"):
                for _bp_id, bp in self.session._breakpoint_store.items():
                    if bp.source_path:
                        source_files.add(bp.source_path)

            for source_file in source_files:
                source = Source(path=source_file)
                args = SetBreakpointsArguments(source=source, breakpoints=[])
                request = SetBreakpointsRequest(seq=0, arguments=args)
                await self._send_and_ensure(request, SetBreakpointsResponse)

            if hasattr(self.session, "_breakpoint_store"):
                self.session._breakpoint_store.clear()

            return AidbBreakpointsResponse()

        if source_path:
            source = Source(path=source_path)
            args = SetBreakpointsArguments(source=source, breakpoints=[])
            request = SetBreakpointsRequest(seq=0, arguments=args)
            breakpoints_response = await self._send_and_ensure(
                request,
                SetBreakpointsResponse,
            )
            mapped = AidbBreakpointsResponse.from_dap(breakpoints_response)

            try:
                self.session._clear_breakpoints_for_source(source_path)
            except Exception as e:
                self.ctx.debug(f"Failed to clear breakpoint store: {e}")

            return mapped

        msg = "Either source_path or clear_all=True must be specified"
        raise ValueError(msg)

    async def remove(
        self,
        source_path: str,
        line: int,
    ) -> AidbBreakpointsResponse:
        """Remove a single breakpoint from a source file.

        Parameters
        ----------
        source_path : str
            Path to the source file containing the breakpoint
        line : int
            Line number of the breakpoint to remove

        Returns
        -------
        AidbBreakpointsResponse
            Response containing the updated list of breakpoints
        """
        self.ctx.debug(
            f"remove: Removing breakpoint at {source_path}:{line}",
        )

        normalized_path = normalize_path(source_path)
        remaining_breakpoints = []

        if hasattr(self.session, "_breakpoint_store"):
            for _bp_id, bp in self.session._breakpoint_store.items():
                if (
                    normalize_path(bp.source_path) == normalized_path
                    and bp.line != line
                ):
                    source_bp = SourceBreakpoint(line=bp.line)
                    if bp.condition:
                        source_bp.condition = bp.condition
                    if bp.hit_condition:
                        source_bp.hitCondition = bp.hit_condition
                    if bp.log_message:
                        source_bp.logMessage = bp.log_message
                    remaining_breakpoints.append(source_bp)

        source = Source(path=source_path)
        args = SetBreakpointsArguments(
            source=source,
            breakpoints=remaining_breakpoints,
        )
        request = SetBreakpointsRequest(seq=0, arguments=args)

        breakpoints_response = await self._send_and_ensure(
            request,
            SetBreakpointsResponse,
        )
        mapped = AidbBreakpointsResponse.from_dap(breakpoints_response, request)

        try:
            breakpoint_list = list(mapped.breakpoints.values())
            await self.session._update_breakpoints_from_response(
                source_path,
                breakpoint_list,
            )
        except Exception as e:
            self.ctx.error(f"Failed to update breakpoint store: {e}", exc_info=True)

        return mapped

    async def list_all(self) -> AidbBreakpointsResponse:
        """List all current breakpoints.

        Returns
        -------
        AidbBreakpointsResponse
            Response containing all current breakpoints
        """
        breakpoints = {}
        if hasattr(self.session, "_breakpoint_store"):
            for bp_id, bp in self.session._breakpoint_store.items():
                breakpoints[bp_id] = bp

        return AidbBreakpointsResponse(breakpoints=breakpoints)

    async def set_logpoints(
        self,
        source_path: str,
        logpoints: list[SourceBreakpoint],
    ) -> AidbBreakpointsResponse:
        """Set logpoints for debugging without stopping execution.

        Parameters
        ----------
        source_path : str
            Path to the source file
        logpoints : list[SourceBreakpoint]
            List of logpoint specifications

        Returns
        -------
        AidbBreakpointsResponse
            Response containing successfully set logpoints
        """
        if not self.session.supports_logpoints():
            msg = f"Logpoints not supported by {self.session.language} adapter"
            raise NotImplementedError(msg)

        source = Source(path=source_path)
        source_breakpoints = [
            SourceBreakpoint(
                line=lp.line,
                logMessage=lp.logMessage,
                condition=lp.condition,
                hitCondition=lp.hitCondition,
            )
            for lp in logpoints
        ]
        args = SetBreakpointsArguments(source=source, breakpoints=source_breakpoints)
        request = SetBreakpointsRequest(seq=0, arguments=args)

        breakpoints_response = await self._send_and_ensure(
            request,
            SetBreakpointsResponse,
        )
        mapped = AidbBreakpointsResponse.from_dap(breakpoints_response, request)

        try:
            breakpoint_list = list(mapped.breakpoints.values())
            await self.session._update_breakpoints_from_response(
                source_path,
                breakpoint_list,
            )
        except Exception as e:
            self.ctx.debug(f"Failed to update logpoint store: {e}")

        return mapped

    async def set_data(
        self,
        request: SetDataBreakpointsRequest,
    ) -> AidbDataBreakpointsResponse:
        """Set data breakpoints (watchpoints) on memory locations.

        Parameters
        ----------
        request : SetDataBreakpointsRequest
            DAP request for setting data breakpoints

        Returns
        -------
        AidbDataBreakpointsResponse
            Response containing data breakpoint status
        """
        data_response = await self._send_and_ensure(request, SetDataBreakpointsResponse)
        return AidbDataBreakpointsResponse.from_dap(data_response)

    async def set_exception(
        self,
        request: SetExceptionBreakpointsRequest,
    ) -> AidbExceptionBreakpointsResponse:
        """Configure exception breakpoints.

        Parameters
        ----------
        request : SetExceptionBreakpointsRequest
            DAP request for configuring exception breakpoints

        Returns
        -------
        AidbExceptionBreakpointsResponse
            Response confirming exception breakpoint configuration
        """
        exception_response = await self._send_and_ensure(
            request,
            SetExceptionBreakpointsResponse,
        )
        return AidbExceptionBreakpointsResponse.from_dap(exception_response)

    async def set_function(
        self,
        request: SetFunctionBreakpointsRequest,
    ) -> AidbFunctionBreakpointsResponse:
        """Set function breakpoints.

        Parameters
        ----------
        request : SetFunctionBreakpointsRequest
            DAP request for setting function breakpoints

        Returns
        -------
        AidbFunctionBreakpointsResponse
            Response containing function breakpoint status
        """
        func_response = await self._send_and_ensure(
            request,
            SetFunctionBreakpointsResponse,
        )
        return AidbFunctionBreakpointsResponse.from_dap(func_response)

    async def get_data_info(
        self,
        variable_reference: int,
        name: str,
    ) -> AidbDataBreakpointInfoResponse:
        """Get information needed to set a data breakpoint.

        Parameters
        ----------
        variable_reference : int
            Reference to the variable
        name : str
            Name of the variable

        Returns
        -------
        AidbDataBreakpointInfoResponse
            Information about the data breakpoint
        """
        args = DataBreakpointInfoArguments(
            variablesReference=variable_reference,
            name=name,
        )
        request = DataBreakpointInfoRequest(
            seq=await self.session.dap.get_next_seq(),
            arguments=args,
        )
        info_response = await self._send_and_ensure(request, DataBreakpointInfoResponse)
        return AidbDataBreakpointInfoResponse.from_dap(info_response)

    async def clear_function(self) -> AidbFunctionBreakpointsResponse:
        """Clear all function breakpoints.

        Returns
        -------
        AidbFunctionBreakpointsResponse
            Response confirming function breakpoints were cleared
        """
        args = SetFunctionBreakpointsArguments(breakpoints=[])
        request = SetFunctionBreakpointsRequest(
            seq=await self.session.dap.get_next_seq(),
            arguments=args,
        )
        await self._send_and_ensure(request, SetFunctionBreakpointsResponse)
        return AidbFunctionBreakpointsResponse(
            success=True,
            message="Function breakpoints cleared",
        )

    async def clear_data(self) -> AidbDataBreakpointsResponse:
        """Clear all data breakpoints.

        Returns
        -------
        AidbDataBreakpointsResponse
            Response confirming data breakpoints were cleared
        """
        args = SetDataBreakpointsArguments(breakpoints=[])
        request = SetDataBreakpointsRequest(
            seq=await self.session.dap.get_next_seq(),
            arguments=args,
        )
        await self._send_and_ensure(request, SetDataBreakpointsResponse)
        return AidbDataBreakpointsResponse(
            success=True,
            message="Data breakpoints cleared",
        )

    def validate_hit_condition(
        self,
        hit_condition: str,
        language: str | None = None,
    ) -> tuple[bool, str | None]:
        """Validate a hit condition for the current or specified language.

        Hit conditions control when a breakpoint fires based on hit count.
        Different languages support different hit condition formats.

        Parameters
        ----------
        hit_condition : str
            The hit condition string to validate (e.g., ">5", "==3", "%10", "5")
        language : str, optional
            Language to validate against. If None, uses session's language.

        Returns
        -------
        tuple[bool, str | None]
            A tuple of (is_valid, error_message).
            On success: (True, None)
            On failure: (False, error_message)
        """
        # Get language from session if not provided
        if language is None:
            language = getattr(self.session, "language", "python")

        # First try to parse the hit condition
        try:
            mode, _ = HitConditionMode.parse(hit_condition)
        except ValueError as e:
            return (False, f"Invalid hit condition format: {e}")

        # Check if the language supports this hit condition
        if not supports_hit_condition(language, hit_condition):
            supported = get_supported_hit_conditions(language)
            return (
                False,
                f"The {language} adapter doesn't support {mode.name} hit conditions. "
                f"Supported: {', '.join(supported)}",
            )

        return (True, None)
