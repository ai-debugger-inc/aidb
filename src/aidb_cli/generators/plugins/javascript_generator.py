"""JavaScript language generator plugin."""

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


class JavaScriptGenerator(LanguageGenerator):
    """Generate JavaScript test programs."""

    @property
    def language_name(self) -> str:
        """Get language name."""
        return "javascript"

    @property
    def file_extension(self) -> str:
        """Get file extension for generated files."""
        return ".js"

    @property
    def comment_prefix(self) -> str:
        """Get comment prefix for the language."""
        return "//"

    def generate_variable(self, construct: VariableConstruct) -> str:
        """Generate JavaScript variable declaration/assignment."""
        marker = self.format_marker(construct.marker) if construct.marker else ""

        if construct.operation == "increment":
            return f"{construct.name}++;  {marker}"
        if construct.operation == "decrement":
            return f"{construct.name}--;  {marker}"
        if construct.operation == "add" and construct.value:
            return f"{construct.name} += {construct.value};  {marker}"
        if construct.operation == "assign" and construct.value is not None:
            return f"{construct.name} = {self.format_value(construct.value)};  {marker}"
        if construct.initial_value is not None:
            initial_val = self.format_value(construct.initial_value)
            if marker:
                return f"let {construct.name} = {initial_val};  {marker}"
            return f"let {construct.name} = {initial_val};"
        if marker:
            return f"let {construct.name} = null;  {marker}"
        return f"let {construct.name} = null;"

    def generate_loop(self, construct: LoopConstruct) -> str:
        """Generate JavaScript loop."""
        marker = self.format_marker(construct.marker) if construct.marker else ""

        if construct.loop_type == LoopType.FOR:
            if construct.iterable:
                # For-of style loop
                loop_header = (
                    f"for (const {construct.variable} of {construct.iterable}) {{  "
                    f"{marker}"
                )
            else:
                # Traditional for loop
                start = construct.start if construct.start is not None else 0
                end = construct.end if construct.end is not None else 10
                step = construct.step if construct.step != 1 else 1

                if step == 1:
                    loop_header = (
                        f"for (let {construct.variable} = {start}; "
                        f"{construct.variable} < {end}; {construct.variable}++) {{  "
                        f"{marker}"
                    )
                else:
                    loop_header = (
                        f"for (let {construct.variable} = {start}; "
                        f"{construct.variable} < {end}; "
                        f"{construct.variable} += {step}) {{  {marker}"
                    )

            # Generate body
            if construct.body:
                body = self.generate_body(construct.body)
                return f"{loop_header}\n{body}\n}}"
            return f"{loop_header}\n}}"

        if construct.loop_type == LoopType.WHILE:
            condition = construct.condition if construct.condition else "true"
            loop_header = f"while ({condition}) {{  {marker}"

            if construct.body:
                body = self.generate_body(construct.body)
                return f"{loop_header}\n{body}\n}}"
            return f"{loop_header}\n}}"

        # For-of loop fallback
        loop_header = (
            f"for (const {construct.variable} of {construct.iterable}) {{  {marker}"
        )
        if construct.body:
            body = self.generate_body(construct.body)
            return f"{loop_header}\n{body}\n}}"
        return f"{loop_header}\n}}"

    def generate_function(self, construct: FunctionConstruct) -> str:
        """Generate JavaScript function definition or call."""
        marker = self.format_marker(construct.marker) if construct.marker else ""

        if construct.operation == "call":
            # Function call
            args = ", ".join(str(arg) for arg in construct.arguments)
            call_expr = f"{construct.name}({args})"

            if construct.result_variable:
                return f"const {construct.result_variable} = {call_expr};  {marker}"
            return f"{call_expr};  {marker}"

        # Function definition
        params = ", ".join(param.name for param in construct.parameters)
        func_header = f"function {construct.name}({params}) {{  {marker}"

        if construct.body:
            body = self.generate_body(construct.body)
            return f"{func_header}\n{body}\n}}"
        return f"{func_header}\n}}"

    def generate_conditional(self, construct: ConditionalConstruct) -> str:
        """Generate JavaScript if/else statement."""
        marker = self.format_marker(construct.marker) if construct.marker else ""

        result = f"if ({construct.condition}) {{  {marker}"

        if construct.true_body:
            true_code = self.generate_body(construct.true_body)
            result += f"\n{true_code}\n}}"
        else:
            result += "\n}"

        if construct.false_body:
            result += " else {"
            false_code = self.generate_body(construct.false_body)
            result += f"\n{false_code}\n}}"

        return result

    def generate_exception(self, construct: ExceptionConstruct) -> str:
        """Generate JavaScript try/catch block."""
        marker = self.format_marker(construct.marker) if construct.marker else ""

        result = f"try {{  {marker}"

        if construct.body:
            body = self.generate_body(construct.body)
            result += f"\n{body}\n}}"
        else:
            result += "\n}"

        # Add catch blocks
        for catch_block in construct.catch_blocks:
            exception_class = catch_block.get("exception_class", "Error")
            catch_marker = catch_block.get("marker", "")
            catch_marker_str = self.format_marker(catch_marker) if catch_marker else ""

            # JavaScript doesn't have typed catch, so we check type inside
            if exception_class != "Error":
                result += f" catch (e) {{  {catch_marker_str}"
                result += f"\n    if (e instanceof {exception_class}) {{"
                catch_body = catch_block.get("body", [])
                if catch_body:
                    body_code = self.generate_body(catch_body, indent_level=2)
                    result += f"\n{body_code}"
                result += "\n    } else {\n        throw e;\n    }"
                result += "\n}"
            else:
                result += f" catch (e) {{  {catch_marker_str}"
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
        """Generate JavaScript console.log statement."""
        marker = self.format_marker(construct.marker) if construct.marker else ""

        # Format the message with variable interpolation
        message = construct.message
        if "{" in message:
            # Convert Python-style {var} to JavaScript template literal ${var}
            formatted_message = message
            for match in message.split("{"):
                if "}" in match:
                    var_name = match.split("}")[0]
                    formatted_message = formatted_message.replace(
                        f"{{{var_name}}}",
                        f"${{{var_name}}}",
                    )
            formatted_message = f"`{formatted_message}`"
        else:
            formatted_message = f'"{message}"'

        return f"console.log({formatted_message});  {marker}"

    def generate_return(self, construct: ReturnConstruct) -> str:
        """Generate JavaScript return statement."""
        marker = self.format_marker(construct.marker) if construct.marker else ""

        if construct.value is not None:
            return f"return {self.format_value(construct.value)};  {marker}"
        return f"return;  {marker}"

    def generate_array(self, construct: ArrayConstruct) -> str:
        """Generate JavaScript array creation."""
        marker = self.format_marker(construct.marker) if construct.marker else ""

        if construct.initialize == "range" and construct.size:
            array_expr = f"Array.from({{length: {construct.size}}}, (_, i) => i)"
            return f"const {construct.name} = {array_expr};  {marker}"
        if construct.initialize == "zeros" and construct.size:
            array_expr = f"new Array({construct.size}).fill(0)"
            return f"const {construct.name} = {array_expr};  {marker}"
        if construct.values:
            values_str = "[" + ", ".join(str(v) for v in construct.values) + "]"
            return f"const {construct.name} = {values_str};  {marker}"
        return f"const {construct.name} = [];  {marker}"

    def generate_syntax_error(self, construct: SyntaxErrorConstruct) -> str:
        """Generate intentionally malformed JavaScript code."""
        marker = self.format_marker(construct.marker) if construct.marker else ""

        if construct.error_type == "unclosed_bracket":
            return f"function brokenFunction(x, y {{  {marker}\n    return x + y;\n}}"
        if construct.error_type == "missing_semicolon":
            return f"let x = 5  {marker}\nlet y = 10"
        if construct.error_type == "unclosed_brace":
            return f"if (true) {{  {marker}\n    console.log('test');"
        if construct.error_type == "undefined_variable":
            return f"const result = undefinedVar + 1;  {marker}"
        if construct.code_snippet:
            return f"{construct.code_snippet}  {marker}"
        return f"function syntaxError( {{  {marker}"

    def format_program(self, code_blocks: list[str], scenario: Scenario) -> str:
        """Format code blocks into a complete JavaScript program."""
        program = []

        # Add header comment
        program.append("// Generated test program")
        program.append(f"// Name: {scenario.name}")
        if scenario.description:
            program.append(f"// Description: {scenario.description}")
        program.append(f"// Generated from scenario: {scenario.id}")
        program.append("")

        # Check if we have any function definitions
        has_functions = any("function " in block for block in code_blocks)

        if has_functions:
            # Add all code blocks
            for block in code_blocks:
                program.append(block)
                program.append("")

            # Add main function call if we have a main function
            has_main = any("function main(" in block for block in code_blocks)
            if has_main:
                program.append("main();")
        else:
            # No functions, wrap everything in main
            program.append("function main() {")

            for block in code_blocks:
                # Indent the block
                indented = self.indent(block)
                program.append(indented)

            program.append("}")
            program.append("")
            program.append("main();")

        return "\n".join(program)

    def validate_syntax(self, code: str) -> ValidationResult:
        """Validate JavaScript syntax."""
        # Basic validation - in production we'd use esprima or similar
        # For now, just check for balanced braces
        try:
            open_braces = code.count("{")
            close_braces = code.count("}")

            if open_braces != close_braces:
                error_msg = (
                    f"Unbalanced braces: {open_braces} open, {close_braces} close"
                )
                return ValidationResult(is_valid=False, errors=[error_msg])

            return ValidationResult(is_valid=True)
        except Exception as e:  # Return validation errors rather than raising
            return ValidationResult(is_valid=False, errors=[str(e)])

    def format_value(self, value) -> str:
        """Format a value for JavaScript code."""
        if isinstance(value, str):
            # Check if it's a variable reference or expression
            if any(op in value for op in ["+", "-", "*", "/", "%"]):
                return value  # It's an expression
            if value in ["true", "false", "null", "undefined"]:
                return value  # JavaScript keywords
            if value.isidentifier():
                return value  # Variable name
            return f'"{value}"'  # String literal
        if isinstance(value, bool):
            return "true" if value else "false"
        if value is None:
            return "null"
        return str(value)

    def parse_constructs(self, constructs_data):
        """Parse nested constructs from catch/finally blocks."""
        from aidb_cli.generators.core.parser import ScenarioParser

        parser = ScenarioParser()
        return parser.parse_constructs(constructs_data)
