"""Base class for language-specific debugging starters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any

from aidb_common.constants import Language
from aidb_common.discovery.adapters import (
    get_popular_frameworks as _get_popular_frameworks,
)
from aidb_common.discovery.adapters import (
    get_supported_frameworks as _get_supported_frameworks,
)
from aidb_common.io import safe_read_json
from aidb_common.io.files import FileOperationError
from aidb_common.path import normalize_path
from aidb_logging import get_mcp_logger as get_logger

from ..core import LaunchMode, ToolName

if TYPE_CHECKING:
    from ..core.types import DebugAdapterConfig

logger = get_logger(__name__)


class BaseStarter(ABC):
    """Abstract base class for language-specific debugging starters.

    Each language implementation provides framework-specific debugging examples
    and workspace context discovery without requiring adapter initialization.

    Attributes
    ----------
    language : str
        The programming language this starter supports
    adapter_config : DebugAdapterConfig | None
        The adapter configuration class for this language
    """

    def __init__(self, language: str, adapter_config: DebugAdapterConfig | None = None):
        """Initialize the starter.

        Parameters
        ----------
        language : str
            The programming language (e.g., "python", "javascript")
        adapter_config : DebugAdapterConfig, optional
            The adapter configuration class, if available
        """
        self.language = language
        self.adapter_config = adapter_config
        logger.debug(
            "Starter initialized",
            extra={
                "language": language,
                "has_adapter_config": adapter_config is not None,
                "starter_class": self.__class__.__name__,
            },
        )

    def get_supported_frameworks(self) -> list[str]:
        """Get list of frameworks supported by this language adapter.

        Returns
        -------
        List[str]
            List of supported framework names
        """
        return _get_supported_frameworks(self.language)

    def get_popular_frameworks(self) -> list[str]:
        """Get list of popular frameworks to show as examples.

        Returns
        -------
        List[str]
            List of popular framework names (2-3 max)
        """
        return _get_popular_frameworks(self.language)

    def normalize_framework(self, framework: str | None) -> str | None:
        """Normalize and fuzzy match framework name.

        Parameters
        ----------
        framework : str, optional
            User-provided framework name

        Returns
        -------
        str or None
            Matched framework name from supported list, or None if no match
        """
        if not framework:
            return None

        # Remove all non-alphanumeric chars and lowercase
        normalized = "".join(c for c in framework.lower() if c.isalnum())

        # Get supported frameworks
        supported = self.get_supported_frameworks()

        # Check each supported framework
        for sup in supported:
            sup_normalized = "".join(c for c in sup.lower() if c.isalnum())

            # Check if either contains the other
            if normalized in sup_normalized or sup_normalized in normalized:
                logger.debug(
                    "Framework normalized",
                    extra={
                        "input": framework,
                        "normalized": normalized,
                        "matched": sup,
                        "language": self.language,
                    },
                )
                return sup  # Return the original supported name

        logger.debug(
            "Framework not matched",
            extra={
                "input": framework,
                "normalized": normalized,
                "supported": supported,
                "language": self.language,
            },
        )
        return None

    @abstractmethod
    def get_launch_example(
        self,
        target: str | None = None,
        framework: str | None = None,
        workspace_root: str | None = None,
    ) -> dict[str, Any]:
        """Generate a launch mode debugging example.

        Parameters
        ----------
        target : str, optional
            Target file to debug
        framework : str, optional
            Specific framework to generate example for
        workspace_root : str, optional
            Workspace root directory for context discovery

        Returns
        -------
        Dict[str, Any]
            Example parameters for session_start tool
        """

    @abstractmethod
    def get_attach_example(
        self,
        mode: str = "local",
        pid: int | None = None,
        host: str | None = None,
        port: int | None = None,
    ) -> dict[str, Any]:
        """Generate an attach mode debugging example.

        Parameters
        ----------
        mode : str
            Attach mode - local for PID or remote for ``host:port``
        pid : int, optional
            Process ID for local attach
        host : str, optional
            Host for remote attach
        port : int, optional
            Port for remote attach

        Returns
        -------
        Dict[str, Any]
            Example parameters for session_start tool
        """

    @abstractmethod
    def get_common_breakpoints(
        self,
        framework: str | None = None,
        target: str | None = None,
    ) -> list[str]:
        """Get common breakpoint suggestions for the framework.

        Parameters
        ----------
        framework : str, optional
            Specific framework to get breakpoints for
        target : str, optional
            Target file to suggest breakpoints for

        Returns
        -------
        List[str]
            List of suggested breakpoint locations (``file:line`` format)
        """

    def discover_workspace_context(
        self,
        workspace_root: str | None = None,
    ) -> dict[str, Any]:
        """Discover workspace-specific context.

        Looks for launch configurations and project files.

        Parameters
        ----------
        workspace_root : str, optional
            Root directory to search in, defaults to current directory

        Returns
        -------
        Dict[str, Any]
            Dictionary containing discovered context:
            - launch_configs: List of VS Code launch configuration names
            - workspace_root: Resolved workspace root path
            - project_files: Relevant project configuration files found
        """
        if workspace_root is None:
            workspace_root = str(Path.cwd())

        workspace_path = Path(workspace_root)
        context: dict[str, Any] = {
            "workspace_root": normalize_path(
                workspace_path,
                strict=False,
                return_path=False,
            ),
            "project_files": [],
        }

        # Check for launch configurations in any IDE directory
        # (.vscode, .windsurf, .cursor, etc.)
        launch_json_paths = list(workspace_path.glob(".*/launch.json"))

        if launch_json_paths:
            # Use the first launch.json found
            launch_json_path = launch_json_paths[0]
            try:
                launch_data = safe_read_json(launch_json_path) or {}
                configs = launch_data.get("configurations", [])

                # Just get all configuration names, no filtering
                # Let the core adapter layer handle validation
                launch_configs = [
                    cfg.get("name", "Unnamed")
                    for cfg in configs
                    if cfg.get("name")  # Only include configs with names
                ]

                if launch_configs:
                    context["launch_configs"] = launch_configs
                    context["launch_config_source"] = str(
                        launch_json_path.parent.name,
                    )

                logger.debug(
                    "Found launch configurations",
                    extra={
                        "source": str(launch_json_path),
                        "config_count": len(launch_configs) if launch_configs else 0,
                        "workspace": str(workspace_path),
                    },
                )
            except FileOperationError as e:
                # Silently skip if we can't read launch.json
                logger.debug(
                    "Could not read launch.json",
                    extra={"path": str(launch_json_path), "error": str(e)},
                )

        # Let subclasses add language-specific discovery
        self._discover_language_context(workspace_path, context)

        return context

    def discover_multi_root_context(self, workspace_roots: list[str]) -> dict[str, Any]:
        """Discover context across multiple workspace roots.

        Parameters
        ----------
        workspace_roots : List[str]
            List of workspace root directories

        Returns
        -------
        Dict[str, Any]
            Combined context from all roots with:
            - roots: Dict mapping each root to its context
            - all_launch_configs: Combined list of launch configs
            - primary_root: Root with richest context
        """
        combined_context: dict[str, Any] = {
            "roots": {},
            "primary_root": None,
        }
        all_launch_configs = []

        # Discover context for each root
        for root in workspace_roots:
            context = self.discover_workspace_context(root)
            combined_context["roots"][root] = context

            # Combine launch configs
            all_launch_configs.extend(
                context.get("launch_configs", []),
            )

        # Determine primary root (with most context)
        if workspace_roots:
            primary_root = max(
                workspace_roots,
                key=lambda r: (
                    len(combined_context["roots"][r].get("launch_configs", [])),
                    len(combined_context["roots"][r].get("project_files", [])),
                ),
            )
            combined_context["primary_root"] = primary_root
            combined_context["primary_context"] = combined_context["roots"][
                primary_root
            ]

        # Only add all_launch_configs if there are any
        if all_launch_configs:
            combined_context["all_launch_configs"] = all_launch_configs

        return combined_context

    def _discover_language_context(  # noqa: B027
        self,
        workspace_path: Path,
        context: dict[str, Any],
    ) -> None:
        """Add hook for language-specific context discovery.

        Subclasses can override this to add language-specific discoveries like
        virtual environments, package files, etc.

        Parameters
        ----------
        workspace_path : Path
            The workspace root as a Path object
        context : Dict[str, Any]
            Context dictionary to populate with discoveries
        """

    def validate_environment(self) -> dict[str, Any]:
        """Validate that the environment is ready for debugging.

        Checks for required tools, available ports, permissions, etc.

        Returns
        -------
        Dict[str, Any]
            Validation results:
            - is_valid: Boolean indicating if environment is ready
            - issues: List of any issues found
            - warnings: List of non-critical warnings
        """
        result: dict[str, Any] = {"is_valid": True, "issues": [], "warnings": []}

        # Check if adapter config is available
        if not self.adapter_config:
            warning = f"No adapter configuration found for {self.language}"
            result["warnings"].append(warning)
            logger.debug(
                "Environment validation warning",
                extra={"language": self.language, "warning": warning},
            )

        # Check default port availability (basic check)
        if self.adapter_config and hasattr(self.adapter_config, "adapter_port"):
            port = self.adapter_config.adapter_port
            # Note: Actual port checking would require socket operations
            # This is a placeholder for the concept
            result["default_port"] = port

        # Let subclasses add language-specific validation
        self._validate_language_environment(result)

        # Set is_valid based on issues found
        if result["issues"]:
            result["is_valid"] = False
            logger.warning(
                "Environment validation failed",
                extra={
                    "language": self.language,
                    "issues": result["issues"],
                    "warnings": result["warnings"],
                },
            )
        else:
            logger.debug(
                "Environment validation passed",
                extra={"language": self.language, "warnings": result["warnings"]},
            )

        return result

    def _validate_language_environment(self, result: dict[str, Any]) -> None:  # noqa: B027
        """Add hook for language-specific environment validation.

        Subclasses can override this to add language-specific checks.

        Parameters
        ----------
        result : Dict[str, Any]
            Validation result dictionary to populate
        """

    def _discover_workspace(
        self,
        workspace_root: str | None,
        workspace_roots: list[str] | None,
    ) -> tuple[dict[str, Any], str | None]:
        """Discover workspace context.

        Parameters
        ----------
        workspace_root : str, optional
            Single workspace root
        workspace_roots : list[str], optional
            Multiple workspace roots

        Returns
        -------
        tuple[dict[str, Any], str | None]
            Discovered context and primary workspace
        """
        if workspace_roots:
            discovered = self.discover_multi_root_context(workspace_roots)
            primary_workspace = discovered.get("primary_root", workspace_roots[0])
        else:
            discovered = self.discover_workspace_context(workspace_root)
            primary_workspace = discovered.get("workspace_root")
        return discovered, primary_workspace

    def _get_next_call_example(
        self,
        mode: str | None,
        normalized_framework: str | None,
        primary_workspace: str | None,
    ) -> dict[str, Any]:
        """Get the next call example based on mode.

        Parameters
        ----------
        mode : str, optional
            Debug mode
        normalized_framework : str, optional
            Normalized framework name
        primary_workspace : str, optional
            Primary workspace path

        Returns
        -------
        dict[str, Any]
            Next call example
        """
        if mode == LaunchMode.ATTACH.value:
            return self.get_attach_example(mode="local")
        if mode == LaunchMode.REMOTE_ATTACH.value:
            return self.get_attach_example(mode="remote")
        # Launch mode - use normalized framework if valid
        return self.get_launch_example(
            framework=normalized_framework,
            workspace_root=primary_workspace,
        )

    def _build_examples(
        self,
        framework: str | None,
        normalized_framework: str | None,
        primary_workspace: str | None,
        response: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Build framework examples.

        Parameters
        ----------
        framework : str, optional
            Original framework parameter
        normalized_framework : str, optional
            Normalized framework name
        primary_workspace : str, optional
            Primary workspace path
        response : dict[str, Any]
            Response dictionary to add notes to

        Returns
        -------
        list[dict[str, Any]]
            List of example configurations
        """
        examples = []

        if normalized_framework:
            # Valid framework - include single example for that framework
            example = self.get_launch_example(
                framework=normalized_framework,
                workspace_root=primary_workspace,
            )
            examples.append(
                {
                    "framework": normalized_framework,
                    "description": f"Debug with {normalized_framework}",
                    "session_start_params": example,
                },
            )
        elif framework:
            # Framework provided but not supported - show popular examples
            popular_frameworks = self.get_popular_frameworks()

            for fw in popular_frameworks[:3]:  # Max 3 examples
                example = self.get_launch_example(
                    framework=fw,
                    workspace_root=primary_workspace,
                )
                examples.append(
                    {
                        "framework": fw,
                        "description": f"Debug with {fw}",
                        "session_start_params": example,
                    },
                )

            # Add note about why we're showing generic examples
            response["note"] = (
                f"Framework '{framework}' not explicitly supported. "
                f"Showing popular {self.language} framework examples."
            )
            logger.info(
                "Unsupported framework requested",
                extra={
                    "language": self.language,
                    "requested": framework,
                    "supported": self.get_supported_frameworks(),
                },
            )
        else:
            # No framework specified - don't show framework examples
            response["note"] = (
                "No framework specified. Specify 'framework' parameter "
                "for framework-specific examples."
            )

        return examples

    def _build_tips(
        self,
        discovered: dict[str, Any],
        workspace_roots: list[str] | None,
        primary_workspace: str | None,
    ) -> list[str]:
        """Build debugging tips based on discoveries.

        Parameters
        ----------
        discovered : dict[str, Any]
            Discovered workspace context
        workspace_roots : list[str], optional
            Multiple workspace roots
        primary_workspace : str, optional
            Primary workspace path

        Returns
        -------
        list[str]
            List of debugging tips
        """
        tips: list[str] = []

        # Tip about launch configs
        if workspace_roots:
            all_configs = discovered.get("all_launch_configs", [])
            if all_configs:
                tips.append(
                    f"Found {len(all_configs)} launch configs across workspaces. "
                    f"Use launch_config_name='{all_configs[0]}' to use one.",
                )
        elif discovered:  # Check if discovered exists first
            launch_configs = discovered.get("launch_configs", [])
            if launch_configs:
                tips.append(
                    f"Use launch_config_name='{launch_configs[0]}' "
                    "to use VS Code configuration",
                )

        # Tip about multi-root workspace
        if workspace_roots and len(workspace_roots) > 1:
            tips.append(
                f"Multi-root workspace with {len(workspace_roots)} roots. "
                f"Using {primary_workspace} as primary.",
            )

        # Target/entrypoint guidance tips
        project_files = discovered.get("project_files", [])

        # Detect project structure patterns for targeted tips
        if any("test" in f.lower() for f in project_files):
            tips.append(
                "Testing project detected. Remember: target runs tests (pytest, npm), "
                "breakpoints go in source code being tested, not test files.",
            )

        if any(
            f in project_files for f in ["package.json", "pyproject.toml", "pom.xml"]
        ):
            tips.append(
                "Complex project structure detected. Consider using launch_config "
                "to abstract target/args/env setup instead of manual configuration.",
            )

        # General entrypoint guidance based on language
        language_tips = {
            Language.PYTHON.value: (
                "Python debugging: target is entry script (main.py, app.py), "
                "set breakpoints in modules where bugs occur (models/, utils/)."
            ),
            Language.JAVASCRIPT.value: (
                "Node.js debugging: target starts app (index.js, server.js), "
                "set breakpoints in route handlers, services, or utility modules."
            ),
            Language.JAVA.value: (
                "Java debugging: target is your main class or JAR file, "
                "set breakpoints in service classes, utilities, or business logic."
            ),
        }

        if self.language in language_tips:
            tips.append(language_tips[self.language])

        return tips

    def _add_educational_content(self, response: dict[str, Any]) -> None:
        """Add educational content for verbose mode.

        Parameters
        ----------
        response : dict[str, Any]
            Response dictionary to add content to
        """
        # Add concise breakpoint format reference
        response["breakpoint_format"] = {
            "required": {"file": "string", "line": "number"},
            "optional": {
                "condition": "string - e.g., 'x > 5'",
                "hit_condition": "string - e.g., '>5' or '%10'",
                "log_message": "string - logs instead of pausing",
            },
            "examples": [
                {"file": "/path/to/main.py", "line": 10},
                {
                    "file": "/path/to/app.py",
                    "line": 42,
                    "condition": "user_id == 123",
                },
            ],
        }

        # Add key concepts for debugging success
        response["key_concepts"] = {
            "target_vs_breakpoints": {
                "explanation": (
                    "The TARGET is your entrypoint - the file/script that starts "
                    "execution and triggers the codepath you want to debug. "
                    "BREAKPOINTS can be set in any file, oft different from target"
                    "Think: target=main.py (starts app), "
                    "breakpoints={file: '/path/to/utils/helper.py', line: 25} "
                    "(where you want to pause)."
                ),
                "examples": [
                    {
                        "scenario": "Web application debugging",
                        "target": "app.py",
                        "breakpoints": [
                            {"file": "/path/to/routes/api.py", "line": 45},
                            {"file": "/path/to/models/user.py", "line": 78},
                        ],
                        "reasoning": "app.py starts server, debug API logic",
                    },
                    {
                        "scenario": "CLI tool debugging",
                        "target": "main.py",
                        "breakpoints": [
                            {"file": "/path/to/utils/parser.py", "line": 23},
                            {"file": "/path/to/config/settings.py", "line": 156},
                        ],
                        "reasoning": "main.py is entry point, issues in utilities",
                    },
                ],
            },
            "launch_configs": {
                "purpose": (
                    "VS Code launch.json configs abstract away complex setups. "
                    "Instead of specifying target, args, env manually, reference "
                    "a pre-configured launch setup."
                ),
                "when_to_use": (
                    "Use launch configs for: complex apps with multiple entry "
                    "points, specific environment requirements, framework-specific "
                    "debugging (Django, Spring Boot), or team-shared debug setups."
                ),
                "example": (
                    "launch_config_name='Debug API Server' vs target='manage.py'"
                ),
            },
        }

    def generate_response(
        self,
        mode: str | None = None,
        framework: str | None = None,
        workspace_root: str | None = None,
        workspace_roots: list[str] | None = None,
        launch_config_name: str | None = None,
        verbose: bool = False,
    ) -> dict[str, Any]:
        """Generate a complete response for the MCP start tool.

        Parameters
        ----------
        mode : str, optional
            Debug mode (launch, attach, or remote_attach)
        framework : str, optional
            Specific framework to target
        workspace_root : str, optional
            Single workspace root for context discovery
        workspace_roots : List[str], optional
            Multiple workspace roots for multi-root workspaces
        launch_config_name : str, optional
            Name of VS Code launch configuration to reference
        verbose : bool, optional
            Include educational content (key concepts, breakpoint format), default False

        Returns
        -------
        Dict[str, Any]
            Complete response structure with examples and guidance
        """
        # Discover workspace context
        discovered, primary_workspace = self._discover_workspace(
            workspace_root,
            workspace_roots,
        )

        # Get supported frameworks
        supported_frameworks = self.get_supported_frameworks()

        # Normalize/fuzzy match the framework if provided
        normalized_framework = (
            self.normalize_framework(framework) if framework else None
        )

        logger.info(
            "Generating starter response",
            extra={
                "language": self.language,
                "mode": mode,
                "framework": framework,
                "normalized_framework": normalized_framework,
                "has_workspace": bool(workspace_root or workspace_roots),
                "launch_config_name": launch_config_name,
            },
        )

        # Generate primary example based on mode and framework
        next_call = self._get_next_call_example(
            mode,
            normalized_framework,
            primary_workspace,
        )

        # Build response
        response: dict[str, Any] = {
            "language": self.language,
            "framework": normalized_framework or framework,  # Show what they asked for
            "supported_frameworks": supported_frameworks,
            "discovered": discovered,
        }

        # Add next_steps with actual session_start parameters
        response["next_steps"] = [
            {
                "tool": ToolName.SESSION_START,
                "params": next_call,
                "description": "Start debug session",
                "when": "to begin debugging",
            },
        ]

        # Build examples
        examples = self._build_examples(
            framework,
            normalized_framework,
            primary_workspace,
            response,
        )

        # Only add examples field if there are examples to show
        if examples:
            response["examples"] = examples

        # Build and add tips
        response["tips"] = self._build_tips(
            discovered,
            workspace_roots,
            primary_workspace,
        )

        # Add educational content only if verbose mode is enabled
        if verbose:
            self._add_educational_content(response)

        return response
