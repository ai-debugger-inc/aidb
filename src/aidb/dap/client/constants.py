"""Constants for DAP client.

This module contains commonly used string constants across the DAP client implementation
to improve maintainability and reduce magic strings.
"""

from enum import Enum


class MessageType(Enum):
    """DAP message types."""

    REQUEST = "request"
    RESPONSE = "response"
    EVENT = "event"


class EventType(Enum):
    """Common DAP event types."""

    INITIALIZED = "initialized"
    STOPPED = "stopped"
    CONTINUED = "continued"
    TERMINATED = "terminated"
    EXITED = "exited"
    THREAD = "thread"
    OUTPUT = "output"
    BREAKPOINT = "breakpoint"
    MODULE = "module"
    LOADED_SOURCE = "loadedSource"
    PROCESS = "process"
    CAPABILITIES = "capabilities"
    PROGRESSSTART = "progressStart"
    PROGRESSUPDATE = "progressUpdate"
    PROGRESSEND = "progressEnd"
    INVALIDATED = "invalidated"
    MEMORY = "memory"


class CommandType(Enum):
    """DAP command types for setup and connection management."""

    INITIALIZE = "initialize"
    ATTACH = "attach"
    LAUNCH = "launch"
    SET_BREAKPOINTS = "setBreakpoints"
    SET_FUNCTION_BREAKPOINTS = "setFunctionBreakpoints"
    SET_EXCEPTION_BREAKPOINTS = "setExceptionBreakpoints"
    SET_DATA_BREAKPOINTS = "setDataBreakpoints"
    SET_INSTRUCTION_BREAKPOINTS = "setInstructionBreakpoints"
    CONFIGURATION_DONE = "configurationDone"
    DISCONNECT = "disconnect"
    TERMINATE = "terminate"
    START_DEBUGGING = "startDebugging"
    CONTINUE = "continue"
    NEXT = "next"
    STEP_IN = "stepIn"
    STEP_OUT = "stepOut"
    STEP_BACK = "stepBack"
    REVERSE_CONTINUE = "reverseContinue"
    RESTART_FRAME = "restartFrame"
    GOTO = "goto"
    PAUSE = "pause"
    STACK_TRACE = "stackTrace"
    SCOPES = "scopes"
    VARIABLES = "variables"
    SET_VARIABLE = "setVariable"
    SOURCE = "source"
    THREADS = "threads"
    MODULES = "modules"
    LOADED_SOURCES = "loadedSources"
    EVALUATE = "evaluate"
    SET_EXPRESSION = "setExpression"
    STEP_IN_TARGETS = "stepInTargets"
    GOTO_TARGETS = "gotoTargets"
    COMPLETIONS = "completions"
    EXCEPTION_INFO = "exceptionInfo"
    READ_MEMORY = "readMemory"
    WRITE_MEMORY = "writeMemory"
    DISASSEMBLE = "disassemble"


# Connection setup commands that can be retried on failure
CONNECTION_SETUP_COMMANDS = {
    CommandType.INITIALIZE.value,
    CommandType.ATTACH.value,
    CommandType.LAUNCH.value,
    CommandType.SET_BREAKPOINTS.value,
    CommandType.SET_FUNCTION_BREAKPOINTS.value,
    CommandType.SET_EXCEPTION_BREAKPOINTS.value,
    CommandType.SET_DATA_BREAKPOINTS.value,
    CommandType.SET_INSTRUCTION_BREAKPOINTS.value,
    CommandType.CONFIGURATION_DONE.value,
    CommandType.DISCONNECT.value,
    CommandType.TERMINATE.value,
}


class StopReason(Enum):
    """Reasons for debugger stopping."""

    STEP = "step"
    BREAKPOINT = "breakpoint"
    EXCEPTION = "exception"
    PAUSE = "pause"
    ENTRY = "entry"
    EXIT = "exit"
    GOTO = "goto"
    FUNCTION_BREAKPOINT = "function breakpoint"
    DATA_BREAKPOINT = "data breakpoint"
    INSTRUCTION_BREAKPOINT = "instruction breakpoint"


# Environment variable names
ENV_VAR_NAMES = {
    "AIDB_ADAPTER_TRACE": "AIDB_ADAPTER_TRACE",
    "AIDB_LOG_LEVEL": "AIDB_LOG_LEVEL",
    "AIDB_DAP_REQUEST_WAIT_TIMEOUT": "AIDB_DAP_REQUEST_WAIT_TIMEOUT",
}
