"""Memory-related entity models."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DisassembledInstruction:
    """Represents a single disassembled instruction.

    Attributes
    ----------
    address : str
        The address of the instruction as a string (memory reference)
    instruction : str
        The disassembled instruction text
    instructionBytes : Optional[str]
        Raw bytes of the instruction encoded as hex string
    symbol : Optional[str]
        Symbol/function name associated with this instruction
    location : Optional[str]
        Source location if available
    line : Optional[int]
        Line number in source if available
    column : Optional[int]
        Column in source if available
    endLine : Optional[int]
        End line in source for multi-line instructions
    endColumn : Optional[int]
        End column in source
    """

    address: str
    instruction: str
    instructionBytes: str | None = None
    symbol: str | None = None
    location: str | None = None
    line: int | None = None
    column: int | None = None
    endLine: int | None = None
    endColumn: int | None = None


@dataclass(frozen=True)
class Module:
    """Represents a loaded module in the debugger.

    Attributes
    ----------
    id : int
        Unique identifier for the module (adapter-specific)
    name : str
        Module name or path
    path : Optional[str]
        Full path to the module on the file system
    isOptimized : Optional[bool]
        Whether the module is optimized
    isUserCode : Optional[bool]
        Whether this is user code vs system code
    version : Optional[str]
        Version information for the module
    symbolStatus : Optional[str]
        Status of symbol loading for the module
    symbolFilePath : Optional[str]
        Path to symbol file if separate from module
    dateTimeStamp : Optional[str]
        Module timestamp
    addressRange : Optional[str]
        Memory address range occupied by the module
    """

    id: int
    name: str
    path: str | None = None
    isOptimized: bool | None = None
    isUserCode: bool | None = None
    version: str | None = None
    symbolStatus: str | None = None
    symbolFilePath: str | None = None
    dateTimeStamp: str | None = None
    addressRange: str | None = None
