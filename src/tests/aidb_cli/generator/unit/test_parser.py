"""Tests for scenario YAML parser."""

import tempfile
from pathlib import Path

import pytest
import yaml

from aidb_cli.core.yaml import YamlOperationError
from aidb_cli.generators.core.parser import ScenarioParser
from aidb_cli.generators.core.types import (
    ComplexityLevel,
    LoopType,
    ScenarioCategory,
    VariableConstruct,
)


class TestScenarioParser:
    """Tests for ScenarioParser class."""

    def test_parse_valid_yaml(self, valid_scenario_yaml: str):
        """Test parsing valid YAML scenario."""
        parser = ScenarioParser()

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".yaml",
            delete=False,
        ) as f:
            f.write(valid_scenario_yaml)
            temp_file = Path(f.name)

        try:
            scenarios = parser.parse_file(temp_file)
            assert len(scenarios) == 1
            assert scenarios[0].id == "test_scenario"
            assert scenarios[0].name == "Test Scenario"
        finally:
            temp_file.unlink()

    def test_parse_missing_scenarios_key(self):
        """Test error handling for YAML without 'scenarios' key."""
        parser = ScenarioParser()
        bad_yaml = "some_key: some_value"

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".yaml",
            delete=False,
        ) as f:
            f.write(bad_yaml)
            temp_file = Path(f.name)

        try:
            with pytest.raises(ValueError, match="No scenarios found"):
                parser.parse_file(temp_file)
        finally:
            temp_file.unlink()

    def test_parse_malformed_yaml(self, malformed_yaml: str):
        """Test error handling for malformed YAML."""
        parser = ScenarioParser()

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".yaml",
            delete=False,
        ) as f:
            f.write(malformed_yaml)
            temp_file = Path(f.name)

        try:
            with pytest.raises(YamlOperationError):
                parser.parse_file(temp_file)
        finally:
            temp_file.unlink()

    def test_parse_scenario_missing_id(self):
        """Test error for scenario missing required 'id' field."""
        parser = ScenarioParser()
        data = {
            "name": "Test",
            "description": "Test scenario",
        }

        with pytest.raises(ValueError, match="missing required 'id'"):
            parser.parse_scenario(data)

    def test_parse_scenario_with_defaults(self):
        """Test that defaults are applied for optional fields."""
        parser = ScenarioParser()
        data = {
            "id": "test_id",
        }

        scenario = parser.parse_scenario(data)

        assert scenario.id == "test_id"
        assert scenario.name == "test_id"  # Default to ID
        assert scenario.description == ""
        assert scenario.category == ScenarioCategory.DEBUGGING
        assert scenario.complexity == ComplexityLevel.BASIC
        assert len(scenario.constructs) == 0

    def test_parse_scenario_with_category(self):
        """Test parsing scenario with explicit category."""
        parser = ScenarioParser()
        data = {
            "id": "test_id",
            "category": "control_flow",
        }

        scenario = parser.parse_scenario(data)
        assert scenario.category == ScenarioCategory.CONTROL_FLOW

    def test_parse_scenario_with_invalid_category(self):
        """Test that invalid category falls back to default."""
        parser = ScenarioParser()
        data = {
            "id": "test_id",
            "category": "invalid_category",
        }

        scenario = parser.parse_scenario(data)
        assert scenario.category == ScenarioCategory.DEBUGGING

    def test_parse_scenario_with_complexity(self):
        """Test parsing scenario with explicit complexity."""
        parser = ScenarioParser()
        data = {
            "id": "test_id",
            "complexity": "advanced",
        }

        scenario = parser.parse_scenario(data)
        assert scenario.complexity == ComplexityLevel.ADVANCED

    def test_parse_scenario_with_expected_markers(self):
        """Test parsing scenario with expected markers."""
        parser = ScenarioParser()
        data = {
            "id": "test_id",
            "expected_markers": {
                "var.init.x": 1,
                "func.print.hello": 1,
            },
        }

        scenario = parser.parse_scenario(data)
        assert scenario.expected_markers == {
            "var.init.x": 1,
            "func.print.hello": 1,
        }


class TestConstructParsing:
    """Tests for construct parsing."""

    def test_parse_variable_construct(self):
        """Test parsing variable construct."""
        parser = ScenarioParser()
        data = {
            "type": "variable",
            "name": "counter",
            "initial_value": 0,
            "marker": "var.init.counter",
        }

        construct = parser.parse_construct(data)

        assert isinstance(construct, VariableConstruct)
        assert construct.name == "counter"
        assert construct.initial_value == 0
        assert construct.marker == "var.init.counter"

    def test_parse_variable_with_defaults(self):
        """Test variable parsing with default values."""
        parser = ScenarioParser()
        data = {
            "type": "variable",
        }

        construct = parser.parse_construct(data)

        assert isinstance(construct, VariableConstruct)
        assert construct.name == "unnamed_var"
        assert construct.scope == "local"

    def test_parse_loop_construct(self):
        """Test parsing loop construct."""
        parser = ScenarioParser()
        data = {
            "type": "loop",
            "loop_type": "for",
            "variable": "i",
            "start": 0,
            "end": 5,
            "body": [
                {
                    "type": "print",
                    "message": "Test",
                    "marker": "func.print.test",
                },
            ],
            "marker": "flow.loop.test",
        }

        construct = parser.parse_construct(data)

        assert construct is not None
        assert construct.marker == "flow.loop.test"
        assert len(construct.body) == 1

    def test_parse_loop_with_invalid_type(self):
        """Test loop parsing with invalid loop_type falls back to FOR."""
        parser = ScenarioParser()
        data = {
            "type": "loop",
            "loop_type": "invalid",
            "marker": "flow.loop.test",
        }

        construct = parser.parse_construct(data)

        assert construct.loop_type == LoopType.FOR

    def test_parse_function_construct(self):
        """Test parsing function construct."""
        parser = ScenarioParser()
        data = {
            "type": "function",
            "name": "greet",
            "parameters": [
                {"name": "name", "type": "string"},
            ],
            "body": [
                {"type": "print", "message": "Hello", "marker": "func.print.hello"},
            ],
            "marker": "func.def.greet",
        }

        construct = parser.parse_construct(data)

        assert construct is not None
        assert construct.name == "greet"
        assert len(construct.parameters) == 1
        assert construct.parameters[0].name == "name"
        assert len(construct.body) == 1

    def test_parse_conditional_construct(self):
        """Test parsing conditional construct."""
        parser = ScenarioParser()
        data = {
            "type": "conditional",
            "condition": "x > 0",
            "true_body": [
                {"type": "print", "message": "Positive"},
            ],
            "false_body": [
                {"type": "print", "message": "Not positive"},
            ],
            "marker": "flow.if.test",
        }

        construct = parser.parse_construct(data)

        assert construct is not None
        assert construct.condition == "x > 0"
        assert len(construct.true_body) == 1
        assert len(construct.false_body) == 1

    def test_parse_exception_construct(self):
        """Test parsing exception construct."""
        parser = ScenarioParser()
        data = {
            "type": "exception",
            "body": [
                {"type": "print", "message": "Trying"},
            ],
            "catch_blocks": [
                {
                    "exception_class": "Exception",
                    "body": [
                        {"type": "print", "message": "Caught"},
                    ],
                },
            ],
            "marker": "flow.try.test",
        }

        construct = parser.parse_construct(data)

        assert construct is not None
        assert len(construct.body) == 1
        assert len(construct.catch_blocks) == 1
        assert construct.catch_blocks[0]["exception_class"] == "Exception"

    def test_parse_print_construct(self):
        """Test parsing print construct."""
        parser = ScenarioParser()
        data = {
            "type": "print",
            "message": "Hello, {name}!",
            "marker": "func.print.hello",
        }

        construct = parser.parse_construct(data)

        assert construct is not None
        assert construct.message == "Hello, {name}!"
        assert construct.marker == "func.print.hello"

    def test_parse_return_construct(self):
        """Test parsing return construct."""
        parser = ScenarioParser()
        data = {
            "type": "return",
            "value": "result",
            "marker": "func.return.result",
        }

        construct = parser.parse_construct(data)

        assert construct is not None
        assert construct.value == "result"

    def test_parse_construct_missing_type(self):
        """Test that construct without type returns None."""
        parser = ScenarioParser()
        data = {
            "name": "test",
        }

        construct = parser.parse_construct(data)
        assert construct is None

    def test_parse_construct_unknown_type(self):
        """Test that unknown construct type returns None."""
        parser = ScenarioParser()
        data = {
            "type": "unknown_type",
        }

        construct = parser.parse_construct(data)
        assert construct is None

    def test_parse_nested_constructs(self):
        """Test parsing nested constructs (loop with body)."""
        parser = ScenarioParser()
        data = {
            "type": "loop",
            "loop_type": "for",
            "variable": "i",
            "start": 0,
            "end": 3,
            "body": [
                {
                    "type": "variable",
                    "name": "temp",
                    "initial_value": 0,
                    "marker": "var.init.temp",
                },
                {
                    "type": "print",
                    "message": "Value: {temp}",
                    "marker": "func.print.value",
                },
            ],
            "marker": "flow.loop.nested",
        }

        construct = parser.parse_construct(data)

        assert construct is not None
        assert len(construct.body) == 2
        assert isinstance(construct.body[0], VariableConstruct)
        assert construct.body[0].name == "temp"
