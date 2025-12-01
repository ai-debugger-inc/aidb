"""Constants for the audit system."""


class MaskingConstants:
    """Constants for sensitive data masking."""

    # Default mask replacement string
    DEFAULT_MASK = "***MASKED***"

    # Sensitive field names that should always be masked
    SENSITIVE_FIELDS = frozenset(
        {
            "password",
            "token",
            "secret",
            "credential",
            "auth",
            "authorization",
            "api_key",
            "access_token",
            "database_url",
            "connection_string",
            "private_key",
            "ssh_key",
            "certificate",
            "bearer_token",
            "session_token",
            "refresh_token",
        },
    )

    # Suffixes that indicate sensitive fields
    SENSITIVE_SUFFIXES = (
        "_key",
        "_token",
        "_secret",
        "_password",
        "_url",
        "_credential",
        "_auth",
    )

    # Configuration defaults
    DEFAULT_MAX_DEPTH = 10
    DEFAULT_MASK_SENSITIVE = True
    DEFAULT_MASK_IN_METADATA = True
    DEFAULT_STRICT_MODE = False
    DEFAULT_CASE_SENSITIVE = False
