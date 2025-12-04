"""Variable-related response models."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..base import OperationResponse, SamplingMixin
from ..entities.variable import AidbVariable, VariableType

if TYPE_CHECKING:
    from aidb.dap.protocol.responses import VariablesResponse


@dataclass(frozen=True)
class AidbVariablesResponse(OperationResponse, SamplingMixin):
    """Response containing a collection of variables."""

    variables: dict[str, AidbVariable] = field(default_factory=dict)

    @property
    def count(self) -> int:
        """Get the total number of variables."""
        return self._get_count(self.variables)

    def sample(self, n: int = 10) -> dict[str, Any]:
        """Sample n variables from the collection.

        Parameters
        ----------
        n : int, optional
            Number of variables to sample, by default 10

        Returns
        -------
        Dict[str, AidbVariable]
            Sampled variables
        """
        return self._sample_dict(self.variables, n)

    def by_type(self, var_type: Any) -> dict[str, Any]:
        """Get variables of a specific type.

        Parameters
        ----------
        var_type : VariableType
            Type of variables to get

        Returns
        -------
        Dict[str, AidbVariable]
            Variables of the specified type
        """
        return self._filter_dict(self.variables, lambda v: v.var_type == var_type)

    def primitives(self) -> dict[str, Any]:
        """Get all primitive variables.

        Returns
        -------
        Dict[str, AidbVariable]
            Primitive variables
        """
        return self.by_type(VariableType.PRIMITIVE)

    def objects(self) -> dict[str, Any]:
        """Get all object variables.

        Returns
        -------
        Dict[str, AidbVariable]
            Object variables
        """
        return self.by_type(VariableType.OBJECT)

    def arrays(self) -> dict[str, Any]:
        """Get all array variables.

        Returns
        -------
        Dict[str, AidbVariable]
            Array variables
        """
        return self.by_type(VariableType.ARRAY)

    def with_children(self) -> dict[str, Any]:
        """Get variables that have children.

        Returns
        -------
        Dict[str, AidbVariable]
            Variables with children
        """
        return self._filter_dict(self.variables, lambda v: v.has_children)

    def to_compact(self) -> dict[str, dict[str, Any]]:
        """Return compact representation of all variables.

        Returns
        -------
        dict[str, dict[str, Any]]
            Dict keyed by variable name, values are compact variable dicts
            with keys: v (value), t (type), varRef (if has children)
        """
        return {name: var.to_compact() for name, var in self.variables.items()}

    @classmethod
    def from_dap(cls, dap_response: "VariablesResponse") -> "AidbVariablesResponse":
        """Create AidbVariablesResponse from DAP VariablesResponse.

        This consolidates the mapper logic directly into the model.

        Parameters
        ----------
        dap_response : VariablesResponse
            The DAP variables response to convert

        Returns
        -------
        AidbVariablesResponse
            The converted variables response
        """
        from aidb.models.type_utils import map_dap_type_to_variable_type

        variables: dict[str, AidbVariable] = {}

        # Extract variables from DAP response
        if dap_response.body and dap_response.body.variables:
            for dap_var in dap_response.body.variables:
                variable = AidbVariable(
                    name=dap_var.name,
                    value=dap_var.value,
                    type_name=getattr(dap_var, "type", "unknown"),
                    var_type=map_dap_type_to_variable_type(
                        getattr(dap_var, "type", None),
                    ),
                    has_children=dap_var.variablesReference > 0,
                )
                variables[variable.name] = variable

        success, message, error_code = OperationResponse.extract_response_fields(
            dap_response,
        )

        return cls(
            variables=variables,
            success=success,
            message=message,
            error_code=error_code,
        )
