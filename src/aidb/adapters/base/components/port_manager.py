"""Port management component for debug adapters.

This module handles port acquisition, verification, and release for debug adapters.
"""

from typing import TYPE_CHECKING, Optional

from aidb.common.errors import DebugAdapterError
from aidb.patterns.base import Obj

if TYPE_CHECKING:
    from aidb.interfaces.context import IContext
    from aidb.interfaces.session import ISessionResource


class PortManager(Obj):
    """Manages port allocation and lifecycle for debug adapters.

    This class encapsulates all port-related operations including:
        - Acquiring available ports from the resource manager
        - Verifying port availability
        - Releasing ports back to the pool
        - Tracking port assignments

    Parameters
    ----------
    resource_manager : ResourceManager
        Resource manager for port allocation
    ctx : IContext, optional
        Context for logging
    """

    def __init__(
        self,
        resource_manager: Optional["ISessionResource"],
        ctx: Optional["IContext"] = None,
    ):
        """Initialize port manager.

        Parameters
        ----------
        resource_manager : ISessionResource, optional
            Resource manager for port tracking
        ctx : IContext, optional
            Context for logging
        """
        super().__init__(ctx)
        self.resource_manager = resource_manager
        self._port: int | None = None

    @property
    def port(self) -> int | None:
        """Get the currently assigned port.

        Returns
        -------
        Optional[int]
            Port number or None if not assigned
        """
        return self._port

    async def acquire(
        self,
        requested_port: int | None = None,
        fallback_start: int = 10000,
    ) -> int:
        """Acquire an available port for the debug adapter.

        Parameters
        ----------
        requested_port : int, optional
            Specific port to request, if available
        fallback_start : int, optional
            Start of port range for fallback allocation

        Returns
        -------
        int
            The acquired port number

        Raises
        ------
        RuntimeError
            If no port could be acquired
        """
        if self._port is not None:
            self.ctx.warning(f"Port {self._port} already acquired, releasing first")
            self.release()

        self.ctx.debug(
            f"[PortManager] acquire() called with requested_port={requested_port}, "
            f"fallback_start={fallback_start}",
        )

        try:
            if requested_port and self.resource_manager:
                # Try to acquire the requested port
                self.ctx.debug(f"Attempting to acquire requested port {requested_port}")
                self._port = await self.resource_manager.acquire_port(
                    start_port=requested_port,
                )
                self.ctx.debug(f"Successfully acquired requested port {self._port}")
            else:
                self.ctx.debug(
                    f"No specific port requested, acquiring from {fallback_start}",
                )
                if self.resource_manager:
                    self._port = await self.resource_manager.acquire_port(
                        start_port=fallback_start,
                    )
                self.ctx.debug(f"Acquired available port {self._port}")

            if self._port is None:
                msg = "Failed to acquire any port"
                raise DebugAdapterError(msg)
            return self._port

        except Exception as e:
            error_msg = f"Failed to acquire port: {e}"
            self.ctx.error(error_msg)
            raise DebugAdapterError(error_msg) from e

    def release(self) -> None:
        """Release the currently held port back to the pool."""
        if self._port is None:
            self.ctx.debug("No port to release")
            return

        try:
            if self.resource_manager:
                self.resource_manager.release_port(self._port)
            self.ctx.debug(f"Released port {self._port}")
            self._port = None
        except Exception as e:
            self.ctx.warning(f"Failed to release port {self._port}: {e}")
            # Clear the port even if release failed
            self._port = None
