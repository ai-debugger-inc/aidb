"""Python-specific debugging starter implementation."""

from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING, Any

from aidb.common.constants import DEFAULT_ADAPTER_HOST, DEFAULT_PYTHON_DEBUG_PORT
from aidb_common.constants import Language
from aidb_common.path import get_aidb_adapters_dir
from aidb_logging import get_mcp_logger as get_logger

from .base import BaseStarter

if TYPE_CHECKING:
    from pathlib import Path

logger = get_logger(__name__)


class PythonStarter(BaseStarter):
    """Python debugging starter with framework-specific examples."""

    def get_launch_example(
        self,
        target: str | None = None,
        framework: str | None = None,
        workspace_root: str | None = None,
    ) -> dict[str, Any]:
        """Get Python launch configuration example.

        Parameters
        ----------
        target : str, optional
            Target file to debug
        framework : str, optional
            Specific framework (pytest, django, etc.)
        workspace_root : str, optional
            Workspace root directory for context discovery

        Returns
        -------
        Dict[str, Any]
            Launch configuration example
        """
        from .framework_registry import get_default_config, get_framework_config

        logger.debug(
            "Generating Python launch example",
            extra={
                "framework": framework,
                "target": target,
                "workspace_root": workspace_root,
                "language": Language.PYTHON,
            },
        )

        # Try to get framework-specific config
        config = get_framework_config(Language.PYTHON.value, framework)
        if config:
            return config.to_launch_example()

        # Fall back to default
        logger.debug(
            "Using generic Python launch config",
            extra={"framework": framework or "none", "language": Language.PYTHON},
        )
        return get_default_config(Language.PYTHON.value).to_launch_example()

    def get_attach_example(
        self,
        mode: str = "local",
        pid: int | None = None,
        host: str | None = None,
        port: int | None = None,
    ) -> dict[str, Any]:
        """Get Python attach configuration example.

        Parameters
        ----------
        mode : str
            Attach mode - "local" for PID or "remote" for host:port
        pid : int, optional
            Process ID for local attach
        host : str, optional
            Host for remote attach
        port : int, optional
            Port for remote attach

        Returns
        -------
        Dict[str, Any]
            Attach configuration example
        """
        logger.debug(
            "Generating Python attach example",
            extra={
                "mode": mode,
                "pid": pid,
                "host": host,
                "port": port,
                "language": Language.PYTHON,
            },
        )

        if mode == "remote":
            return {
                "host": host or DEFAULT_ADAPTER_HOST,
                "port": port or DEFAULT_PYTHON_DEBUG_PORT,
                "comment": (
                    "Start with: python -m debugpy "
                    f"--listen {DEFAULT_PYTHON_DEBUG_PORT} script.py"
                ),
            }
        if mode == "local" and pid:
            return {
                "pid": pid,
                "comment": "Attach to running Python process",
            }
        # Default remote attach example
        return {
            "host": DEFAULT_ADAPTER_HOST,
            "port": DEFAULT_PYTHON_DEBUG_PORT,
            "comment": (
                "Start with: python -m debugpy "
                f"--listen {DEFAULT_PYTHON_DEBUG_PORT} script.py"
            ),
        }

    def get_common_breakpoints(
        self,
        framework: str | None = None,
        target: str | None = None,
    ) -> list[str]:
        """Get common breakpoint suggestions for Python.

        Parameters
        ----------
        framework : str, optional
            Specific framework
        target : str, optional
            Target file to suggest breakpoints for

        Returns
        -------
        List[str]
            Suggested breakpoint locations
        """
        logger.debug(
            "Getting common breakpoints for Python",
            extra={
                "framework": framework,
                "target": target,
                "language": Language.PYTHON,
            },
        )

        if framework == "pytest":
            return [
                "conftest.py:1",  # Test configuration
                "test_*.py:1",  # Test file entry
                "${test_file}:${line}",  # Specific test line
            ]
        if framework == "django":
            return [
                "views.py:1",  # View entry points
                "models.py:1",  # Model definitions
                "urls.py:1",  # URL routing
                "middleware.py:1",  # Middleware processing
            ]
        if framework == "flask":
            return [
                "app.py:@app.route",  # Route handlers
                "blueprints/*.py:1",  # Blueprint modules
                "models.py:1",  # Database models
            ]
        if framework == "fastapi":
            return [
                "main.py:@app.get",  # GET endpoints
                "main.py:@app.post",  # POST endpoints
                "routers/*.py:1",  # Router modules
            ]
        return [
            "main.py:1",  # Entry point
            "__main__:1",  # Main execution
            "${file}:${line}",  # User-specified location
        ]

    def _validate_language_environment(self, result: dict[str, Any]) -> None:
        """Add Python-specific environment validation.

        Parameters
        ----------
        result : Dict[str, Any]
            Validation result dictionary to populate
        """
        logger.debug("Validating Python environment")

        python_path = shutil.which("python") or shutil.which("python3")
        result["python_found"] = bool(python_path)

        if not python_path:
            logger.warning(
                "Python interpreter not found in PATH",
                extra={"language": Language.PYTHON},
            )

        if python_path:
            try:
                version = subprocess.check_output(
                    [python_path, "--version"],
                    stderr=subprocess.STDOUT,
                    text=True,
                ).strip()
                result["python_version"] = version
                logger.debug(
                    "Python version detected",
                    extra={"version": version, "path": python_path},
                )
            except Exception as e:
                logger.debug(
                    "Failed to get Python version",
                    extra={"error": str(e), "path": python_path},
                )

        # Check debugpy in adapter directory
        adapter_debugpy = get_aidb_adapters_dir() / Language.PYTHON / "debugpy"
        if adapter_debugpy.exists():
            result["debugpy_available"] = True
            logger.debug(
                "debugpy adapter available",
                extra={"path": str(adapter_debugpy)},
            )
        else:
            logger.warning(
                "debugpy adapter not installed",
                extra={
                    "language": Language.PYTHON,
                    "expected_path": str(adapter_debugpy),
                },
            )
            result.setdefault("issues", []).append("debugpy adapter not installed")
            result.setdefault("warnings", []).append(
                "Run 'aidb adapter download python' to install the debug adapter",
            )

    def _discover_language_context(
        self,
        workspace_path: Path,
        context: dict[str, Any],
    ) -> None:
        """Add Python-specific context discovery.

        Parameters
        ----------
        workspace_path : Path
            The workspace root as a Path object
        context : Dict[str, Any]
            Context dictionary to populate with discoveries
        """
        logger.debug(
            "Discovering Python-specific context",
            extra={"workspace": str(workspace_path)},
        )
        context.setdefault("project_files", [])

        # Check for Python virtual environments
        venv_indicators = [".venv", "venv", "env", ".env"]
        for venv_dir in venv_indicators:
            venv_path = workspace_path / venv_dir
            if venv_path.exists() and (venv_path / "bin" / "python").exists():
                context["virtual_env"] = str(venv_path)
                break

        # Check for Python config files
        config_patterns = [
            "pyproject.toml",
            "setup.py",
            "setup.cfg",
            "requirements.txt",
            "Pipfile",
            "poetry.lock",
            "tox.ini",
            ".python-version",
        ]
        for pattern in config_patterns:
            if (workspace_path / pattern).exists():
                context["project_files"].append(pattern)

    def get_advanced_examples(self) -> dict[str, Any]:
        """Get advanced Python debugging examples.

        Returns
        -------
        Dict[str, Any]
            Advanced configuration examples
        """
        return {
            "multiprocess": {
                "target": "python",
                "args": ["main.py"],
                "env": {"PYDEVD_USE_MULTIPROCESSING": "True"},
                "comment": "Debug child processes in multiprocessing apps",
            },
            "remote_docker": {
                "host": DEFAULT_ADAPTER_HOST,
                "port": DEFAULT_PYTHON_DEBUG_PORT,
                "pathMappings": [{"localRoot": "${workspace}", "remoteRoot": "/app"}],
                "comment": "Attach to Python running in Docker container",
            },
            "jupyter": {
                "target": "jupyter",
                "args": ["notebook", "--no-browser"],
                "comment": "Debug Jupyter notebooks (requires specific adapter)",
            },
            "conditional_breakpoint": {
                "location": "app.py:42",
                "condition": "user_id == 123",
                "comment": "Break only when condition is true",
            },
            "logpoint": {
                "location": "loop.py:10",
                "log_message": "Iteration {i}, value={value}",
                "comment": "Log without stopping execution",
            },
        }
