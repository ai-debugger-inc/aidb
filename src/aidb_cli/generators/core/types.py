"""Core types and AST nodes for test program generation."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ConstructType(Enum):
    """Types of constructs that can be generated."""

    VARIABLE = "variable"
    LOOP = "loop"
    FUNCTION = "function"
    CONDITIONAL = "conditional"
    EXCEPTION = "exception"
    PRINT = "print"
    RETURN = "return"
    THREAD = "thread"
    SYNTAX_ERROR = "syntax_error"
    ARRAY = "array"
    OBJECT = "object"


class DataType(Enum):
    """Supported data types across languages."""

    INTEGER = "integer"
    FLOAT = "float"
    STRING = "string"
    BOOLEAN = "boolean"
    ARRAY = "array"
    MAP = "map"
    OBJECT = "object"


class LoopType(Enum):
    """Types of loops."""

    FOR = "for"
    WHILE = "while"
    FOR_EACH = "for_each"


class ScenarioCategory(Enum):
    """Categories of test scenarios."""

    CONTROL_FLOW = "control_flow"
    VARIABLES = "variables"
    FUNCTIONS = "functions"
    EXCEPTIONS = "exceptions"
    ASYNC = "async"
    DEBUGGING = "debugging"


class ComplexityLevel(Enum):
    """Complexity levels for scenarios."""

    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


@dataclass
class Marker:
    """Represents a debugging marker."""

    category: str  # bp, var, func, flow, eval
    action: str  # assign, call, loop, etc.
    identifier: str  # unique identifier

    def format(self, comment_prefix: str) -> str:
        """Format marker for embedding in code."""
        return f"{comment_prefix}:{self.category}.{self.action}.{self.identifier}:"


@dataclass
class Construct:
    """Base class for all constructs."""

    marker: str | None = None
    type: ConstructType | None = None

    def get_marker(self) -> Marker | None:
        """Parse marker string into Marker object."""
        if not self.marker:
            return None
        parts = self.marker.split(".")
        if len(parts) >= 2:
            # Handle both "category.identifier" and "category.action.identifier"
            if len(parts) == 2:
                type_value = self.type.value if self.type else "default"
                return Marker(parts[0], type_value, parts[1])
            return Marker(parts[0], parts[1], ".".join(parts[2:]))
        return None


@dataclass
class VariableConstruct(Construct):
    """Represents a variable declaration or operation."""

    name: str = ""
    data_type: DataType | None = None
    initial_value: Any | None = None
    operation: str | None = None  # assign, increment, decrement, etc.
    value: Any | None = None
    scope: str = "local"  # local, global, parameter

    def __post_init__(self):
        self.type = ConstructType.VARIABLE


@dataclass
class LoopConstruct(Construct):
    """Represents a loop construct."""

    loop_type: LoopType = LoopType.FOR
    variable: str | None = None  # Loop variable name
    start: int | None = None  # For loop start
    end: int | None = None  # For loop end
    step: int | None = 1  # For loop step
    condition: str | None = None  # While loop condition
    iterable: str | None = None  # For-each iterable
    body: list[Construct] = field(default_factory=list)

    def __post_init__(self):
        self.type = ConstructType.LOOP


@dataclass
class Parameter:
    """Function parameter definition."""

    name: str = ""
    data_type: DataType | None = None
    default_value: Any | None = None


@dataclass
class FunctionConstruct(Construct):
    """Represents a function definition or call."""

    name: str = ""
    parameters: list[Parameter] = field(default_factory=list)
    return_type: DataType | None = None
    body: list[Construct] = field(default_factory=list)
    # For function calls
    operation: str | None = None  # "call" for function calls
    arguments: list[Any] = field(default_factory=list)
    result_variable: str | None = None  # Variable to store result

    def __post_init__(self):
        self.type = ConstructType.FUNCTION


@dataclass
class ConditionalConstruct(Construct):
    """Represents if/else conditional logic."""

    condition: str = "true"
    true_body: list[Construct] = field(default_factory=list)
    false_body: list[Construct] = field(default_factory=list)

    def __post_init__(self):
        self.type = ConstructType.CONDITIONAL


@dataclass
class ExceptionConstruct(Construct):
    """Represents exception handling constructs."""

    exception_type: str = "try"  # try, catch, finally, throw
    body: list[Construct] = field(default_factory=list)
    catch_blocks: list[dict[str, Any]] = field(default_factory=list)
    finally_block: dict[str, Any] | None = None

    def __post_init__(self):
        self.type = ConstructType.EXCEPTION


@dataclass
class PrintConstruct(Construct):
    """Represents a print/output statement."""

    message: str = ""
    values: list[str] = field(default_factory=list)  # Variables to interpolate

    def __post_init__(self):
        self.type = ConstructType.PRINT


@dataclass
class ReturnConstruct(Construct):
    """Represents a return statement."""

    value: Any | None = None

    def __post_init__(self):
        self.type = ConstructType.RETURN


@dataclass
class SyntaxErrorConstruct(Construct):
    """Represents an intentional syntax error."""

    error_type: str = "generic"  # unclosed_bracket, undefined_var, etc.
    code_snippet: str = ""  # The invalid code to inject

    def __post_init__(self):
        self.type = ConstructType.SYNTAX_ERROR


@dataclass
class ArrayConstruct(Construct):
    """Represents array/list creation."""

    name: str = ""
    data_type: DataType = DataType.INTEGER
    size: int | None = None
    values: list[Any] = field(default_factory=list)
    initialize: str | None = None  # "range", "zeros", etc.

    def __post_init__(self):
        self.type = ConstructType.ARRAY


@dataclass
class ValidationRule:
    """Validation rule for scenarios."""

    type: str = ""
    criteria: str = ""
    description: str | None = None


@dataclass
class Scenario:
    """Complete scenario definition."""

    id: str = ""
    name: str = ""
    description: str = ""
    category: ScenarioCategory = ScenarioCategory.DEBUGGING
    complexity: ComplexityLevel = ComplexityLevel.BASIC
    constructs: list[Construct] = field(default_factory=list)
    expected_markers: dict[str, int] = field(default_factory=dict)
    validation: list[ValidationRule] = field(default_factory=list)


@dataclass
class GenerationResult:
    """Result of generating a scenario."""

    scenario_id: str = ""
    language: str = ""
    code: str = ""
    markers: dict[str, int] = field(default_factory=dict)  # Marker name -> line number
    success: bool = True
    error: str | None = None


@dataclass
class ValidationResult:
    """Result of validation."""

    is_valid: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
