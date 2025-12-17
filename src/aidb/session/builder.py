"""Session builder for cleaner session creation."""

from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from aidb.adapters.base.vslaunch import BaseLaunchConfig, LaunchConfigurationManager
from aidb.common.constants import (
    ADAPTER_ARG_ARGS,
    ADAPTER_ARG_PROGRAM,
    ADAPTER_ARG_TARGET,
)
from aidb.common.errors import AidbError
from aidb.models import AidbBreakpoint, StartRequestType
from aidb.models.entities.breakpoint import BreakpointSpec
from aidb.patterns import Obj
from aidb.session.breakpoint_converter import BreakpointConverter
from aidb.session.session_core import Session

if TYPE_CHECKING:
    from aidb.interfaces.context import IContext


class SessionValidator:
    """Validates session configuration and parameters.

    This class encapsulates all validation logic for session creation, making the
    SessionBuilder cleaner and more focused on construction.
    """

    @staticmethod
    def validate_mode_compatibility(
        mode: StartRequestType,
        target: str | None,
        pid: int | None,
        host: str | None,
        port: int | None,
        args: list[str] | None,
    ) -> None:
        """Validate that parameters are compatible with the session mode.

        Parameters
        ----------
        mode : StartRequestType
            The session mode (LAUNCH or ATTACH)
        target : str, optional
            Target file for launch mode
        pid : int, optional
            Process ID for attach mode
        host : str, optional
            Host for remote attach
        port : int, optional
            Port for remote attach
        args : List[str], optional
            Command-line arguments

        Raises
        ------
        AidbError
            If parameters are incompatible with the mode
        """
        if mode == StartRequestType.LAUNCH:
            if pid or host or port:
                msg = "Cannot use attach parameters (pid, host, port) in launch mode"
                raise AidbError(
                    msg,
                )
            if not target:
                msg = "Target file is required for launch mode"
                raise AidbError(msg)
        else:  # ATTACH mode
            if args:
                msg = "Cannot use 'args' parameter in attach mode"
                raise AidbError(msg)
            if not (pid or (host and port)):
                msg = (
                    "Must provide either 'pid' for local attach or "
                    "'host' and 'port' for remote attach"
                )
                raise AidbError(
                    msg,
                )

    @staticmethod
    def validate_launch_config(config: BaseLaunchConfig) -> None:
        """Validate launch configuration.

        Parameters
        ----------
        config : BaseLaunchConfig
            Launch configuration to validate

        Raises
        ------
        AidbError
            If configuration is invalid
        """
        if not config.name:
            msg = "Launch configuration must have a name"
            raise AidbError(msg)

        if config.request not in ["launch", "attach"]:
            msg = f"Invalid launch configuration request type: {config.request}"
            raise AidbError(
                msg,
            )

    @staticmethod
    def validate_attach_config(
        pid: int | None,
        host: str | None,
        port: int | None,
    ) -> None:
        """Validate attach configuration parameters.

        Parameters
        ----------
        pid : int, optional
            Process ID for local attach
        host : str, optional
            Host for remote attach
        port : int, optional
            Port for remote attach

        Raises
        ------
        AidbError
            If attach configuration is invalid
        """
        from aidb.common.validation import validate_attach_config as _validate

        _validate(pid, host, port)

    @staticmethod
    def determine_mode(
        target: str | None,
        pid: int | None,
        host: str | None,
        port: int | None,
        start_request_type: StartRequestType | None,
    ) -> StartRequestType:
        """Determine the session mode from parameters.

        Parameters
        ----------
        target : str, optional
            Target file
        pid : int, optional
            Process ID
        host : str, optional
            Remote host
        port : int, optional
            Remote port
        start_request_type : StartRequestType, optional
            Explicitly set mode

        Returns
        -------
        StartRequestType
            The determined mode

        Raises
        ------
        AidbError
            If mode cannot be determined
        """
        if start_request_type:
            return start_request_type

        if target:
            return StartRequestType.LAUNCH
        if pid or (host and port):
            return StartRequestType.ATTACH
        msg = (
            "Must provide either 'target' for launch mode, 'pid' for local attach, "
            "or 'host' and 'port' for remote attach"
        )
        raise AidbError(
            msg,
        )


class SessionBuilder(Obj):
    """Builder pattern for creating debug sessions."""

    def __init__(self, ctx: Optional["IContext"] = None):
        """Initialize the SessionBuilder.

        Parameters
        ----------
        ctx : IContext, optional
            Application context
        """
        super().__init__(ctx)
        self.reset()

    def reset(self) -> "SessionBuilder":
        """Reset the builder to initial state.

        Returns
        -------
        SessionBuilder
            Self for chaining
        """
        self._target: str | None = None
        self._language: str | None = None
        self._adapter_host: str = "localhost"
        self._adapter_port: int | None = None
        self._host: str | None = None
        self._port: int | None = None
        self._pid: int | None = None
        self._args: list[str] | None = None
        self._launch_config: BaseLaunchConfig | None = None
        self._launch_config_name: str | None = None
        self._launch_config_workspace: str | Path | None = None
        self._breakpoints: list[AidbBreakpoint] | None = None
        self._project_name: str | None = None
        self._timeout: int = 10000
        self._kwargs: dict[str, Any] = {}
        self._start_request_type: StartRequestType | None = None
        return self

    def _load_and_apply_launch_config(
        self,
        config_name: str,
        workspace_root: str | Path | None = None,
        target: str | None = None,
        override_existing: bool = True,
    ) -> bool:
        """Load launch configuration and apply settings to builder state.

        Parameters
        ----------
        config_name : str
            Name of launch configuration
        workspace_root : str | Path, optional
            Root directory containing .vscode/launch.json
        target : str, optional
            Target for ${file} variable resolution
        override_existing : bool
            If True, override existing target/args; if False, only fill missing values

        Returns
        -------
        bool
            True if configuration was loaded successfully
        """
        manager = LaunchConfigurationManager(workspace_root)
        launch_config = manager.get_configuration(config_name, target=target)

        if not launch_config:
            return False

        adapter_args = launch_config.to_adapter_args()

        # Extract key parameters
        self._language = launch_config.type

        if override_existing or not self._target:
            self._target = adapter_args.pop(
                ADAPTER_ARG_TARGET,
                None,
            ) or adapter_args.pop(ADAPTER_ARG_PROGRAM, None)
        else:
            # Remove but don't use
            adapter_args.pop(ADAPTER_ARG_TARGET, None)
            adapter_args.pop(ADAPTER_ARG_PROGRAM, None)

        if override_existing or not self._args:
            self._args = adapter_args.pop(ADAPTER_ARG_ARGS, None)
        else:
            adapter_args.pop(ADAPTER_ARG_ARGS, None)

        self._launch_config = launch_config

        # Merge remaining adapter args
        self._kwargs.update(adapter_args)
        return True

    def with_launch_config(
        self,
        config_name: str,
        workspace_root: str | Path | None = None,
    ) -> "SessionBuilder":
        """Configure session from launch.json.

        Parameters
        ----------
        config_name : str
            Name of launch configuration
        workspace_root : Union[str, Path], optional
            Root directory containing .vscode/launch.json

        Returns
        -------
        SessionBuilder
            Self for chaining

        Raises
        ------
        AidbError
            If configuration not found
        """
        from aidb.common.errors import VSCodeVariableError

        # Store config name and workspace for lazy resolution later when we have target
        self._launch_config_name = config_name
        self._launch_config_workspace = workspace_root

        # Try to load the config WITHOUT target first (may fail with ${file} error)
        # If it fails, we'll retry later when we have the target
        try:
            self._load_and_apply_launch_config(
                config_name,
                workspace_root,
                target=None,
                override_existing=True,
            )
        except VSCodeVariableError as e:
            # If we get a ${file} error, it's OK - we'll resolve when target is set
            if "${file}" not in str(e) and "${{file}}" not in str(e):
                # Other variable errors should be raised
                raise

        return self

    def with_target(
        self,
        target: str,
        args: list[str] | None = None,
    ) -> "SessionBuilder":
        """Configure for launch mode with target file.

        Parameters
        ----------
        target : str
            Target file to debug
        args : List[str], optional
            Command-line arguments

        Returns
        -------
        SessionBuilder
            Self for chaining
        """
        self._target = target
        self._args = args
        self._start_request_type = StartRequestType.LAUNCH

        # If we have a pending launch config with ${file} variables, resolve it now
        if self._launch_config_name and not self._launch_config:
            import contextlib

            from aidb.common.errors import VSCodeVariableError

            # If still can't resolve ${file}, let it fail later with clear error
            with contextlib.suppress(VSCodeVariableError):
                self._load_and_apply_launch_config(
                    self._launch_config_name,
                    self._launch_config_workspace,
                    target=target,
                    override_existing=False,
                )

        return self

    def with_attach(
        self,
        host: str | None = None,
        port: int | None = None,
        pid: int | None = None,
    ) -> "SessionBuilder":
        """Configure for attach mode.

        Parameters
        ----------
        host : str, optional
            Host of target process (for remote attach)
        port : int, optional
            Port of target process (for remote attach)
        pid : int, optional
            Process ID (for local attach)

        Returns
        -------
        SessionBuilder
            Self for chaining
        """
        self._host = host
        self._port = port
        self._pid = pid
        self._start_request_type = StartRequestType.ATTACH
        return self

    def with_language(self, language: str) -> "SessionBuilder":
        """Set the programming language.

        Parameters
        ----------
        language : str
            Programming language

        Returns
        -------
        SessionBuilder
            Self for chaining
        """
        self._language = language
        return self

    def with_adapter(
        self,
        host: str = "localhost",
        port: int | None = None,
    ) -> "SessionBuilder":
        """Configure debug adapter connection.

        Parameters
        ----------
        host : str
            Adapter host, default "localhost"
        port : int, optional
            Adapter port

        Returns
        -------
        SessionBuilder
            Self for chaining
        """
        self._adapter_host = host
        self._adapter_port = port
        return self

    def with_breakpoints(
        self,
        breakpoints: list[BreakpointSpec] | BreakpointSpec,
        source_file: str | None = None,
    ) -> "SessionBuilder":
        """Add breakpoints to the session.

        Parameters
        ----------
        breakpoints : Union[List[BreakpointSpec], BreakpointSpec]
            Breakpoints conforming to BreakpointSpec schema
        source_file : str, optional
            Fallback source file path when target is not set

        Returns
        -------
        SessionBuilder
            Self for chaining
        """
        self.ctx.debug(
            f"SessionBuilder.with_breakpoints called with "
            f"{len(breakpoints) if isinstance(breakpoints, list) else 1} breakpoint(s)",
        )
        converter = BreakpointConverter(ctx=self.ctx)
        self._breakpoints = converter.convert(
            breakpoints,
            self._target or source_file or "",
            self._language,
        )
        self.ctx.debug(
            f"SessionBuilder.with_breakpoints converted to "
            f"{len(self._breakpoints)} AidbBreakpoint object(s)",
        )
        return self

    def with_project(self, project_name: str) -> "SessionBuilder":
        """Set the project name.

        Parameters
        ----------
        project_name : str
            Project name

        Returns
        -------
        SessionBuilder
            Self for chaining
        """
        self._project_name = project_name
        return self

    def with_timeout(self, timeout: int) -> "SessionBuilder":
        """Set the connection timeout.

        Parameters
        ----------
        timeout : int
            Timeout in milliseconds

        Returns
        -------
        SessionBuilder
            Self for chaining
        """
        self._timeout = timeout
        return self

    def with_kwargs(self, **kwargs: Any) -> "SessionBuilder":
        """Add additional language-specific parameters.

        Parameters
        ----------
        ``**kwargs`` : Any
            Additional parameters

        Returns
        -------
        SessionBuilder
            Self for chaining
        """
        self._kwargs.update(kwargs)
        return self

    def _determine_mode(self) -> StartRequestType:
        """Determine the session mode based on parameters.

        Returns
        -------
        StartRequestType
            The determined mode

        Raises
        ------
        AidbError
            If mode cannot be determined
        """
        return SessionValidator.determine_mode(
            self._target,
            self._pid,
            self._host,
            self._port,
            self._start_request_type,
        )

    def _validate_parameters(self, mode: StartRequestType) -> None:
        """Validate parameters for the given mode.

        Parameters
        ----------
        mode : StartRequestType
            The session mode

        Raises
        ------
        AidbError
            If parameters are invalid for the mode
        """
        SessionValidator.validate_mode_compatibility(
            mode,
            self._target,
            self._pid,
            self._host,
            self._port,
            self._args,
        )

        if mode == StartRequestType.ATTACH:
            SessionValidator.validate_attach_config(self._pid, self._host, self._port)

        if self._launch_config:
            SessionValidator.validate_launch_config(self._launch_config)

    def _infer_language(self) -> str:
        """Infer language from target or raise error.

        Returns
        -------
        str
            The inferred or set language

        Raises
        ------
        AidbError
            If language cannot be determined
        """
        if self._language:
            return self._language

        if self._target:
            from aidb.session.adapter_registry import AdapterRegistry

            registry = AdapterRegistry(self.ctx)
            language = registry.resolve_lang_for_target(self._target)
            if language:
                return language
            msg = f"Could not determine language for target: {self._target}"
            raise AidbError(msg)

        msg = "Language must be specified for attach mode without target"
        raise AidbError(msg)

    def build(self) -> Session:
        """Build the debug session.

        Returns
        -------
        Session
            The created session (not started)

        Raises
        ------
        AidbError
            If parameters are invalid
        """
        # Determine mode and validate
        mode = self._determine_mode()
        self._validate_parameters(mode)

        # Check if we have a pending launch config that couldn't be resolved
        # This happens when launch config has ${file} but no target was provided
        if self._launch_config_name and not self._launch_config:
            from aidb.common.errors import VSCodeVariableError

            msg = (
                f"Launch configuration '{self._launch_config_name}' contains "
                "unresolvable variables (likely '${file}').\n\n"
                "To fix this:\n"
                "1. Add 'target' parameter to your session_start call:\n"
                "   session_start(\n"
                f"       launch_config_name='{self._launch_config_name}',\n"
                "       target='/path/to/file.py'  # <-- Resolves ${file}\n"
                "   )\n\n"
                "2. Or update your launch configuration to use a specific "
                "file path instead"
            )
            raise VSCodeVariableError(msg)

        # Check if target contains unresolved VS Code variables
        if self._target and ("${" in self._target or "${{" in self._target):
            from aidb.common.errors import VSCodeVariableError

            msg = (
                f"Target contains unresolved VS Code variables: {self._target}\n\n"
                "This usually happens when using a launch configuration with ${file} "
                "without providing a 'target' parameter.\n\n"
                "To fix this:\n"
            )
            if self._launch_config_name:
                var_name = self._target.split("$")[1].split("}")[0]
                msg += (
                    f"1. Add 'target' parameter to resolve ${{{var_name}}}:\n"
                    "   session_start(\n"
                    f"       launch_config_name='{self._launch_config_name}',\n"
                    "       target='/path/to/file.py'  # <-- Resolves variable\n"
                    "   )\n\n"
                    "2. Or update your launch configuration to use a specific "
                    "file path"
                )
            else:
                msg += "Provide a valid file path for the 'target' parameter"
            raise VSCodeVariableError(msg)

        # Infer language if needed
        language = self._infer_language()

        # Prepare session kwargs
        session_kwargs = dict(self._kwargs)
        session_kwargs["start_request_type"] = mode

        if self._project_name:
            session_kwargs["project_name"] = self._project_name

        # Log what we're about to pass to Session
        self.ctx.debug(
            f"SessionBuilder.build(): Creating Session with "
            f"{len(self._breakpoints) if self._breakpoints else 0} breakpoint(s) "
            f"for language={language}",
        )

        # Create session - target can be None for attach mode
        session = Session(
            ctx=self.ctx,
            target=self._target or "",
            language=language,
            breakpoints=self._breakpoints,
            adapter_host=self._adapter_host,
            adapter_port=self._adapter_port,
            target_host=self._host or "localhost",
            target_port=self._port,
            args=self._args if mode == StartRequestType.LAUNCH else None,
            **session_kwargs,
        )

        session.started = False

        # Store attach parameters if needed
        if mode == StartRequestType.ATTACH:
            session._attach_params = {
                "host": self._host,
                "port": self._port,
                "pid": self._pid,
                "timeout": self._timeout,
                "project_name": self._project_name,
            }

        # Store launch config if available
        if self._launch_config:
            from dataclasses import asdict

            session._launch_config = asdict(self._launch_config)

        self.ctx.debug(f"Built session for {language} ({mode.value} mode)")

        return session
