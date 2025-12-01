"""Tests for Java language generator."""

from aidb_cli.generators.plugins.java_generator import JavaGenerator
from tests.aidb_cli.generator.unit.test_utils import assert_valid_java, extract_markers


class TestJavaGeneratorBasics:
    """Tests for basic Java generator functionality."""

    def test_generator_properties(self, java_generator: JavaGenerator):
        """Test generator properties."""
        assert java_generator.language_name == "java"
        assert java_generator.file_extension == ".java"
        assert java_generator.comment_prefix == "//"

    def test_format_marker(self, java_generator: JavaGenerator):
        """Test marker formatting."""
        marker = java_generator.format_marker("var.init.x")
        assert marker == "//:var.init.x:"


class TestVariableGeneration:
    """Tests for variable generation."""

    def test_generate_variable_with_initial_value(
        self,
        java_generator: JavaGenerator,
        sample_variable_construct,
    ):
        """Test generating variable with initial value."""
        code = java_generator.generate_variable(sample_variable_construct)

        assert "int counter = 0" in code
        assert "//:var.init.counter:" in code

    def test_generate_variable_increment(self, java_generator: JavaGenerator):
        """Test generating variable increment."""
        from aidb_cli.generators.core.types import VariableConstruct

        construct = VariableConstruct(
            type="variable",
            name="count",
            operation="increment",
            marker="var.inc.count",
        )

        code = java_generator.generate_variable(construct)

        assert "count++" in code or "count += 1" in code
        assert "//:var.inc.count:" in code

    def test_generate_variable_decrement(self, java_generator: JavaGenerator):
        """Test generating variable decrement."""
        from aidb_cli.generators.core.types import VariableConstruct

        construct = VariableConstruct(
            type="variable",
            name="count",
            operation="decrement",
            marker="var.dec.count",
        )

        code = java_generator.generate_variable(construct)

        assert "count--" in code or "count -= 1" in code

    def test_generate_variable_add(self, java_generator: JavaGenerator):
        """Test generating variable add operation."""
        from aidb_cli.generators.core.types import VariableConstruct

        construct = VariableConstruct(
            type="variable",
            name="total",
            operation="add",
            value=5,
            marker="var.add.total",
        )

        code = java_generator.generate_variable(construct)

        assert "total += 5" in code

    def test_generate_variable_assign(self, java_generator: JavaGenerator):
        """Test generating variable assignment."""
        from aidb_cli.generators.core.types import VariableConstruct

        construct = VariableConstruct(
            type="variable",
            name="result",
            operation="assign",
            value=42,
            marker="var.assign.result",
        )

        code = java_generator.generate_variable(construct)

        assert "result = 42" in code

    def test_generate_variable_no_value(self, java_generator: JavaGenerator):
        """Test generating variable without value (null)."""
        from aidb_cli.generators.core.types import VariableConstruct

        construct = VariableConstruct(
            type="variable",
            name="empty",
            marker="var.init.empty",
        )

        code = java_generator.generate_variable(construct)

        assert "Object empty = null" in code


class TestLoopGeneration:
    """Tests for loop generation."""

    def test_generate_for_loop(
        self,
        java_generator: JavaGenerator,
        sample_loop_construct,
    ):
        """Test generating for loop."""
        code = java_generator.generate_loop(sample_loop_construct)

        assert "for (int i = 0; i < 5; i++)" in code
        assert "//:flow.loop.basic:" in code

    def test_generate_for_loop_with_step(self, java_generator: JavaGenerator):
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

        code = java_generator.generate_loop(construct)

        assert "i += 2" in code

    def test_generate_while_loop(self, java_generator: JavaGenerator):
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

        code = java_generator.generate_loop(construct)

        assert "while (i < 10)" in code
        assert "//:flow.loop.while:" in code

    def test_generate_foreach_loop(self, java_generator: JavaGenerator):
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

        code = java_generator.generate_loop(construct)

        assert "for (var item : items)" in code

    def test_generate_loop_with_body(self, java_generator: JavaGenerator):
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

        code = java_generator.generate_loop(construct)

        assert "for (int i = 0; i < 3; i++)" in code
        assert "System.out.println(" in code


class TestFunctionGeneration:
    """Tests for function generation."""

    def test_generate_function_definition(
        self,
        java_generator: JavaGenerator,
        sample_function_construct,
    ):
        """Test generating function definition."""
        code = java_generator.generate_function(sample_function_construct)

        assert "public static void greet()" in code
        assert "//:func.def.greet:" in code

    def test_generate_function_with_parameters(
        self,
        java_generator: JavaGenerator,
    ):
        """Test generating function with parameters."""
        from aidb_cli.generators.core.types import FunctionConstruct, Parameter

        construct = FunctionConstruct(
            type="function",
            name="add",
            parameters=[
                Parameter(name="a", data_type="int"),
                Parameter(name="b", data_type="int"),
            ],
            body=[],
            marker="func.def.add",
        )

        code = java_generator.generate_function(construct)

        assert "public static void add(int a, int b)" in code

    def test_generate_function_call(self, java_generator: JavaGenerator):
        """Test generating function call."""
        from aidb_cli.generators.core.types import FunctionConstruct

        construct = FunctionConstruct(
            type="function",
            name="calculate",
            operation="call",
            arguments=["x", "y"],
            marker="func.call.calculate",
        )

        code = java_generator.generate_function(construct)

        assert "calculate(x, y)" in code

    def test_generate_function_call_with_result(
        self,
        java_generator: JavaGenerator,
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

        code = java_generator.generate_function(construct)

        assert "var sum = add(a, b)" in code


class TestConditionalGeneration:
    """Tests for conditional generation."""

    def test_generate_conditional(
        self,
        java_generator: JavaGenerator,
        sample_conditional_construct,
    ):
        """Test generating conditional."""
        code = java_generator.generate_conditional(sample_conditional_construct)

        assert "if (x > 0)" in code
        assert "else" in code

    def test_generate_conditional_without_else(
        self,
        java_generator: JavaGenerator,
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

        code = java_generator.generate_conditional(construct)

        assert "if (value > 10)" in code
        # Should not generate empty else
        lines = code.strip().split("\n")
        assert not any(line.strip() == "else {" for line in lines)


class TestExceptionGeneration:
    """Tests for exception generation."""

    def test_generate_exception(
        self,
        java_generator: JavaGenerator,
        sample_exception_construct,
    ):
        """Test generating exception handling."""
        code = java_generator.generate_exception(sample_exception_construct)

        assert "try" in code
        assert "catch" in code

    def test_generate_exception_with_finally(
        self,
        java_generator: JavaGenerator,
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

        code = java_generator.generate_exception(construct)

        assert "try" in code
        assert "catch" in code
        assert "finally" in code


class TestArrayGeneration:
    """Tests for array generation."""

    def test_generate_array_with_values(self, java_generator: JavaGenerator):
        """Test generating array with explicit values."""
        from aidb_cli.generators.core.types import ArrayConstruct

        construct = ArrayConstruct(
            name="numbers",
            values=[10, 20, 30],
            marker="var.init.array",
        )
        code = java_generator.generate_array(construct)

        assert "int[] numbers = {10, 20, 30}" in code
        assert "//:var.init.array:" in code

    def test_generate_array_with_range(self, java_generator: JavaGenerator):
        """Test generating array with range initialization."""
        from aidb_cli.generators.core.types import ArrayConstruct

        construct = ArrayConstruct(
            name="nums",
            size=100,
            initialize="range",
            marker="var.range.array",
        )
        code = java_generator.generate_array(construct)

        assert "IntStream.range(0, 100)" in code
        assert "//:var.range.array:" in code

    def test_generate_array_with_zeros(self, java_generator: JavaGenerator):
        """Test generating array with zeros."""
        from aidb_cli.generators.core.types import ArrayConstruct

        construct = ArrayConstruct(
            name="zeroes",
            size=50,
            initialize="zeros",
            marker="var.zeros.array",
        )
        code = java_generator.generate_array(construct)

        assert "int[] zeroes = new int[50]" in code
        assert "//:var.zeros.array:" in code

    def test_generate_empty_array(self, java_generator: JavaGenerator):
        """Test generating empty array."""
        from aidb_cli.generators.core.types import ArrayConstruct

        construct = ArrayConstruct(
            name="empty",
            marker="var.empty.array",
        )
        code = java_generator.generate_array(construct)

        assert "int[] empty = {}" in code
        assert "//:var.empty.array:" in code


class TestPrintGeneration:
    """Tests for print statement generation."""

    def test_generate_print_simple(self, java_generator: JavaGenerator):
        """Test generating simple print statement."""
        from aidb_cli.generators.core.types import PrintConstruct

        construct = PrintConstruct(
            type="print",
            message="Hello, World!",
            marker="func.print.hello",
        )

        code = java_generator.generate_print(construct)

        assert 'System.out.println("Hello, World!")' in code
        assert "//:func.print.hello:" in code

    def test_generate_print_with_variable(self, java_generator: JavaGenerator):
        """Test generating print with variable interpolation."""
        from aidb_cli.generators.core.types import PrintConstruct

        construct = PrintConstruct(
            type="print",
            message="Value: {x}",
            marker="func.print.value",
        )

        code = java_generator.generate_print(construct)

        assert "System.out.println(" in code
        assert "//:func.print.value:" in code


class TestProgramGeneration:
    """Tests for complete program generation."""

    def test_format_program(
        self,
        java_generator: JavaGenerator,
        simple_scenario,
    ):
        """Test formatting complete program."""
        code = java_generator.generate_program(simple_scenario)

        # Should have class and main method
        assert "public class TestProgram" in code
        assert "public static void main(String[] args)" in code

        # Should be valid Java
        assert_valid_java(code)

    def test_validate_syntax_valid_code(self, java_generator: JavaGenerator):
        """Test syntax validation with valid code."""
        code = """
public class TestProgram {
    public static void main(String[] args) {
        int x = 10;
        System.out.println(x);
    }
}
"""
        result = java_generator.validate_syntax(code)

        assert result.is_valid
        assert len(result.errors) == 0

    def test_validate_syntax_invalid_code(self, java_generator: JavaGenerator):
        """Test syntax validation with invalid code."""
        code = """
public class TestProgram {
    public static void main(String[] args) {
        if (true) {
    }
"""
        result = java_generator.validate_syntax(code)

        assert not result.is_valid
        assert len(result.errors) > 0
        assert "Unbalanced braces" in result.errors[0]


class TestMarkerEmbedding:
    """Tests for marker embedding."""

    def test_markers_present_in_generated_code(
        self,
        java_generator: JavaGenerator,
        simple_scenario,
    ):
        """Test that all markers are embedded in generated code."""
        code = java_generator.generate_program(simple_scenario)

        markers = extract_markers(code, "//")

        # Check expected markers are present
        for marker_name in simple_scenario.expected_markers:
            assert marker_name in markers, f"Missing marker: {marker_name}"

    def test_marker_format_consistency(self, java_generator: JavaGenerator):
        """Test that markers have consistent format."""
        from aidb_cli.generators.core.types import VariableConstruct

        construct = VariableConstruct(
            type="variable",
            name="test",
            initial_value=1,
            marker="var.init.test",
        )

        code = java_generator.generate_variable(construct)

        # Should have marker in format //:category.action.id:
        assert "//:var.init.test:" in code


class TestSyntaxErrorGeneration:
    """Tests for syntax error generation."""

    def test_generate_syntax_error_unclosed_bracket(
        self,
        java_generator: JavaGenerator,
    ):
        """Test generating syntax error with unclosed bracket."""
        from aidb_cli.generators.core.types import SyntaxErrorConstruct

        construct = SyntaxErrorConstruct(
            error_type="unclosed_bracket",
            marker="error.syntax.unclosed",
        )

        code = java_generator.generate_syntax_error(construct)

        assert "brokenMethod" in code
        assert "//:error.syntax.unclosed:" in code
        assert "(" in code

    def test_generate_syntax_error_missing_semicolon(
        self,
        java_generator: JavaGenerator,
    ):
        """Test generating syntax error with missing semicolon."""
        from aidb_cli.generators.core.types import SyntaxErrorConstruct

        construct = SyntaxErrorConstruct(
            error_type="missing_semicolon",
            marker="error.syntax.semicolon",
        )

        code = java_generator.generate_syntax_error(construct)

        assert "int x = 5" in code
        assert "//:error.syntax.semicolon:" in code

    def test_generate_syntax_error_type_mismatch(self, java_generator: JavaGenerator):
        """Test generating syntax error with type mismatch."""
        from aidb_cli.generators.core.types import SyntaxErrorConstruct

        construct = SyntaxErrorConstruct(
            error_type="type_mismatch",
            marker="error.syntax.type",
        )

        code = java_generator.generate_syntax_error(construct)

        assert "int result" in code
        assert "//:error.syntax.type:" in code

    def test_generate_syntax_error_with_code_snippet(
        self,
        java_generator: JavaGenerator,
    ):
        """Test generating syntax error with custom code snippet."""
        from aidb_cli.generators.core.types import SyntaxErrorConstruct

        construct = SyntaxErrorConstruct(
            code_snippet="int[] arr = {1, 2, 3",
            marker="error.syntax.custom",
        )

        code = java_generator.generate_syntax_error(construct)

        assert "int[] arr = {1, 2, 3" in code
        assert "//:error.syntax.custom:" in code

    def test_syntax_error_has_marker(self, java_generator: JavaGenerator):
        """Test that syntax error includes marker."""
        from aidb_cli.generators.core.types import SyntaxErrorConstruct

        construct = SyntaxErrorConstruct(
            error_type="unclosed_bracket",
            marker="error.test.marker",
        )

        code = java_generator.generate_syntax_error(construct)

        assert "//:error.test.marker:" in code


class TestInfiniteLoopGeneration:
    """Tests for infinite loop generation."""

    def test_infinite_loop_with_true_condition(self, java_generator: JavaGenerator):
        """Test generating while (true) infinite loop."""
        from aidb_cli.generators.core.types import LoopConstruct, LoopType

        construct = LoopConstruct(
            loop_type=LoopType.WHILE,
            condition="true",
            marker="flow.loop.infinite",
        )

        code = java_generator.generate_loop(construct)

        assert "while (true)" in code
        assert "//:flow.loop.infinite:" in code

    def test_infinite_loop_with_uppercase_true(
        self,
        java_generator: JavaGenerator,
    ):
        """Test that uppercase 'True' still works (gets used as-is)."""
        from aidb_cli.generators.core.types import LoopConstruct, LoopType

        construct = LoopConstruct(
            loop_type=LoopType.WHILE,
            condition="True",
            marker="flow.loop.infinite",
        )

        code = java_generator.generate_loop(construct)

        assert "while (True)" in code
        assert "//:flow.loop.infinite:" in code

    def test_infinite_loop_with_counter_body(self, java_generator: JavaGenerator):
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
            condition="true",
            marker="flow.loop.infinite",
            body=[body_construct],
        )

        code = java_generator.generate_loop(construct)

        assert "while (true)" in code
        assert "counter++" in code or "counter += 1" in code
        assert "//:flow.loop.infinite:" in code
        assert "//:var.increment.counter:" in code

    def test_infinite_loop_with_one_literal(self, java_generator: JavaGenerator):
        """Test infinite loop using while (1) pattern."""
        from aidb_cli.generators.core.types import LoopConstruct, LoopType

        construct = LoopConstruct(
            loop_type=LoopType.WHILE,
            condition="1",
            marker="flow.loop.infinite",
        )

        code = java_generator.generate_loop(construct)

        assert "while (1)" in code
        assert "//:flow.loop.infinite:" in code

    def test_infinite_loop_has_marker(self, java_generator: JavaGenerator):
        """Test that infinite loop includes marker."""
        from aidb_cli.generators.core.types import LoopConstruct, LoopType

        construct = LoopConstruct(
            loop_type=LoopType.WHILE,
            condition="true",
            marker="test.infinite.marker",
        )

        code = java_generator.generate_loop(construct)

        assert "//:test.infinite.marker:" in code


class TestRecursiveFunctionGeneration:
    """Tests for recursive function generation."""

    def test_recursive_function_definition(self, java_generator: JavaGenerator):
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
            name="recursiveFunction",
            operation="call",
            arguments=["depth + 1"],
            marker="func.call.recursive",
        )

        construct = FunctionConstruct(
            name="recursiveFunction",
            parameters=[Parameter(name="depth")],
            body=[print_construct, call_construct],
            marker="func.def.recursive",
        )

        code = java_generator.generate_function(construct)

        assert "public static void recursiveFunction(int depth)" in code
        assert 'System.out.println(String.format("Depth: %s", depth))' in code
        assert "recursiveFunction(depth + 1)" in code
        assert "//:func.def.recursive:" in code

    def test_recursive_function_call(self, java_generator: JavaGenerator):
        """Test generating recursive function call."""
        from aidb_cli.generators.core.types import FunctionConstruct

        construct = FunctionConstruct(
            name="recursiveFunction",
            operation="call",
            arguments=[0],
            marker="func.call.start",
        )

        code = java_generator.generate_function(construct)

        assert "recursiveFunction(0)" in code
        assert "//:func.call.start:" in code

    def test_recursive_with_parameter(self, java_generator: JavaGenerator):
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

        code = java_generator.generate_function(construct)

        assert "public static void recurse(int n)" in code
        assert "recurse(n - 1)" in code
        assert "//:func.def.recurse:" in code

    def test_recursive_with_multiple_calls(self, java_generator: JavaGenerator):
        """Test recursive function with multiple recursive calls."""
        from aidb_cli.generators.core.types import (
            FunctionConstruct,
            Parameter,
        )

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

        code = java_generator.generate_function(construct)

        assert "public static void fib(int n)" in code
        assert "fib(n - 1)" in code
        assert "fib(n - 2)" in code

    def test_recursive_has_markers(self, java_generator: JavaGenerator):
        """Test that recursive function includes all markers."""
        from aidb_cli.generators.core.types import (
            FunctionConstruct,
            Parameter,
        )

        call_construct = FunctionConstruct(
            name="testFunc",
            operation="call",
            arguments=["x + 1"],
            marker="test.call.marker",
        )

        construct = FunctionConstruct(
            name="testFunc",
            parameters=[Parameter(name="x")],
            body=[call_construct],
            marker="test.def.marker",
        )

        code = java_generator.generate_function(construct)

        assert "//:test.def.marker:" in code
        assert "//:test.call.marker:" in code


class TestLargeArrayGeneration:
    """Tests for large array generation."""

    def test_large_array_with_range(self, java_generator):
        """Test generation of large array with range initialization."""
        from aidb_cli.generators.core.types import ArrayConstruct

        construct = ArrayConstruct(
            name="largeNumbers",
            size=3000,
            initialize="range",
            marker="var.create.large_array",
        )

        code = java_generator.generate_array(construct)

        assert "int[] largeNumbers = IntStream.range(0, 3000).toArray();" in code
        assert "//:var.create.large_array:" in code

    def test_large_array_iteration(self, java_generator):
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
            iterable="largeNumbers",
            body=[conditional_construct],
            marker="flow.loop.iterate",
        )

        code = java_generator.generate_loop(loop_construct)

        assert "for (var item : largeNumbers) {" in code
        assert "if (item % 500 == 0) {" in code
        assert 'String.format("Checkpoint: %s", item)' in code
        assert "//:flow.loop.iterate:" in code
        assert "//:flow.if.checkpoint:" in code
        assert "//:func.print.checkpoint:" in code

    def test_large_array_with_zeros(self, java_generator):
        """Test generation of large array initialized with zeros."""
        from aidb_cli.generators.core.types import ArrayConstruct

        construct = ArrayConstruct(
            name="zerosArray",
            size=3000,
            initialize="zeros",
            marker="var.create.zeros",
        )

        code = java_generator.generate_array(construct)

        assert "int[] zerosArray = new int[3000];" in code
        assert "//:var.create.zeros:" in code

    def test_large_array_checkpoint_logic(self, java_generator):
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

        code = java_generator.generate_conditional(conditional_construct)

        assert "if (item % 500 == 0) {" in code
        assert 'String.format("Checkpoint: %s", item)' in code
        assert "//:flow.if.checkpoint:" in code
        assert "//:func.print.checkpoint:" in code

    def test_large_array_scenario_markers(self, java_generator):
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
            name="largeNumbers",
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
            iterable="largeNumbers",
            body=[conditional_construct],
            marker="flow.loop.iterate",
        )

        array_code = java_generator.generate_array(array_construct)
        loop_code = java_generator.generate_loop(loop_construct)

        # Verify all 4 expected markers
        assert "//:var.create.large_array:" in array_code
        assert "//:flow.loop.iterate:" in loop_code
        assert "//:flow.if.checkpoint:" in loop_code
        assert "//:func.print.checkpoint:" in loop_code
