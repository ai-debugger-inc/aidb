"""Memory introspection operations."""

from typing import TYPE_CHECKING, cast

from aidb.common import AidbContext
from aidb.dap.protocol.bodies import (
    DisassembleArguments,
    ReadMemoryArguments,
    VariablesArguments,
    WriteMemoryArguments,
)
from aidb.dap.protocol.requests import (
    DisassembleRequest,
    ReadMemoryRequest,
    VariablesRequest,
    WriteMemoryRequest,
)
from aidb.models import (
    AidbDisassembleResponse,
    AidbReadMemoryResponse,
    AidbWriteMemoryResponse,
)

from ..base import SessionOperationsMixin
from ..decorators import requires_capability

if TYPE_CHECKING:
    from aidb.dap.protocol.base import Response
    from aidb.dap.protocol.responses import (
        DisassembleResponse,
        ReadMemoryResponse,
        VariablesResponse,
        WriteMemoryResponse,
    )
    from aidb.session import Session


class MemoryOperations(SessionOperationsMixin):
    """Memory introspection operations."""

    def __init__(self, session: "Session", ctx: AidbContext | None = None) -> None:
        """Initialize memory operations.

        Parameters
        ----------
        session : Session
            Debug session instance
        ctx : AidbContext, optional
            Application context, by default `None`
        """
        super().__init__(session, ctx)

    @requires_capability("supportsReadMemoryRequest", "memory reading")
    async def read_memory(
        self,
        memory_reference: str,
        offset: int = 0,
        count: int = 256,
    ) -> AidbReadMemoryResponse:
        """Read raw memory from the target.

        Parameters
        ----------
        memory_reference : str
            Memory reference (e.g., "0x1000" or variable reference)
        offset : int
            Offset from the memory reference in bytes, by default 0
        count : int
            Number of bytes to read, by default 256

        Returns
        -------
        AidbReadMemoryResponse
            Raw memory data and address information
        """
        request = ReadMemoryRequest(
            seq=0,  # Will be overwritten by client
            arguments=ReadMemoryArguments(
                memoryReference=memory_reference,
                offset=offset,
                count=count,
            ),
        )

        response: Response = await self.session.dap.send_request(request)
        response.ensure_success()

        # Map the response using from_dap
        read_response = cast("ReadMemoryResponse", response)
        return AidbReadMemoryResponse.from_dap(read_response)

    @requires_capability("supportsWriteMemoryRequest", "memory writing")
    async def write_memory(
        self,
        memory_reference: str,
        data: str,
        offset: int = 0,
        allow_partial: bool = False,
    ) -> AidbWriteMemoryResponse:
        """Write raw memory to the target.

        Parameters
        ----------
        memory_reference : str
            Memory reference (e.g., "0x1000" or variable reference)
        data : str
            Base64-encoded data to write
        offset : int
            Offset from the memory reference in bytes, by default 0
        allow_partial : bool
            Whether to allow partial writes if not all bytes can be written,
            by default False

        Returns
        -------
        AidbWriteMemoryResponse
            Information about bytes written and starting address
        """
        request = WriteMemoryRequest(
            seq=0,  # Will be overwritten by client
            arguments=WriteMemoryArguments(
                memoryReference=memory_reference,
                offset=offset,
                allowPartial=allow_partial,
                data=data,
            ),
        )

        response: Response = await self.session.dap.send_request(request)
        response.ensure_success()

        # Map the response using from_dap
        write_response = cast("WriteMemoryResponse", response)
        return AidbWriteMemoryResponse.from_dap(write_response)

    async def get_memory_reference(self, variable_reference: int) -> str | None:
        """Get memory reference for a variable.

        This method retrieves the memory reference (e.g., pointer address) for
        a given variable reference. This is useful for getting the address of
        variables to pass to read_memory or write_memory operations.

        Parameters
        ----------
        variable_reference : int
            AidbVariable reference ID from a variables response

        Returns
        -------
        Optional[str]
            Memory reference string if available, None otherwise
        """
        # Get variable details
        request = VariablesRequest(
            seq=0,  # Will be overwritten by client
            arguments=VariablesArguments(variablesReference=variable_reference),
        )

        response: Response = await self.session.dap.send_request(request)
        var_response = cast("VariablesResponse", response)
        var_response.ensure_success()

        # Look for memory reference in variables
        if var_response.body and var_response.body.variables:
            for var in var_response.body.variables:
                # Some adapters provide memory reference as a special property
                if hasattr(var, "memoryReference") and var.memoryReference:
                    return var.memoryReference
                # Some adapters include address in the value field
                if var.value and (
                    var.value.startswith("0x") or var.value.startswith("0X")
                ):
                    # Extract potential memory address from value
                    parts = var.value.split()
                    if parts:
                        addr = parts[0]
                        if addr.startswith(("0x", "0X")):
                            return addr

        return None

    @requires_capability("supportsDisassembleRequest", "disassembly")
    async def disassemble(
        self,
        memory_reference: str,
        offset: int = 0,
        instruction_offset: int = -5,
        instruction_count: int = 20,
        resolve_symbols: bool = True,
    ) -> AidbDisassembleResponse:
        """Disassemble machine code to instructions.

        Parameters
        ----------
        memory_reference : str
            Memory reference to start disassembly (e.g., "0x1000" or frame PC)
        offset : int
            Byte offset from memory reference, by default 0
        instruction_offset : int
            Number of instructions before the reference to include
            (negative value), by default -5
        instruction_count : int
            Total number of instructions to disassemble, by default 20
        resolve_symbols : bool
            Whether to resolve symbol names in disassembly, by default True

        Returns
        -------
        AidbDisassembleResponse
            Disassembled instructions with addresses and optional source locations
        """
        request = DisassembleRequest(
            seq=0,  # Will be overwritten by client
            arguments=DisassembleArguments(
                memoryReference=memory_reference,
                offset=offset,
                instructionOffset=instruction_offset,
                instructionCount=instruction_count,
                resolveSymbols=resolve_symbols,
            ),
        )

        response: Response = await self.session.dap.send_request(request)
        response.ensure_success()

        # Map the response using from_dap
        disassemble_response = cast("DisassembleResponse", response)
        return AidbDisassembleResponse.from_dap(disassemble_response)
