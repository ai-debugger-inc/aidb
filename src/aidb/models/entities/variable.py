"""Variable entity models."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any


class VariableType(Enum):
    """Types of variables that can be represented."""

    PRIMITIVE = auto()
    OBJECT = auto()
    ARRAY = auto()
    FUNCTION = auto()
    CLASS = auto()
    MODULE = auto()
    UNKNOWN = auto()


@dataclass(frozen=True)
class AidbVariable:
    """Information about a single variable."""

    name: str
    value: Any
    type_name: str
    var_type: VariableType
    has_children: bool = False
    children: dict[str, "AidbVariable"] = field(default_factory=dict)
    id: int | None = None

    def __str__(self) -> str:
        """Return a string representation of the variable."""
        return f"{self.name} = {self.value} ({self.type_name})"


@dataclass(frozen=True)
class EvaluationResult:
    """Result of evaluating an expression."""

    expression: str
    result: Any
    type_name: str
    var_type: VariableType
    error: str | None = None
    has_children: bool = False
    children: dict[str, AidbVariable] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def is_error(self) -> bool:
        """Check if evaluation resulted in an error."""
        return self.error is not None


@dataclass(frozen=True)
class ScopeVariables:
    """Variables grouped by scope."""

    locals: dict[str, AidbVariable] = field(default_factory=dict)
    globals: dict[str, AidbVariable] = field(default_factory=dict)
    frame_id: int = 0
