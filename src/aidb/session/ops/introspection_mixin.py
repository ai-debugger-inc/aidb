"""Introspection operations mixin for state inspection.

This module delegates to the introspection subpackage modules for better organization.
"""

from typing import TYPE_CHECKING

from aidb.common import AidbContext
from aidb.dap.protocol.types import ValueFormat
from aidb.models import (
    AidbCallStackResponse,
    AidbDisassembleResponse,
    AidbExceptionResponse,
    AidbModulesResponse,
    AidbReadMemoryResponse,
    AidbStackFrame,
    AidbThreadsResponse,
    AidbVariable,
    AidbVariablesResponse,
    AidbWriteMemoryResponse,
    EvaluationResult,
)
from aidb.models.entities.session import SessionStatus, StopReason

from .base import BaseOperations
from .introspection import (
    MemoryOperations,
    StackOperations,
    VariableOperations,
)

if TYPE_CHECKING:
    from aidb.session import Session


class IntrospectionMixin(BaseOperations):
    """Introspection operations mixin for state inspection.

    This class delegates to the specialized operation classes in the introspection
    subpackage.
    """

    def __init__(self, session: "Session", ctx: AidbContext | None = None) -> None:
        """Initialize introspection operations.

        Parameters
        ----------
        session : Session
            The session that owns this debugger operations
        ctx : AidbContext, optional
            Application context, by default `None`
        """
        super().__init__(session, ctx)

        # Initialize delegated operation classes
        self._variable_ops = VariableOperations(session, ctx)
        self._memory_ops = MemoryOperations(session, ctx)
        self._stack_ops = StackOperations(session, ctx)

    # Stack and AidbThread Operations (delegated to StackOperations)

    async def callstack(self, thread_id: int) -> AidbCallStackResponse:
        """Get call stack for specific thread.

        Parameters
        ----------
        thread_id : int
            ID of the thread to get call stack for

        Returns
        -------
        AidbCallStackResponse
            Call stack frames for the specified thread
        """
        return await self._stack_ops.callstack(thread_id)

    async def threads(self) -> AidbThreadsResponse:
        """Get all threads and their current states.

        Returns
        -------
        AidbThreadsResponse
            Response containing all threads and their current states
        """
        return await self._stack_ops.threads()

    async def frame(self, frame_id: int | None = None) -> AidbStackFrame:
        """Get information about a stack frame.

        Parameters
        ----------
        frame_id : int, optional
            Frame ID to get info for. If None, uses current active frame, by
            default None

        Returns
        -------
        AidbStackFrame
            Information about the specified stack frame
        """
        return await self._stack_ops.frame(frame_id)

    async def get_scopes(self, frame_id: int | None = None):
        """Get variable scopes for a stack frame.

        Parameters
        ----------
        frame_id : Optional[int]
            Frame ID to get scopes for. If None, uses current frame.

        Returns
        -------
        list[Scope]
            List of available scopes in the frame
        """
        if frame_id is None:
            thread_id = await self.get_current_thread_id()
            frame_id = await self.get_current_frame_id(thread_id)
        return await self._stack_ops.get_scopes(frame_id)

    async def exception(self, thread_id: int) -> AidbExceptionResponse:
        """Get exception information for specific thread.

        Parameters
        ----------
        thread_id : int
            ID of the thread to get exception information for

        Returns
        -------
        AidbExceptionResponse
            Exception information including details and break mode
        """
        return await self._stack_ops.exception(thread_id)

    async def get_execution_state(self):
        """Get current execution state of the debug session.

        Returns
        -------
        ExecutionStateResponse
            Current execution state with status, location, and stop reason

        Raises
        ------
        AidbError
            If unable to determine execution state
        """
        from aidb.models import ExecutionStateResponse

        # Get session status
        session_status = self.session.status
        self.ctx.debug(f"[get_execution_state] session_status={session_status}")

        # Determine basic state flags
        terminated = session_status in (SessionStatus.TERMINATED, SessionStatus.ERROR)
        paused = session_status == SessionStatus.PAUSED
        running = session_status == SessionStatus.RUNNING
        self.ctx.debug(
            f"[get_execution_state] terminated={terminated}, paused={paused}, running={running}",
        )

        # Initialize execution state fields
        stop_reason = None
        thread_id = None
        frame_id = None
        current_file = None
        current_line = None
        exception_info = None

        # If terminated, set stop reason
        if terminated:
            stop_reason = StopReason.EXIT

        # If paused, try to get additional context
        elif paused:
            try:
                # Get stop reason from event processor if available
                if hasattr(self.session.dap, "_event_processor") and hasattr(
                    self.session.dap._event_processor,
                    "_state",
                ):
                    processor_state = self.session.dap._event_processor._state
                    if processor_state.stop_reason:
                        stop_reason = processor_state.stop_reason
                        self.ctx.debug(
                            f"[get_execution_state] Got stop_reason from processor: {stop_reason}",
                        )
                    else:
                        stop_reason = StopReason.UNKNOWN
                        self.ctx.debug(
                            "[get_execution_state] No stop_reason in processor, using UNKNOWN",
                        )

                # Try to get current thread and location
                thread_id = await self.get_current_thread_id()
                self.ctx.debug(f"[get_execution_state] thread_id={thread_id}")

                # Get call stack to find current location
                callstack_response = await self.callstack(thread_id)
                self.ctx.debug(
                    f"[get_execution_state] callstack success={callstack_response.success}, "
                    f"frames_count={len(callstack_response.frames) if callstack_response.frames else 0}",
                )
                if callstack_response.success and callstack_response.frames:
                    top_frame = callstack_response.frames[0]
                    frame_id = top_frame.id
                    current_file = top_frame.source.path if top_frame.source else None
                    current_line = top_frame.line
                    self.ctx.debug(
                        f"[get_execution_state] Got location: file={current_file}, line={current_line}",
                    )

                # Check for exception info if stop reason is exception
                if stop_reason == StopReason.EXCEPTION:
                    try:
                        exc_response = await self.exception(thread_id)
                        if exc_response.success:
                            exception_info = {
                                "description": exc_response.exception_id,
                                "details": exc_response.description,
                                "break_mode": exc_response.break_mode,
                            }
                    except Exception:
                        # Exception info not critical, continue without it
                        pass

            except Exception as e:
                # If we can't get location/thread info, still return basic state
                self.ctx.debug(
                    f"Could not get full execution context: {e}",
                )
                # Use unknown stop reason if we couldn't determine it
                if stop_reason is None:
                    stop_reason = StopReason.UNKNOWN

        # Build execution state
        from aidb.models.entities.session import ExecutionState

        exec_state = ExecutionState(
            status=session_status,
            running=running,
            paused=paused,
            terminated=terminated,
            stop_reason=stop_reason,
            thread_id=thread_id,
            frame_id=frame_id,
            current_file=current_file,
            current_line=current_line,
            exception_info=exception_info,
        )

        self.ctx.debug(f"[get_execution_state] Built exec_state: {exec_state}")

        return ExecutionStateResponse(
            success=True,
            execution_state=exec_state,
        )

    async def get_modules(
        self,
        start_module: int = 0,
        module_count: int = 100,
    ) -> AidbModulesResponse:
        """Get list of loaded modules.

        Parameters
        ----------
        start_module : int
            Index of first module to return
        module_count : int
            Maximum number of modules to return

        Returns
        -------
        AidbModulesResponse
            Response containing list of loaded modules

        Raises
        ------
        AdapterCapabilityNotSupportedError
            If the adapter does not support module introspection
        """
        return await self._stack_ops.get_modules(start_module, module_count)

    # AidbVariable Operations (delegated to VariableOperations)

    async def evaluate(
        self,
        expression: str,
        frame_id: int | None = None,
        context: str = "watch",
    ) -> EvaluationResult:
        """Evaluate an expression in the current context.

        Parameters
        ----------
        expression : str
            Expression to evaluate
        frame_id : int, optional
            ID of the stack frame in which to evaluate. If None, uses current
            active frame, by default None
        context : str
            Evaluation context ("watch", "repl", "hover"), by default "watch"

        Returns
        -------
        EvaluationResult
            Result of expression evaluation including value and type information
        """
        return await self._variable_ops.evaluate(expression, frame_id, context)

    async def globals(self, frame_id: int | None = None) -> AidbVariablesResponse:
        """Get global variables for a specific frame.

        Parameters
        ----------
        frame_id : int, optional
            Frame ID to get variables for. If None, uses current active frame,
            by default None

        Returns
        -------
        AidbVariablesResponse
            Global variables in the specified frame
        """
        return await self._variable_ops.globals(frame_id)

    async def locals(self, frame_id: int | None = None) -> AidbVariablesResponse:
        """Get local variables for a specific frame.

        Parameters
        ----------
        frame_id : int, optional
            Frame ID to get variables for. If None, uses current active frame,
            by default None

        Returns
        -------
        AidbVariablesResponse
            Local variables in the specified frame
        """
        return await self._variable_ops.locals(frame_id)

    async def watch(self, expression: str, frame_id: int) -> EvaluationResult:
        """Watch an expression in specific frame.

        Parameters
        ----------
        expression : str
            Expression to evaluate and watch
        frame_id : int
            ID of the stack frame to evaluate expression in

        Returns
        -------
        EvaluationResult
            Result of expression evaluation including value and type information
        """
        return await self._variable_ops.watch(expression, frame_id)

    async def get_variables(self, variables_reference: int) -> dict:
        """Get variables for a given reference.

        Parameters
        ----------
        variables_reference : int
            Reference to the variable container

        Returns
        -------
        dict
            Dictionary of variables with their details
        """
        return await self._variable_ops.get_variables(variables_reference)

    async def get_child_variables(self, variables_reference: int) -> dict:
        """Get child variables for a given variable reference.

        This is essentially an alias for get_variables() but with a more
        descriptive name when specifically getting children of a complex variable.

        Parameters
        ----------
        variables_reference : int
            Reference to the parent variable

        Returns
        -------
        dict
            Dictionary of child variables with their details
        """
        return await self._variable_ops.get_child_variables(variables_reference)

    async def set_variable(
        self,
        variable_ref: int,
        name: str,
        value: str,
        value_format: ValueFormat | None = None,
    ) -> AidbVariable:
        """Modify a variable's value.

        Parameters
        ----------
        variable_ref : int
            Container reference from variables() call
        name : str
            AidbVariable name to modify
        value : str
            New value as string representation
        value_format : ValueFormat, optional
            Optional formatting hints for value interpretation

        Returns
        -------
        AidbVariable
            Updated variable with new value
        """
        return await self._variable_ops.set_variable(
            variable_ref,
            name,
            value,
            value_format,
        )

    async def set_expression(
        self,
        expression: str,
        value: str,
        frame_id: int | None = None,
        value_format: ValueFormat | None = None,
    ) -> AidbVariable:
        """Modify a value using an expression.

        This is more powerful than set_variable as it allows modifying nested
        properties and calling methods. For example:
        - 'obj.field.subfield = "new value"'
        - 'array[5] = 42'
        - 'obj.setValue(newValue)'

        Parameters
        ----------
        expression : str
            The expression to evaluate and modify (e.g., 'user.profile.name')
        value : str
            The new value to assign as a string representation
        frame_id : int, optional
            Stack frame context for the expression. Uses current frame if not provided.
        value_format : ValueFormat, optional
            Optional formatting hints for value interpretation

        Returns
        -------
        AidbVariable
            The modified variable with its new value

        Raises
        ------
        UnsupportedOperationError
            If the adapter doesn't support set expression
        AidbError
            If the expression is invalid or modification fails
        """
        return await self._variable_ops.set_expression(
            expression,
            value,
            frame_id,
            value_format,
        )

    # Memory Operations (delegated to MemoryOperations)

    async def read_memory(
        self,
        memory_reference: str,
        offset: int = 0,
        count: int = 256,
    ) -> AidbReadMemoryResponse:
        """Read raw memory from the target.

        Parameters
        ----------
        memory_reference : str
            Memory reference (e.g., "0x1000" or variable reference)
        offset : int
            Offset from the memory reference in bytes, by default 0
        count : int
            Number of bytes to read, by default 256

        Returns
        -------
        AidbReadMemoryResponse
            Raw memory data and address information
        """
        return await self._memory_ops.read_memory(memory_reference, offset, count)

    async def write_memory(
        self,
        memory_reference: str,
        data: str,
        offset: int = 0,
        allow_partial: bool = False,
    ) -> AidbWriteMemoryResponse:
        """Write raw memory to the target.

        Parameters
        ----------
        memory_reference : str
            Memory reference (e.g., "0x1000" or variable reference)
        data : str
            Base64-encoded data to write
        offset : int
            Offset from the memory reference in bytes, by default 0
        allow_partial : bool
            Whether to allow partial writes if not all bytes can be written,
            by default False

        Returns
        -------
        AidbWriteMemoryResponse
            Information about bytes written and starting address
        """
        return await self._memory_ops.write_memory(
            memory_reference,
            data,
            offset,
            allow_partial,
        )

    async def get_memory_reference(self, variable_reference: int) -> str | None:
        """Get memory reference for a variable.

        This method retrieves the memory reference (e.g., pointer address) for
        a given variable reference. This is useful for getting the address of
        variables to pass to read_memory or write_memory operations.

        Parameters
        ----------
        variable_reference : int
            AidbVariable reference ID from a variables response

        Returns
        -------
        Optional[str]
            Memory reference string if available, None otherwise
        """
        return await self._memory_ops.get_memory_reference(variable_reference)

    async def disassemble(
        self,
        memory_reference: str,
        offset: int = 0,
        instruction_offset: int = -5,
        instruction_count: int = 20,
        resolve_symbols: bool = True,
    ) -> AidbDisassembleResponse:
        """Disassemble machine code to instructions.

        Parameters
        ----------
        memory_reference : str
            Memory reference to start disassembly (e.g., "0x1000" or frame PC)
        offset : int
            Byte offset from memory reference, by default 0
        instruction_offset : int
            Number of instructions before the reference to include
            (negative value), by default -5
        instruction_count : int
            Total number of instructions to disassemble, by default 20
        resolve_symbols : bool
            Whether to resolve symbol names in disassembly, by default True

        Returns
        -------
        AidbDisassembleResponse
            Disassembled instructions with addresses and optional source locations
        """
        return await self._memory_ops.disassemble(
            memory_reference,
            offset,
            instruction_offset,
            instruction_count,
            resolve_symbols,
        )
