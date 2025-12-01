"""Stack frame entity models."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aidb.common.code_context import CodeContextResult


@dataclass(frozen=True)
class SourceLocation:
    """Source code location information."""

    path: str
    line: int
    column: int | None = None
    timestamp: datetime = field(default_factory=datetime.now)

    def __str__(self) -> str:
        """Return a string representation of the source location."""
        if self.column is not None:
            return f"{self.path}:{self.line}:{self.column}"
        return f"{self.path}:{self.line}"


@dataclass(frozen=True)
class AidbStackFrame:
    """Information about a single stack frame."""

    id: int
    name: str
    source: SourceLocation
    module: str
    locals: dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    code_context: "CodeContextResult | None" = None

    @property
    def file(self) -> str:
        """Get the file path."""
        return self.source.path

    @property
    def line(self) -> int:
        """Get the line number."""
        return self.source.line
