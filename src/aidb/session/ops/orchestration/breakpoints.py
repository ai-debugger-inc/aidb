"""AidbBreakpoint orchestration operations."""

from typing import TYPE_CHECKING, Optional, cast

from aidb.dap.protocol.requests import (
    DataBreakpointInfoRequest,
    SetBreakpointsRequest,
    SetDataBreakpointsRequest,
    SetExceptionBreakpointsRequest,
    SetFunctionBreakpointsRequest,
)
from aidb.dap.protocol.types import SourceBreakpoint
from aidb.models import (
    AidbBreakpointsResponse,
    AidbDataBreakpointInfoResponse,
    AidbDataBreakpointsResponse,
    AidbExceptionBreakpointsResponse,
    AidbFunctionBreakpointsResponse,
)

from ..base import SessionOperationsMixin

if TYPE_CHECKING:
    from aidb.dap.protocol.base import Response
    from aidb.dap.protocol.responses import (
        DataBreakpointInfoResponse,
        SetBreakpointsResponse,
        SetDataBreakpointsResponse,
        SetExceptionBreakpointsResponse,
        SetFunctionBreakpointsResponse,
    )
    from aidb.interfaces import IContext
    from aidb.session import Session


class BreakpointOperations(SessionOperationsMixin):
    """AidbBreakpoint orchestration operations."""

    def __init__(self, session: "Session", ctx: Optional["IContext"] = None) -> None:
        """Initialize breakpoint operations.

        Parameters
        ----------
        session : Session
            Debug session instance
        ctx : AidbContext, optional
            Application context, by default `None`
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

            # Read file and count lines
            with file_path.open(encoding="utf-8", errors="ignore") as f:  # noqa: ASYNC230
                line_count = sum(1 for _ in f)

            # Track invalid line numbers
            for idx, bp in enumerate(request.arguments.breakpoints):
                if bp.line < 1 or bp.line > line_count:
                    # Debugpy adjusts invalid lines - track for correction
                    requested_lines[idx] = bp.line
                    self.ctx.warning(
                        f"Breakpoint line {bp.line} is out of range "
                        f"(file has {line_count} lines): {source_path}",
                    )
        except Exception as e:
            # Non-fatal: validation failure shouldn't break breakpoint setting
            self.ctx.debug(f"Failed to validate breakpoint line numbers: {e}")

        return requested_lines

    async def breakpoint(  # noqa: C901
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
            Response containing successfully set breakpoints with their IDs and
            states

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
                        from aidb.models.entities.breakpoint import HitConditionMode

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
                            raise ValueError(
                                msg,
                            )
                        except ValueError as e:
                            if "Invalid hit condition format" in str(e):
                                msg = (
                                    f"Invalid hit condition format: "
                                    f"'{bp.hitCondition}'. "
                                    f"Valid formats: '5', '%5', '>5', '>=5', '<5', "
                                    f"'<=5', '==5'"
                                )
                                raise ValueError(
                                    msg,
                                ) from e
                            raise

        # Validate line numbers and track invalid ones for correction
        requested_lines = self._validate_breakpoint_lines(request)

        response: Response = await self.session.dap.send_request(request)
        response.ensure_success()
        # Cast to the expected response type
        breakpoints_response = cast("SetBreakpointsResponse", response)

        # Fix debugpy quirk: mark invalid breakpoints as unverified
        # Debugpy adjusts invalid line numbers to valid ones but marks them as verified
        if (
            requested_lines
            and breakpoints_response.body
            and breakpoints_response.body.breakpoints
        ):
            for idx, bp in enumerate(breakpoints_response.body.breakpoints):
                # If this breakpoint index corresponds to an invalid requested line
                if idx in requested_lines:
                    requested_line = requested_lines[idx]
                    bp.verified = False
                    if not bp.message:
                        bp.message = f"Line {requested_line} is out of range"

        # Log any unverified breakpoints for debugging
        if breakpoints_response.body and breakpoints_response.body.breakpoints:
            for bp in breakpoints_response.body.breakpoints:
                if not bp.verified:
                    line = bp.line if bp.line else "unknown"
                    msg = bp.message or "not an executable line"
                    self.ctx.warning(
                        f"Breakpoint at line {line} could not be verified: {msg}",
                    )

        # Pass original request to preserve optional fields (logMessage, etc.)
        mapped = AidbBreakpointsResponse.from_dap(breakpoints_response, request)
        # Update session-scoped breakpoint store for this source
        source_path = (
            request.arguments.source.path
            if request.arguments and request.arguments.source
            else None
        )
        try:
            # Extract the list of breakpoints from the response object
            breakpoint_list = list(mapped.breakpoints.values())
            if source_path:
                await self.session._update_breakpoints_from_response(
                    source_path,
                    breakpoint_list,
                )
        except Exception as e:
            # Non-fatal: mapping/store update should not break caller
            self.ctx.error(f"Failed to update breakpoint store: {e}", exc_info=True)
        return mapped

    async def clear_breakpoints(
        self,
        source_path: str | None = None,
        _clear_all: bool = False,
    ) -> AidbBreakpointsResponse:
        """Clear breakpoints for a specific source file or all files.

        Parameters
        ----------
        source_path : str, optional
            Path to the source file to clear breakpoints from.
            Required if all=False.
        all : bool, optional
            If True, clear all breakpoints from all files.
            Default is False.

        Returns
        -------
        AidbBreakpointsResponse
            Response confirming breakpoints have been cleared
        """
        from aidb.dap.protocol.bodies import SetBreakpointsArguments
        from aidb.dap.protocol.types import Source

        if _clear_all is True:
            # Clear all breakpoints from all source files
            source_files = set()
            if hasattr(self.session, "_breakpoint_store"):
                for _bp_id, bp in self.session._breakpoint_store.items():
                    if bp.source_path:
                        source_files.add(bp.source_path)

            # Clear breakpoints for each source file
            for source_file in source_files:
                source = Source(path=source_file)
                args = SetBreakpointsArguments(
                    source=source,
                    breakpoints=[],  # Empty list clears all breakpoints
                )
                request = SetBreakpointsRequest(seq=0, arguments=args)
                response: Response = await self.session.dap.send_request(request)
                response.ensure_success()

            # Clear the entire breakpoint store
            if hasattr(self.session, "_breakpoint_store"):
                self.session._breakpoint_store.clear()

            return AidbBreakpointsResponse()

        if source_path:
            # Original single-file clearing logic
            source = Source(path=source_path)
            args = SetBreakpointsArguments(
                source=source,
                breakpoints=[],  # Empty list clears all breakpoints
            )
            request = SetBreakpointsRequest(seq=0, arguments=args)
            clear_response: Response = await self.session.dap.send_request(request)
            clear_response.ensure_success()
            # Cast to the expected response type
            breakpoints_response = cast("SetBreakpointsResponse", clear_response)
            mapped = AidbBreakpointsResponse.from_dap(breakpoints_response)
            # Clear from session-scoped breakpoint store
            try:
                self.session._clear_breakpoints_for_source(source_path)
            except Exception as e:
                # Non-fatal: store update should not break caller
                self.ctx.debug(f"Failed to clear breakpoint store: {e}")
            return mapped

        msg = "Either source_path or clear_all=True must be specified"
        raise ValueError(msg)

    async def remove_breakpoint(
        self,
        source_path: str,
        line: int,
    ) -> AidbBreakpointsResponse:
        """Remove a single breakpoint from a source file.

        This method removes a specific breakpoint while preserving all others
        in the same file. It works by getting the current breakpoints, filtering
        out the one to remove, and setting the updated list.

        Parameters
        ----------
        source_path : str
            Path to the source file containing the breakpoint
        line : int
            Line number of the breakpoint to remove

        Returns
        -------
        AidbBreakpointsResponse
            Response containing the updated list of breakpoints for the file
        """
        from aidb_common.path import normalize_path

        self.ctx.debug(
            f"remove_breakpoint: Removing breakpoint at {source_path}:{line}",
        )

        # Get current breakpoints for this file
        normalized_path = normalize_path(source_path)
        remaining_breakpoints = []

        # Log current store state
        if hasattr(self.session, "_breakpoint_store"):
            bp_ids = list(self.session._breakpoint_store.keys())
            self.ctx.debug(
                f"remove_breakpoint: Store has {len(self.session._breakpoint_store)} "
                f"breakpoint(s) before removal: {bp_ids}",
            )
        else:
            self.ctx.warning("remove_breakpoint: Session has no _breakpoint_store!")

        # Collect all breakpoints except the one to remove
        if hasattr(self.session, "_breakpoint_store"):
            for _bp_id, bp in self.session._breakpoint_store.items():
                if (
                    normalize_path(bp.source_path) == normalized_path
                    and bp.line != line
                ):
                    # Keep this breakpoint
                    from aidb.dap.protocol.types import SourceBreakpoint

                    source_bp = SourceBreakpoint(line=bp.line)
                    if bp.condition:
                        source_bp.condition = bp.condition
                    if bp.hit_condition:
                        source_bp.hitCondition = bp.hit_condition
                    if bp.log_message:
                        source_bp.logMessage = bp.log_message
                    remaining_breakpoints.append(source_bp)

        self.ctx.debug(
            f"remove_breakpoint: Keeping {len(remaining_breakpoints)} breakpoint(s) "
            f"after filtering out {source_path}:{line}",
        )

        # Set the updated list of breakpoints
        from aidb.dap.protocol.bodies import SetBreakpointsArguments
        from aidb.dap.protocol.types import Source

        source = Source(path=source_path)
        args = SetBreakpointsArguments(
            source=source,
            breakpoints=remaining_breakpoints,
        )
        request = SetBreakpointsRequest(seq=0, arguments=args)

        self.ctx.debug(
            f"remove_breakpoint: Sending setBreakpoints request with "
            f"{len(remaining_breakpoints)} breakpoint(s)",
        )

        response: Response = await self.session.dap.send_request(request)
        response.ensure_success()

        # Cast to the expected response type
        breakpoints_response = cast("SetBreakpointsResponse", response)
        # Pass original request to preserve optional fields (logMessage, etc.)
        mapped = AidbBreakpointsResponse.from_dap(breakpoints_response, request)

        self.ctx.debug(
            f"remove_breakpoint: DAP response success, "
            f"returned {len(mapped.breakpoints)} breakpoint(s)",
        )

        # Update session-scoped breakpoint store
        try:
            breakpoint_list = list(mapped.breakpoints.values())
            bp_count = len(breakpoint_list)
            self.ctx.debug(
                f"remove_breakpoint: Updating store with {bp_count} breakpoint(s)",
            )
            await self.session._update_breakpoints_from_response(
                source_path,
                breakpoint_list,
            )
            self.ctx.debug(
                f"remove_breakpoint: Store update complete. "
                f"Store now has {len(self.session._breakpoint_store)} breakpoint(s)",
            )
        except Exception as e:
            # Non-fatal: store update should not break caller
            self.ctx.error(
                f"remove_breakpoint: Failed to update breakpoint store: {e}",
                exc_info=True,
            )

        return mapped

    async def set_logpoints(
        self,
        source_path: str,
        logpoints: list[SourceBreakpoint],
    ) -> AidbBreakpointsResponse:
        """Set logpoints for debugging without stopping execution.

        Logpoints are like breakpoints but instead of stopping execution, they
        log a message to the debug console. This is useful for tracing execution
        without interrupting the program flow.

        Parameters
        ----------
        source_path : str
            Path to the source file where logpoints should be set
        logpoints : List[SourceBreakpoint]
            List of logpoint specifications with line numbers and log messages

        Returns
        -------
        AidbBreakpointsResponse
            Response containing successfully set logpoints with their IDs

        Raises
        ------
        NotImplementedError
            If the debug adapter doesn't support logpoints
        """
        if not self.session.supports_logpoints():
            msg = f"Logpoints not supported by {self.session.language} adapter"
            raise NotImplementedError(
                msg,
            )

        # Create request with logMessage field set for each breakpoint
        from aidb.dap.protocol.bodies import SetBreakpointsArguments
        from aidb.dap.protocol.types import Source, SourceBreakpoint

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

        response: Response = await self.session.dap.send_request(request)
        response.ensure_success()

        # Cast to the expected response type
        breakpoints_response = cast("SetBreakpointsResponse", response)
        # Pass original request to preserve logMessage (DAP doesn't echo it back)
        mapped = AidbBreakpointsResponse.from_dap(breakpoints_response, request)

        # Update session-scoped breakpoint store
        try:
            # Extract the list of breakpoints from the response object
            breakpoint_list = list(mapped.breakpoints.values())
            await self.session._update_breakpoints_from_response(
                source_path,
                breakpoint_list,
            )
        except Exception as e:
            # Non-fatal: store update should not break caller
            self.ctx.debug(f"Failed to update logpoint store: {e}")

        return mapped

    async def set_hit_conditional_breakpoints(
        self,
        source_path: str,
        breakpoints: list[SourceBreakpoint],
    ) -> AidbBreakpointsResponse:
        """Set breakpoints with hit count conditions.

        Hit conditional breakpoints only trigger after being hit a certain
        number of times. For example, a hit condition of "5" stops on the 5th
        hit, while "%10" stops on every 10th hit.

        Parameters
        ----------
        source_path : str
            Path to the source file where breakpoints should be set
        breakpoints : List[SourceBreakpoint]
            List of breakpoint specifications with hit conditions

        Returns
        -------
        AidbBreakpointsResponse
            Response containing successfully set breakpoints with their IDs

        Raises
        ------
        NotImplementedError
            If the debug adapter doesn't support hit conditional breakpoints
        """
        if not self.session.supports_hit_conditional_breakpoints():
            msg = (
                f"Hit conditional breakpoints not supported by "
                f"{self.session.language} adapter"
            )
            raise NotImplementedError(
                msg,
            )

        # Create request with hitCondition field set for each breakpoint
        from aidb.dap.protocol.bodies import SetBreakpointsArguments
        from aidb.dap.protocol.types import Source, SourceBreakpoint

        source = Source(path=source_path)
        source_breakpoints = [
            SourceBreakpoint(
                line=bp.line,
                condition=bp.condition,
                hitCondition=bp.hitCondition,
                logMessage=bp.logMessage,
            )
            for bp in breakpoints
        ]
        args = SetBreakpointsArguments(source=source, breakpoints=source_breakpoints)
        request = SetBreakpointsRequest(seq=0, arguments=args)

        response: Response = await self.session.dap.send_request(request)
        response.ensure_success()

        # Cast to the expected response type
        breakpoints_response = cast("SetBreakpointsResponse", response)
        # Pass original request to preserve optional fields (logMessage, etc.)
        mapped = AidbBreakpointsResponse.from_dap(breakpoints_response, request)

        # Update session-scoped breakpoint store
        try:
            # Extract the list of breakpoints from the response object
            breakpoint_list = list(mapped.breakpoints.values())
            await self.session._update_breakpoints_from_response(
                source_path,
                breakpoint_list,
            )
        except Exception as e:
            # Non-fatal: store update should not break caller
            self.ctx.debug(f"Failed to update hit conditional breakpoint store: {e}")

        return mapped

    async def data_breakpoint(
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
        response: Response = await self.session.dap.send_request(request)
        response.ensure_success()
        # Cast to the expected response type
        data_response = cast("SetDataBreakpointsResponse", response)
        return AidbDataBreakpointsResponse.from_dap(data_response)

    async def exception_breakpoint(
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
        response: Response = await self.session.dap.send_request(request)
        response.ensure_success()
        exception_response = cast("SetExceptionBreakpointsResponse", response)
        return AidbExceptionBreakpointsResponse.from_dap(exception_response)

    async def function_breakpoint(
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
        response: Response = await self.session.dap.send_request(request)
        response.ensure_success()
        # Cast to the expected response type
        func_response = cast("SetFunctionBreakpointsResponse", response)
        return AidbFunctionBreakpointsResponse.from_dap(func_response)

    async def get_data_breakpoint_info(
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
        from aidb.dap.protocol.bodies import DataBreakpointInfoArguments

        args = DataBreakpointInfoArguments(
            variablesReference=variable_reference,
            name=name,
        )
        request = DataBreakpointInfoRequest(
            seq=await self.session.dap.get_next_seq(),
            arguments=args,
        )
        response: Response = await self.session.dap.send_request(request)
        response.ensure_success()

        info_response = cast("DataBreakpointInfoResponse", response)
        return AidbDataBreakpointInfoResponse.from_dap(info_response)

    async def clear_function_breakpoints(
        self,
        _names: list[str] | None = None,
    ) -> AidbFunctionBreakpointsResponse:
        """Clear function breakpoints.

        Parameters
        ----------
        names : Optional[List[str]]
            Specific function names to clear breakpoints from.
            If None, clears all function breakpoints.

        Returns
        -------
        AidbFunctionBreakpointsResponse
            Response confirming function breakpoints were cleared
        """
        from aidb.dap.protocol.bodies import SetFunctionBreakpointsArguments
        from aidb.dap.protocol.requests import SetFunctionBreakpointsRequest

        # Simply clear all function breakpoints - no tracking needed
        args = SetFunctionBreakpointsArguments(breakpoints=[])
        request = SetFunctionBreakpointsRequest(
            seq=await self.session.dap.get_next_seq(),
            arguments=args,
        )
        response: Response = await self.session.dap.send_request(request)
        response.ensure_success()
        return AidbFunctionBreakpointsResponse(
            success=True,
            message="Function breakpoints cleared",
        )

    async def clear_data_breakpoints(self) -> AidbDataBreakpointsResponse:
        """Clear all data breakpoints.

        Returns
        -------
        AidbDataBreakpointsResponse
            Empty response confirming data breakpoints were cleared
        """
        # Send empty list to clear all data breakpoints
        from aidb.dap.protocol.bodies import SetDataBreakpointsArguments
        from aidb.dap.protocol.requests import SetDataBreakpointsRequest

        args = SetDataBreakpointsArguments(breakpoints=[])
        request = SetDataBreakpointsRequest(
            seq=await self.session.dap.get_next_seq(),
            arguments=args,
        )
        response: Response = await self.session.dap.send_request(request)
        response.ensure_success()
        return AidbDataBreakpointsResponse(
            success=True,
            message="Data breakpoints cleared",
        )
