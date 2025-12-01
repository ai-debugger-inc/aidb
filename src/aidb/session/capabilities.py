"""Capability checking utilities for debug sessions."""

from typing import Protocol


class CapabilityProvider(Protocol):
    """Protocol for objects that provide capability checking."""

    def has_capability(self, capability: str) -> bool:
        """Check if a capability is supported."""
        ...


class CapabilityChecker:
    """Consolidated capability checking for debug sessions.

    This class provides a unified interface for checking debug adapter capabilities,
    reducing code duplication and improving maintainability.
    """

    # Mapping of logical capability names to DAP capability attributes
    CAPABILITY_MAP: dict[str, str] = {
        "conditional_breakpoints": "supportsConditionalBreakpoints",
        "data_breakpoints": "supportsDataBreakpoints",
        "delayed_stack_trace": "supportsDelayedStackTraceLoading",
        "evaluate_for_hovers": "supportsEvaluateForHovers",
        "exception_filter_options": "supportsExceptionFilterOptions",
        "exception_info": "supportsExceptionInfoRequest",
        "exception_options": "supportsExceptionOptions",
        "function_breakpoints": "supportsFunctionBreakpoints",
        "goto": "supportsGotoTargetsRequest",
        "hit_conditional_breakpoints": "supportsHitConditionalBreakpoints",
        "logpoints": "supportsLogPoints",
        "modules": "supportsModulesRequest",
        "restart": "supportsRestartRequest",
        "set_expression": "supportsSetExpression",
        "set_variable": "supportsSetVariable",
        "step_back": "supportsStepBack",
        "terminate": "supportsTerminateRequest",
    }

    def __init__(self, provider: CapabilityProvider) -> None:
        """Initialize the capability checker.

        Parameters
        ----------
        provider : CapabilityProvider
            Object that provides has_capability method.
        """
        self.provider = provider

    def check(self, capability_name: str) -> bool:
        """Check if a capability is supported.

        Parameters
        ----------
        capability_name : str
            Logical name of the capability to check.

        Returns
        -------
        bool
            True if the capability is supported, False otherwise.
        """
        dap_attribute = self.CAPABILITY_MAP.get(capability_name)
        if dap_attribute is None:
            return False
        return self.provider.has_capability(dap_attribute)

    def get(self, capability_name: str, default: bool = False) -> bool:
        """Get a capability value with a default fallback.

        This method mimics dict.get() behavior for compatibility with code
        that expects a dict-like interface.

        Parameters
        ----------
        capability_name : str
            The DAP capability attribute name (e.g., 'supportsReadMemoryRequest')
        default : bool
            Default value to return if capability is not found

        Returns
        -------
        bool
            True if the capability is supported, default otherwise
        """
        # For direct DAP attribute names (not mapped names)
        if self.provider.has_capability(capability_name):
            return True
        # Check if it's a mapped name
        return (
            self.check(capability_name)
            if capability_name in self.CAPABILITY_MAP
            else default
        )

    def supports_conditional_breakpoints(self) -> bool:
        """Check if conditional breakpoints are supported."""
        return self.check("conditional_breakpoints")

    def supports_data_breakpoints(self) -> bool:
        """Check if data breakpoints (watchpoints) are supported."""
        return self.check("data_breakpoints")

    def supports_delayed_stack_trace(self) -> bool:
        """Check if lazy stack trace loading is supported."""
        return self.check("delayed_stack_trace")

    def supports_evaluate_for_hovers(self) -> bool:
        """Check if hover evaluation is supported."""
        return self.check("evaluate_for_hovers")

    def supports_exception_filter_options(self) -> bool:
        """Check if per-exception filter options are supported."""
        return self.check("exception_filter_options")

    def supports_exception_info(self) -> bool:
        """Check if exception info request is supported."""
        return self.check("exception_info")

    def supports_exception_options(self) -> bool:
        """Check if exception options are supported."""
        return self.check("exception_options")

    def supports_function_breakpoints(self) -> bool:
        """Check if function breakpoints are supported."""
        return self.check("function_breakpoints")

    def supports_goto(self) -> bool:
        """Check if jumping to locations is supported."""
        return self.check("goto")

    def supports_hit_conditional_breakpoints(self) -> bool:
        """Check if hit count conditional breakpoints are supported."""
        return self.check("hit_conditional_breakpoints")

    def supports_logpoints(self) -> bool:
        """Check if logpoints (non-breaking diagnostics) are supported."""
        return self.check("logpoints")

    def supports_modules(self) -> bool:
        """Check if module inspection is supported."""
        return self.check("modules")

    def supports_restart(self) -> bool:
        """Check if session restart is supported."""
        return self.check("restart")

    def supports_set_expression(self) -> bool:
        """Check if set expression (complex assignments) is supported."""
        return self.check("set_expression")

    def supports_set_variable(self) -> bool:
        """Check if variable modification is supported."""
        return self.check("set_variable")

    def supports_step_back(self) -> bool:
        """Check if stepping backwards is supported."""
        return self.check("step_back")

    def supports_terminate(self) -> bool:
        """Check if terminate request is supported."""
        return self.check("terminate")

    def supports_evaluate(self) -> bool:
        """Check if evaluate is supported (baseline - always True)."""
        return True  # Baseline operation, always supported

    def store_capabilities(self, capabilities) -> None:
        """Store capabilities - delegates to provider if supported."""
        if hasattr(self.provider, "store_capabilities"):
            self.provider.store_capabilities(capabilities)
