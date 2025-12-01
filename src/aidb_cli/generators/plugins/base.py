"""Base plugin interface for language generators."""

from abc import ABC, abstractmethod

from aidb_cli.generators.core.types import (
    ArrayConstruct,
    ConditionalConstruct,
    Construct,
    ExceptionConstruct,
    FunctionConstruct,
    LoopConstruct,
    PrintConstruct,
    ReturnConstruct,
    Scenario,
    SyntaxErrorConstruct,
    ValidationResult,
    VariableConstruct,
)


class LanguageGenerator(ABC):
    """Base class for all language-specific generators."""

    @property
    @abstractmethod
    def language_name(self) -> str:
        """Return the language name (e.g., 'python', 'javascript')."""

    @property
    @abstractmethod
    def file_extension(self) -> str:
        """Return the file extension (e.g., '.py', '.js')."""

    @property
    @abstractmethod
    def comment_prefix(self) -> str:
        """Return the single-line comment prefix (e.g., '#', '//')."""

    def generate_program(self, scenario: Scenario) -> str:
        """Generate a complete program from a scenario."""
        # Generate all constructs
        construct_code = []
        for construct in scenario.constructs:
            code = self.generate_construct(construct)
            if code:
                construct_code.append(code)

        # Format into complete program
        return self.format_program(construct_code, scenario)

    def generate_construct(self, construct: Construct) -> str:
        """Generate code for a single construct."""
        if isinstance(construct, VariableConstruct):
            return self.generate_variable(construct)
        if isinstance(construct, LoopConstruct):
            return self.generate_loop(construct)
        if isinstance(construct, FunctionConstruct):
            return self.generate_function(construct)
        if isinstance(construct, ConditionalConstruct):
            return self.generate_conditional(construct)
        if isinstance(construct, ExceptionConstruct):
            return self.generate_exception(construct)
        if isinstance(construct, PrintConstruct):
            return self.generate_print(construct)
        if isinstance(construct, ReturnConstruct):
            return self.generate_return(construct)
        if isinstance(construct, SyntaxErrorConstruct):
            return self.generate_syntax_error(construct)
        if isinstance(construct, ArrayConstruct):
            return self.generate_array(construct)
        return (
            f"{self.comment_prefix} TODO: Unsupported construct type: {construct.type}"
        )

    @abstractmethod
    def generate_variable(self, construct: VariableConstruct) -> str:
        """Generate variable declaration/assignment code."""

    @abstractmethod
    def generate_loop(self, construct: LoopConstruct) -> str:
        """Generate loop code."""

    @abstractmethod
    def generate_function(self, construct: FunctionConstruct) -> str:
        """Generate function definition or call code."""

    @abstractmethod
    def generate_conditional(self, construct: ConditionalConstruct) -> str:
        """Generate conditional (if/else) code."""

    @abstractmethod
    def generate_exception(self, construct: ExceptionConstruct) -> str:
        """Generate exception handling code."""

    @abstractmethod
    def generate_print(self, construct: PrintConstruct) -> str:
        """Generate print/output statement."""

    @abstractmethod
    def generate_return(self, construct: ReturnConstruct) -> str:
        """Generate return statement."""

    def generate_syntax_error(self, construct: SyntaxErrorConstruct) -> str:
        """Generate intentional syntax error."""
        # Default implementation - can be overridden
        marker = self.format_marker(construct.marker) if construct.marker else ""
        return f"{construct.code_snippet}  {marker}"

    def generate_array(self, construct: ArrayConstruct) -> str:
        """Generate array/list creation."""
        # Default implementation - should be overridden
        marker = self.format_marker(construct.marker) if construct.marker else ""
        return f"{self.comment_prefix} TODO: Array generation  {marker}"

    def format_marker(self, marker_text: str | None) -> str:
        """Format a marker for embedding in code."""
        if not marker_text:
            return ""
        return f"{self.comment_prefix}:{marker_text}:"

    @abstractmethod
    def format_program(self, code_blocks: list[str], scenario: Scenario) -> str:
        """Format code blocks into a complete program."""

    @abstractmethod
    def validate_syntax(self, code: str) -> ValidationResult:
        """Validate that generated code has correct syntax."""

    def indent(self, code: str, level: int = 1, width: int = 4) -> str:
        """Indent code by specified level."""
        indent_str = " " * (level * width)
        lines = code.split("\n")
        return "\n".join(
            f"{indent_str}{line}" if line.strip() else line for line in lines
        )

    def generate_body(self, constructs: list[Construct], indent_level: int = 1) -> str:
        """Generate code for a list of body constructs."""
        body_code = []
        for construct in constructs:
            code = self.generate_construct(construct)
            if code:
                indented_code = self.indent(code, indent_level)
                body_code.append(indented_code)
        return "\n".join(body_code)

    def format_string_interpolation(
        self,
        template: str,
        variables: dict[str, str],
    ) -> str:
        """Format string interpolation for the target language."""
        # Default implementation - should be overridden
        result = template
        for var_name in variables:
            result = result.replace(f"{{{var_name}}}", f"${var_name}")
        return result
