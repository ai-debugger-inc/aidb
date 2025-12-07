# ============================================================================
# HAND-WRITTEN FILE - Versioned by DAP spec but not auto-generated
#
# Spec hash:    f4feadc09927d22d
# Updated:      2025-12-07T01:35:14Z
# ============================================================================
"""DAP Protocol - Base protocol classes and core interfaces.

Auto-generated from Debug Adapter Protocol specification. Do not edit manually.
"""

import builtins
import json
import logging
from dataclasses import dataclass
from typing import (
    Any,
    Literal,
    Optional,
    TypeVar,
)

from aidb.common.errors import AidbError, DAPProtocolError
from aidb.dap.serialization import SerializableMixin

T = TypeVar("T", bound="ProtocolMessage")
D = TypeVar("D", bound="DAPDataclass")


class DAPDataclass(SerializableMixin):
    """Base class for all DAP protocol dataclasses."""

    def to_dict(self) -> dict[str, Any]:
        """Convert the dataclass to a dictionary for JSON serialization.

        Includes both dataclass fields and dynamically added attributes, which is
        essential for DAP configuration with adapter-specific fields.
        """
        result = super().to_dict()

        # Handle private attributes with name mangling for DAP specific use
        for attr_name, attr_value in self.__dict__.items():
            if attr_name.startswith(f"_{self.__class__.__name__}__"):
                # Include mangled private attributes (like __restart)
                result[attr_name] = self._serialize_value(attr_value)

        return result


class ImmutableAfterInit:
    """Mixin that makes instances immutable after dataclass initialization.

    We cannot use @dataclass(frozen=True) on shared bases because requests remain
    mutable while responses/events should be immutable. This mixin freezes instances in
    __post_init__ and blocks any subsequent attribute mutation or deletion.
    """

    _frozen: bool = False

    def __setattr__(self, name: str, value: Any) -> None:
        # Allow setting before freeze, and always allow setting the flag itself
        if name == "_frozen" or not getattr(self, "_frozen", False):
            return object.__setattr__(self, name, value)
        msg = f"{self.__class__.__name__} is immutable; cannot modify '{name}'"
        raise AttributeError(msg)

    def __delattr__(self, name: str) -> None:
        if not getattr(self, "_frozen", False):
            return object.__delattr__(self, name)
        msg = f"{self.__class__.__name__} is immutable; cannot delete '{name}'"
        raise AttributeError(msg)

    def __post_init__(self):  # Called by dataclasses after __init__
        # Dataclasses always call self.__post_init__() if present on the class
        # hierarchy. This reliably freezes all subclasses after construction.
        object.__setattr__(self, "_frozen", True)


@dataclass
class ProtocolMessage(DAPDataclass):
    """Base class for all DAP protocol messages.

    This includes requests, responses, and events. Each message has a sequence number
    that is used to identify responses to requests.
    """

    # _spec.json#7

    seq: int
    type: Literal["request", "response", "event"]

    def to_json(self) -> str:
        """Convert the message to a JSON string."""
        return json.dumps(self.to_dict())

    def to_dap_message(self) -> bytes:
        """Convert to DAP TCP message format with Content-Length header."""
        json_content = self.to_json()
        content_length = len(json_content.encode("utf-8"))
        return f"Content-Length: {content_length}\r\n\r\n{json_content}".encode()

    @classmethod
    def from_json(cls: builtins.type[T], json_str: str) -> T:
        """Create instance from JSON string."""
        return cls.from_dict(json.loads(json_str))

    @classmethod
    def from_dap_message(cls: builtins.type[T], message: str | bytes) -> T:
        """Parse DAP message from bytes or string with Content-Length header."""
        if isinstance(message, bytes):
            message = message.decode("utf-8")

        lines = message.split("\r\n")
        if not lines[0].startswith("Content-Length:"):
            msg = "Invalid DAP message format: missing Content-Length header"
            raise DAPProtocolError(msg)

        try:
            content_length = int(lines[0].split(": ")[1])
        except (IndexError, ValueError) as e:
            msg = "Invalid Content-Length header"
            raise DAPProtocolError(msg) from e

        # Find the empty line that separates headers from content
        content_start = None
        for i, line in enumerate(lines):
            if line == "":
                content_start = i + 1
                break

        if content_start is None:
            msg = "Invalid DAP message format: no header/content separator"
            raise DAPProtocolError(msg)

        json_content = "\r\n".join(lines[content_start:])
        if len(json_content.encode("utf-8")) != content_length:
            msg = "Content length mismatch"
            raise DAPProtocolError(msg)

        return cls.from_json(json_content)


@dataclass
class Request(ProtocolMessage):
    """A client or debug adapter initiated request."""

    # _spec.json#31

    type: Literal["request"] = "request"
    command: str = ""
    arguments: dict[str, Any] | Any | None = None


@dataclass
class Response(ImmutableAfterInit, ProtocolMessage):
    """Response for a request."""

    # _spec.json#109

    type: Literal["response"] = "response"
    request_seq: int = 0
    success: bool = True
    command: str = ""
    message: str | None = None
    body: Optional["OperationResponseBody"] = None

    # Catch-all for operation-specific data
    extra: dict[str, Any] | None = None

    def ensure_success(self) -> None:
        """Ensure the response was successful or raise AidbError."""
        if not self.success:
            msg = f"{self.command} failed: {self.message}"
            raise AidbError(msg)


@dataclass
class Event(ImmutableAfterInit, ProtocolMessage):
    """A debug adapter initiated event."""

    # _spec.json#70

    type: Literal["event"] = "event"
    event: str = ""
    body: Optional["OperationEventBody"] = None

    # Catch-all for operation-specific data
    extra: dict[str, Any] | None = None

    _EVENT_BODY_MAP = {
        "breakpoint": "BreakpointEventBody",
        "capabilities": "CapabilitiesEventBody",
        "continued": "ContinuedEventBody",
        "exited": "ExitedEventBody",
        "invalidated": "InvalidatedEventBody",
        "loadedSource": "LoadedSourceEventBody",
        "memory": "MemoryEventBody",
        "module": "ModuleEventBody",
        "output": "OutputEventBody",
        "process": "ProcessEventBody",
        "progressEnd": "ProgressEndEventBody",
        "progressStart": "ProgressStartEventBody",
        "progressUpdate": "ProgressUpdateEventBody",
        "stopped": "StoppedEventBody",
        "terminated": "TerminatedEventBody",
        "thread": "ThreadEventBody",
    }

    @classmethod
    def from_dict(cls, data: dict[str, Any]):
        """Create Event instance with proper event body deserialization."""
        # Make a copy to avoid modifying original data
        data_copy = data.copy()

        # Handle event body deserialization based on event type
        if "body" in data_copy and data_copy["body"] is not None:
            event_type = data_copy.get("event", "")
            body_class_name = cls._EVENT_BODY_MAP.get(event_type)

            if body_class_name:
                from ..protocol import bodies

                if hasattr(bodies, body_class_name):
                    body_class = getattr(bodies, body_class_name)
                    try:
                        # Deserialize body to the specific event body class
                        data_copy["body"] = body_class.from_dict(data_copy["body"])
                    except Exception as e:
                        msg = (
                            f"Failed to deserialize event body for "
                            f"{data_copy.get('event', 'unknown')}: {e}"
                        )
                        logging.debug(msg)
                # If specific body class not found, leave as dict
            # If no mapping found or custom event, leave body as dict

        # Create Event instance directly, avoiding parent's recursive processing
        # which would try to deserialize body field again
        return cls(
            seq=data_copy.get("seq", 0),
            type=data_copy.get("type", "event"),
            event=data_copy.get("event", ""),
            body=data_copy.get("body"),
            extra=data_copy.get("extra"),
        )


@dataclass
class OperationResponseBody(ImmutableAfterInit, SerializableMixin):
    """Base class for all DAP response body types.

    This class serves as the base type for all operation-specific response body
    dataclasses, providing type safety and better IDE support compared to using generic
    dictionaries.
    """


@dataclass
class OperationEventBody(ImmutableAfterInit, SerializableMixin):
    """Base class for all DAP event body types.

    This class serves as the base type for all operation-specific event body
    dataclasses, providing type safety and better IDE support compared to using generic
    dictionaries.
    """
