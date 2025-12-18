"""Java-specific debugging starter implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aidb.common.constants import DEFAULT_ADAPTER_HOST, DEFAULT_JAVA_DEBUG_PORT
from aidb_common.constants import Language
from aidb_logging import get_mcp_logger as get_logger

from .base import BaseStarter

if TYPE_CHECKING:
    from pathlib import Path

logger = get_logger(__name__)


class JavaStarter(BaseStarter):
    """Java debugging starter with framework-specific examples."""

    def get_launch_example(
        self,
        target: str | None = None,
        framework: str | None = None,
        workspace_root: str | None = None,
    ) -> dict[str, Any]:
        """Get Java launch configuration example.

        Parameters
        ----------
        target : str, optional
            Target file to debug
        framework : str, optional
            Specific framework (junit, spring, etc.)
        workspace_root : str, optional
            Workspace root directory for context discovery

        Returns
        -------
        Dict[str, Any]
            Launch configuration example
        """
        from .framework_registry import get_default_config, get_framework_config

        logger.debug(
            "Generating Java launch example",
            extra={
                "framework": framework,
                "target": target,
                "workspace_root": workspace_root,
                "language": Language.JAVA,
            },
        )

        # Try to get framework-specific config
        config = get_framework_config(Language.JAVA.value, framework)
        if config:
            return config.to_launch_example()

        # Fall back to default
        logger.debug(
            "Using generic Java launch config",
            extra={"framework": framework or "none", "language": Language.JAVA},
        )
        return get_default_config(Language.JAVA.value).to_launch_example()

    def get_attach_example(
        self,
        mode: str = "local",
        pid: int | None = None,
        host: str | None = None,
        port: int | None = None,
    ) -> dict[str, Any]:
        """Get Java attach configuration example.

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
            "Generating Java attach example",
            extra={
                "mode": mode,
                "pid": pid,
                "host": host,
                "port": port,
                "language": Language.JAVA,
            },
        )

        if mode == "remote":
            return {
                "host": host or DEFAULT_ADAPTER_HOST,
                "port": port or DEFAULT_JAVA_DEBUG_PORT,
                "comment": (
                    "Start JVM with: -agentlib:jdwp=transport=dt_socket,"
                    f"server=y,suspend=n,address={DEFAULT_JAVA_DEBUG_PORT}"
                ),
            }
        if mode == "local" and pid:
            return {
                "pid": pid,
                "comment": "Attach to running Java process",
            }
        return {
            "host": DEFAULT_ADAPTER_HOST,
            "port": DEFAULT_JAVA_DEBUG_PORT,
            "comment": (
                "Start JVM with: -agentlib:jdwp=transport=dt_socket,"
                f"server=y,suspend=n,address={DEFAULT_JAVA_DEBUG_PORT}"
            ),
        }

    def get_common_breakpoints(
        self,
        framework: str | None = None,
        target: str | None = None,
    ) -> list[str]:
        """Get common breakpoint suggestions for Java.

        Parameters
        ----------
        framework : str, optional
            Specific framework
        target : str, optional
            Target file to suggest breakpoints for

        Returns
        -------
        List[str]
        """
        logger.debug(
            "Getting common breakpoints for Java",
            extra={"framework": framework, "target": target, "language": Language.JAVA},
        )
        if framework == "junit":
            return [
                "*Test.java:@Test",
                "*Tests.java:@Test",
                "TestBase.java:1",
            ]
        if framework == "spring":
            return [
                "*Controller.java:@RequestMapping",
                "*Service.java:1",
                "Application.java:main",
            ]
        return [
            "Main.java:main",
            "src/main/java/**/*.java:1",
        ]

    def _validate_language_environment(self, result: dict[str, Any]) -> None:
        """Add Java-specific environment validation.

        Parameters
        ----------
        result : Dict[str, Any]
            Validation result dictionary to populate
        """
        # Check Java availability
        import shutil

        java_path = shutil.which("java")
        result["java_found"] = bool(java_path)

        if java_path:
            # Get Java version
            import subprocess

            try:
                version = subprocess.check_output(
                    [java_path, "-version"],
                    stderr=subprocess.STDOUT,
                    text=True,
                ).strip()
                result["java_version"] = version
            except Exception as e:
                msg = f"Failed to get Java version: {e}"
                logger.debug(msg)

        # Check build tools
        if shutil.which("mvn"):
            result["build_tool"] = "maven"
        elif shutil.which("gradle"):
            result["build_tool"] = "gradle"

    def _discover_language_context(
        self,
        workspace_path: Path,
        context: dict[str, Any],
    ) -> None:
        """Add Java-specific context discovery.

        Parameters
        ----------
        workspace_path : Path
            The workspace root as a Path object
        context : Dict[str, Any]
            Context dictionary to populate with discoveries
        """
        context.setdefault("project_files", [])

        # Check for build files and configs
        java_configs = [
            "pom.xml",
            "build.gradle",
            "build.gradle.kts",
            "settings.gradle",
            "settings.gradle.kts",
            ".mvn/wrapper/maven-wrapper.properties",
            "gradlew",
            "mvnw",
        ]

        for config_file in java_configs:
            config_path = workspace_path / config_file
            if config_path.exists():
                context["project_files"].append(config_file)

        # Check for target/build directories
        if (workspace_path / "target").exists():
            context["has_maven_target"] = True
        if (workspace_path / "build").exists():
            context["has_gradle_build"] = True

        # Check for source directories
        if (workspace_path / "src" / "main" / "java").exists():
            context["standard_layout"] = True

    def get_advanced_examples(self) -> dict[str, Any]:
        """Get advanced Java debugging examples.

        Returns
        -------
        Dict[str, Any]
            Advanced configuration examples
        """
        return {
            "remote_container": {
                "host": DEFAULT_ADAPTER_HOST,
                "port": DEFAULT_JAVA_DEBUG_PORT,
                "comment": "Attach to Java in Docker container",
            },
            "maven_debug": {
                "target": "mvn",
                "args": ["test", "-Dmaven.surefire.debug"],
                "comment": "Debug Maven tests with automatic port",
            },
        }
