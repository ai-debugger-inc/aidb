"""Test constants for CI/CD test suite.

Centralized constants to eliminate magic strings and numbers across tests.
"""


class TestURLs:
    """API endpoint URLs used in tests."""

    PYPI_API = "https://pypi.org/pypi/{package}/json"
    NPM_REGISTRY = "https://registry.npmjs.org/{package}/latest"
    GITHUB_API_RELEASES = "https://api.github.com/repos/{repo}/releases"
    GITHUB_RATE_LIMIT = "https://api.github.com/rate_limit"
    GITHUB_RELEASE_TAG = "https://github.com/{repo}/releases/tag/{tag}"
    DOCKER_HUB_REPO = "https://hub.docker.com/v2/repositories/{namespace}/{repo}"
    DOCKER_HUB_TAGS = "https://hub.docker.com/v2/repositories/{namespace}/{repo}/tags"
    DOCKER_HUB_TAG_DETAIL = (
        "https://hub.docker.com/v2/repositories/{namespace}/{repo}/tags/{tag}"
    )
    ENDOFLIFE_API = "https://endoflife.date/api/{product}.json"
    ENDOFLIFE_CYCLE = "https://endoflife.date/api/{product}/{cycle}.json"


class TestRepos:
    """Repository identifiers used in tests."""

    DEBUGPY = "microsoft/debugpy"
    VS_CODE_JS_DEBUG = "microsoft/vscode-js-debug"
    JAVA_DEBUG = "microsoft/java-debug"
    EXAMPLE_REPO = "example/repo"


class TestVersions:
    """Common test version numbers."""

    PYTHON_OLD = "3.11.0"
    PYTHON_NEW = "3.12.1"
    PYTHON_CYCLE_OLD = "3.11"
    PYTHON_CYCLE_NEW = "3.12"

    DEBUGPY_OLD = "1.8.0"
    DEBUGPY_NEW = "1.8.1"

    JS_ADAPTER_OLD = "v1.85.0"
    JS_ADAPTER_NEW = "v1.86.0"
    JS_ADAPTER_NEWER = "v1.87.0"

    JAVA_ADAPTER_OLD = "0.50.0"
    JAVA_ADAPTER_NEW = "0.51.0"

    NODE_OLD = "20.0.0"
    NODE_NEW = "20.10.0"
    NODE_CYCLE = "20"

    JAVA_OLD = "21.0.0"
    JAVA_NEW = "21.0.1"
    JAVA_CYCLE = "21"

    SETUPTOOLS_OLD = "68.0.0"
    SETUPTOOLS_NEW = "69.0.0"

    TYPESCRIPT_OLD = "5.3.0"
    TYPESCRIPT_NEW = "5.3.3"


class TestPackages:
    """Package names used in tests."""

    SETUPTOOLS = "setuptools"
    TYPESCRIPT = "typescript"
    PYTEST = "pytest"
    EXPRESS = "express"


class TestDockerImages:
    """Docker image names used in tests."""

    PYTHON_OFFICIAL = "python"
    NODE_OFFICIAL = "node"
    ECLIPSE_TEMURIN = "eclipse-temurin"


class HTTPStatus:
    """HTTP status codes."""

    OK = 200
    NOT_FOUND = 404
    RATE_LIMIT = 429
    INTERNAL_ERROR = 500


class TestTimeouts:
    """Timeout values in seconds."""

    HTTP_REQUEST = 30
    API_CALL = 10
