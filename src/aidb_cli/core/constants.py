"""Constants and enums for AIDB CLI."""

from enum import Enum

from aidb_common.constants import SUPPORTED_LANGUAGES as _SHARED_SUPPORTED_LANGUAGES
from aidb_common.constants import Language  # noqa: F401


class LogLevel(str, Enum):
    """Supported log levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


# Streaming configuration
STREAM_WINDOW_SIZE = 10  # Maximum lines for boxed streaming output


class ExitCode:
    """Exit codes for CLI operations."""

    SUCCESS = 0
    GENERAL_ERROR = 1
    NOT_FOUND = 2
    CONFIG_ERROR = 3
    PERMISSION_ERROR = 4
    TIMEOUT = 124


class Icons:
    """Unicode icons for CLI output.

    Note: General output (CliOutput methods) use colors instead of these icons.
    Icons are reserved for:
    - Errors
    - Headers and metadata sections
    - Status indicators and special attention-type logs
    - Process and action labels
    """

    # Status and error indicators
    SUCCESS = "✅"  # For status indicators and special attention logs only
    ERROR = "❌"
    WARNING = "⚠️"  # For status indicators and special attention logs only
    INFO = "📄"  # For headers and metadata sections only

    # Process and action icons
    ROCKET = "🚀"
    GEAR = "⚙️"
    PACKAGE = "📦"
    SHELL = "🐚"
    CLEAN = "🧹"
    BUILD = "🔨"
    TEST = "🧪"
    DEBUG = "🐞"
    FOLDER = "📁"
    TRASH = "🗑️"
    DOCKER = "🐳"
    LIGHTNING = "⚡"
    PLUG = "🔌"
    GLOBE = "🌐"
    MAGNIFYING = "🔍"
    SEARCH = "🔍"
    MARKERS = "❎"
    LOOP = "🔄"
    STOP = "🛑"
    DOWN_ARROW = "⬇"
    DOWNLOAD = "⬇️"
    ARROW_RIGHT = "→"
    CHECK = "✓"
    KEY = "🔑"
    SHIELD = "🛡️"
    LOCK = "🔒"
    VERIFY = "✓"

    # Process action icons
    PROCESS = "⚙️"
    CONFIG = "🔧"
    LIST = "📋"
    REPORT = "📊"
    TARGET = "🎯"

    # CI/CD status icons
    SKIPPED = "⏭️"
    UNKNOWN = "❓"


class EnvVars:
    """Environment variable names."""

    LOG_LEVEL = "AIDB_LOG_LEVEL"
    ADAPTER_TRACE = "AIDB_ADAPTER_TRACE"
    USE_CI_ARTIFACTS = "AIDB_USE_CI_ARTIFACTS"
    REPO_ROOT = "AIDB_REPO_ROOT"
    DOCKER_DEFAULT_PLATFORM = "DOCKER_DEFAULT_PLATFORM"
    USE_HOST_PLATFORM = "AIDB_USE_HOST_PLATFORM"
    BUILD_PLATFORM = "AIDB_BUILD_PLATFORM"
    BUILD_ARCH = "AIDB_BUILD_ARCH"
    CLI_FORCE_ANSI = "AIDB_CLI_FORCE_ANSI"
    CLI_FORCE_STREAMING = "AIDB_CLI_FORCE_STREAMING"
    CONSOLE_LOGGING = "AIDB_CONSOLE_LOGGING"
    NO_FILE_LOGGING = "AIDB_NO_FILE_LOGGING"
    DOCS_PORT = "AIDB_DOCS_PORT"
    PYTEST_SESSION_ID = "PYTEST_SESSION_ID"

    # CI/CD environment detection variables
    CI_ENVIRONMENT_VARS: tuple[str, ...] = (
        "CI",
        "GITHUB_ACTIONS",
        "GITLAB_CI",
        "JENKINS_HOME",
        "CIRCLECI",
        "TRAVIS",
        "BUILDKITE",
        "DRONE",
        "TEAMCITY_VERSION",
        "TF_BUILD",
    )


class PreCommitEnvVars:
    """Pre-commit environment variable names."""

    SKIP = "SKIP"


class PreCommitHooks:
    """Pre-commit hook identifiers."""

    VULTURE = "vulture"
    BANDIT = "bandit"
    MYPY = "mypy"


class ProjectNames:
    """Project and service names used in AIDB CLI."""

    MCP_SERVER = "aidb-debug"
    TEST_PROJECT = "aidb-test"


class DockerProfiles:
    """Docker Compose profiles."""

    BASE = "base"
    MCP = "mcp"
    ADAPTERS = "adapters"
    SHELL = "shell"

    # All valid docker-compose profiles
    ALL_PROFILES = {
        BASE,
        MCP,
        ADAPTERS,
        SHELL,
        "all",
        "generated",
        "python",
        "javascript",
        "java",
        "frameworks",
        "debug",
        "matrix",
        "launch",
        "shared",
        "e2e",
    }

    # Suites that should map to base profile
    BASE_PROFILE_SUITES = {"shared", "cli", "ci_cd", "common", "logging"}


class DockerLabels:
    """Docker labels for AIDB resource identification and management."""

    PROJECT = "com.aidb.project"
    COMPONENT = "com.aidb.component"
    MANAGED = "com.aidb.managed"
    ENVIRONMENT = "com.aidb.environment"
    TYPE = "com.aidb.type"


class DockerLabelValues:
    """Standard values for Docker labels."""

    PROJECT_NAME = "aidb"
    MANAGED_TRUE = "true"

    # Component types
    COMPONENT_TEST = "test"
    COMPONENT_DOCS = "docs"
    COMPONENT_MCP = "mcp"
    COMPONENT_ADAPTER = "adapter"
    COMPONENT_SHELL = "shell"
    COMPONENT_LOGS = "logs"
    COMPONENT_UTILITY = "utility"

    # Resource types
    TYPE_CACHE = "cache"
    TYPE_VOLUME = "volume"
    TYPE_NETWORK = "network"
    TYPE_CONTAINER = "container"
    TYPE_IMAGE = "image"


class OutputFormat(str, Enum):
    """Output format options."""

    JSON = "json"
    YAML = "yaml"
    TABLE = "table"
    TEXT = "text"


class HttpMethod(str, Enum):
    """HTTP method constants."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


class HttpStatus:
    """HTTP status codes."""

    OK = 200
    CREATED = 201
    NO_CONTENT = 204

    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    TOO_MANY_REQUESTS = 429

    INTERNAL_SERVER_ERROR = 500
    BAD_GATEWAY = 502
    SERVICE_UNAVAILABLE = 503
    GATEWAY_TIMEOUT = 504


class HttpHeader:
    """HTTP header constants."""

    CONTENT_TYPE = "Content-Type"
    AUTHORIZATION = "Authorization"
    USER_AGENT = "User-Agent"


class ContentType:
    """Content-Type header values."""

    JSON = "application/json"
    FORM_URLENCODED = "application/x-www-form-urlencoded"
    TEXT_PLAIN = "text/plain"


class HttpTimeout:
    """HTTP timeout constants in seconds."""

    DEFAULT_REQUEST = 30
    HEALTH_CHECK = 10
    SHORT = 10
    LONG = 60


class HttpRetry:
    """HTTP retry configuration constants."""

    MAX_RETRIES = 3
    BACKOFF_FACTOR = 1


# Environment variable prefixes for filtering/grouping
ENV_VAR_PREFIXES = ["AIDB_", "TEST_", "PYTEST_", "DOCKER_", "COMPOSE_"]

# Default values for CLI operations
DEFAULT_LOG_LINES = 200


def _get_supported_languages() -> list[str]:
    """Get supported languages from AdapterRegistry with fallback."""
    try:
        from aidb.session.adapter_registry import AdapterRegistry

        return AdapterRegistry().get_languages()
    except Exception:
        # Fallback to shared list if AdapterRegistry is not available
        return _SHARED_SUPPORTED_LANGUAGES


SUPPORTED_LANGUAGES = _get_supported_languages()
ALL_LOG_LEVELS = [LogLevel.DEBUG, LogLevel.INFO, LogLevel.WARNING, LogLevel.ERROR]


class CIJobPatterns:
    """GitHub Actions job name patterns."""

    TEST_PREFIX = "test-"
    TEST_SUMMARY_JOB = "test summary"
    RUN_TESTS_PREFIX = "run-tests / "
    RUN_TESTS_TEST_PREFIX = "run-tests / test-"


class CIJobStatus:
    """GitHub Actions job conclusion statuses."""

    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"
    UNKNOWN = "unknown"

    # Statuses that need attention
    NEEDS_ATTENTION = (FAILURE, CANCELLED)


class CIArtifactPatterns:
    """GitHub Actions artifact name patterns."""

    SUMMARY_PREFIX = "test-summary-"
    LOGS_PREFIX = "test-logs-"
    SUMMARY_FILE = "summary.md"
    FLAKES_FILE = "flakes.json"
    FLAKES_REPORT_ARTIFACT = "flaky-tests-report"
    FLAKES_REPORT_FILE = "flaky-tests-report.json"


class CIFormatting:
    """CI summary output formatting constants."""

    TABLE_WIDTH = 60
    SECTION_WIDTH = 80
    TABLE_SEPARATOR = "─"
    SECTION_SEPARATOR = "="
    SUBSECTION_SEPARATOR = "-"

    # Flakes output formatting
    MAX_FLAKY_TESTS_DISPLAY = 30
    MAX_FAILING_TESTS_DISPLAY = 20
    TEST_NAME_MAX_LENGTH = 55
    TEST_NAME_TRUNCATE_LENGTH = 52
