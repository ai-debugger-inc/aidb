"""Session entity models."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any

from aidb_common.constants import Language


class SessionStatus(Enum):
    """Possible states for a debug session."""

    INITIALIZING = auto()
    INITIALIZED = auto()  # Session initialized but not yet running
    READY = auto()  # Session ready for debugging
    RUNNING = auto()
    PAUSED = auto()
    TERMINATED = auto()
    ERROR = auto()


class StopReason(Enum):
    """Reasons why execution might stop."""

    BREAKPOINT = auto()
    STEP = auto()
    PAUSE = auto()
    EXCEPTION = auto()
    ENTRY = auto()
    EXIT = auto()
    UNKNOWN = auto()


@dataclass(frozen=True)
class SessionInfo:
    """Information about the current debug session."""

    id: str
    status: SessionStatus
    target: str
    pid: int | None = None
    language: str = Language.PYTHON.value
    timestamp: datetime = field(default_factory=datetime.now)
    host: str = "localhost"
    port: int = 0
    adapter_id: str | None = None

    @property
    def is_active(self) -> bool:
        """Check if session is active."""
        return self.status in (SessionStatus.RUNNING, SessionStatus.PAUSED)


@dataclass(frozen=True)
class ExecutionState:
    """Detailed state of execution."""

    status: SessionStatus
    running: bool
    paused: bool
    stop_reason: StopReason | None = None
    thread_id: int | None = None
    frame_id: int | None = None
    exception_info: dict[str, Any] | None = None
    terminated: bool = False
    current_file: str | None = None
    current_line: int | None = None
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def is_exception(self) -> bool:
        """Check if execution stopped due to an exception."""
        return self.stop_reason == StopReason.EXCEPTION

    @property
    def is_active(self) -> bool:
        """Check if debugger is active (running or paused)."""
        return self.running or self.paused
