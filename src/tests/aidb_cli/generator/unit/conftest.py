"""Fixtures for generator unit tests."""

import tempfile
from pathlib import Path
from typing import Any

import pytest

from aidb_cli.generators.core.generator import Generator
from aidb_cli.generators.core.types import (
    ConditionalConstruct,
    Construct,
    ExceptionConstruct,
    FunctionConstruct,
    LoopConstruct,
    LoopType,
    PrintConstruct,
    ReturnConstruct,
    Scenario,
    VariableConstruct,
)
from aidb_cli.generators.plugins.java_generator import JavaGenerator
from aidb_cli.generators.plugins.javascript_generator import JavaScriptGenerator
from aidb_cli.generators.plugins.python_generator import PythonGenerator


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Path:
    """Provide temporary directory for generated output."""
    output_dir = tmp_path / "generated"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


@pytest.fixture
def sample_variable_construct() -> VariableConstruct:
    """Return a simple variable construct for testing."""
    return VariableConstruct(
        type="variable",
        name="counter",
        initial_value=0,
        marker="var.init.counter",
    )


@pytest.fixture
def sample_loop_construct() -> LoopConstruct:
    """Return a simple loop construct for testing."""
    return LoopConstruct(
        type="loop",
        loop_type=LoopType.FOR,
        variable="i",
        start=0,
        end=5,
        body=[
            PrintConstruct(
                type="print",
                message="Iteration {i}",
                marker="func.print.iteration",
            ),
        ],
        marker="flow.loop.basic",
    )


@pytest.fixture
def sample_function_construct() -> FunctionConstruct:
    """Return a simple function construct for testing."""
    return FunctionConstruct(
        type="function",
        name="greet",
        parameters=[],
        body=[
            PrintConstruct(
                type="print",
                message="Hello!",
                marker="func.print.hello",
            ),
        ],
        marker="func.def.greet",
    )


@pytest.fixture
def sample_conditional_construct() -> ConditionalConstruct:
    """Return a simple conditional construct for testing."""
    return ConditionalConstruct(
        type="conditional",
        condition="x > 0",
        true_body=[
            PrintConstruct(
                type="print",
                message="Positive",
                marker="func.print.positive",
            ),
        ],
        false_body=[
            PrintConstruct(
                type="print",
                message="Non-positive",
                marker="func.print.nonpositive",
            ),
        ],
        marker="flow.if.sign",
    )


@pytest.fixture
def sample_exception_construct() -> ExceptionConstruct:
    """Return a simple exception construct for testing."""
    # Exception constructs now have parsed body constructs
    return ExceptionConstruct(
        type="exception",
        body=[],  # Empty try body
        catch_blocks=[
            {
                "exception_class": "Exception",
                "variable": "e",
                "body": [
                    PrintConstruct(
                        type="print",
                        message="Error occurred",
                        marker="func.print.error",
                    ),
                ],
            },
        ],
        marker="flow.try.basic",
    )


@pytest.fixture
def simple_scenario() -> Scenario:
    """Return a simple scenario for testing."""
    return Scenario(
        id="test_simple",
        name="Simple Test",
        description="A simple test scenario",
        category="basic",
        constructs=[
            VariableConstruct(
                type="variable",
                name="x",
                initial_value=10,
                marker="var.init.x",
            ),
            PrintConstruct(
                type="print",
                message="Value: {x}",
                marker="func.print.value",
            ),
        ],
        expected_markers={"var.init.x": 1, "func.print.value": 1},
    )


@pytest.fixture
def python_generator() -> PythonGenerator:
    """Return a Python generator instance."""
    return PythonGenerator()


@pytest.fixture
def javascript_generator() -> JavaScriptGenerator:
    """Return a JavaScript generator instance."""
    return JavaScriptGenerator()


@pytest.fixture
def java_generator() -> JavaGenerator:
    """Return a Java generator instance."""
    return JavaGenerator()


@pytest.fixture
def generator() -> Generator:
    """Return a main generator instance."""
    return Generator()


@pytest.fixture
def valid_scenario_yaml() -> str:
    """Return valid YAML for a scenario."""
    return """
scenarios:
  - id: test_scenario
    name: Test Scenario
    description: A test scenario
    category: basic
    constructs:
      - type: variable
        name: counter
        initial_value: 0
        marker: var.init.counter
      - type: loop
        loop_type: for
        variable: i
        start: 0
        end: 3
        body:
          - type: print
            message: "Count: {i}"
            marker: func.print.count
        marker: flow.loop.count
"""


@pytest.fixture
def invalid_scenario_yaml() -> str:
    """Return invalid YAML for testing error handling."""
    return """
scenarios:
  - id: test_scenario
    name: Test Scenario
    # Missing required 'constructs' field
"""


@pytest.fixture
def malformed_yaml() -> str:
    """Return malformed YAML for testing error handling."""
    return """
scenarios:
  - id: test_scenario
    name: Test Scenario
    constructs: [
      this is not valid yaml
"""
