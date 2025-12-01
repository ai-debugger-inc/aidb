"""Thread entity models."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto


class ThreadState(Enum):
    """Possible states for a thread."""

    RUNNING = auto()
    STOPPED = auto()
    TERMINATED = auto()
    UNKNOWN = auto()


@dataclass(frozen=True)
class AidbThread:
    """Information about a debug thread."""

    id: int
    name: str
    state: ThreadState
    is_stopped: bool = False
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def is_running(self) -> bool:
        """Check if thread is running."""
        return self.state == ThreadState.RUNNING
