"""Evaluation-related response models."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..base import OperationResponse
from ..entities.variable import EvaluationResult, VariableType

if TYPE_CHECKING:
    from aidb.dap.protocol.responses import EvaluateResponse


@dataclass(frozen=True)
class AidbEvaluationResponse(OperationResponse):
    """Response from evaluating an expression.

    This wraps the EvaluationResult entity with response metadata.
    """

    result: EvaluationResult | None = None
    expression: str | None = None
    frame_id: int | None = None

    @classmethod
    def from_dap(
        cls,
        dap_response: "EvaluateResponse",
        expression: str = "",
        frame_id: int | None = None,
    ) -> "AidbEvaluationResponse":
        """Create AidbEvaluationResponse from DAP EvaluateResponse.

        This consolidates the mapper logic directly into the model.

        Parameters
        ----------
        dap_response : EvaluateResponse
            The DAP evaluate response to convert
        expression : str, optional
            The expression that was evaluated
        frame_id : int, optional
            The frame ID where evaluation occurred

        Returns
        -------
        AidbEvaluationResponse
            The converted evaluation response
        """
        from aidb.models.type_utils import map_dap_type_to_variable_type

        # Extract evaluation result
        if dap_response.body:
            body = dap_response.body

            # Extract type information
            type_str = body.type if hasattr(body, "type") and body.type else "unknown"

            result = EvaluationResult(
                expression=expression,
                result=body.result,
                type_name=type_str,
                var_type=map_dap_type_to_variable_type(type_str),
                has_children=(
                    body.variablesReference > 0
                    if hasattr(body, "variablesReference")
                    else False
                ),
                error=(
                    None
                    if dap_response.success
                    else getattr(dap_response, "message", "Evaluation failed")
                ),
            )
        else:
            # No response body - create error result
            result = EvaluationResult(
                expression=expression,
                result="",
                type_name="unknown",
                var_type=VariableType.UNKNOWN,
                error=(
                    getattr(dap_response, "message", "No response body")
                    if not dap_response.success
                    else None
                ),
            )

        success, message, error_code = OperationResponse.extract_response_fields(
            dap_response,
        )

        return cls(
            result=result,
            expression=expression,
            frame_id=frame_id,
            success=success,
            message=message,
            error_code=error_code,
        )
