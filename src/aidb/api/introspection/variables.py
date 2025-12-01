"""AidbVariable inspection and modification operations."""

from typing import TYPE_CHECKING, Optional

from aidb.audit.middleware import audit_operation
from aidb.common.errors import AidbError
from aidb.dap.protocol.bodies import SetVariableResponseBody
from aidb.models import (
    AidbVariablesResponse,
    EvaluationResult,
)
from aidb.session import Session

from ..base import APIOperationBase
from ..constants import (
    EVALUATION_CONTEXT_REPL,
    EVALUATION_CONTEXT_WATCH,
    SCOPE_GLOBAL,
    SCOPE_GLOBALS,
    SCOPE_LOCAL,
    SCOPE_LOCALS,
)

if TYPE_CHECKING:
    from aidb.common import AidbContext


class VariableOperations(APIOperationBase):
    """AidbVariable inspection and modification operations."""

    def __init__(self, session: Session, ctx: Optional["AidbContext"] = None):
        """Initialize the VariableOperations instance.

        Parameters
        ----------
        session : Session
            Session to use
        ctx : AidbContext, optional
            Application context
        """
        super().__init__(session, ctx)

    @audit_operation(component="api.introspection", operation="get_locals")
    async def locals(self, frame_id: int | None = None) -> AidbVariablesResponse:
        """Get local variables from the current or specified frame.

        This operation is automatically audited when audit logging is enabled.

        Parameters
        ----------
        frame_id : int, optional
            Frame to get locals from, by default None (top frame)

        Returns
        -------
        AidbVariablesResponse
            Local variables in the frame

        Raises
        ------
        AidbError
            If session is not paused or frame not found
        """
        return await self.session.debug.locals(frame_id=frame_id)

    @audit_operation(component="api.introspection", operation="get_globals")
    async def globals(self, frame_id: int | None = None) -> AidbVariablesResponse:
        """Get global variables from the current or specified frame.

        This operation is automatically audited when audit logging is enabled.

        Parameters
        ----------
        frame_id : int, optional
            Frame to get globals from, by default None (top frame)

        Returns
        -------
        AidbVariablesResponse
            Global variables accessible from the frame

        Raises
        ------
        AidbError
            If session is not paused or frame not found
        """
        return await self.session.debug.globals(frame_id=frame_id)

    @audit_operation(component="api.introspection", operation="evaluate")
    async def evaluate(
        self,
        expression: str,
        frame_id: int | None = None,
        context: str = EVALUATION_CONTEXT_REPL,
    ) -> EvaluationResult:
        """Evaluate an expression in the current context.

        This operation is automatically audited when audit logging is enabled.

        Parameters
        ----------
        expression : str
            Expression to evaluate
        frame_id : int, optional
            Frame context for evaluation, by default None (top frame)
        context : str
            Evaluation context: "repl", "watch", or "hover"

        Returns
        -------
        EvaluateResponseModel
            Result of the evaluation
        """
        return await self.session.debug.evaluate(
            expression=expression,
            frame_id=frame_id,
            context=context,
        )

    @audit_operation(component="api.introspection", operation="set_variable")
    async def set_variable(
        self,
        name: str,
        value: str,
        variables_reference: int | None = None,
        frame_id: int | None = None,
    ) -> SetVariableResponseBody:
        """Set the value of a variable.

        This operation is automatically audited when audit logging is enabled.

        Parameters
        ----------
        name : str
            AidbVariable name to set
        value : str
            New value (as string representation)
        variables_reference : int, optional
            Reference to the variable container
        frame_id : int, optional
            Frame containing the variable

        Returns
        -------
        SetVariableResponseModel
            Information about the set variable
        """
        # If no variables_reference provided, try to find it from the frame
        if variables_reference is None:
            if not self.session.is_paused():
                current_status = self.session.status.name
                msg = (
                    f"Cannot set variable - session is not paused "
                    f"(current status: {current_status})"
                )
                raise AidbError(msg)

            resolved_frame_id = frame_id

            # Get scopes and find the variable
            scopes = await self.session.debug.get_scopes(frame_id=resolved_frame_id)
            if not scopes:
                msg = f"Failed to get scopes for frame {resolved_frame_id}"
                raise AidbError(msg)

            self.ctx.debug(f"Got {len(scopes)} scopes for frame {resolved_frame_id}")

            # Try to find the appropriate scope for the variable
            # The Python adapter has issues with variablesReference when
            # checking variables, so we'll just try locals first without verification
            locals_scopes = [SCOPE_LOCALS, SCOPE_LOCAL]
            globals_scopes = [SCOPE_GLOBALS, SCOPE_GLOBAL]

            # First try to find a locals scope
            locals_ref = None
            globals_ref = None

            for scope in scopes:
                scope_name = scope.name.lower() if scope.name else ""
                if scope_name in locals_scopes and locals_ref is None:
                    locals_ref = scope.variablesReference
                    self.ctx.debug(
                        f"Found locals scope '{scope.name}' with ref {locals_ref}",
                    )
                elif scope_name in globals_scopes and globals_ref is None:
                    globals_ref = scope.variablesReference
                    self.ctx.debug(
                        f"Found globals scope '{scope.name}' with ref {globals_ref}",
                    )

            # Try locals first (most variables are local)
            if locals_ref is not None:
                variables_reference = locals_ref
                self.ctx.debug(f"Using locals scope for variable '{name}'")
            elif globals_ref is not None:
                # Fallback to globals if no locals scope found
                variables_reference = globals_ref
                self.ctx.debug(f"Using globals scope for variable '{name}'")

        if variables_reference is None:
            # Log what scopes we found for debugging
            scope_names = [s.name for s in scopes] if scopes else []
            msg = (
                f"Could not find variable '{name}' in any scope. "
                f"Available scopes: {scope_names}. "
                "You may need to provide variables_reference directly."
            )
            raise AidbError(
                msg,
            )

        # Delegate to session.debug.set_variable() which handles all the DAP logic
        result = await self.session.debug.set_variable(
            variable_ref=variables_reference,
            name=name,
            value=value,
        )

        # Convert AidbVariable result to SetVariableResponseBody
        return SetVariableResponseBody(
            value=result.value,
            type=result.type_name,
            variablesReference=result.id if result.has_children else 0,
            namedVariables=None,  # Not available from AidbVariable
            indexedVariables=None,  # Not available from AidbVariable
        )

    @audit_operation(component="api.introspection", operation="watch")
    async def watch(
        self,
        expression: str,
        frame_id: int | None = None,
    ) -> EvaluationResult:
        """Add a watch expression.

        This is a convenience method that evaluates an expression in watch context.
        This operation is automatically audited when audit logging is enabled.

        Parameters
        ----------
        expression : str
            Expression to watch
        frame_id : int, optional
            Frame context for evaluation

        Returns
        -------
        EvaluationResult
            Current value of the watch expression
        """
        return await self.evaluate(
            expression,
            frame_id,
            context=EVALUATION_CONTEXT_WATCH,
        )
