"""JavaScript-specific debugging starter implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aidb_logging import get_mcp_logger as get_logger

from .base import BaseStarter

if TYPE_CHECKING:
    from pathlib import Path

logger = get_logger(__name__)


class JavaScriptStarter(BaseStarter):
    """JavaScript debugging starter with framework-specific examples."""

    def get_launch_example(
        self,
        target: str | None = None,
        framework: str | None = None,
        workspace_root: str | None = None,
    ) -> dict[str, Any]:
        """Get JavaScript launch configuration example.

        Parameters
        ----------
        target : str, optional
            Target file to debug
        framework : str, optional
            Specific framework (jest, mocha, etc.)
        workspace_root : str, optional
            Workspace root directory for context discovery

        Returns
        -------
        Dict[str, Any]
            Launch configuration example
        """
        logger.debug(
            "Generating JavaScript launch example",
            extra={
                "framework": framework,
                "target": target,
                "workspace_root": workspace_root,
                "language": "javascript",
            },
        )

        if framework == "jest":
            return {
                "target": "npm",
                "args": ["test", "--", "--runInBand", "--no-coverage"],
                "cwd": "${workspace_root}",
                "comment": "Debug Jest tests",
                "breakpoints": [
                    {
                        "file": "/path/to/src/utils/calculator.js",
                        "line": 15,
                    },  # Source code being tested
                    {
                        "file": "/path/to/src/services/api.js",
                        "line": 42,
                    },  # Service functions
                    {
                        "file": "/path/to/lib/validation.js",
                        "line": 78,
                    },  # Validation logic
                ],
            }
        if framework == "mocha":
            return {
                "target": "mocha",
                "args": ["--inspect-brk", "test/**/*.test.js"],
                "cwd": "${workspace_root}",
                "comment": "Debug Mocha tests",
                "breakpoints": [
                    {
                        "file": "/path/to/src/controllers/user.js",
                        "line": 25,
                    },  # Business logic
                    {
                        "file": "/path/to/src/models/database.js",
                        "line": 67,
                    },  # Database operations
                    {
                        "file": "/path/to/utils/helpers.js",
                        "line": 34,
                    },  # Helper functions
                ],
            }
        # Generic Node.js launch
        logger.debug(
            "Using generic Node.js launch config",
            extra={"framework": framework or "none", "language": "javascript"},
        )
        return {
            "target": "node",
            "args": ["index.js"],
            "cwd": "${workspace_root}",
            "breakpoints": [
                {"file": "/path/to/lib/server.js", "line": 45},  # Server setup
                {"file": "/path/to/routes/api.js", "line": 78},  # API routes
                {"file": "/path/to/middleware/auth.js", "line": 23},  # Authentication
            ],
        }

    def get_attach_example(
        self,
        mode: str = "local",
        pid: int | None = None,
        host: str | None = None,
        port: int | None = None,
    ) -> dict[str, Any]:
        """Get JavaScript attach configuration example.

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
            "Generating JavaScript attach example",
            extra={
                "mode": mode,
                "pid": pid,
                "host": host,
                "port": port,
                "language": "javascript",
            },
        )

        if mode == "remote":
            return {
                "host": host or "localhost",
                "port": port or 9229,
                "comment": "Start Node with: node --inspect index.js",
            }
        if mode == "local" and pid:
            return {
                "pid": pid,
                "comment": "Attach to running Node.js process",
            }
        return {
            "host": "localhost",
            "port": 9229,
            "comment": "Start Node with: node --inspect index.js",
        }

    def get_common_breakpoints(
        self,
        framework: str | None = None,
        target: str | None = None,
    ) -> list[str]:
        """Get common breakpoint suggestions for JavaScript.

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
            "Getting common breakpoints for JavaScript",
            extra={"framework": framework, "target": target, "language": "javascript"},
        )

        if framework == "jest":
            return [
                "**/*.test.js:1",
                "**/*.spec.js:1",
                "setupTests.js:1",
            ]
        return [
            "index.js:1",
            "app.js:1",
            "src/main.js:1",
        ]

    def _validate_language_environment(self, result: dict[str, Any]) -> None:
        """Add JavaScript-specific environment validation.

        Parameters
        ----------
        result : Dict[str, Any]
            Validation result dictionary to populate
        """
        logger.debug("Validating JavaScript environment")

        # Check Node.js availability
        import shutil

        node_path = shutil.which("node")
        result["node_found"] = bool(node_path)

        if not node_path:
            logger.warning(
                "Node.js not found in PATH",
                extra={"language": "javascript"},
            )

        if node_path:
            # Get Node version
            import subprocess

            try:
                version = subprocess.check_output(
                    [node_path, "--version"],
                    text=True,
                ).strip()
                logger.debug(
                    "Node.js version detected",
                    extra={"version": version, "path": node_path},
                )
                result["node_version"] = version
            except Exception as e:
                msg = f"Failed to get Node.js version: {e}"
                logger.debug(msg)

        # Check package managers
        if shutil.which("npm"):
            result["package_manager"] = "npm"
        elif shutil.which("yarn"):
            result["package_manager"] = "yarn"
        elif shutil.which("pnpm"):
            result["package_manager"] = "pnpm"

    def _discover_language_context(
        self,
        workspace_path: Path,
        context: dict[str, Any],
    ) -> None:
        """Add JavaScript-specific context discovery.

        Parameters
        ----------
        workspace_path : Path
            The workspace root as a Path object
        context : Dict[str, Any]
            Context dictionary to populate with discoveries
        """
        context.setdefault("project_files", [])

        # Check for package files and configs
        js_configs = [
            "package.json",
            "tsconfig.json",
            "jsconfig.json",
            ".npmrc",
            "yarn.lock",
            "package-lock.json",
            "pnpm-lock.yaml",
        ]

        for config_file in js_configs:
            if (workspace_path / config_file).exists():
                context["project_files"].append(config_file)

        # Check for node_modules
        if (workspace_path / "node_modules").exists():
            context["has_node_modules"] = True

        # Check for TypeScript
        if (workspace_path / "tsconfig.json").exists():
            context["uses_typescript"] = True

    def get_advanced_examples(self) -> dict[str, Any]:
        """Get advanced JavaScript debugging examples.

        Returns
        -------
        Dict[str, Any]
            Advanced configuration examples
        """
        return {
            "typescript": {
                "target": "node",
                "args": ["--require", "ts-node/register", "src/index.ts"],
                "comment": "Debug TypeScript with ts-node",
            },
            "chrome": {
                "host": "localhost",
                "port": 9222,
                "comment": "Attach to Chrome DevTools",
            },
        }
