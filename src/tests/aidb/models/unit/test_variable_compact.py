"""Tests for variable compact format serialization.

These tests ensure that AidbVariable and AidbVariablesResponse correctly produce compact
format for token-efficient MCP responses.
"""

import pytest

from aidb.models.entities.variable import AidbVariable, VariableType
from aidb.models.responses.variables import AidbVariablesResponse


class TestAidbVariableCompact:
    """Tests for AidbVariable.to_compact() method."""

    def test_primitive_variable_compact(self):
        """Primitive variables produce minimal compact output."""
        var = AidbVariable(
            name="x",
            value="10",
            type_name="int",
            var_type=VariableType.PRIMITIVE,
            has_children=False,
        )

        compact = var.to_compact()

        assert compact == {"v": "10", "t": "int"}
        assert "varRef" not in compact

    def test_object_variable_with_children(self):
        """Variables with children include varRef in compact output."""
        var = AidbVariable(
            name="user",
            value="User(name='Alice')",
            type_name="User",
            var_type=VariableType.OBJECT,
            has_children=True,
            id=42,
        )

        compact = var.to_compact()

        assert compact == {"v": "User(name='Alice')", "t": "User", "varRef": 42}

    def test_variable_with_children_but_no_id(self):
        """Variables with has_children=True but no id omit varRef."""
        var = AidbVariable(
            name="data",
            value="[...]",
            type_name="list",
            var_type=VariableType.ARRAY,
            has_children=True,
            id=None,
        )

        compact = var.to_compact()

        assert compact == {"v": "[...]", "t": "list"}
        assert "varRef" not in compact

    def test_variable_with_id_but_no_children(self):
        """Variables with id but has_children=False omit varRef."""
        var = AidbVariable(
            name="count",
            value="5",
            type_name="int",
            var_type=VariableType.PRIMITIVE,
            has_children=False,
            id=99,
        )

        compact = var.to_compact()

        assert compact == {"v": "5", "t": "int"}
        assert "varRef" not in compact


class TestAidbVariablesResponseCompact:
    """Tests for AidbVariablesResponse.to_compact() method."""

    def test_empty_variables_compact(self):
        """Empty variables response produces empty dict."""
        response = AidbVariablesResponse(variables={})

        compact = response.to_compact()

        assert compact == {}

    def test_single_variable_compact(self):
        """Single variable produces correctly keyed compact dict."""
        var = AidbVariable(
            name="x",
            value="42",
            type_name="int",
            var_type=VariableType.PRIMITIVE,
        )
        response = AidbVariablesResponse(variables={"x": var})

        compact = response.to_compact()

        assert compact == {"x": {"v": "42", "t": "int"}}

    def test_multiple_variables_compact(self):
        """Multiple variables all appear in compact output."""
        variables = {
            "a": AidbVariable(
                name="a",
                value="10",
                type_name="int",
                var_type=VariableType.PRIMITIVE,
            ),
            "b": AidbVariable(
                name="b",
                value="20",
                type_name="int",
                var_type=VariableType.PRIMITIVE,
            ),
            "result": AidbVariable(
                name="result",
                value="30",
                type_name="int",
                var_type=VariableType.PRIMITIVE,
            ),
        }
        response = AidbVariablesResponse(variables=variables)

        compact = response.to_compact()

        assert compact == {
            "a": {"v": "10", "t": "int"},
            "b": {"v": "20", "t": "int"},
            "result": {"v": "30", "t": "int"},
        }

    def test_mixed_variables_compact(self):
        """Mixed primitive and object variables produce correct compact format."""
        variables = {
            "count": AidbVariable(
                name="count",
                value="5",
                type_name="int",
                var_type=VariableType.PRIMITIVE,
            ),
            "items": AidbVariable(
                name="items",
                value="[1, 2, 3]",
                type_name="list",
                var_type=VariableType.ARRAY,
                has_children=True,
                id=123,
            ),
        }
        response = AidbVariablesResponse(variables=variables)

        compact = response.to_compact()

        assert compact == {
            "count": {"v": "5", "t": "int"},
            "items": {"v": "[1, 2, 3]", "t": "list", "varRef": 123},
        }


class TestCompactFormatTokenEfficiency:
    """Tests validating token efficiency of compact format."""

    def test_compact_is_smaller_than_dict(self):
        """Compact format uses fewer characters than full dict serialization."""
        var = AidbVariable(
            name="x",
            value="10",
            type_name="int",
            var_type=VariableType.PRIMITIVE,
            has_children=False,
            children={},
            id=None,
        )

        compact = var.to_compact()
        full_dict = {
            "name": var.name,
            "value": var.value,
            "type_name": var.type_name,
            "var_type": var.var_type.name,
            "has_children": var.has_children,
            "children": var.children,
            "id": var.id,
        }

        compact_str = str(compact)
        full_str = str(full_dict)

        assert len(compact_str) < len(full_str)
        # Compact should be at least 50% smaller
        assert len(compact_str) < len(full_str) * 0.5
