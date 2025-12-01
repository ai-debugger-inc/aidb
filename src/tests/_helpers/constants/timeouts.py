"""Timeout and limit configurations for AIDB test suite."""


class TestTimeouts:
    """Standard timeout values for different test scenarios."""

    QUICK = 1.0  # Quick operations
    DEFAULT = 5.0  # Standard operations
    SLOW = 10.0  # Slow operations
    DOCKER = 30.0  # Docker container operations
    NETWORK = 15.0  # Network operations
    ADAPTER_START = 10.0  # Adapter startup
    SESSION_INIT = 5.0  # Session initialization
    BREAKPOINT_HIT = 3.0  # Waiting for breakpoint
    STEP_COMPLETE = 2.0  # Step operation completion


class TestLimits:
    """Execution step limits for testing."""

    MAX_STEPS_COMPLETION = 1000  # For run_to_completion
    MAX_STEPS_NAVIGATION = 100  # For step_until_line
    MAX_BREAKPOINTS = 50
    MAX_VARIABLES = 1000


__all__ = [
    "TestLimits",
    "TestTimeouts",
]
