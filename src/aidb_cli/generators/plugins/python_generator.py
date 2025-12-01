"""Python language generator plugin."""

import ast

from aidb_cli.generators.core.types import (
    ArrayConstruct,
    ConditionalConstruct,
    ExceptionConstruct,
    FunctionConstruct,
    LoopConstruct,
    LoopType,
    PrintConstruct,
    ReturnConstruct,
    Scenario,
    SyntaxErrorConstruct,
    ValidationResult,
    VariableConstruct,
)
from aidb_cli.generators.plugins.base import LanguageGenerator


class PythonGenerator(LanguageGenerator):
    """Generate Python test programs."""

    @property
    def language_name(self) -> str:
        """Get language name."""
        return "python"

    @property
    def file_extension(self) -> str:
        """Get file extension for generated files."""
        return ".py"

    @property
    def comment_prefix(self) -> str:
        """Get comment prefix for the language."""
        return "#"

    def generate_variable(self, construct: VariableConstruct) -> str:
        """Generate Python variable declaration/assignment."""
        marker = self.format_marker(construct.marker) if construct.marker else ""

        if construct.operation == "increment":
            return f"{construct.name} += 1  {marker}"
        if construct.operation == "decrement":
            return f"{construct.name} -= 1  {marker}"
        if construct.operation == "add" and construct.value:
            return f"{construct.name} += {construct.value}  {marker}"
        if construct.operation == "assign" and construct.value is not None:
            val = self.format_value(construct.value)
            return f"{construct.name} = {val}  {marker}"
        if construct.initial_value is not None:
            val = self.format_value(construct.initial_value)
            if marker:
                return f"{construct.name} = {val}  {marker}"
            return f"{construct.name} = {val}"
        if marker:
            return f"{construct.name} = None  {marker}"
        return f"{construct.name} = None"

    def generate_loop(self, construct: LoopConstruct) -> str:
        """Generate Python loop."""
        marker = self.format_marker(construct.marker) if construct.marker else ""

        if construct.loop_type == LoopType.FOR:
            if construct.iterable:
                # For-each style loop
                loop_header = (
                    f"for {construct.variable} in {construct.iterable}:  {marker}"
                )
            else:
                # Range-based for loop
                start = construct.start if construct.start is not None else 0
                end = construct.end if construct.end is not None else 10
                step = construct.step if construct.step != 1 else None

                if step:
                    range_expr = f"range({start}, {end}, {step})"
                else:
                    range_expr = f"range({start}, {end})"

                loop_header = f"for {construct.variable} in {range_expr}:  {marker}"

            # Generate body
            if construct.body:
                body = self.generate_body(construct.body)
                return f"{loop_header}\n{body}"
            return f"{loop_header}\n    pass"

        if construct.loop_type == LoopType.WHILE:
            condition = construct.condition if construct.condition else "True"
            condition = condition.replace("true", "True").replace("false", "False")
            loop_header = f"while {condition}:  {marker}"

            if construct.body:
                body = self.generate_body(construct.body)
                return f"{loop_header}\n{body}"
            return f"{loop_header}\n    pass"

        # For-each loop
        loop_header = f"for {construct.variable} in {construct.iterable}:  {marker}"
        if construct.body:
            body = self.generate_body(construct.body)
            return f"{loop_header}\n{body}"
        return f"{loop_header}\n    pass"

    def generate_function(self, construct: FunctionConstruct) -> str:
        """Generate Python function definition or call."""
        marker = self.format_marker(construct.marker) if construct.marker else ""

        if construct.operation == "call":
            # Function call
            args = ", ".join(str(arg) for arg in construct.arguments)
            call_expr = f"{construct.name}({args})"

            if construct.result_variable:
                return f"{construct.result_variable} = {call_expr}  {marker}"
            return f"{call_expr}  {marker}"
        # Function definition
        params = ", ".join(param.name for param in construct.parameters)
        func_header = f"def {construct.name}({params}):  {marker}"

        if construct.body:
            body = self.generate_body(construct.body)
            return f"{func_header}\n{body}"
        return f"{func_header}\n    pass"

    def generate_conditional(self, construct: ConditionalConstruct) -> str:
        """Generate Python if/else statement."""
        marker = self.format_marker(construct.marker) if construct.marker else ""

        result = f"if {construct.condition}:  {marker}"

        if construct.true_body:
            true_code = self.generate_body(construct.true_body)
            result += f"\n{true_code}"
        else:
            result += "\n    pass"

        if construct.false_body:
            result += "\nelse:"
            false_code = self.generate_body(construct.false_body)
            result += f"\n{false_code}"

        return result

    def generate_exception(self, construct: ExceptionConstruct) -> str:
        """Generate Python try/except block."""
        marker = self.format_marker(construct.marker) if construct.marker else ""

        result = f"try:  {marker}"

        if construct.body:
            body = self.generate_body(construct.body)
            result += f"\n{body}"
        else:
            result += "\n    pass"

        # Add catch blocks
        for catch_block in construct.catch_blocks:
            exception_class = catch_block.get("exception_class", "Exception")
            catch_marker = catch_block.get("marker", "")
            catch_marker_str = self.format_marker(catch_marker) if catch_marker else ""

            result += f"\nexcept {exception_class} as e:  {catch_marker_str}"

            catch_body = catch_block.get("body", [])
            if catch_body:
                body_code = self.generate_body(catch_body)
                result += f"\n{body_code}"
            else:
                result += "\n    pass"

        # Add finally block if present
        if construct.finally_block:
            finally_marker = construct.finally_block.get("marker", "")
            finally_marker_str = (
                self.format_marker(finally_marker) if finally_marker else ""
            )

            result += f"\nfinally:  {finally_marker_str}"

            finally_body = construct.finally_block.get("body", [])
            if finally_body:
                body_code = self.generate_body(finally_body)
                result += f"\n{body_code}"
            else:
                result += "\n    pass"

        return result

    def generate_print(self, construct: PrintConstruct) -> str:
        """Generate Python print statement."""
        marker = self.format_marker(construct.marker) if construct.marker else ""

        # Format the message with variable interpolation
        message = construct.message
        # Use f-string formatting for variable interpolation
        formatted_message = f'f"{message}"' if "{" in message else f'"{message}"'

        return f"print({formatted_message})  {marker}"

    def generate_return(self, construct: ReturnConstruct) -> str:
        """Generate Python return statement."""
        marker = self.format_marker(construct.marker) if construct.marker else ""

        if construct.value is not None:
            return f"return {self.format_value(construct.value)}  {marker}"
        return f"return  {marker}"

    def generate_array(self, construct: ArrayConstruct) -> str:
        """Generate Python list/array creation."""
        marker = self.format_marker(construct.marker) if construct.marker else ""

        if construct.initialize == "range" and construct.size:
            return f"{construct.name} = list(range({construct.size}))  {marker}"
        if construct.initialize == "zeros" and construct.size:
            return f"{construct.name} = [0] * {construct.size}  {marker}"
        if construct.values:
            values_str = "[" + ", ".join(str(v) for v in construct.values) + "]"
            return f"{construct.name} = {values_str}  {marker}"
        return f"{construct.name} = []  {marker}"

    def generate_syntax_error(self, construct: SyntaxErrorConstruct) -> str:
        """Generate intentionally malformed Python code."""
        marker = self.format_marker(construct.marker) if construct.marker else ""

        if construct.error_type == "unclosed_bracket":
            return f"def broken_function(x, y:  {marker}\n    return x + y"
        if construct.error_type == "missing_colon":
            return f"if True  {marker}\n    pass"
        if construct.error_type == "indentation_error":
            return f"def bad_indent():  {marker}\npass"
        if construct.error_type == "undefined_variable":
            return f"result = undefined_var + 1  {marker}"
        if construct.code_snippet:
            return f"{construct.code_snippet}  {marker}"
        return f"def syntax_error(  {marker}"

    def format_program(self, code_blocks: list[str], scenario: Scenario) -> str:
        """Format code blocks into a complete Python program."""
        program = []

        # Add shebang and module docstring
        program.append("#!/usr/bin/env python3")
        program.append('"""')
        program.append(f"Generated test program: {scenario.name}")
        if scenario.description:
            program.append(f"Description: {scenario.description}")
        program.append(f"Generated from scenario: {scenario.id}")
        program.append('"""')
        program.append("")

        # Check if we have any function definitions
        has_functions = any("def " in block for block in code_blocks)

        if has_functions:
            # Add imports if needed (we'll expand this later)
            program.append("")

            # Add all code blocks
            for block in code_blocks:
                program.append(block)
                program.append("")

            # Add main guard if we have a main function
            has_main = any("def main(" in block for block in code_blocks)
            if has_main:
                program.append("")
                program.append('if __name__ == "__main__":')
                program.append("    main()")
        else:
            # No functions, wrap everything in main
            program.append("")
            program.append("def main():")

            for block in code_blocks:
                # Indent the block
                indented = self.indent(block)
                program.append(indented)

            program.append("")
            program.append("")
            program.append('if __name__ == "__main__":')
            program.append("    main()")

        return "\n".join(program)

    def validate_syntax(self, code: str) -> ValidationResult:
        """Validate Python syntax."""
        try:
            ast.parse(code)
            return ValidationResult(is_valid=True)
        except SyntaxError as e:
            return ValidationResult(
                is_valid=False,
                errors=[f"Syntax error at line {e.lineno}: {e.msg}"],
            )

    def format_value(self, value) -> str:
        """Format a value for Python code."""
        if isinstance(value, str):
            # Check if it's a variable reference or expression
            if any(op in value for op in ["+", "-", "*", "/", "%"]):
                return value  # It's an expression
            if value in ["True", "False", "None"]:
                return value  # Python keywords
            if value.isidentifier():
                return value  # Variable name
            return f'"{value}"'  # String literal
        if isinstance(value, bool):
            return "True" if value else "False"
        if value is None:
            return "None"
        return str(value)

    def parse_constructs(self, constructs_data):
        """Parse nested constructs from catch/finally blocks."""
        # This is a simplified version - in production we'd use the real parser
        from aidb_cli.generators.core.parser import ScenarioParser

        parser = ScenarioParser()
        return parser.parse_constructs(constructs_data)
