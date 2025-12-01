"""Common test marker descriptions for AIDB."""


def get_marker_descriptions() -> dict[str, str]:
    """Get descriptions for common pytest markers.

    This provides a centralized source of marker descriptions that can be
    shared between parameter types and CLI commands to avoid DRY violations.

    Returns
    -------
    dict[str, str]
        Dictionary mapping marker names to their descriptions
    """
    return {
        "unit": "Unit tests",
        "integration": "Integration tests",
        "e2e": "End-to-end tests",
        "slow": "Slow tests",
        "asyncio": "Async tests",
        "parametrize": "Parametrized tests",
        "skip": "Skipped tests",
        "skipif": "Conditionally skipped tests",
        "xfail": "Expected to fail tests",
        # Add more as needed
    }
