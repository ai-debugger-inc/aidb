"""Memory and module-related response models."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..base import OperationResponse, SamplingMixin

if TYPE_CHECKING:
    from aidb.dap.protocol.responses import (
        DisassembleResponse,
        ModulesResponse,
        ReadMemoryResponse,
        WriteMemoryResponse,
    )


@dataclass(frozen=True)
class AidbDisassembleResponse(OperationResponse, SamplingMixin):
    """Response model for disassemble operations.

    Attributes
    ----------
    instructions : List[DisassembledInstruction]
        List of disassembled instructions
    """

    instructions: list[Any] = field(
        default_factory=list,
    )  # Will use DisassembledInstruction from entities

    @property
    def instruction_count(self) -> int:
        """Get the number of instructions."""
        return len(self.instructions)

    def sample_instructions(self, n: int = 10) -> list[Any]:
        """Sample a subset of instructions.

        Parameters
        ----------
        n : int
            Number of instructions to sample

        Returns
        -------
        List[DisassembledInstruction]
            Sampled instructions
        """
        return self._sample_list(self.instructions, n)

    @classmethod
    def from_dap(cls, dap_response: "DisassembleResponse") -> "AidbDisassembleResponse":
        """Create from DAP DisassembleResponse.

        Parameters
        ----------
        dap_response : DisassembleResponse
            The DAP response to convert

        Returns
        -------
        AidbDisassembleResponse
            The converted response
        """
        instructions = []
        if dap_response.body and dap_response.body.instructions:
            instructions = dap_response.body.instructions

        return cls(
            instructions=instructions,
            success=dap_response.success,
            message=dap_response.message if not dap_response.success else None,
        )


@dataclass(frozen=True)
class AidbModulesResponse(OperationResponse, SamplingMixin):
    """Response model for modules listing.

    Attributes
    ----------
    modules : List[Module]
        List of loaded modules
    totalModules : Optional[int]
        Total number of modules if different from returned count
    """

    modules: list[Any] = field(default_factory=list)  # Will use Module from entities
    totalModules: int | None = None

    @property
    def module_count(self) -> int:
        """Get the number of modules returned."""
        return len(self.modules)

    def get_user_modules(self) -> list[Any]:
        """Get only user code modules.

        Returns
        -------
        List[Module]
            List of modules marked as user code
        """
        return [m for m in self.modules if m.isUserCode]

    def get_system_modules(self) -> list[Any]:
        """Get only system modules.

        Returns
        -------
        List[Module]
            List of modules not marked as user code
        """
        return [m for m in self.modules if not m.isUserCode]

    @classmethod
    def from_dap(cls, dap_response: "ModulesResponse") -> "AidbModulesResponse":
        """Create from DAP ModulesResponse.

        Parameters
        ----------
        dap_response : ModulesResponse
            The DAP response to convert

        Returns
        -------
        AidbModulesResponse
            The converted response
        """
        modules = []
        total_modules = None
        if dap_response.body:
            if dap_response.body.modules:
                modules = dap_response.body.modules
            total_modules = dap_response.body.totalModules

        return cls(
            modules=modules,
            totalModules=total_modules,
            success=dap_response.success,
            message=dap_response.message if not dap_response.success else None,
        )


@dataclass(frozen=True)
class AidbReadMemoryResponse(OperationResponse):
    """Response model for memory read operations.

    Attributes
    ----------
    address : str
        The memory address that was read
    unreadableBytes : Optional[int]
        Number of bytes that could not be read
    data : Optional[str]
        The memory contents as base64-encoded string
    """

    address: str = ""
    data: str | None = None
    unreadableBytes: int | None = None

    def get_bytes(self) -> bytes | None:
        """Decode the base64 data to bytes.

        Returns
        -------
        Optional[bytes]
            Decoded memory contents or None if no data
        """
        if self.data:
            import base64

            return base64.b64decode(self.data)
        return None

    @classmethod
    def from_dap(cls, dap_response: "ReadMemoryResponse") -> "AidbReadMemoryResponse":
        """Create from DAP ReadMemoryResponse.

        Parameters
        ----------
        dap_response : ReadMemoryResponse
            The DAP response to convert

        Returns
        -------
        AidbReadMemoryResponse
            The converted response
        """
        address = ""
        data = None
        unreadable_bytes = None

        if dap_response.body:
            address = dap_response.body.address
            data = dap_response.body.data
            unreadable_bytes = dap_response.body.unreadableBytes

        return cls(
            address=address,
            data=data,
            unreadableBytes=unreadable_bytes,
            success=dap_response.success,
            message=dap_response.message if not dap_response.success else None,
        )


@dataclass(frozen=True)
class AidbWriteMemoryResponse(OperationResponse):
    """Response model for memory write operations.

    Attributes
    ----------
    offset : Optional[int]
        Offset from requested address where write began
    bytesWritten : Optional[int]
        Number of bytes actually written
    """

    offset: int | None = None
    bytesWritten: int | None = None

    @classmethod
    def from_dap(cls, dap_response: "WriteMemoryResponse") -> "AidbWriteMemoryResponse":
        """Create from DAP WriteMemoryResponse.

        Parameters
        ----------
        dap_response : WriteMemoryResponse
            The DAP response to convert

        Returns
        -------
        AidbWriteMemoryResponse
            The converted response
        """
        offset = None
        bytes_written = None

        if dap_response.body:
            offset = dap_response.body.offset
            bytes_written = dap_response.body.bytesWritten

        return cls(
            offset=offset,
            bytesWritten=bytes_written,
            success=dap_response.success,
            message=dap_response.message if not dap_response.success else None,
        )
