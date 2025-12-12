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
        EvaluationResult
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

    @audit_operation(component="api.introspection", operation="get_children")
    async def get_children(
        self,
        variables_reference: int,
    ) -> AidbVariablesResponse:
        """Get child variables for a given variable reference.

        This retrieves the expandable children of a complex variable (objects,
        arrays, etc.) using the variable's variablesReference.

        This operation is automatically audited when audit logging is enabled.

        Parameters
        ----------
        variables_reference : int
            Reference to the parent variable (from AidbVariable.id)

        Returns
        -------
        AidbVariablesResponse
            Child variables of the parent variable
        """
        variables_dict = await self.session.debug.get_child_variables(
            variables_reference,
        )
        return AidbVariablesResponse(success=True, variables=variables_dict)

    @audit_operation(component="api.introspection", operation="resolve_variable")
    async def resolve_variable(
        self,
        var_name: str,
        frame_id: int | None = None,
    ) -> tuple[int, str | None]:
        """Resolve a variable name to its variablesReference.

        Handles nested names like "user.email" by traversing the object tree.
        Searches in locals first, then globals.

        This operation is automatically audited when audit logging is enabled.

        Parameters
        ----------
        var_name : str
            Variable name, optionally with dot notation for nested access
            (e.g., "user", "user.email", "data.items[0].name")
        frame_id : int, optional
            Frame to search in, by default None (top frame)

        Returns
        -------
        tuple[int, str | None]
            A tuple of (variables_reference, error_message).
            On success: (reference_id, None)
            On failure: (0, error_message)

        Examples
        --------
        >>> ref, err = await api.introspection.resolve_variable("user")
        >>> if err:
        ...     print(f"Error: {err}")
        ... else:
        ...     print(f"Found variable with reference: {ref}")
        """
        locals_response = await self.locals(frame_id=frame_id)
        var_parts = var_name.split(".")
        current_vars = locals_response.variables

        for i, part in enumerate(var_parts):
            if part not in current_vars:
                # Try globals for the first part only
                if i == 0:
                    globals_response = await self.globals(frame_id=frame_id)
                    if part in globals_response.variables:
                        current_vars = globals_response.variables
                    else:
                        return (0, f"Variable '{part}' not found in locals or globals")
                else:
                    return (0, f"Field '{part}' not found on variable")

            var = current_vars[part]
            if i == len(var_parts) - 1:
                # Final variable - return its reference
                if var.id:
                    return (var.id, None)
                return (0, f"Variable '{var_name}' has no reference (primitive type)")

            # Need to traverse deeper
            if var.has_children and var.id:
                # Expand children for nested access
                children_response = await self.get_children(var.id)
                current_vars = children_response.variables
            else:
                return (0, f"Variable '{part}' has no expandable children")

        return (0, f"Could not resolve variable reference for '{var_name}'")
