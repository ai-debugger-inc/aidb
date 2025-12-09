"""Framework configuration registry for debugging starters.

This module provides a centralized registry of framework configurations,
eliminating the large if/elif chains in language-specific starters.

Each framework config contains:
- Target executable/module
- Arguments
- Environment variables
- Optional breakpoint patterns for examples
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aidb_common.constants import Language


@dataclass
class FrameworkConfig:
    """Configuration for a specific framework.

    Attributes
    ----------
    target : str
        The target executable or module name
    args : list[str], optional
        Command line arguments
    env : dict[str, str], optional
        Environment variables
    module : bool
        Whether to run as a module (-m flag)
    cwd : str
        Working directory (supports ${workspace_root})
    breakpoint_patterns : list[dict[str, Any]], optional
        Example breakpoint locations with comments
    """

    target: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    module: bool = False
    cwd: str = "${workspace_root}"
    breakpoint_patterns: list[dict[str, Any]] = field(default_factory=list)

    def to_launch_example(self) -> dict[str, Any]:
        """Convert to launch configuration example.

        Returns
        -------
        dict[str, Any]
            Launch configuration dict for MCP response
        """
        result: dict[str, Any] = {
            "target": self.target,
            "cwd": self.cwd,
        }

        if self.args:
            result["args"] = self.args

        if self.env:
            result["env"] = self.env

        if self.module:
            result["module"] = True

        if self.breakpoint_patterns:
            result["breakpoints"] = self.breakpoint_patterns

        return result


# =============================================================================
# Python Framework Configurations
# =============================================================================

PYTHON_FRAMEWORKS: dict[str, FrameworkConfig] = {
    "pytest": FrameworkConfig(
        target="pytest",
        module=True,
        args=["-xvs", "tests/test_example.py::TestClass::test_method"],
        env={"PYTEST_CURRENT_TEST": "true"},
        breakpoint_patterns=[
            {"file": "/path/to/src/calculator.py", "line": 15},
            {"file": "/path/to/src/utils/validator.py", "line": 42},
        ],
    ),
    "unittest": FrameworkConfig(
        target="unittest",
        module=True,
        args=["tests.test_module.TestCase.test_method"],
    ),
    "django": FrameworkConfig(
        target="python",
        args=["manage.py", "runserver", "--noreload"],
        env={"DJANGO_SETTINGS_MODULE": "myproject.settings"},
        breakpoint_patterns=[
            {"file": "/path/to/myapp/views.py", "line": 25},
            {"file": "/path/to/myapp/models.py", "line": 78},
            {"file": "/path/to/core/utils.py", "line": 156},
        ],
    ),
    "flask": FrameworkConfig(
        target="python",
        args=["app.py"],
        env={"FLASK_APP": "app.py", "FLASK_ENV": "development"},
        breakpoint_patterns=[
            {"file": "/path/to/routes/api.py", "line": 45},
            {"file": "/path/to/models/user.py", "line": 78},
            {"file": "/path/to/utils/auth.py", "line": 23},
        ],
    ),
    "fastapi": FrameworkConfig(
        target="uvicorn",
        module=True,
        args=["main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"],
        breakpoint_patterns=[
            {"file": "/path/to/routers/users.py", "line": 32},
            {"file": "/path/to/core/database.py", "line": 15},
            {"file": "/path/to/services/auth.py", "line": 89},
        ],
    ),
    "pyramid": FrameworkConfig(
        target="pserve",
        module=True,
        args=["development.ini", "--reload"],
    ),
    "asyncio": FrameworkConfig(
        target="python",
        args=["async_script.py"],
        env={"PYTHONASYNCIODEBUG": "1"},
    ),
    "behave": FrameworkConfig(
        target="behave",
        module=True,
        args=["features/example.feature", "--no-capture"],
    ),
}

PYTHON_DEFAULT = FrameworkConfig(
    target="python",
    args=["main.py"],
    breakpoint_patterns=[
        {"file": "/path/to/utils/helper.py", "line": 25},
        {"file": "/path/to/config/settings.py", "line": 10},
    ],
)

# =============================================================================
# JavaScript Framework Configurations
# =============================================================================

JAVASCRIPT_FRAMEWORKS: dict[str, FrameworkConfig] = {
    "express": FrameworkConfig(
        target="node",
        args=["server.js"],
        env={"NODE_ENV": "development", "DEBUG": "express:*"},
        breakpoint_patterns=[
            {"file": "/path/to/routes/api.js", "line": 25},
            {"file": "/path/to/middleware/auth.js", "line": 42},
            {"file": "/path/to/controllers/user.js", "line": 78},
        ],
    ),
    "jest": FrameworkConfig(
        target="npx",
        args=["jest", "--runInBand", "tests/example.test.js"],
        env={"NODE_ENV": "test"},
        breakpoint_patterns=[
            {"file": "/path/to/src/calculator.js", "line": 15},
            {"file": "/path/to/src/utils/validator.js", "line": 42},
        ],
    ),
    "mocha": FrameworkConfig(
        target="npx",
        args=["mocha", "--no-timeouts", "test/**/*.test.js"],
        env={"NODE_ENV": "test"},
    ),
    "nextjs": FrameworkConfig(
        target="npx",
        args=["next", "dev"],
        env={"NODE_OPTIONS": "--inspect"},
        breakpoint_patterns=[
            {"file": "/path/to/pages/api/users.js", "line": 15},
            {"file": "/path/to/lib/database.js", "line": 32},
        ],
    ),
    "nestjs": FrameworkConfig(
        target="npx",
        args=["nest", "start", "--debug", "--watch"],
        breakpoint_patterns=[
            {"file": "/path/to/src/users/users.controller.ts", "line": 25},
            {"file": "/path/to/src/users/users.service.ts", "line": 42},
        ],
    ),
    "typescript": FrameworkConfig(
        target="npx",
        args=["ts-node", "src/index.ts"],
        breakpoint_patterns=[
            {"file": "/path/to/src/services/api.ts", "line": 45},
        ],
    ),
    "vitest": FrameworkConfig(
        target="npx",
        args=["vitest", "run", "--no-threads"],
        env={"NODE_ENV": "test"},
    ),
}

JAVASCRIPT_DEFAULT = FrameworkConfig(
    target="node",
    args=["index.js"],
    breakpoint_patterns=[
        {"file": "/path/to/src/utils/helper.js", "line": 25},
        {"file": "/path/to/src/config/settings.js", "line": 10},
    ],
)

# =============================================================================
# Java Framework Configurations
# =============================================================================

JAVA_FRAMEWORKS: dict[str, FrameworkConfig] = {
    "junit": FrameworkConfig(
        target="mvn",
        args=["test", "-Dtest=MyTest#testMethod"],
        breakpoint_patterns=[
            {"file": "/path/to/src/main/java/Calculator.java", "line": 25},
            {"file": "/path/to/src/main/java/utils/Validator.java", "line": 42},
        ],
    ),
    "junit5": FrameworkConfig(
        target="mvn",
        args=["test", "-Dtest=MyTest#testMethod"],
        breakpoint_patterns=[
            {"file": "/path/to/src/main/java/Calculator.java", "line": 25},
        ],
    ),
    "spring": FrameworkConfig(
        target="mvn",
        args=["spring-boot:run"],
        env={"SPRING_PROFILES_ACTIVE": "dev"},
        breakpoint_patterns=[
            {"file": "/path/to/controller/UserController.java", "line": 45},
            {"file": "/path/to/service/UserService.java", "line": 78},
            {"file": "/path/to/repository/UserRepository.java", "line": 23},
        ],
    ),
    "springboot": FrameworkConfig(
        target="mvn",
        args=["spring-boot:run"],
        env={"SPRING_PROFILES_ACTIVE": "dev"},
        breakpoint_patterns=[
            {"file": "/path/to/controller/UserController.java", "line": 45},
            {"file": "/path/to/service/UserService.java", "line": 78},
        ],
    ),
    "gradle": FrameworkConfig(
        target="gradle",
        args=["test", "--debug-jvm"],
    ),
    "maven": FrameworkConfig(
        target="mvn",
        args=["exec:java", "-Dexec.mainClass=com.example.Main"],
    ),
    "testng": FrameworkConfig(
        target="mvn",
        args=["test", "-DsuiteXmlFile=testng.xml"],
    ),
}

JAVA_DEFAULT = FrameworkConfig(
    target="java",
    args=["-cp", "target/classes", "com.example.Main"],
    breakpoint_patterns=[
        {"file": "/path/to/src/main/java/Main.java", "line": 15},
        {"file": "/path/to/src/main/java/utils/Helper.java", "line": 25},
    ],
)

# =============================================================================
# Registry Access Functions
# =============================================================================

_FRAMEWORK_REGISTRIES: dict[str, dict[str, FrameworkConfig]] = {
    Language.PYTHON.value: PYTHON_FRAMEWORKS,
    Language.JAVASCRIPT.value: JAVASCRIPT_FRAMEWORKS,
    Language.JAVA.value: JAVA_FRAMEWORKS,
}

_DEFAULT_CONFIGS: dict[str, FrameworkConfig] = {
    Language.PYTHON.value: PYTHON_DEFAULT,
    Language.JAVASCRIPT.value: JAVASCRIPT_DEFAULT,
    Language.JAVA.value: JAVA_DEFAULT,
}


def get_framework_registry(language: str) -> dict[str, FrameworkConfig]:
    """Get the framework registry for a language.

    Parameters
    ----------
    language : str
        The programming language

    Returns
    -------
    dict[str, FrameworkConfig]
        Mapping of framework names to configurations
    """
    return _FRAMEWORK_REGISTRIES.get(language.lower(), {})


def get_framework_config(
    language: str,
    framework: str | None,
) -> FrameworkConfig | None:
    """Get configuration for a specific framework.

    Parameters
    ----------
    language : str
        The programming language
    framework : str, optional
        The framework name

    Returns
    -------
    FrameworkConfig, optional
        The framework config if found, None otherwise
    """
    if not framework:
        return None

    registry = get_framework_registry(language)
    return registry.get(framework.lower())


def get_default_config(language: str) -> FrameworkConfig:
    """Get the default configuration for a language.

    Parameters
    ----------
    language : str
        The programming language

    Returns
    -------
    FrameworkConfig
        The default configuration
    """
    return _DEFAULT_CONFIGS.get(
        language.lower(),
        FrameworkConfig(target="unknown", args=["main"]),
    )


def get_supported_frameworks(language: str) -> list[str]:
    """Get list of supported frameworks for a language.

    Parameters
    ----------
    language : str
        The programming language

    Returns
    -------
    list[str]
        List of supported framework names
    """
    return list(get_framework_registry(language).keys())


def is_framework_supported(language: str, framework: str) -> bool:
    """Check if a framework is supported for a language.

    Parameters
    ----------
    language : str
        The programming language
    framework : str
        The framework name

    Returns
    -------
    bool
        True if the framework is supported
    """
    return framework.lower() in get_framework_registry(language)
