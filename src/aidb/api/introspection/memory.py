"""Memory inspection and manipulation operations."""

from typing import TYPE_CHECKING, Optional

from aidb.audit.middleware import audit_operation
from aidb.common.errors import AidbError
from aidb.models import (
    AidbDisassembleResponse,
    AidbReadMemoryResponse,
    AidbWriteMemoryResponse,
)
from aidb.session import Session

from ..base import APIOperationBase
from ..constants import (
    DEFAULT_ALLOW_PARTIAL_MEMORY,
    DEFAULT_INSTRUCTION_COUNT,
    DEFAULT_MEMORY_COUNT,
    DEFAULT_MEMORY_OFFSET,
    DEFAULT_RESOLVE_SYMBOLS,
)

if TYPE_CHECKING:
    from aidb.common import AidbContext


class MemoryOperations(APIOperationBase):
    """Memory inspection and manipulation operations."""

    def __init__(self, session: Session, ctx: Optional["AidbContext"] = None):
        """Initialize the MemoryOperations instance.

        Parameters
        ----------
        session : Session
            Session to use
        ctx : AidbContext, optional
            Application context
        """
        super().__init__(session, ctx)

    @audit_operation(component="api.introspection", operation="read_memory")
    async def read_memory(
        self,
        memory_reference: str,
        offset: int = DEFAULT_MEMORY_OFFSET,
        count: int = DEFAULT_MEMORY_COUNT,
        allow_partial: bool = DEFAULT_ALLOW_PARTIAL_MEMORY,
    ) -> AidbReadMemoryResponse:
        """Read memory from the debugged process.

        This operation is automatically audited when audit logging is enabled.

        Parameters
        ----------
        memory_reference : str
            Memory reference/address to read from
        offset : int
            Offset from the reference, default 0
        count : int
            Number of bytes to read, default 256
        allow_partial : bool
            Allow partial reads if full read fails, default False

        Returns
        -------
        AidbReadMemoryResponse
            Memory content and metadata

        Raises
        ------
        AidbError
            If memory read is not supported
        """
        # Check if memory operations are supported
        if not self.session.has_capability("supportsReadMemoryRequest"):
            msg = "Memory read is not supported by this debug adapter"
            raise AidbError(msg)

        try:
            # Use session's memory operations
            return await self.session.debug.read_memory(
                memory_reference=memory_reference,
                offset=offset,
                count=count,
            )
        except Exception as e:
            if allow_partial:
                self.ctx.warning(f"Partial memory read at {memory_reference}: {e}")
                return AidbReadMemoryResponse(
                    address=memory_reference,
                    data="",
                    unreadableBytes=count,
                )
            msg = f"Failed to read memory at {memory_reference}: {e}"
            raise AidbError(msg) from e

    @audit_operation(component="api.introspection", operation="write_memory")
    async def write_memory(
        self,
        memory_reference: str,
        data: str,
        offset: int = DEFAULT_MEMORY_OFFSET,
        allow_partial: bool = DEFAULT_ALLOW_PARTIAL_MEMORY,
    ) -> AidbWriteMemoryResponse:
        """Write memory to the debugged process.

        This operation is automatically audited when audit logging is enabled.

        Parameters
        ----------
        memory_reference : str
            Memory reference/address to write to
        data : str
            Base64-encoded data to write
        offset : int
            Offset from the reference, default 0
        allow_partial : bool
            Allow partial writes if full write fails, default False

        Returns
        -------
        AidbWriteMemoryResponse
            Information about the written memory

        Raises
        ------
        AidbError
            If memory write is not supported
        """
        # Check if memory operations are supported
        if not self.session.has_capability("supportsWriteMemoryRequest"):
            msg = "Memory write is not supported by this debug adapter"
            raise AidbError(msg)

        try:
            # Use session's memory operations
            response = await self.session.debug.write_memory(
                memory_reference=memory_reference,
                data=data,
                offset=offset,
                allow_partial=allow_partial,
            )

            if response.bytes_written == 0 and not allow_partial:
                msg = f"No bytes written to memory at {memory_reference}"
                raise AidbError(msg)

            return response
        except Exception as e:
            msg = f"Failed to write memory at {memory_reference}: {e}"
            raise AidbError(msg) from e

    @audit_operation(component="api.introspection", operation="disassemble")
    async def disassemble(
        self,
        memory_reference: str,
        byte_offset: int = DEFAULT_MEMORY_OFFSET,
        instruction_offset: int = 0,
        instruction_count: int = DEFAULT_INSTRUCTION_COUNT,
        resolve_symbols: bool = DEFAULT_RESOLVE_SYMBOLS,
    ) -> AidbDisassembleResponse:
        """Disassemble memory into instructions.

        This operation is automatically audited when audit logging is enabled.

        Parameters
        ----------
        memory_reference : str
            Memory reference/address to disassemble from
        byte_offset : int
            Byte offset from the reference, default 0
        instruction_offset : int
            Instruction offset from the reference, default 0
        instruction_count : int
            Number of instructions to disassemble, default 10
        resolve_symbols : bool
            Resolve symbolic names, default True

        Returns
        -------
        AidbDisassembleResponse
            Disassembled instructions

        Raises
        ------
        AidbError
            If disassembly is not supported
        """
        # Check if disassembly is supported
        if not self.session.has_capability("supportsDisassembleRequest"):
            msg = "Disassembly is not supported by this debug adapter"
            raise AidbError(msg)

        try:
            # Use session's disassemble operation
            return await self.session.debug.disassemble(
                memory_reference=memory_reference,
                byte_offset=byte_offset,
                instruction_offset=instruction_offset,
                instruction_count=instruction_count,
                resolve_symbols=resolve_symbols,
            )
        except Exception as e:
            msg = f"Failed to disassemble memory at {memory_reference}: {e}"
            raise AidbError(
                msg,
            ) from e
