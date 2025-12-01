"""Tests for Python language generator."""

from aidb_cli.generators.plugins.python_generator import PythonGenerator
from tests.aidb_cli.generator.unit.test_utils import (
    assert_valid_python,
    extract_markers,
)


class TestPythonGeneratorBasics:
    """Tests for basic Python generator functionality."""

    def test_generator_properties(self, python_generator: PythonGenerator):
        """Test generator properties."""
        assert python_generator.language_name == "python"
        assert python_generator.file_extension == ".py"
        assert python_generator.comment_prefix == "#"

    def test_format_marker(self, python_generator: PythonGenerator):
        """Test marker formatting."""
        marker = python_generator.format_marker("var.init.x")
        assert marker == "#:var.init.x:"


class TestVariableGeneration:
    """Tests for variable generation."""

    def test_generate_variable_with_initial_value(
        self,
        python_generator: PythonGenerator,
        sample_variable_construct,
    ):
        """Test generating variable with initial value."""
        code = python_generator.generate_variable(sample_variable_construct)

        assert "counter = 0" in code
        assert "#:var.init.counter:" in code
        assert_valid_python(code)

    def test_generate_variable_increment(self, python_generator: PythonGenerator):
        """Test generating variable increment."""
        from aidb_cli.generators.core.types import VariableConstruct

        construct = VariableConstruct(
            type="variable",
            name="count",
            operation="increment",
            marker="var.inc.count",
        )

        code = python_generator.generate_variable(construct)

        assert "count += 1" in code
        assert "#:var.inc.count:" in code

    def test_generate_variable_decrement(self, python_generator: PythonGenerator):
        """Test generating variable decrement."""
        from aidb_cli.generators.core.types import VariableConstruct

        construct = VariableConstruct(
            type="variable",
            name="count",
            operation="decrement",
            marker="var.dec.count",
        )

        code = python_generator.generate_variable(construct)

        assert "count -= 1" in code

    def test_generate_variable_add(self, python_generator: PythonGenerator):
        """Test generating variable add operation."""
        from aidb_cli.generators.core.types import VariableConstruct

        construct = VariableConstruct(
            type="variable",
            name="total",
            operation="add",
            value=5,
            marker="var.add.total",
        )

        code = python_generator.generate_variable(construct)

        assert "total += 5" in code

    def test_generate_variable_assign(self, python_generator: PythonGenerator):
        """Test generating variable assignment."""
        from aidb_cli.generators.core.types import VariableConstruct

        construct = VariableConstruct(
            type="variable",
            name="result",
            operation="assign",
            value=42,
            marker="var.assign.result",
        )

        code = python_generator.generate_variable(construct)

        assert "result = 42" in code

    def test_generate_variable_no_value(self, python_generator: PythonGenerator):
        """Test generating variable without value (None)."""
        from aidb_cli.generators.core.types import VariableConstruct

        construct = VariableConstruct(
            type="variable",
            name="empty",
            marker="var.init.empty",
        )

        code = python_generator.generate_variable(construct)

        assert "empty = None" in code


class TestLoopGeneration:
    """Tests for loop generation."""

    def test_generate_for_loop(
        self,
        python_generator: PythonGenerator,
        sample_loop_construct,
    ):
        """Test generating for loop."""
        code = python_generator.generate_loop(sample_loop_construct)

        assert "for i in range(0, 5):" in code
        assert "#:flow.loop.basic:" in code
        assert_valid_python(code)

    def test_generate_for_loop_with_step(self, python_generator: PythonGenerator):
        """Test generating for loop with custom step."""
        from aidb_cli.generators.core.types import LoopConstruct, LoopType

        construct = LoopConstruct(
            type="loop",
            loop_type=LoopType.FOR,
            variable="i",
            start=0,
            end=10,
            step=2,
            body=[],
            marker="flow.loop.step",
        )

        code = python_generator.generate_loop(construct)

        assert "range(0, 10, 2)" in code

    def test_generate_while_loop(self, python_generator: PythonGenerator):
        """Test generating while loop."""
        from aidb_cli.generators.core.types import LoopConstruct, LoopType

        construct = LoopConstruct(
            type="loop",
            loop_type=LoopType.WHILE,
            variable="i",
            condition="i < 10",
            body=[],
            marker="flow.loop.while",
        )

        code = python_generator.generate_loop(construct)

        assert "while i < 10:" in code
        assert "#:flow.loop.while:" in code

    def test_generate_foreach_loop(self, python_generator: PythonGenerator):
        """Test generating for-each loop."""
        from aidb_cli.generators.core.types import LoopConstruct, LoopType

        construct = LoopConstruct(
            type="loop",
            loop_type=LoopType.FOR_EACH,
            variable="item",
            iterable="items",
            body=[],
            marker="flow.loop.foreach",
        )

        code = python_generator.generate_loop(construct)

        assert "for item in items:" in code

    def test_generate_loop_with_body(self, python_generator: PythonGenerator):
        """Test generating loop with body."""
        from aidb_cli.generators.core.types import (
            LoopConstruct,
            LoopType,
            PrintConstruct,
        )

        construct = LoopConstruct(
            type="loop",
            loop_type=LoopType.FOR,
            variable="i",
            start=0,
            end=3,
            body=[
                PrintConstruct(
                    type="print",
                    message="Iteration {i}",
                    marker="func.print.iter",
                ),
            ],
            marker="flow.loop.body",
        )

        code = python_generator.generate_loop(construct)

        assert "for i in range(0, 3):" in code
        assert "print(" in code
        assert_valid_python(code)


class TestFunctionGeneration:
    """Tests for function generation."""

    def test_generate_function_definition(
        self,
        python_generator: PythonGenerator,
        sample_function_construct,
    ):
        """Test generating function definition."""
        code = python_generator.generate_function(sample_function_construct)

        assert "def greet():" in code
        assert "#:func.def.greet:" in code
        assert_valid_python(code)

    def test_generate_function_with_parameters(
        self,
        python_generator: PythonGenerator,
    ):
        """Test generating function with parameters."""
        from aidb_cli.generators.core.types import FunctionConstruct, Parameter

        construct = FunctionConstruct(
            type="function",
            name="add",
            parameters=[
                Parameter(name="a", data_type=None),
                Parameter(name="b", data_type=None),
            ],
            body=[],
            marker="func.def.add",
        )

        code = python_generator.generate_function(construct)

        assert "def add(a, b):" in code

    def test_generate_function_call(self, python_generator: PythonGenerator):
        """Test generating function call."""
        from aidb_cli.generators.core.types import FunctionConstruct

        construct = FunctionConstruct(
            type="function",
            name="calculate",
            operation="call",
            arguments=["x", "y"],
            marker="func.call.calculate",
        )

        code = python_generator.generate_function(construct)

        assert "calculate(x, y)" in code

    def test_generate_function_call_with_result(
        self,
        python_generator: PythonGenerator,
    ):
        """Test generating function call with result variable."""
        from aidb_cli.generators.core.types import FunctionConstruct

        construct = FunctionConstruct(
            type="function",
            name="add",
            operation="call",
            arguments=["a", "b"],
            result_variable="sum",
            marker="func.call.add",
        )

        code = python_generator.generate_function(construct)

        assert "sum = add(a, b)" in code


class TestConditionalGeneration:
    """Tests for conditional generation."""

    def test_generate_conditional(
        self,
        python_generator: PythonGenerator,
        sample_conditional_construct,
    ):
        """Test generating conditional."""
        code = python_generator.generate_conditional(sample_conditional_construct)

        assert "if x > 0:" in code
        assert "else:" in code
        assert_valid_python(code)

    def test_generate_conditional_without_else(
        self,
        python_generator: PythonGenerator,
    ):
        """Test generating conditional without else block."""
        from aidb_cli.generators.core.types import (
            ConditionalConstruct,
            PrintConstruct,
        )

        construct = ConditionalConstruct(
            type="conditional",
            condition="value > 10",
            true_body=[
                PrintConstruct(
                    type="print",
                    message="Large value",
                    marker="func.print.large",
                ),
            ],
            false_body=[],
            marker="flow.if.check",
        )

        code = python_generator.generate_conditional(construct)

        assert "if value > 10:" in code
        assert "else:" not in code  # Should not generate empty else


class TestExceptionGeneration:
    """Tests for exception generation."""

    def test_generate_exception(
        self,
        python_generator: PythonGenerator,
        sample_exception_construct,
    ):
        """Test generating exception handling."""
        code = python_generator.generate_exception(sample_exception_construct)

        assert "try:" in code
        assert "except" in code
        assert_valid_python(code)

    def test_generate_exception_with_finally(
        self,
        python_generator: PythonGenerator,
    ):
        """Test generating exception with finally block."""
        from aidb_cli.generators.core.types import ExceptionConstruct, PrintConstruct

        construct = ExceptionConstruct(
            type="exception",
            body=[
                PrintConstruct(
                    type="print",
                    message="Trying",
                    marker="func.print.try",
                ),
            ],
            catch_blocks=[
                {
                    "exception_class": "Exception",
                    "variable": "e",
                    "body": [
                        PrintConstruct(
                            type="print",
                            message="Error",
                            marker="func.print.error",
                        ),
                    ],
                },
            ],
            finally_block={
                "body": [
                    PrintConstruct(
                        type="print",
                        message="Cleanup",
                        marker="func.print.cleanup",
                    ),
                ],
            },
            marker="flow.try.complete",
        )

        code = python_generator.generate_exception(construct)

        assert "try:" in code
        assert "except" in code
        assert "finally:" in code


class TestArrayGeneration:
    """Tests for array/list generation."""

    def test_generate_array_with_values(self, python_generator: PythonGenerator):
        """Test generating array with explicit values."""
        from aidb_cli.generators.core.types import ArrayConstruct

        construct = ArrayConstruct(
            name="numbers",
            values=[10, 20, 30],
            marker="var.init.array",
        )
        code = python_generator.generate_array(construct)

        assert "numbers = [10, 20, 30]" in code
        assert "#:var.init.array:" in code
        assert_valid_python(code)

    def test_generate_array_with_range(self, python_generator: PythonGenerator):
        """Test generating array with range initialization."""
        from aidb_cli.generators.core.types import ArrayConstruct

        construct = ArrayConstruct(
            name="nums",
            size=100,
            initialize="range",
            marker="var.range.array",
        )
        code = python_generator.generate_array(construct)

        assert "nums = list(range(100))" in code
        assert "#:var.range.array:" in code
        assert_valid_python(code)

    def test_generate_array_with_zeros(self, python_generator: PythonGenerator):
        """Test generating array with zeros."""
        from aidb_cli.generators.core.types import ArrayConstruct

        construct = ArrayConstruct(
            name="zeroes",
            size=50,
            initialize="zeros",
            marker="var.zeros.array",
        )
        code = python_generator.generate_array(construct)

        assert "zeroes = [0] * 50" in code
        assert "#:var.zeros.array:" in code
        assert_valid_python(code)

    def test_generate_empty_array(self, python_generator: PythonGenerator):
        """Test generating empty array."""
        from aidb_cli.generators.core.types import ArrayConstruct

        construct = ArrayConstruct(
            name="empty",
            marker="var.empty.array",
        )
        code = python_generator.generate_array(construct)

        assert "empty = []" in code
        assert "#:var.empty.array:" in code
        assert_valid_python(code)


class TestPrintGeneration:
    """Tests for print statement generation."""

    def test_generate_print_simple(self, python_generator: PythonGenerator):
        """Test generating simple print statement."""
        from aidb_cli.generators.core.types import PrintConstruct

        construct = PrintConstruct(
            type="print",
            message="Hello, World!",
            marker="func.print.hello",
        )

        code = python_generator.generate_print(construct)

        assert 'print("Hello, World!")' in code
        assert "#:func.print.hello:" in code

    def test_generate_print_with_variable(self, python_generator: PythonGenerator):
        """Test generating print with variable interpolation."""
        from aidb_cli.generators.core.types import PrintConstruct

        construct = PrintConstruct(
            type="print",
            message="Value: {x}",
            marker="func.print.value",
        )

        code = python_generator.generate_print(construct)

        assert "print(f" in code or "print(" in code
        assert "#:func.print.value:" in code


class TestProgramGeneration:
    """Tests for complete program generation."""

    def test_format_program(
        self,
        python_generator: PythonGenerator,
        simple_scenario,
    ):
        """Test formatting complete program."""
        code = python_generator.generate_program(simple_scenario)

        # Should have main function wrapper
        assert "def main():" in code
        assert 'if __name__ == "__main__":' in code
        assert "main()" in code

        # Should be valid Python
        assert_valid_python(code)

    def test_validate_syntax_valid_code(self, python_generator: PythonGenerator):
        """Test syntax validation with valid code."""
        code = """
def main():
    x = 10
    print(x)

if __name__ == "__main__":
    main()
"""
        result = python_generator.validate_syntax(code)

        assert result.is_valid
        assert len(result.errors) == 0

    def test_validate_syntax_invalid_code(self, python_generator: PythonGenerator):
        """Test syntax validation with invalid code."""
        code = "def broken("  # Missing closing paren

        result = python_generator.validate_syntax(code)

        assert not result.is_valid
        assert len(result.errors) > 0


class TestMarkerEmbedding:
    """Tests for marker embedding."""

    def test_markers_present_in_generated_code(
        self,
        python_generator: PythonGenerator,
        simple_scenario,
    ):
        """Test that all markers are embedded in generated code."""
        code = python_generator.generate_program(simple_scenario)

        markers = extract_markers(code, "#")

        # Check expected markers are present
        for marker_name in simple_scenario.expected_markers:
            assert marker_name in markers, f"Missing marker: {marker_name}"

    def test_marker_format_consistency(self, python_generator: PythonGenerator):
        """Test that markers have consistent format."""
        from aidb_cli.generators.core.types import VariableConstruct

        construct = VariableConstruct(
            type="variable",
            name="test",
            initial_value=1,
            marker="var.init.test",
        )

        code = python_generator.generate_variable(construct)

        # Should have marker in format #:category.action.id:
        assert "#:var.init.test:" in code


class TestSyntaxErrorGeneration:
    """Tests for syntax error generation."""

    def test_generate_syntax_error_unclosed_bracket(
        self,
        python_generator: PythonGenerator,
    ):
        """Test generating syntax error with unclosed bracket."""
        from aidb_cli.generators.core.types import SyntaxErrorConstruct

        construct = SyntaxErrorConstruct(
            error_type="unclosed_bracket",
            marker="error.syntax.unclosed",
        )

        code = python_generator.generate_syntax_error(construct)

        assert "def broken_function" in code
        assert "#:error.syntax.unclosed:" in code
        assert "(" in code

    def test_generate_syntax_error_missing_colon(
        self,
        python_generator: PythonGenerator,
    ):
        """Test generating syntax error with missing colon."""
        from aidb_cli.generators.core.types import SyntaxErrorConstruct

        construct = SyntaxErrorConstruct(
            error_type="missing_colon",
            marker="error.syntax.colon",
        )

        code = python_generator.generate_syntax_error(construct)

        assert "if True" in code
        first_line = code.split("#:")[0]
        assert ":" not in first_line
        assert "#:error.syntax.colon:" in code

    def test_generate_syntax_error_indentation(
        self,
        python_generator: PythonGenerator,
    ):
        """Test generating syntax error with indentation error."""
        from aidb_cli.generators.core.types import SyntaxErrorConstruct

        construct = SyntaxErrorConstruct(
            error_type="indentation_error",
            marker="error.syntax.indent",
        )

        code = python_generator.generate_syntax_error(construct)

        assert "def bad_indent" in code
        assert "#:error.syntax.indent:" in code

    def test_generate_syntax_error_with_code_snippet(
        self,
        python_generator: PythonGenerator,
    ):
        """Test generating syntax error with custom code snippet."""
        from aidb_cli.generators.core.types import SyntaxErrorConstruct

        construct = SyntaxErrorConstruct(
            code_snippet="x = [1, 2, 3",
            marker="error.syntax.custom",
        )

        code = python_generator.generate_syntax_error(construct)

        assert "x = [1, 2, 3" in code
        assert "#:error.syntax.custom:" in code

    def test_syntax_error_has_marker(self, python_generator: PythonGenerator):
        """Test that syntax error includes marker."""
        from aidb_cli.generators.core.types import SyntaxErrorConstruct

        construct = SyntaxErrorConstruct(
            error_type="unclosed_bracket",
            marker="error.test.marker",
        )

        code = python_generator.generate_syntax_error(construct)

        assert "#:error.test.marker:" in code


class TestInfiniteLoopGeneration:
    """Tests for infinite loop generation."""

    def test_infinite_loop_with_true_condition(
        self,
        python_generator: PythonGenerator,
    ):
        """Test generating while True infinite loop."""
        from aidb_cli.generators.core.types import LoopConstruct, LoopType

        construct = LoopConstruct(
            loop_type=LoopType.WHILE,
            condition="True",
            marker="flow.loop.infinite",
        )

        code = python_generator.generate_loop(construct)

        assert "while True:" in code
        assert "#:flow.loop.infinite:" in code

    def test_infinite_loop_with_lowercase_true(
        self,
        python_generator: PythonGenerator,
    ):
        """Test that lowercase 'true' gets converted to 'True' in Python."""
        from aidb_cli.generators.core.types import LoopConstruct, LoopType

        construct = LoopConstruct(
            loop_type=LoopType.WHILE,
            condition="true",
            marker="flow.loop.infinite",
        )

        code = python_generator.generate_loop(construct)

        assert "while True:" in code
        assert "#:flow.loop.infinite:" in code

    def test_infinite_loop_with_counter_body(
        self,
        python_generator: PythonGenerator,
    ):
        """Test infinite loop with counter increment body."""
        from aidb_cli.generators.core.types import (
            LoopConstruct,
            LoopType,
            VariableConstruct,
        )

        body_construct = VariableConstruct(
            name="counter",
            operation="increment",
            marker="var.increment.counter",
        )

        construct = LoopConstruct(
            loop_type=LoopType.WHILE,
            condition="True",
            marker="flow.loop.infinite",
            body=[body_construct],
        )

        code = python_generator.generate_loop(construct)

        assert "while True:" in code
        assert "counter += 1" in code
        assert "#:flow.loop.infinite:" in code
        assert "#:var.increment.counter:" in code

    def test_infinite_loop_with_one_literal(
        self,
        python_generator: PythonGenerator,
    ):
        """Test infinite loop using while 1: pattern."""
        from aidb_cli.generators.core.types import LoopConstruct, LoopType

        construct = LoopConstruct(
            loop_type=LoopType.WHILE,
            condition="1",
            marker="flow.loop.infinite",
        )

        code = python_generator.generate_loop(construct)

        assert "while 1:" in code
        assert "#:flow.loop.infinite:" in code

    def test_infinite_loop_has_marker(self, python_generator: PythonGenerator):
        """Test that infinite loop includes marker."""
        from aidb_cli.generators.core.types import LoopConstruct, LoopType

        construct = LoopConstruct(
            loop_type=LoopType.WHILE,
            condition="True",
            marker="test.infinite.marker",
        )

        code = python_generator.generate_loop(construct)

        assert "#:test.infinite.marker:" in code


class TestRecursiveFunctionGeneration:
    """Tests for recursive function generation."""

    def test_recursive_function_definition(
        self,
        python_generator: PythonGenerator,
    ):
        """Test generating recursive function definition."""
        from aidb_cli.generators.core.types import (
            FunctionConstruct,
            Parameter,
            PrintConstruct,
        )

        # Function body with recursive call
        print_construct = PrintConstruct(
            message="Depth: {depth}",
            marker="func.print.depth",
        )
        call_construct = FunctionConstruct(
            name="recursive_function",
            operation="call",
            arguments=["depth + 1"],
            marker="func.call.recursive",
        )

        construct = FunctionConstruct(
            name="recursive_function",
            parameters=[Parameter(name="depth")],
            body=[print_construct, call_construct],
            marker="func.def.recursive",
        )

        code = python_generator.generate_function(construct)

        assert "def recursive_function(depth):" in code
        assert 'print(f"Depth: {depth}")' in code
        assert "recursive_function(depth + 1)" in code
        assert "#:func.def.recursive:" in code

    def test_recursive_function_call(
        self,
        python_generator: PythonGenerator,
    ):
        """Test generating recursive function call."""
        from aidb_cli.generators.core.types import FunctionConstruct

        construct = FunctionConstruct(
            name="recursive_function",
            operation="call",
            arguments=[0],
            marker="func.call.start",
        )

        code = python_generator.generate_function(construct)

        assert "recursive_function(0)" in code
        assert "#:func.call.start:" in code

    def test_recursive_with_parameter(
        self,
        python_generator: PythonGenerator,
    ):
        """Test recursive function with parameter."""
        from aidb_cli.generators.core.types import (
            FunctionConstruct,
            Parameter,
        )

        call_construct = FunctionConstruct(
            name="recurse",
            operation="call",
            arguments=["n - 1"],
            marker="func.call.recurse",
        )

        construct = FunctionConstruct(
            name="recurse",
            parameters=[Parameter(name="n")],
            body=[call_construct],
            marker="func.def.recurse",
        )

        code = python_generator.generate_function(construct)

        assert "def recurse(n):" in code
        assert "recurse(n - 1)" in code
        assert "#:func.def.recurse:" in code

    def test_recursive_with_multiple_calls(
        self,
        python_generator: PythonGenerator,
    ):
        """Test recursive function with multiple recursive calls."""
        from aidb_cli.generators.core.types import FunctionConstruct, Parameter

        call1 = FunctionConstruct(
            name="fib",
            operation="call",
            arguments=["n - 1"],
            marker="func.call.fib1",
        )
        call2 = FunctionConstruct(
            name="fib",
            operation="call",
            arguments=["n - 2"],
            marker="func.call.fib2",
        )

        construct = FunctionConstruct(
            name="fib",
            parameters=[Parameter(name="n")],
            body=[call1, call2],
            marker="func.def.fib",
        )

        code = python_generator.generate_function(construct)

        assert "def fib(n):" in code
        assert "fib(n - 1)" in code
        assert "fib(n - 2)" in code

    def test_recursive_has_markers(
        self,
        python_generator: PythonGenerator,
    ):
        """Test that recursive function includes all markers."""
        from aidb_cli.generators.core.types import (
            FunctionConstruct,
            Parameter,
        )

        call_construct = FunctionConstruct(
            name="test_func",
            operation="call",
            arguments=["x + 1"],
            marker="test.call.marker",
        )

        construct = FunctionConstruct(
            name="test_func",
            parameters=[Parameter(name="x")],
            body=[call_construct],
            marker="test.def.marker",
        )

        code = python_generator.generate_function(construct)

        assert "#:test.def.marker:" in code
        assert "#:test.call.marker:" in code


class TestLargeArrayGeneration:
    """Tests for large array generation."""

    def test_large_array_with_range(self, python_generator):
        """Test generation of large array with range initialization."""
        from aidb_cli.generators.core.types import ArrayConstruct

        construct = ArrayConstruct(
            name="large_numbers",
            size=3000,
            initialize="range",
            marker="var.create.large_array",
        )

        code = python_generator.generate_array(construct)

        assert "large_numbers = list(range(3000))" in code
        assert "#:var.create.large_array:" in code

    def test_large_array_iteration(self, python_generator):
        """Test generation of loop iterating over large array."""
        from aidb_cli.generators.core.types import (
            ConditionalConstruct,
            LoopConstruct,
            LoopType,
            PrintConstruct,
        )

        print_construct = PrintConstruct(
            message="Checkpoint: {item}",
            marker="func.print.checkpoint",
        )
        conditional_construct = ConditionalConstruct(
            condition="item % 500 == 0",
            true_body=[print_construct],
            marker="flow.if.checkpoint",
        )
        loop_construct = LoopConstruct(
            loop_type=LoopType.FOR_EACH,
            variable="item",
            iterable="large_numbers",
            body=[conditional_construct],
            marker="flow.loop.iterate",
        )

        code = python_generator.generate_loop(loop_construct)

        assert "for item in large_numbers:" in code
        assert "if item % 500 == 0:" in code
        assert 'print(f"Checkpoint: {item}")' in code
        assert "#:flow.loop.iterate:" in code
        assert "#:flow.if.checkpoint:" in code
        assert "#:func.print.checkpoint:" in code

    def test_large_array_with_zeros(self, python_generator):
        """Test generation of large array initialized with zeros."""
        from aidb_cli.generators.core.types import ArrayConstruct

        construct = ArrayConstruct(
            name="zeros_array",
            size=3000,
            initialize="zeros",
            marker="var.create.zeros",
        )

        code = python_generator.generate_array(construct)

        assert "zeros_array = [0] * 3000" in code
        assert "#:var.create.zeros:" in code

    def test_large_array_checkpoint_logic(self, python_generator):
        """Test generation of checkpoint logic within large array iteration."""
        from aidb_cli.generators.core.types import ConditionalConstruct, PrintConstruct

        print_construct = PrintConstruct(
            message="Checkpoint: {item}",
            marker="func.print.checkpoint",
        )
        conditional_construct = ConditionalConstruct(
            condition="item % 500 == 0",
            true_body=[print_construct],
            marker="flow.if.checkpoint",
        )

        code = python_generator.generate_conditional(conditional_construct)

        assert "if item % 500 == 0:" in code
        assert 'print(f"Checkpoint: {item}")' in code
        assert "#:flow.if.checkpoint:" in code
        assert "#:func.print.checkpoint:" in code

    def test_large_array_scenario_markers(self, python_generator):
        """Test all markers are present in large array scenario."""
        from aidb_cli.generators.core.types import (
            ArrayConstruct,
            ConditionalConstruct,
            LoopConstruct,
            LoopType,
            PrintConstruct,
        )

        # Array creation
        array_construct = ArrayConstruct(
            name="large_numbers",
            size=3000,
            initialize="range",
            marker="var.create.large_array",
        )

        # Loop with conditional and print
        print_construct = PrintConstruct(
            message="Checkpoint: {item}",
            marker="func.print.checkpoint",
        )
        conditional_construct = ConditionalConstruct(
            condition="item % 500 == 0",
            true_body=[print_construct],
            marker="flow.if.checkpoint",
        )
        loop_construct = LoopConstruct(
            loop_type=LoopType.FOR_EACH,
            variable="item",
            iterable="large_numbers",
            body=[conditional_construct],
            marker="flow.loop.iterate",
        )

        array_code = python_generator.generate_array(array_construct)
        loop_code = python_generator.generate_loop(loop_construct)

        # Verify all 4 expected markers
        assert "#:var.create.large_array:" in array_code
        assert "#:flow.loop.iterate:" in loop_code
        assert "#:flow.if.checkpoint:" in loop_code
        assert "#:func.print.checkpoint:" in loop_code
