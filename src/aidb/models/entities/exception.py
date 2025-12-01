"""Exception entity models."""

from dataclasses import dataclass, field
from datetime import datetime

from .stack import AidbStackFrame


@dataclass(frozen=True)
class ExceptionInfo:
    """Information about an exception that occurred during debugging."""

    type_name: str
    message: str
    description: str | None = None
    stack_frames: list[AidbStackFrame] = field(default_factory=list)
    is_uncaught: bool = True
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def has_stack_trace(self) -> bool:
        """Check if exception has stack trace information."""
        return bool(self.stack_frames)
