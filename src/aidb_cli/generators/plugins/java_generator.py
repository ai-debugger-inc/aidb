"""Java language generator plugin."""

from aidb_cli.generators.core.types import (
    ArrayConstruct,
    ConditionalConstruct,
    DataType,
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


class JavaGenerator(LanguageGenerator):
    """Generate Java test programs."""

    @property
    def language_name(self) -> str:
        """Get language name."""
        return "java"

    @property
    def file_extension(self) -> str:
        """Get file extension for generated files."""
        return ".java"

    @property
    def comment_prefix(self) -> str:
        """Get comment prefix for the language."""
        return "//"

    def _datatype_to_java(self, data_type: DataType | str | None) -> str:
        """Convert DataType enum to Java type string."""
        if data_type is None:
            return "int"

        if isinstance(data_type, DataType):
            type_map = {
                DataType.INTEGER: "int",
                DataType.FLOAT: "double",
                DataType.STRING: "String",
                DataType.BOOLEAN: "boolean",
                DataType.ARRAY: "int[]",
                DataType.MAP: "Map",
                DataType.OBJECT: "Object",
            }
            return type_map.get(data_type, "int")

        # If it's already a string, return as-is
        return str(data_type)

    def _infer_type(self, value) -> str:
        """Infer Java type from value."""
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int):
            return "int"
        if isinstance(value, float):
            return "double"
        if isinstance(value, str):
            # Check if it's an expression or variable
            if any(op in value for op in ["+", "-", "*", "/", "%"]):
                return "int"  # Assume int for arithmetic
            return "String"
        return "Object"

    def generate_variable(self, construct: VariableConstruct) -> str:
        """Generate Java variable declaration/assignment."""
        marker = self.format_marker(construct.marker) if construct.marker else ""

        if construct.operation == "increment":
            return f"{construct.name}++;  {marker}"
        if construct.operation == "decrement":
            return f"{construct.name}--;  {marker}"
        if construct.operation == "add" and construct.value:
            return f"{construct.name} += {construct.value};  {marker}"
        if construct.operation == "assign" and construct.value is not None:
            val = self.format_value(construct.value)
            return f"{construct.name} = {val};  {marker}"
        if construct.initial_value is not None:
            if construct.data_type:
                java_type = self._datatype_to_java(construct.data_type)
            else:
                java_type = self._infer_type(construct.initial_value)
            val = self.format_value(construct.initial_value)
            if marker:
                return f"{java_type} {construct.name} = {val};  {marker}"
            return f"{java_type} {construct.name} = {val};"
        if marker:
            return f"Object {construct.name} = null;  {marker}"
        return f"Object {construct.name} = null;"

    def generate_loop(self, construct: LoopConstruct) -> str:
        """Generate Java loop."""
        marker = self.format_marker(construct.marker) if construct.marker else ""

        if construct.loop_type == LoopType.FOR:
            if construct.iterable:
                # Enhanced for loop
                loop_header = (
                    f"for (var {construct.variable} : {construct.iterable}) {{  "
                    f"{marker}"
                )
            else:
                # Traditional for loop
                start = construct.start if construct.start is not None else 0
                end = construct.end if construct.end is not None else 10
                step = construct.step if construct.step != 1 else 1

                if step == 1:
                    loop_header = (
                        f"for (int {construct.variable} = {start}; "
                        f"{construct.variable} < {end}; {construct.variable}++) {{  "
                        f"{marker}"
                    )
                else:
                    loop_header = (
                        f"for (int {construct.variable} = {start}; "
                        f"{construct.variable} < {end}; "
                        f"{construct.variable} += {step}) {{  {marker}"
                    )

            # Generate body
            if construct.body:
                body = self.generate_body(construct.body, indent_level=2)
                return f"{loop_header}\n{body}\n        }}"
            return f"{loop_header}\n        }}"

        if construct.loop_type == LoopType.WHILE:
            condition = construct.condition if construct.condition else "true"
            loop_header = f"while ({condition}) {{  {marker}"

            if construct.body:
                body = self.generate_body(construct.body, indent_level=2)
                return f"{loop_header}\n{body}\n        }}"
            return f"{loop_header}\n        }}"

        # Enhanced for loop fallback
        loop_header = (
            f"for (var {construct.variable} : {construct.iterable}) {{  {marker}"
        )
        if construct.body:
            body = self.generate_body(construct.body, indent_level=2)
            return f"{loop_header}\n{body}\n        }}"
        return f"{loop_header}\n        }}"

    def generate_function(self, construct: FunctionConstruct) -> str:
        """Generate Java function definition or call."""
        marker = self.format_marker(construct.marker) if construct.marker else ""

        if construct.operation == "call":
            # Function call
            args = ", ".join(str(arg) for arg in construct.arguments)
            call_expr = f"{construct.name}({args})"

            if construct.result_variable:
                result_type = construct.return_type if construct.return_type else "var"
                result_var = construct.result_variable
                return f"{result_type} {result_var} = {call_expr};  {marker}"
            return f"{call_expr};  {marker}"

        # Function definition (static method)
        params = ", ".join(
            f"{self._datatype_to_java(param.data_type)} {param.name}"
            for param in construct.parameters
        )
        # Convert return type if it's a DataType enum
        if construct.return_type:
            return_type = self._datatype_to_java(construct.return_type)
        else:
            return_type = "void"
        func_header = (
            f"public static {return_type} {construct.name}({params}) {{  {marker}"
        )

        if construct.body:
            body = self.generate_body(construct.body)
            return f"{func_header}\n{body}\n    }}"
        return f"{func_header}\n    }}"

    def generate_conditional(self, construct: ConditionalConstruct) -> str:
        """Generate Java if/else statement."""
        marker = self.format_marker(construct.marker) if construct.marker else ""

        result = f"if ({construct.condition}) {{  {marker}"

        if construct.true_body:
            true_code = self.generate_body(construct.true_body, indent_level=2)
            result += f"\n{true_code}\n        }}"
        else:
            result += "\n        }"

        if construct.false_body:
            result += " else {"
            false_code = self.generate_body(construct.false_body, indent_level=2)
            result += f"\n{false_code}\n        }}"

        return result

    def generate_exception(self, construct: ExceptionConstruct) -> str:
        """Generate Java try/catch block."""
        marker = self.format_marker(construct.marker) if construct.marker else ""

        result = f"try {{  {marker}"

        if construct.body:
            body = self.generate_body(construct.body)
            result += f"\n{body}\n}}"
        else:
            result += "\n}"

        # Add catch blocks
        for catch_block in construct.catch_blocks:
            exception_class = catch_block.get("exception_class", "Exception")
            catch_marker = catch_block.get("marker", "")
            catch_marker_str = self.format_marker(catch_marker) if catch_marker else ""

            result += f" catch ({exception_class} e) {{  {catch_marker_str}"

            catch_body = catch_block.get("body", [])
            if catch_body:
                body_code = self.generate_body(catch_body)
                result += f"\n{body_code}"
            result += "\n}"

        # Add finally block if present
        if construct.finally_block:
            finally_marker = construct.finally_block.get("marker", "")
            finally_marker_str = (
                self.format_marker(finally_marker) if finally_marker else ""
            )

            result += f" finally {{  {finally_marker_str}"

            finally_body = construct.finally_block.get("body", [])
            if finally_body:
                body_code = self.generate_body(finally_body)
                result += f"\n{body_code}"
            result += "\n}"

        return result

    def generate_print(self, construct: PrintConstruct) -> str:
        """Generate Java System.out.println statement."""
        marker = self.format_marker(construct.marker) if construct.marker else ""

        # Format the message with variable interpolation
        message = construct.message
        if "{" in message:
            # Convert to String.format style
            format_args = []
            formatted_message = message
            for match in message.split("{"):
                if "}" in match:
                    var_name = match.split("}")[0]
                    formatted_message = formatted_message.replace(
                        f"{{{var_name}}}",
                        "%s",
                    )
                    format_args.append(var_name)

            if format_args:
                args_str = ", ".join(format_args)
                return (
                    f'System.out.println(String.format("{formatted_message}", '
                    f"{args_str}));  {marker}"
                )

        return f'System.out.println("{message}");  {marker}'

    def generate_return(self, construct: ReturnConstruct) -> str:
        """Generate Java return statement."""
        marker = self.format_marker(construct.marker) if construct.marker else ""

        if construct.value is not None:
            return f"return {self.format_value(construct.value)};  {marker}"
        return f"return;  {marker}"

    def generate_array(self, construct: ArrayConstruct) -> str:
        """Generate Java array creation."""
        marker = self.format_marker(construct.marker) if construct.marker else ""

        if construct.initialize == "range" and construct.size:
            return (
                f"int[] {construct.name} = IntStream.range(0, {construct.size})"
                f".toArray();  {marker}"
            )
        if construct.initialize == "zeros" and construct.size:
            return f"int[] {construct.name} = new int[{construct.size}];  {marker}"
        if construct.values:
            values_str = "{" + ", ".join(str(v) for v in construct.values) + "}"
            return f"int[] {construct.name} = {values_str};  {marker}"
        return f"int[] {construct.name} = {{}};  {marker}"

    def generate_syntax_error(self, construct: SyntaxErrorConstruct) -> str:
        """Generate intentionally malformed Java code."""
        marker = self.format_marker(construct.marker) if construct.marker else ""

        if construct.error_type == "unclosed_bracket":
            return (
                f"public static void brokenMethod(int x, int y {{  {marker}\n"
                "            return x + y;\n        }"
            )
        if construct.error_type == "missing_semicolon":
            return f"int x = 5  {marker}\n        int y = 10;"
        if construct.error_type == "unclosed_brace":
            return f'if (true) {{  {marker}\n            System.out.println("test");'
        if construct.error_type == "type_mismatch":
            return f'int result = "not an integer";  {marker}'
        if construct.error_type == "undefined_variable":
            return f"int result = undefinedVar + 1;  {marker}"
        if construct.code_snippet:
            return f"{construct.code_snippet}  {marker}"
        return f"public static void syntaxError( {{  {marker}"

    def format_program(self, code_blocks: list[str], scenario: Scenario) -> str:
        """Format code blocks into a complete Java program."""
        program = []

        # Add header comment
        program.append("// Generated test program")
        program.append(f"// Name: {scenario.name}")
        if scenario.description:
            program.append(f"// Description: {scenario.description}")
        program.append(f"// Generated from scenario: {scenario.id}")
        program.append("")

        # Add imports if needed
        needs_stream = any("IntStream" in block for block in code_blocks)
        if needs_stream:
            program.append("import java.util.stream.IntStream;")
            program.append("")

        # Start class
        program.append("public class TestProgram {")
        program.append("")

        # Separate function definitions from main code
        function_defs, main_code = self._classify_code_blocks(code_blocks)

        # Build program structure
        program.extend(self._build_program_structure(function_defs, main_code))

        program.append("}")

        return "\n".join(program)

    def validate_syntax(self, code: str) -> ValidationResult:
        """Validate Java syntax."""
        # Basic validation - in production we'd use a Java parser
        try:
            open_braces = code.count("{")
            close_braces = code.count("}")

            if open_braces != close_braces:
                error_msg = (
                    f"Unbalanced braces: {open_braces} open, {close_braces} close"
                )
                return ValidationResult(is_valid=False, errors=[error_msg])

            # Check for class definition
            if "public class" not in code:
                return ValidationResult(
                    is_valid=False,
                    errors=["Java code must have a public class definition"],
                )

            return ValidationResult(is_valid=True)
        except Exception as e:  # Return validation errors rather than raising
            return ValidationResult(is_valid=False, errors=[str(e)])

    def format_value(self, value) -> str:
        """Format a value for Java code."""
        if isinstance(value, str):
            # Check if it's a variable reference or expression
            if any(op in value for op in ["+", "-", "*", "/", "%"]):
                return value  # It's an expression
            if value in ["true", "false", "null"]:
                return value  # Java keywords
            if value.isidentifier():
                return value  # Variable name
            return f'"{value}"'  # String literal
        if isinstance(value, bool):
            return "true" if value else "false"
        if value is None:
            return "null"
        return str(value)

    def _extract_main_function_body(self, block: str) -> list[str]:
        """Extract body from main function definition.

        Parameters
        ----------
        block : str
            Code block potentially containing main function

        Returns
        -------
        list[str]
            List of code lines from main function body
        """
        lines = block.split("\n")
        main_code = []

        # Extract marker from header if present
        if len(lines) > 0:
            header = lines[0]
            if "//:func.def.main:" in header:
                main_code.append("        //:func.def.main:")

        # Extract body (skip first and last lines)
        if len(lines) > 2:
            main_code.extend(lines[1:-1])

        return main_code

    def _is_main_function_definition(self, block: str) -> bool:
        """Check if block is main function definition.

        Parameters
        ----------
        block : str
            Code block to check

        Returns
        -------
        bool
            True if block is main function definition
        """
        return "public static" in block and "void main(" in block

    def _classify_code_blocks(
        self,
        code_blocks: list[str],
    ) -> tuple[list[str], list[str]]:
        """Classify code blocks into function definitions and main code.

        Parameters
        ----------
        code_blocks : list[str]
            All code blocks to classify

        Returns
        -------
        tuple[list[str], list[str]]
            Function definitions and main code blocks
        """
        function_defs = []
        main_code = []

        for block in code_blocks:
            if self._is_main_function_definition(block):
                # Extract body from main function definition
                main_code.extend(self._extract_main_function_body(block))
            elif "public static" in block:
                # Regular function definition
                function_defs.append(block)
            else:
                # Regular code to go in main
                main_code.append(block)

        return function_defs, main_code

    def _build_program_structure(
        self,
        function_defs: list[str],
        main_code: list[str],
    ) -> list[str]:
        """Build complete program structure with functions and main.

        Parameters
        ----------
        function_defs : list[str]
            Function definition code blocks
        main_code : list[str]
            Main method code blocks

        Returns
        -------
        list[str]
            Complete program lines
        """
        program = []

        # Add function definitions first
        for func_def in function_defs:
            indented = self.indent(func_def)
            program.append(indented)
            program.append("")

        # Add main method
        program.append("    public static void main(String[] args) {")
        for code in main_code:
            if isinstance(code, str):
                # If already indented from function body, don't re-indent
                if code.startswith("        "):
                    program.append(code)
                else:
                    indented = self.indent(code, level=2)
                    program.append(indented)
        program.append("    }")

        return program

    def parse_constructs(self, constructs_data):
        """Parse nested constructs from catch/finally blocks."""
        from aidb_cli.generators.core.parser import ScenarioParser

        parser = ScenarioParser()
        return parser.parse_constructs(constructs_data)
