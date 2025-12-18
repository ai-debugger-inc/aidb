"""DAP capability constants and operation names.

This module centralizes DAP capability strings and their associated operation names for
consistent use across the codebase.
"""


class DAPCapability:
    """DAP capability attribute names.

    These strings correspond to the capability attributes returned in the DAP
    InitializeResponse.
    """

    # Breakpoint capabilities
    CONDITIONAL_BREAKPOINTS = "supportsConditionalBreakpoints"
    FUNCTION_BREAKPOINTS = "supportsFunctionBreakpoints"
    LOG_POINTS = "supportsLogPoints"
    DATA_BREAKPOINTS = "supportsDataBreakpoints"
    INSTRUCTION_BREAKPOINTS = "supportsInstructionBreakpoints"
    HIT_CONDITION = "supportsHitConditionalBreakpoints"

    # Execution control capabilities
    GOTO_TARGETS = "supportsGotoTargetsRequest"
    RESTART = "supportsRestartRequest"
    STEP_BACK = "supportsStepBack"
    STEPPING_GRANULARITY = "supportsSteppingGranularity"
    TERMINATE = "supportsTerminateRequest"
    SUSPEND_DEBUGGEE = "supportsSuspendDebuggee"
    TERMINATE_DEBUGGEE = "supportTerminateDebuggee"

    # Introspection capabilities
    EXCEPTION_INFO = "supportsExceptionInfoRequest"
    MODULES = "supportsModulesRequest"
    EXCEPTION_OPTIONS = "supportsExceptionOptions"
    LOADED_SOURCES = "supportsLoadedSourcesRequest"
    READ_MEMORY = "supportsReadMemoryRequest"
    WRITE_MEMORY = "supportsWriteMemoryRequest"
    DISASSEMBLE = "supportsDisassembleRequest"

    # Variable modification capabilities
    SET_VARIABLE = "supportsSetVariable"
    SET_EXPRESSION = "supportsSetExpression"
    VALUE_FORMATTING = "supportsValueFormattingOptions"

    # Evaluation capabilities
    EVALUATE_FOR_HOVERS = "supportsEvaluateForHovers"
    CLIPBOARD_CONTEXT = "supportsClipboardContext"
    COMPLETIONS = "supportsCompletionsRequest"

    # Configuration capabilities
    CONFIGURATION_DONE = "supportsConfigurationDoneRequest"
    DELAYED_STACK_TRACE = "supportsDelayedStackTraceLoading"


class OperationName:
    """Human-readable operation names for capability error messages.

    These names are used in error messages when a capability is required but not
    supported by the debug adapter.
    """

    JUMP = "jump to location"
    RESTART = "restart"
    STEP_BACK = "step back"
    EXCEPTION_INFO = "exception information"
    MODULES = "module introspection"
    SET_VARIABLE = "variable modification"
    SET_EXPRESSION = "set expression"
    TERMINATE = "terminate"
    DATA_BREAKPOINTS = "data breakpoints"
    FUNCTION_BREAKPOINTS = "function breakpoints"
    CONDITIONAL_BREAKPOINTS = "conditional breakpoints"
    LOG_POINTS = "log points"
    READ_MEMORY = "memory read"
    WRITE_MEMORY = "memory write"
    DISASSEMBLE = "disassembly"
