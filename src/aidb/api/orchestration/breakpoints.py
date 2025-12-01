"""AidbBreakpoint operations for debugging control flow."""

from typing import TYPE_CHECKING, Any, Optional

from aidb.audit.middleware import audit_operation
from aidb.common.errors import AidbError
from aidb.dap.protocol.types import Source, SourceBreakpoint
from aidb.models import AidbBreakpoint, AidbBreakpointsResponse
from aidb.models.entities.breakpoint import BreakpointSpec
from aidb.models.responses.breakpoints import AidbFunctionBreakpointsResponse
from aidb.session import Session
from aidb_common.path import normalize_path

from ..base import APIOperationBase
from ..breakpoint_utils import convert_breakpoints, process_breakpoint_inputs

if TYPE_CHECKING:
    from aidb.common import AidbContext


class BreakpointOperations(APIOperationBase):
    """AidbBreakpoint operations for debugging control flow."""

    def __init__(self, session: Session, ctx: Optional["AidbContext"] = None):
        """Initialize the BreakpointOperations instance.

        Parameters
        ----------
        session : Session
            Session to use
        ctx : AidbContext, optional
            Application context
        """
        super().__init__(session, ctx)

    def _get_existing_breakpoints_for_file(
        self,
        source_path: str,
    ) -> list[AidbBreakpoint]:
        """Get existing breakpoints for a specific source file.

        Parameters
        ----------
        source_path : str
            Path to the source file

        Returns
        -------
        List[AidbBreakpoint]
            List of existing breakpoints for the file
        """
        existing_bps = []
        if (
            hasattr(self.session, "current_breakpoints")
            and self.session.current_breakpoints
        ):
            for _bp_id, bp in self.session.current_breakpoints.breakpoints.items():
                if normalize_path(bp.source_path) == normalize_path(source_path):
                    existing_bps.append(bp)
            self.ctx.debug(
                f"Found {len(existing_bps)} existing breakpoints for {source_path}",
            )
        return existing_bps

    def _merge_with_existing_breakpoints(
        self,
        request,
        existing_bps: list[AidbBreakpoint],
    ) -> None:
        """Merge existing breakpoints with new ones in the request.

        Parameters
        ----------
        request : SetBreakpointsRequest
            DAP request to modify
        existing_bps : List[AidbBreakpoint]
            List of existing breakpoints to preserve
        """
        if not existing_bps or not request.arguments.breakpoints:
            return

        # Create a set of new breakpoint lines for comparison
        new_lines = {bp.line for bp in request.arguments.breakpoints if bp.line}
        self.ctx.debug(f"New breakpoint lines: {new_lines}")

        # Add existing breakpoints that aren't being replaced
        for existing_bp in existing_bps:
            if existing_bp.line not in new_lines:
                self.ctx.debug(
                    f"Preserving existing breakpoint at line "
                    f"{existing_bp.line}, column={existing_bp.column}",
                )
                source_bp = SourceBreakpoint(
                    line=existing_bp.line,
                    column=(
                        existing_bp.column
                        if existing_bp.column and existing_bp.column > 0
                        else None
                    ),
                    condition=(
                        existing_bp.condition if existing_bp.condition else None
                    ),
                    hitCondition=(
                        existing_bp.hit_condition if existing_bp.hit_condition else None
                    ),
                    logMessage=(
                        existing_bp.log_message if existing_bp.log_message else None
                    ),
                )
                request.arguments.breakpoints.append(source_bp)

        self.ctx.debug(
            f"Final breakpoint count for {request.arguments.source.path}: "
            f"{len(request.arguments.breakpoints)}",
        )

    @audit_operation(component="api.orchestration", operation="set_breakpoints")
    async def breakpoint(
        self,
        breakpoints: list[BreakpointSpec] | BreakpointSpec,
    ) -> AidbBreakpointsResponse:
        """Set one or more breakpoints in the debugger.

        Breakpoints must conform to the BreakpointSpec schema with required
        'file' and 'line' fields.

        Examples
        --------
        >>> # Single breakpoint
        >>> api.breakpoint({"file": "main.py", "line": 42})

        >>> # Multiple breakpoints
        >>> api.breakpoint([
        ...     {"file": "script.py", "line": 10},
        ...     {"file": "script.py", "line": 20}
        ... ])

        >>> # Conditional breakpoint
        >>> api.breakpoint({
        ...     "file": "app.py",
        ...     "line": 10,
        ...     "condition": "x > 5"
        ... })

        >>> # Breakpoint with hit condition
        >>> api.breakpoint({
        ...     "file": "app.py",
        ...     "line": 15,
        ...     "hit_condition": ">5"  # Break after 5 hits
        ... })

        Parameters
        ----------
        breakpoints : Union[List[BreakpointSpec], BreakpointSpec]
            Breakpoint specifications conforming to BreakpointSpec schema

        Returns
        -------
        AidbBreakpointsResponse
            Information about all set breakpoints
        """
        # Convert input to standardized format and validate
        breakpoint_list = process_breakpoint_inputs(breakpoints)

        # Convert to DAP breakpoint requests
        breakpoint_requests = convert_breakpoints(breakpoint_list, self.session.adapter)

        # IMPORTANT: DAP setBreakpoints replaces ALL breakpoints for a file.
        # We need to merge with existing breakpoints to preserve them.
        all_responses = []
        for request in breakpoint_requests:
            # Get the source file from the request
            if request.arguments and request.arguments.source:
                source_path = request.arguments.source.path

                # Skip if source_path is None
                if source_path is None:
                    continue

                # Get existing breakpoints for this file and merge them
                existing_bps = self._get_existing_breakpoints_for_file(source_path)
                self._merge_with_existing_breakpoints(request, existing_bps)

            # Use session.debug.breakpoint() which returns AidbBreakpointsResponse
            response = await self.session.debug.breakpoint(request)
            all_responses.append(response)

        # Combine all breakpoint responses
        all_breakpoints = {}
        for response in all_responses:
            if response.breakpoints:
                all_breakpoints.update(response.breakpoints)

        return AidbBreakpointsResponse(
            breakpoints=all_breakpoints,
        )

    @audit_operation(component="api.orchestration", operation="remove_breakpoint")
    async def remove_breakpoint(
        self,
        source_file: str,
        line: int,
    ) -> AidbBreakpointsResponse:
        """Remove a single breakpoint from a source file.

        Parameters
        ----------
        source_file : str
            Path to the source file
        line : int
            Line number of the breakpoint to remove

        Returns
        -------
        AidbBreakpointsResponse
            Updated list of breakpoints for the file
        """
        return await self.session.debug.remove_breakpoint(source_file, line)

    @audit_operation(component="api.orchestration", operation="clear_breakpoints")
    async def clear_breakpoints(
        self,
        source_file: str | None = None,
        clear_all: bool = False,
    ) -> AidbBreakpointsResponse:
        """Clear all breakpoints or breakpoints in a specific file.

        Parameters
        ----------
        source_file : str, optional
            Clear only breakpoints in this file.
        clear_all : bool, optional
            If True, clear all breakpoints from all files.

        Returns
        -------
        AidbBreakpointsResponse
            Empty response indicating breakpoints were cleared
        """
        if clear_all or source_file is None:
            # Clear all breakpoints
            return await self.session.debug.clear_breakpoints(clear_all=True)
        # Clear breakpoints for specific file
        source = Source(path=source_file)
        return await self.session.debug.clear_breakpoints(source=source)

    @audit_operation(component="api.orchestration", operation="data_breakpoint")
    async def data_breakpoint(
        self,
        data_id: str,
        access_type: str = "write",
        condition: str | None = None,
        hit_condition: str | None = None,
    ) -> AidbBreakpointsResponse:
        """Set a data breakpoint (watchpoint) on a variable.

        Parameters
        ----------
        data_id : str
            The data ID from a previous variables request
        access_type : str
            Type of access to break on: "read", "write", or "readWrite"
        condition : str, optional
            Expression that must evaluate to true to break
        hit_condition : str, optional
            Expression controlling how many hits are required

        Returns
        -------
        AidbBreakpointsResponse
            Information about the set data breakpoint
        """
        # Create proper DAP request
        # Import and convert access type
        from aidb.dap.protocol.bodies import SetDataBreakpointsArguments
        from aidb.dap.protocol.requests import SetDataBreakpointsRequest
        from aidb.dap.protocol.types import DataBreakpoint, DataBreakpointAccessType

        # Convert access type string to enum
        access_type_enum = DataBreakpointAccessType[access_type.upper()]

        data_bp = DataBreakpoint(
            dataId=data_id,
            accessType=access_type_enum,
            condition=condition,
            hitCondition=hit_condition,
        )

        args = SetDataBreakpointsArguments(breakpoints=[data_bp])
        request = SetDataBreakpointsRequest(seq=0, arguments=args)

        # Use session.debug.data_breakpoint() which returns AidbDataBreakpointsResponse
        response = await self.session.debug.data_breakpoint(request)

        # Convert to AidbBreakpointsResponse for API compatibility
        if response.breakpoints:
            bp = (
                list(response.breakpoints.values())[0] if response.breakpoints else None
            )
            if bp:
                # Return dict with single breakpoint
                return AidbBreakpointsResponse(
                    breakpoints={0: bp},
                    success=True,
                )

        return AidbBreakpointsResponse(
            breakpoints={},
            success=False,
        )

    @audit_operation(component="api.orchestration", operation="exception_breakpoint")
    async def exception_breakpoint(
        self,
        filters: list[str] | None = None,
        exception_options: list[dict[str, Any]] | None = None,
    ) -> AidbBreakpointsResponse:
        """Configure exception breakpoints.

        Parameters
        ----------
        filters : List[str], optional
            Exception filter IDs (e.g., ["raised", "uncaught"])
        exception_options : List[Dict], optional
            Detailed exception options with paths and break modes

        Returns
        -------
        AidbBreakpointsResponse
            Information about configured exception breakpoints
        """
        # Create proper DAP request
        from aidb.dap.protocol.bodies import SetExceptionBreakpointsArguments
        from aidb.dap.protocol.requests import SetExceptionBreakpointsRequest
        from aidb.dap.protocol.types import ExceptionOptions

        # filters is a required parameter, default to empty list
        filters_list = filters if filters is not None else []
        args = SetExceptionBreakpointsArguments(filters=filters_list)
        if exception_options is not None:
            # Convert dict to ExceptionOptions objects
            args.exceptionOptions = [
                ExceptionOptions(**opt) for opt in exception_options
            ]

        request = SetExceptionBreakpointsRequest(seq=0, arguments=args)

        # Use session.debug.exception_breakpoint()
        response = await self.session.debug.exception_breakpoint(request)

        # Convert to AidbBreakpointsResponse for API compatibility
        if response.breakpoints:
            # Already a dict, use it directly
            return AidbBreakpointsResponse(
                breakpoints=response.breakpoints,
                success=True,
            )

        # Import BreakpointState for default breakpoint
        from aidb.models import BreakpointState

        # Exception breakpoints don't always return traditional breakpoint objects
        # Return a summary response with a default breakpoint
        default_bp = AidbBreakpoint(
            id=0,
            source_path="exception",
            line=0,
            state=BreakpointState.VERIFIED,
            verified=True,
            message=(
                f"Exception breakpoint configured: {filters_list or exception_options}"
            ),
        )
        return AidbBreakpointsResponse(
            breakpoints={0: default_bp},
            success=True,
        )

    @audit_operation(component="api.orchestration", operation="function_breakpoint")
    async def function_breakpoint(
        self,
        name: str,
        condition: str | None = None,
        hit_condition: str | None = None,
    ) -> AidbBreakpointsResponse:
        """Set a breakpoint on a function by name.

        Parameters
        ----------
        name : str
            Name of the function to break on
        condition : str, optional
            Expression that must evaluate to true to break
        hit_condition : str, optional
            Expression controlling how many hits are required

        Returns
        -------
        AidbBreakpointsResponse
            Information about the set function breakpoint
        """
        # Use session's set_function_breakpoints method
        from aidb.dap.protocol.types import FunctionBreakpoint

        func_bp = FunctionBreakpoint(
            name=name,
            condition=condition,
            hitCondition=hit_condition,
        )

        response = await self.session.debug.set_function_breakpoints([func_bp])

        # Convert to AidbBreakpointsResponse for API compatibility
        if response.breakpoints:
            return AidbBreakpointsResponse(
                breakpoints=response.breakpoints,
                success=response.success,
                message=response.message,
            )

        # Even if no breakpoints, return success if response was successful
        if response.success:
            return AidbBreakpointsResponse(
                breakpoints={},
                success=True,
            )

        msg = (
            f"Failed to set function breakpoint on '{name}': "
            f"{response.message or 'Unknown error'}"
        )
        raise AidbError(
            msg,
        )

    async def clear_function_breakpoints(
        self,
        names: list[str] | None = None,
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
            Response containing cleared breakpoint information

        Raises
        ------
        AidbError
            If the operation fails
        """
        # Pass names to session layer for selective clearing
        return await self.session.debug.clear_function_breakpoints(names)

    @audit_operation(component="api.orchestration", operation="list_breakpoints")
    async def list_breakpoints(self) -> AidbBreakpointsResponse:
        """List all currently set breakpoints with their verification status.

        Returns the current breakpoint store, which is automatically synchronized
        with the debug adapter via event handlers. Verification state is updated
        asynchronously as breakpoints are verified.

        Returns
        -------
        AidbBreakpointsResponse
            Response containing all breakpoints with their current verification state.
            Returns empty response if no breakpoints are set.

        Examples
        --------
        >>> # List breakpoints with current verification status
        >>> response = await api.orchestration.list_breakpoints()
        >>> for bp_id, bp in response.breakpoints.items():
        ...     print(f"{bp.source_path}:{bp.line} verified={bp.verified}")
        """
        current_breakpoints = self.session.current_breakpoints
        if current_breakpoints is None:
            return AidbBreakpointsResponse(breakpoints={})
        return current_breakpoints
