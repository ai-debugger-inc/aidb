"""Default configurations and test data patterns for AIDB test suite."""

from aidb_common.constants import SUPPORTED_LANGUAGES, Language
from tests._helpers.constants.ports import DebugPorts, PortRanges

# Default languages for testing (can be overridden via environment)
DEFAULT_TEST_LANGUAGES = SUPPORTED_LANGUAGES.copy()


class LanguageTestHelpers:
    """Test-specific helpers for Language enum."""

    @staticmethod
    def get_default_port(language: Language | str) -> int:
        """Get default debug port for language.

        Parameters
        ----------
        language : Language | str
            Programming language

        Returns
        -------
        int
            Default debug port for the language
        """
        lang_str = language.value if isinstance(language, Language) else language
        port_map = {
            Language.PYTHON.value: DebugPorts.PYTHON,
            Language.JAVASCRIPT.value: DebugPorts.JAVASCRIPT,
            Language.JAVA.value: DebugPorts.JAVA,
            "typescript": DebugPorts.JAVASCRIPT,
        }
        return port_map.get(lang_str, DebugPorts.PYTHON)

    @staticmethod
    def get_file_extension(language: Language | str) -> str:
        """Get primary file extension for language.

        Parameters
        ----------
        language : Language | str
            Programming language

        Returns
        -------
        str
            File extension for the language
        """
        lang_str = language.value if isinstance(language, Language) else language
        ext_map = {
            Language.PYTHON.value: ".py",
            Language.JAVASCRIPT.value: ".js",
            Language.JAVA.value: ".java",
            "typescript": ".ts",
        }
        return ext_map.get(lang_str, ".txt")

    @staticmethod
    def get_comment_prefix(language: Language | str) -> str:
        """Get single-line comment prefix for language.

        Parameters
        ----------
        language : Language | str
            Programming language

        Returns
        -------
        str
            Comment prefix for the language
        """
        lang_str = language.value if isinstance(language, Language) else language
        comment_map = {
            Language.PYTHON.value: "#",
            Language.JAVASCRIPT.value: "//",
            Language.JAVA.value: "//",
            "typescript": "//",
        }
        return comment_map.get(lang_str, "#")


class TestPattern:
    """Common test data patterns."""

    # Sample code snippets for different languages
    HELLO_WORLD = {
        Language.PYTHON: 'print("Hello, World!")',
        Language.JAVASCRIPT: 'console.log("Hello, World!");',
        Language.JAVA: 'System.out.println("Hello, World!");',
    }

    # Breakpoint test code
    BREAKPOINT_CODE = {
        Language.PYTHON: """
def calculate(a, b):
    result = a + b  # Set breakpoint here
    return result

x = 10
y = 20
total = calculate(x, y)
print(f"Total: {total}")
""",
        Language.JAVASCRIPT: """
function calculate(a, b) {
    const result = a + b;  // Set breakpoint here
    return result;
}

const x = 10;
const y = 20;
const total = calculate(x, y);
console.log(`Total: ${total}`);
""",
        Language.JAVA: """
public class Test {
    public static int calculate(int a, int b) {
        int result = a + b;  // Set breakpoint here
        return result;
    }

    public static void main(String[] args) {
        int x = 10;
        int y = 20;
        int total = calculate(x, y);
        System.out.println("Total: " + total);
    }
}
""",
    }


class ErrorMessage:
    """Standard error messages for assertions."""

    SESSION_NOT_STARTED = "Session failed to start"
    ADAPTER_NOT_RUNNING = "Adapter is not running"
    BREAKPOINT_NOT_SET = "Breakpoint was not set"
    BREAKPOINT_NOT_HIT = "Breakpoint was not hit"
    TIMEOUT_EXCEEDED = "Operation timed out"
    PORT_NOT_AVAILABLE = "Port is not available"
    DOCKER_NOT_AVAILABLE = "Docker is not available"
    LOG_ERROR_FOUND = "Unexpected error in logs"
    CONNECTION_FAILED = "Failed to connect to debug adapter"


class DockerConfig:
    """Docker-related configuration for tests."""

    # Container prefixes
    CONTAINER_PREFIX = "aidb_test_"
    NETWORK_PREFIX = "aidb_test_net_"
    VOLUME_PREFIX = "aidb_test_vol_"

    # Default images for languages
    IMAGES = {
        Language.PYTHON: "python:3.11-slim",
        Language.JAVASCRIPT: "node:20-slim",
        Language.JAVA: "openjdk:17-slim",
    }

    # Container limits
    MEMORY_LIMIT = "512m"
    CPU_LIMIT = "1.0"

    # Timeouts
    CONTAINER_START_TIMEOUT = 30
    CONTAINER_STOP_TIMEOUT = 10


class TestData:
    """Common test data constants."""

    EMAIL = "test@example.com"
    USER_ID = "test_user"
    ORG_ID = "test_org_id"


def get_default_config(language: Language) -> dict:
    """Get default configuration for a language.

    Parameters
    ----------
    language : Language
        Programming language

    Returns
    -------
    Dict
        Default configuration including port, extensions, etc.
    """
    return {
        "language": language.value,
        "default_port": language.default_port,
        "file_extension": language.file_extension,
        "port_ranges": getattr(PortRanges, language.name, PortRanges.DEFAULT),
    }


def get_test_file_content(language: Language, pattern: str = "hello") -> str:
    """Get test file content for a language.

    Parameters
    ----------
    language : Language
        Programming language
    pattern : str
        Pattern type ("hello" or "breakpoint")

    Returns
    -------
    str
        Test file content
    """
    if pattern == "hello":
        return TestPattern.HELLO_WORLD.get(
            language,
            TestPattern.HELLO_WORLD[Language.PYTHON],
        )
    if pattern == "breakpoint":
        return TestPattern.BREAKPOINT_CODE.get(
            language,
            TestPattern.BREAKPOINT_CODE[Language.PYTHON],
        )
    return ""


__all__ = [
    "DEFAULT_TEST_LANGUAGES",
    "DockerConfig",
    "ErrorMessage",
    "LanguageTestHelpers",
    "TestData",
    "TestPattern",
    "get_default_config",
    "get_test_file_content",
]
