"""Variable inspection service operations."""

from typing import TYPE_CHECKING

from aidb.common.capabilities import DAPCapability, OperationName
from aidb.common.constants import (
    EVALUATION_CONTEXT_WATCH,
    SCOPE_GLOBAL,
    SCOPE_GLOBALS,
    SCOPE_LOCAL,
    SCOPE_LOCALS,
)
from aidb.common.errors import AidbError
from aidb.dap.protocol.bodies import (
    EvaluateArguments,
    ScopesArguments,
    SetExpressionArguments,
    SetVariableArguments,
    VariablesArguments,
)
from aidb.dap.protocol.requests import (
    EvaluateRequest,
    ScopesRequest,
    SetExpressionRequest,
    SetVariableRequest,
    VariablesRequest,
)
from aidb.dap.protocol.responses import (
    EvaluateResponse,
    ScopesResponse,
    SetExpressionResponse,
    SetVariableResponse,
    VariablesResponse,
)
from aidb.dap.protocol.types import Scope, ValueFormat
from aidb.models import (
    AidbVariable,
    AidbVariablesResponse,
    EvaluationResult,
    VariableType,
)
from aidb.service.decorators import requires_capability

from ..base import BaseServiceComponent
from ..stack import StackService

if TYPE_CHECKING:
    from aidb.interfaces import IContext
    from aidb.session import Session


class VariableService(BaseServiceComponent):
    """Variable inspection and modification service.

    Provides methods for evaluating expressions, getting variables by scope, and
    modifying variable values.
    """

    def __init__(self, session: "Session", ctx: "IContext | None" = None) -> None:
        """Initialize variable service.

        Parameters
        ----------
        session : Session
            Debug session instance
        ctx : IContext, optional
            Application context
        """
        super().__init__(session, ctx)

    async def evaluate(
        self,
        expression: str,
        frame_id: int | None = None,
        context: str = EVALUATION_CONTEXT_WATCH,
    ) -> EvaluationResult:
        """Evaluate an expression in the current context.

        Parameters
        ----------
        expression : str
            Expression to evaluate
        frame_id : int, optional
            ID of the stack frame in which to evaluate
        context : str
            Evaluation context ("watch", "repl", "hover")

        Returns
        -------
        EvaluationResult
            Result of expression evaluation
        """
        frame_id = await self._resolve_frame_id(frame_id)

        request = EvaluateRequest(
            seq=0,
            arguments=EvaluateArguments(
                expression=expression,
                frameId=frame_id,
                context=context,
            ),
        )

        evaluate_response = await self._send_and_ensure(request, EvaluateResponse)

        if evaluate_response.body:
            return EvaluationResult(
                expression=expression,
                result=evaluate_response.body.result,
                type_name=evaluate_response.body.type or "unknown",
                var_type=self._determine_variable_type(
                    evaluate_response.body.type or "",
                ),
                has_children=(evaluate_response.body.variablesReference or 0) > 0,
            )
        msg = f"Failed to evaluate expression: {expression}"
        raise AidbError(msg)

    async def globals(self, frame_id: int | None = None) -> AidbVariablesResponse:
        """Get global variables for a specific frame.

        Parameters
        ----------
        frame_id : int, optional
            Frame ID to get variables for

        Returns
        -------
        AidbVariablesResponse
            Global variables in the specified frame
        """
        frame_id = await self._resolve_frame_id(frame_id)
        return await self._get_variables_by_scope(frame_id, SCOPE_GLOBALS.capitalize())

    async def locals(self, frame_id: int | None = None) -> AidbVariablesResponse:
        """Get local variables for a specific frame.

        Parameters
        ----------
        frame_id : int, optional
            Frame ID to get variables for

        Returns
        -------
        AidbVariablesResponse
            Local variables in the specified frame
        """
        frame_id = await self._resolve_frame_id(frame_id)
        return await self._get_variables_by_scope(frame_id, SCOPE_LOCALS.capitalize())

    async def _get_variables_by_scope(
        self,
        frame_id: int,
        scope_name: str,
    ) -> AidbVariablesResponse:
        """Get variables for a specific scope within a frame."""
        scopes_request = ScopesRequest(
            seq=0,
            arguments=ScopesArguments(frameId=frame_id),
        )

        scopes_response = await self._send_and_ensure(scopes_request, ScopesResponse)

        matching_scopes = []
        if scopes_response.body and scopes_response.body.scopes:
            for scope in scopes_response.body.scopes:
                if self._scope_matches(scope, scope_name):
                    matching_scopes.append(scope)

        if not matching_scopes:
            return AidbVariablesResponse(variables={})

        all_variables_dict = {}
        for scope in matching_scopes:
            variables_request = VariablesRequest(
                seq=0,
                arguments=VariablesArguments(
                    variablesReference=scope.variablesReference,
                ),
            )

            variables_response = await self._send_and_ensure(
                variables_request,
                VariablesResponse,
            )

            if variables_response.body and variables_response.body.variables:
                for var in variables_response.body.variables:
                    aidb_var = AidbVariable(
                        name=var.name,
                        value=var.value or "",
                        type_name=var.type or "unknown",
                        var_type=self._determine_variable_type(var.type or ""),
                        has_children=(var.variablesReference or 0) > 0,
                        id=var.variablesReference or 0,
                    )
                    all_variables_dict[var.name] = aidb_var

        return AidbVariablesResponse(variables=all_variables_dict, success=True)

    def _scope_matches(self, scope: Scope, target_name: str) -> bool:
        """Check if a scope matches the target name."""
        scope_lower = scope.name.lower()
        target_lower = target_name.lower()
        js_patterns = (target_lower + ":", target_lower.rstrip("s") + ":")

        return (
            scope.name == target_name
            or scope_lower == target_lower
            or (target_lower == SCOPE_LOCALS and scope_lower == SCOPE_LOCAL)
            or (target_lower == SCOPE_LOCAL and scope_lower == SCOPE_LOCALS)
            or (target_lower == SCOPE_GLOBALS and scope_lower == SCOPE_GLOBAL)
            or (target_lower == SCOPE_GLOBAL and scope_lower == SCOPE_GLOBALS)
            or scope_lower.startswith(js_patterns)
            or (
                target_lower == SCOPE_LOCALS
                and hasattr(scope, "presentationHint")
                and scope.presentationHint == SCOPE_LOCALS
            )
        )

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
            Result of expression evaluation
        """
        request = EvaluateRequest(
            seq=0,
            arguments=EvaluateArguments(
                expression=expression,
                frameId=frame_id,
                context=EVALUATION_CONTEXT_WATCH,
            ),
        )

        evaluate_response = await self._send_and_ensure(request, EvaluateResponse)

        if evaluate_response.body:
            return EvaluationResult(
                expression=expression,
                result=evaluate_response.body.result,
                type_name=evaluate_response.body.type or "unknown",
                var_type=self._determine_variable_type(
                    evaluate_response.body.type or "",
                ),
                has_children=(evaluate_response.body.variablesReference or 0) > 0,
            )
        msg = f"Failed to evaluate expression: {expression}"
        raise AidbError(msg)

    @requires_capability(DAPCapability.SET_VARIABLE, OperationName.SET_VARIABLE)
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
            Variable name to modify
        value : str
            New value as string representation
        value_format : ValueFormat, optional
            Optional formatting hints

        Returns
        -------
        AidbVariable
            Updated variable with new value
        """
        args = SetVariableArguments(
            variablesReference=variable_ref,
            name=name,
            value=value,
            format=value_format,
        )
        request = SetVariableRequest(seq=0, arguments=args)
        var_response = await self._send_and_ensure(request, SetVariableResponse)

        if hasattr(var_response, "body") and var_response.body:
            body = var_response.body
            type_name = body.type if hasattr(body, "type") and body.type else "unknown"
            var_ref = (
                body.variablesReference
                if hasattr(body, "variablesReference") and body.variablesReference
                else 0
            )
            return AidbVariable(
                name=name,
                value=body.value,
                type_name=type_name,
                var_type=VariableType.UNKNOWN,
                has_children=var_ref > 0,
            )

        return AidbVariable(
            name=name,
            value=value,
            type_name="unknown",
            var_type=VariableType.UNKNOWN,
            has_children=False,
        )

    @requires_capability(DAPCapability.SET_VARIABLE, OperationName.SET_VARIABLE)
    async def set_variable_by_name(
        self,
        name: str,
        value: str,
        frame_id: int | None = None,
    ) -> AidbVariable:
        """Set a variable by name, resolving the variable reference automatically.

        This is a convenience method that resolves the variable reference from
        the frame scopes before calling set_variable().

        Parameters
        ----------
        name : str
            Variable name to modify
        value : str
            New value as string representation
        frame_id : int, optional
            Frame containing the variable. If None, uses current frame.

        Returns
        -------
        AidbVariable
            Updated variable with new value

        Raises
        ------
        AidbError
            If session is not paused or variable reference cannot be resolved
        """
        if not self.session.is_paused():
            current_status = self.session.status.name
            msg = (
                f"Cannot set variable - session is not paused "
                f"(current status: {current_status})"
            )
            raise AidbError(msg)

        # Get scopes for the frame (avoid session.debug dependency)
        stack_service = StackService(self.session, self.ctx)
        scopes = await stack_service.get_scopes(frame_id=frame_id)
        if not scopes:
            msg = f"Failed to get scopes for frame {frame_id}"
            raise AidbError(msg)

        self.ctx.debug(f"Got {len(scopes)} scopes for frame {frame_id}")

        # Find locals and globals scope references
        locals_scopes = [SCOPE_LOCALS, SCOPE_LOCAL]
        globals_scopes = [SCOPE_GLOBALS, SCOPE_GLOBAL]

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
        variable_ref = locals_ref
        if variable_ref is None:
            variable_ref = globals_ref
        if variable_ref is None:
            msg = f"Could not find variable scope for '{name}'"
            raise AidbError(msg)

        self.ctx.debug(f"Using variable ref {variable_ref} for variable '{name}'")
        return await self.set_variable(variable_ref, name, value)

    @requires_capability(DAPCapability.SET_EXPRESSION, OperationName.SET_EXPRESSION)
    async def set_expression(
        self,
        expression: str,
        value: str,
        frame_id: int | None = None,
        value_format: ValueFormat | None = None,
    ) -> AidbVariable:
        """Modify a value using an expression.

        Parameters
        ----------
        expression : str
            The expression to evaluate and modify
        value : str
            The new value to assign
        frame_id : int, optional
            Stack frame context
        value_format : ValueFormat, optional
            Optional formatting hints

        Returns
        -------
        AidbVariable
            The modified variable
        """
        frame_id = await self._resolve_frame_id(frame_id)

        arguments = SetExpressionArguments(
            expression=expression,
            value=value,
            frameId=frame_id,
            format=value_format,
        )

        request = SetExpressionRequest(seq=0, arguments=arguments)
        expr_response = await self._send_and_ensure(request, SetExpressionResponse)

        if hasattr(expr_response, "body") and expr_response.body:
            body = expr_response.body
            type_name = body.type if hasattr(body, "type") and body.type else "unknown"
            var_ref = (
                body.variablesReference
                if hasattr(body, "variablesReference") and body.variablesReference
                else 0
            )
            indexed = (
                body.indexedVariables
                if hasattr(body, "indexedVariables") and body.indexedVariables
                else 0
            )

            var_type = VariableType.UNKNOWN
            if (
                indexed > 0
                or "array" in type_name.lower()
                or "list" in type_name.lower()
            ):
                var_type = VariableType.ARRAY
            elif var_ref > 0:
                var_type = VariableType.OBJECT

            return AidbVariable(
                name=expression,
                value=body.value,
                type_name=type_name,
                var_type=var_type,
                has_children=var_ref > 0 or indexed > 0,
            )

        return AidbVariable(
            name=expression,
            value=value,
            type_name="unknown",
            var_type=VariableType.UNKNOWN,
            has_children=False,
        )

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
        request = VariablesRequest(
            seq=0,
            arguments=VariablesArguments(variablesReference=variables_reference),
        )

        variables_response = await self._send_and_ensure(request, VariablesResponse)

        variables_dict = {}
        if variables_response.body and variables_response.body.variables:
            for var in variables_response.body.variables:
                aidb_var = AidbVariable(
                    name=var.name,
                    value=var.value or "",
                    type_name=var.type or "unknown",
                    var_type=self._determine_variable_type(var.type or ""),
                    has_children=(var.variablesReference or 0) > 0,
                    id=var.variablesReference or 0,
                )
                variables_dict[var.name] = aidb_var

        return variables_dict

    async def get_child_variables(self, variables_reference: int) -> dict:
        """Get child variables for a given variable reference.

        Parameters
        ----------
        variables_reference : int
            Reference to the parent variable

        Returns
        -------
        dict
            Dictionary of child variables
        """
        return await self.get_variables(variables_reference)

    def _determine_variable_type(self, type_name: str) -> VariableType:
        """Determine the VariableType from a type name string."""
        if not type_name:
            return VariableType.UNKNOWN

        type_lower = type_name.lower()

        if type_lower in ["int", "float", "str", "bool", "string", "number", "boolean"]:
            return VariableType.PRIMITIVE

        if "list" in type_lower or "array" in type_lower or type_lower.endswith("[]"):
            return VariableType.ARRAY

        if (
            "function" in type_lower
            or "method" in type_lower
            or "callable" in type_lower
        ):
            return VariableType.FUNCTION

        if "class" in type_lower or "type" in type_lower:
            return VariableType.CLASS

        if "module" in type_lower:
            return VariableType.MODULE

        return VariableType.OBJECT

    async def resolve_variable(
        self,
        var_name: str,
        frame_id: int | None = None,
    ) -> tuple[int, str | None]:
        """Resolve a variable name to its variablesReference.

        Handles nested names like "user.email" by traversing the object tree.
        Searches in locals first, then globals.

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
        >>> ref, err = await service.variables.resolve_variable("user")
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
                current_vars = await self.get_child_variables(var.id)
            else:
                return (0, f"Variable '{part}' has no expandable children")

        # Should not reach here, but return error just in case
        return (0, f"Failed to resolve variable '{var_name}'")
