"""Constants for AIDB process tagging and orphan detection."""


class ProcessTags:
    """Environment variable names for AIDB process tagging.

    These environment variables are injected into all AIDB-spawned processes to enable
    safe orphan detection and cleanup.
    """

    OWNER = "AIDB_OWNER"
    SESSION_ID = "AIDB_SESSION_ID"
    PROCESS_TYPE = "AIDB_PROCESS_TYPE"
    LANGUAGE = "AIDB_LANGUAGE"
    START_TIME = "AIDB_START_TIME"
    IS_POOL_RESOURCE = "AIDB_IS_POOL_RESOURCE"

    OWNER_VALUE = "aidb"


class ProcessType:
    """Process type constants for AIDB_PROCESS_TYPE tag."""

    ADAPTER = "adapter"
    DEBUGGEE = "debuggee"
    LSP_SERVER = "lsp_server"
