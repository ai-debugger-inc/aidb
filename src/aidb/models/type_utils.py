"""Type mapping utilities shared across mappers.

This module centralizes logic for mapping DAP type strings to internal VariableType
enums to ensure consistency across the codebase.
"""

from aidb.models.entities.variable import VariableType

PRIMITIVE_TYPE_KEYWORDS: set[str] = {
    "int",
    "float",
    "bool",
    "str",
    "string",
    "number",
    "double",
    "long",
}

ARRAY_TYPE_KEYWORDS: set[str] = {"list", "array", "tuple", "set", "vector"}

OBJECT_TYPE_KEYWORDS: set[str] = {"dict", "map", "hash", "object"}

FUNCTION_TYPE_KEYWORDS: set[str] = {"function", "method", "lambda", "closure"}

MODULE_TYPE_KEYWORDS: set[str] = {"module", "package", "namespace"}

CLASS_TYPE_KEYWORDS: set[str] = {"class", "type"}


def map_dap_type_to_variable_type(type_str: str | None) -> VariableType:
    """Map DAP type string to VariableType enum.

    Parameters
    ----------
    type_str : Optional[str]
        The type string from DAP (e.g., "int", "List[str]", "dict", etc.)

    Returns
    -------
    VariableType
        The mapped variable type
    """
    if not type_str:
        return VariableType.UNKNOWN

    t = type_str.lower()

    if any(x in t for x in PRIMITIVE_TYPE_KEYWORDS):
        return VariableType.PRIMITIVE

    if any(x in t for x in ARRAY_TYPE_KEYWORDS):
        return VariableType.ARRAY

    if any(x in t for x in OBJECT_TYPE_KEYWORDS):
        return VariableType.OBJECT

    if any(x in t for x in FUNCTION_TYPE_KEYWORDS):
        return VariableType.FUNCTION

    if any(x in t for x in MODULE_TYPE_KEYWORDS):
        return VariableType.MODULE

    if any(x in t for x in CLASS_TYPE_KEYWORDS):
        return VariableType.CLASS

    return VariableType.OBJECT
