"""AidbVariable introspection operations."""

from typing import TYPE_CHECKING, cast

from aidb.common import AidbContext
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
from aidb.dap.protocol.types import Scope, ValueFormat
from aidb.models import (
    AidbVariable,
    AidbVariablesResponse,
    EvaluationResult,
    VariableType,
)

from ..base import SessionOperationsMixin
from ..decorators import requires_capability

if TYPE_CHECKING:
    from aidb.dap.protocol.base import Response
    from aidb.dap.protocol.responses import (
        EvaluateResponse,
        ScopesResponse,
        SetExpressionResponse,
        SetVariableResponse,
        VariablesResponse,
    )
    from aidb.session import Session


class VariableOperations(SessionOperationsMixin):
    """AidbVariable introspection operations."""

    def __init__(self, session: "Session", ctx: AidbContext | None = None) -> None:
        """Initialize variable operations.

        Parameters
        ----------
        session : Session
            Debug session instance
        ctx : AidbContext, optional
            Application context, by default `None`
        """
        super().__init__(session, ctx)

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
        # Get current frame ID dynamically if not provided
        if frame_id is None:
            thread_id = await self.get_current_thread_id()
            frame_id = await self.get_current_frame_id(thread_id)

        request = EvaluateRequest(
            seq=0,  # Will be overwritten by client
            arguments=EvaluateArguments(
                expression=expression,
                frameId=frame_id,
                context=context,
            ),
        )

        response: Response = await self.session.dap.send_request(request)
        response.ensure_success()
        # Cast to the expected response type
        evaluate_response = cast("EvaluateResponse", response)

        # Create EvaluationResult from the response
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
            Frame ID to get variables for. If None, uses current active frame,
            by default None

        Returns
        -------
        AidbVariablesResponse
            Global variables in the specified frame
        """
        # Get current frame ID dynamically if not provided
        if frame_id is None:
            thread_id = await self.get_current_thread_id()
            frame_id = await self.get_current_frame_id(thread_id)

        return await self._get_variables_by_scope(frame_id, "Globals")

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
        # Get current frame ID dynamically if not provided
        if frame_id is None:
            thread_id = await self.get_current_thread_id()
            frame_id = await self.get_current_frame_id(thread_id)

        return await self._get_variables_by_scope(frame_id, "Locals")

    async def _get_variables_by_scope(
        self,
        frame_id: int,
        scope_name: str,
    ) -> AidbVariablesResponse:
        """Get variables for a specific scope within a frame.

        For languages with block scoping (JavaScript, TypeScript), this may collect
        variables from multiple scopes that match the target name.
        """
        # First get scopes for the frame
        scopes_request = ScopesRequest(
            seq=0,  # Will be overwritten by client
            arguments=ScopesArguments(frameId=frame_id),
        )

        scopes_response = cast(
            "ScopesResponse",
            await self.session.dap.send_request(scopes_request),
        )
        scopes_response.ensure_success()

        # Collect ALL matching scopes (not just the first one)
        matching_scopes = []
        if scopes_response.body and scopes_response.body.scopes:
            for scope in scopes_response.body.scopes:
                self.ctx.debug(
                    f"Checking scope '{scope.name}' against target '{scope_name}'",
                )
                if self._scope_matches(scope, scope_name):
                    matching_scopes.append(scope)
                    self.ctx.debug(f"Found matching scope: {scope.name}")

        if not matching_scopes:
            self.ctx.debug(f"No matching scope found for '{scope_name}'")
            return AidbVariablesResponse(variables={})

        # Collect variables from ALL matching scopes
        all_variables_dict = {}
        for scope in matching_scopes:
            self.ctx.debug(
                f"Getting variables for scope '{scope.name}' "
                f"(reference: {scope.variablesReference})",
            )
            variables_request = VariablesRequest(
                seq=0,  # Will be overwritten by client
                arguments=VariablesArguments(
                    variablesReference=scope.variablesReference,
                ),
            )

            variables_response = cast(
                "VariablesResponse",
                await self.session.dap.send_request(variables_request),
            )
            variables_response.ensure_success()

            # Merge variables from this scope (later scopes can override earlier ones)
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

        self.ctx.debug(
            f"Collected {len(all_variables_dict)} variables from "
            f"{len(matching_scopes)} matching scope(s)",
        )
        return AidbVariablesResponse(variables=all_variables_dict, success=True)

    def _scope_matches(self, scope: Scope, target_name: str) -> bool:
        """Check if a scope matches the target name.

        Parameters
        ----------
        scope : Scope
            DAP scope object to check
        target_name : str
            Target scope name to match against

        Returns
        -------
        bool
            True if scope matches the target name
        """
        scope_lower = scope.name.lower()
        target_lower = target_name.lower()
        # JavaScript DAP patterns: "Local: funcname", "Global: module"
        js_patterns = (target_lower + ":", target_lower.rstrip("s") + ":")

        return (
            scope.name == target_name
            or scope_lower == target_lower
            or (target_lower == "locals" and scope_lower == "local")
            or (target_lower == "local" and scope_lower == "locals")
            or (target_lower == "globals" and scope_lower == "global")
            or (target_lower == "global" and scope_lower == "globals")
            or scope_lower.startswith(js_patterns)
            # Also check presentationHint for "locals"
            or (
                target_lower == "locals"
                and hasattr(scope, "presentationHint")
                and scope.presentationHint == "locals"
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
            Result of expression evaluation including value and type information
        """
        request = EvaluateRequest(
            seq=0,  # Will be overwritten by client
            arguments=EvaluateArguments(
                expression=expression,
                frameId=frame_id,
                context="watch",  # Indicate this is for watch purposes
            ),
        )

        response: Response = await self.session.dap.send_request(request)
        response.ensure_success()
        # Cast to the expected response type
        evaluate_response = cast("EvaluateResponse", response)

        # Create EvaluationResult from the response
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

    @requires_capability("supportsSetVariable", "variable modification")
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
        format : ValueFormat, optional
            Optional formatting hints for value interpretation

        Returns
        -------
        AidbVariable
            Updated variable with new value
        """
        # Create and send request
        args = SetVariableArguments(
            variablesReference=variable_ref,
            name=name,
            value=value,
            format=value_format,
        )
        request = SetVariableRequest(seq=0, arguments=args)
        response = await self.session.dap.send_request(request)
        response.ensure_success()

        # Map response to our AidbVariable model
        var_response = cast("SetVariableResponse", response)
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
        # Fallback if no body in response
        return AidbVariable(
            name=name,
            value=value,
            type_name="unknown",
            var_type=VariableType.UNKNOWN,
            has_children=False,
        )

    @requires_capability("supportsSetExpression", "set expression")
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
        format : ValueFormat, optional
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
        # Use current frame if not provided
        if frame_id is None:
            frame_id = self._current_frame_id

        if frame_id is None:
            msg = "No frame context available for set expression"
            raise AidbError(msg)

        # Create request
        arguments = SetExpressionArguments(
            expression=expression,
            value=value,
            frameId=frame_id,
            format=value_format,
        )

        request = SetExpressionRequest(
            seq=0,
            arguments=arguments,  # Will be overwritten by client
        )

        # Send request
        response: Response = await self.session.dap.send_request(request)
        response.ensure_success()

        # Map response
        expr_response = cast("SetExpressionResponse", response)

        if hasattr(expr_response, "body") and expr_response.body:
            body = expr_response.body
            type_name = body.type if hasattr(body, "type") and body.type else "unknown"
            var_ref = (
                body.variablesReference
                if hasattr(body, "variablesReference") and body.variablesReference
                else 0
            )

            # Check if there's an indexedVariables field for arrays
            indexed = (
                body.indexedVariables
                if hasattr(body, "indexedVariables") and body.indexedVariables
                else 0
            )

            # Determine variable type from type_name string (heuristic)
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
        # Fallback if no body in response
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
            seq=0,  # Will be overwritten by client
            arguments=VariablesArguments(variablesReference=variables_reference),
        )

        response: Response = await self.session.dap.send_request(request)
        variables_response = cast("VariablesResponse", response)
        variables_response.ensure_success()

        # Convert DAP variables to dictionary
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
        return await self.get_variables(variables_reference)

    def _determine_variable_type(self, type_name: str) -> VariableType:
        """Determine the VariableType from a type name string.

        Parameters
        ----------
        type_name : str
            The type name string from the DAP response

        Returns
        -------
        VariableType
            The determined variable type
        """
        if not type_name:
            return VariableType.UNKNOWN

        type_lower = type_name.lower()

        # Primitive types
        if type_lower in ["int", "float", "str", "bool", "string", "number", "boolean"]:
            return VariableType.PRIMITIVE

        # Array/list types
        if "list" in type_lower or "array" in type_lower or type_lower.endswith("[]"):
            return VariableType.ARRAY

        # Function types
        if (
            "function" in type_lower
            or "method" in type_lower
            or "callable" in type_lower
        ):
            return VariableType.FUNCTION

        # Class types
        if "class" in type_lower or "type" in type_lower:
            return VariableType.CLASS

        # Module types
        if "module" in type_lower:
            return VariableType.MODULE

        # Default to object for complex types
        return VariableType.OBJECT
