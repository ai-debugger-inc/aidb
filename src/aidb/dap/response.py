"""DAP response registry."""

from typing import TYPE_CHECKING, Any, Optional, TypeVar

import aidb.dap.protocol as protocol
from aidb.patterns import Obj
from aidb_common.patterns import Singleton

from .protocol import ProtocolMessage, Response

if TYPE_CHECKING:
    from aidb.common.context import AidbContext

T = TypeVar("T", bound=ProtocolMessage)

RESPONSE_SUFFIX_LENGTH = 8


class ResponseRegistry(Singleton["ResponseRegistry"], Obj):
    """Map DAP commands to their specific response classes.

    Provides dynamic lookup of typed response classes based on command names, enabling
    full type safety when deserializing DAP responses.

    This registry is a singleton because DAP protocol response classes are static and
    never change at runtime, so there's no need for multiple instances.
    """

    _initialized: bool

    def __init__(self, ctx: Optional["AidbContext"] = None):
        """Initialize DAP response factory.

        Parameters
        ----------
        ctx : AidbContext, optional
            Context for logging
        """
        super().__init__(ctx)
        # Only initialize once (using parent's _initialized check)
        if hasattr(self, "_initialized") and self._initialized:
            return

        self._registry: dict[str, type[Response]] = {}
        self._populate_registry()
        self._initialized = True

    def _populate_registry(self) -> None:
        """Auto-populate registry by inspecting the protocol module."""
        for attr_name in dir(protocol):
            if attr_name.endswith("Response") and attr_name != "Response":
                cls = getattr(protocol, attr_name)
                if isinstance(cls, type) and issubclass(cls, Response):
                    # Convert class name to command name e.g.,
                    # InitializeResponse -> initialize
                    command_name = self._class_to_command(attr_name)
                    if command_name:
                        self._registry[command_name] = cls

    def _class_to_command(self, class_name: str) -> str | None:
        """Convert response class name to command name.

        Parameters
        ----------
        class_name : str
            The response class name to convert

        Returns
        -------
        Optional[str]
            The command name, or `None` if conversion fails

        Examples
        --------
        `InitializeResponse` -> `initialize` `SetBreakpointsResponse` ->
        `setBreakpoints` `GotoTargetsResponse` -> `gotoTargets`
        """
        if not class_name.endswith("Response"):
            return None

        # Remove 'Response' suffix
        base_name = class_name[:-RESPONSE_SUFFIX_LENGTH]

        if not base_name:
            return None

        # Convert PascalCase to camelCase First character lowercase, rest
        # unchanged
        return base_name[0].lower() + base_name[1:]

    def get_response_class(self, command: str) -> type[Response]:
        """Get the specific response class for a command.

        Parameters
        ----------
        command : str
            The DAP command name

        Returns
        -------
        Type[Response]
            The specific response class, or generic `Response` if not found
        """
        return self._registry.get(command, Response)

    def create_response(self, msg_dict: dict[str, Any]) -> Response:
        """Create a typed response object from a message dictionary.

        Parameters
        ----------
        msg_dict : dict
            The raw response message dictionary

        Returns
        -------
        Response
            A typed response object (e.g., `InitializeResponse`) or generic
            `Response`
        """
        command = msg_dict.get("command")
        if command:
            response_class = self.get_response_class(command)
            return response_class.from_dict(msg_dict)

        # Fallback to generic response
        return Response.from_dict(msg_dict)

    @property
    def registered_commands(self) -> list[str]:
        """Get list of all registered command names.

        Returns
        -------
        List[str]
            List of all registered command names
        """
        return sorted(self._registry.keys())

    def get_registry_info(self) -> dict[str, str]:
        """Get mapping of commands to their response class names.

        Returns
        -------
        Dict[str, str]
            Mapping of command names to response class names
        """
        return {cmd: cls.__name__ for cmd, cls in self._registry.items()}
