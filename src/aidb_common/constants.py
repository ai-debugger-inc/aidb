"""Shared constants across all AIDB packages.

This module provides constants and enums that are used across aidb, aidb_cli, aidb_mcp,
and tests to ensure consistency and avoid duplication.
"""

from enum import Enum


class Language(str, Enum):
    """Supported programming languages for debugging.

    This enum is used across all AIDB packages and tests for consistency. It inherits
    from str to make it JSON-serializable and easy to use in APIs.
    """

    PYTHON = "python"
    JAVASCRIPT = "javascript"
    JAVA = "java"

    @property
    def file_extension(self) -> str:
        """Get primary file extension for this language.

        Returns
        -------
        str
            File extension including the dot (e.g., ".py")
        """
        ext_map = {
            Language.PYTHON: ".py",
            Language.JAVASCRIPT: ".js",
            Language.JAVA: ".java",
        }
        return ext_map.get(self, ".txt")

    @property
    def comment_prefix(self) -> str:
        """Get single-line comment prefix for this language.

        Returns
        -------
        str
            Comment prefix (e.g., "#" for Python)
        """
        comment_map = {
            Language.PYTHON: "#",
            Language.JAVASCRIPT: "//",
            Language.JAVA: "//",
        }
        return comment_map.get(self, "#")


# All languages supported by AIDB adapters
SUPPORTED_LANGUAGES = [lang.value for lang in Language]


# Base AIDB home directory and subdirectories
AIDB_HOME_DIR = ".aidb"
LOG_SUBDIR = "log"
ADAPTERS_SUBDIR = "adapters"

# Domain constants
AIDB_DOMAIN = "ai-debugger.com"
AIDB_BASE_URL = f"https://{AIDB_DOMAIN}"
AIDB_WWW_URL = f"https://www.{AIDB_DOMAIN}"
