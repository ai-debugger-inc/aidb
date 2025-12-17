"""Java debug adapter - refactored to use component architecture."""

from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from aidb.common.constants import (
    DEFAULT_ADAPTER_HOST,
    DEFAULT_JAVA_DEBUG_PORT,
    DEFAULT_WAIT_TIMEOUT_S,
    SECONDS_PER_DAY,
)
from aidb.common.errors import AidbError
from aidb_common.env import reader

from ...base import DebugAdapter
from ...base.hooks import LifecycleHook
from ...base.target_resolver import TargetResolver
from .compilation import JavaCompilationManager
from .config import JavaAdapterConfig
from .target_resolver import JavaTargetResolver
from .tooling import JavaBuildSystemDetector, JavaClasspathBuilder, JavaToolchain

if TYPE_CHECKING:
    import asyncio

    from aidb.adapters.base.source_path_resolver import SourcePathResolver
    from aidb.interfaces import ISession

    from .lsp import JavaLSPDAPBridge


class JavaAdapter(DebugAdapter):
    """Java debug adapter using component architecture.

    This adapter interfaces with Microsoft's java-debug-server to provide debugging
    capabilities for Java applications.
    """

    # -----------------------
    # Public API / Lifecycle
    # -----------------------

    def _apply_config_overrides(
        self,
        config: JavaAdapterConfig,
        jdk_home: str | None,
        classpath: list[str] | None,
        module_path: list[str] | None,
        vmargs: list[str] | None,
        project_name: str | None,
        jdtls_workspace: str | None,
        auto_compile: bool | None,
    ) -> None:
        """Apply parameter overrides to the configuration.

        Parameters
        ----------
        config : JavaAdapterConfig
            Configuration object to update
        jdk_home : str | None
            Path to JDK installation
        classpath : list[str] | None
            Additional classpath entries
        module_path : list[str] | None
            Module path entries (Java 9+)
        vmargs : list[str] | None
            JVM arguments
        project_name : str | None
            Project name for evaluation context
        jdtls_workspace : str | None
            Workspace directory for JDT LS
        auto_compile : bool | None
            Whether to auto-compile .java files
        """
        if jdk_home:
            config.jdk_home = jdk_home
        if classpath:
            config.classpath.extend(classpath)
        if module_path:
            config.module_path.extend(module_path)
        if vmargs:
            config.vmargs.extend(vmargs)
        if project_name:
            config.projectName = project_name
        if jdtls_workspace:
            config.jdtls_workspace = jdtls_workspace
        if auto_compile is not None:
            config.auto_compile = auto_compile

    def _initialize_java_state(
        self,
        main_class: str | None,
        classpath: list[str] | None,
    ) -> None:
        """Initialize Java-specific state variables.

        Parameters
        ----------
        main_class : str | None
            Main class to debug
        classpath : list[str] | None
            Classpath entries
        """
        self.main_class = main_class
        self.classpath = classpath or []
        self.target: str | None = None
        self._java_debug_server_process = None
        self._jdtls_process = None
        self._temp_compile_dir: str | None = None
        self._jdtls_workspace_dir: Path | None = None
        self._lsp_dap_bridge: JavaLSPDAPBridge | None = None
        self._compilation_manager: JavaCompilationManager | None = None
        self._dummy_process: asyncio.subprocess.Process | None = None  # type: ignore[name-defined]
        self._target_cwd: str | None = None
        self._launch_config: dict[str, Any] | None = (
            None  # Stored during launch for DAP request
        )

        # Initialize tooling utilities
        self._toolchain = JavaToolchain(jdk_home=self.config.jdk_home)
        self._classpath_builder = JavaClasspathBuilder(
            base_classpath=self.config.classpath,
        )

    def __init__(
        self,
        session: "ISession",
        ctx=None,
        adapter_host=DEFAULT_ADAPTER_HOST,
        adapter_port=None,
        target_host=DEFAULT_ADAPTER_HOST,
        target_port=None,
        config: JavaAdapterConfig | None = None,
        # Java-specific parameters
        main_class: str | None = None,
        classpath: list[str] | None = None,
        module_path: list[str] | None = None,
        vmargs: list[str] | None = None,
        jdk_home: str | None = None,
        project_name: str | None = None,
        # JDT LS parameters
        jdtls_workspace: str | None = None,
        auto_compile: bool | None = None,
        **kwargs,
    ):
        """Initialize Java debug adapter using JDT LS.

        Parameters
        ----------
        session : Session
            The debug session this adapter is attached to
        ctx : AidbContext, optional
            Application context for logging and configuration
        adapter_host : str
            Host where java-debug-server will listen
        adapter_port : int, optional
            Port for java-debug-server (will auto-assign if not provided)
        target_host : str
            Not used for Java (kept for API compatibility)
        target_port : int, optional
            Not used for Java (kept for API compatibility)
        config : JavaAdapterConfig, optional
            Configuration object for the adapter
        main_class : str, optional
            Main class to debug (for launch mode)
        classpath : List[str], optional
            Additional classpath entries
        module_path : List[str], optional
            Module path entries (Java 9+)
        vmargs : List[str], optional
            JVM arguments
        jdk_home : str, optional
            Path to JDK installation
        project_name : str, optional
            Project name for evaluation context
        jdtls_workspace : str, optional
            Workspace directory for JDT LS
        auto_compile : bool, optional
            Whether to auto-compile .java files
        """
        # Initialize config first
        if config is None:
            config = JavaAdapterConfig()

        # Apply overrides
        self._apply_config_overrides(
            config,
            jdk_home,
            classpath,
            module_path,
            vmargs,
            project_name,
            jdtls_workspace,
            auto_compile,
        )

        # Initialize base adapter
        super().__init__(
            session=session,
            ctx=ctx,
            adapter_host=adapter_host,
            adapter_port=adapter_port,
            target_host=target_host,
            target_port=target_port,
            config=config,
            **kwargs,
        )

        # At this point, config is guaranteed to be non-None due to the check above
        self.config: JavaAdapterConfig = config

        # Initialize Java-specific state
        self._initialize_java_state(main_class, classpath)

        # Register Java-specific hooks
        self._register_java_hooks()

    def _create_target_resolver(self) -> TargetResolver:
        """Create Java-specific target resolver.

        Returns
        -------
        TargetResolver
            JavaTargetResolver instance for .java/.class/.jar detection
        """
        return JavaTargetResolver(adapter=self, ctx=self.ctx)

    def _create_source_path_resolver(self) -> "SourcePathResolver":
        """Create Java-specific source path resolver.

        Returns
        -------
        SourcePathResolver
            JavaSourcePathResolver instance for JAR path resolution
        """
        from .source_path_resolver import JavaSourcePathResolver

        return JavaSourcePathResolver(adapter=self, ctx=self.ctx)

    def _build_classpath(self, target: str) -> list[str]:
        """Build classpath for the debug session.

        Parameters
        ----------
        target : str
            The target file being debugged

        Returns
        -------
        list[str]
            Classpath entries
        """
        # Delegate to the classpath builder
        return self._classpath_builder.build_classpath(
            target=target,
            additional_entries=self.classpath,
            temp_compile_dir=self._temp_compile_dir,
        )

    async def launch(  # noqa: C901
        self,
        target: str,
        port: int | None = None,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
        launch_config_name: str | None = None,  # noqa: ARG002
        workspace_root: str | None = None,
    ) -> tuple["asyncio.subprocess.Process", int]:
        """Launch the Java debug adapter using JDT LS.

        This method sets up the LSP-DAP bridge for Java debugging.

        Parameters
        ----------
        target : str
            The Java file, class file, or JAR to debug
        port : int, optional
            Specific port to use, if None will find available
        args : List[str], optional
            Additional arguments for the debug adapter
        env : dict[str, str], optional
            Environment variables for the target process
        cwd : str, optional
            Working directory for the target process
        workspace_root : str, optional
            Root directory for resolving relative paths

        Returns
        -------
        Tuple[asyncio.subprocess.Process, int]
            The debug adapter process and the port it's listening on
        """
        # Store original source file before compilation
        original_source = target if target.endswith(".java") else None

        # Compile if needed
        target = await self._compile_if_needed(target)

        # Store target for later use
        self.target = target

        context = await self.execute_hook(
            LifecycleHook.PRE_LAUNCH,
            data={
                "target": target,
                "port": port,
                "args": args,
                "env": env or {},
                "cwd": cwd,
            },
        )

        if context.cancelled:
            msg = context.result if context.result else "Launch cancelled by hook"
            raise RuntimeError(msg)

        # Bridge MUST exist - if not, initialization failed
        if not self._lsp_dap_bridge:
            msg = "JDT LS bridge not available - cannot debug Java programs"
            raise AidbError(msg)

        if port is None:
            port = await self._port_manager.acquire(
                fallback_start=DEFAULT_JAVA_DEBUG_PORT,
            )

        # Start LSP-DAP bridge and get the actual DAP port
        try:
            # Detect build root (Maven/Gradle) using fallback chain
            build_root = JavaBuildSystemDetector.detect_build_root_with_fallbacks(
                workspace_root,
                cwd,
                target,
            )

            # Build workspace folders for JDT LS initialization
            workspace_folders: list[tuple[Path, str]] | None = None
            if build_root:
                project_name = self.config.projectName or build_root.name
                workspace_folders = [(build_root, project_name)]
                self.ctx.info(
                    f"Detected Maven/Gradle project: {build_root} "
                    f"(name: {project_name})",
                )

            # Determine project root using toolchain helper
            # This must be done before the if-block so it's available for both
            # pooled and non-pooled paths
            project_root = JavaToolchain.resolve_project_root(target, cwd)
            if project_root:
                self.ctx.debug(f"Resolved project root: {project_root}")

            # Start or reuse the LSP-DAP bridge
            await self._ensure_bridge_started(
                build_root=build_root,
                project_root=project_root,
                workspace_root=workspace_root,
                cwd=cwd,
                workspace_folders=workspace_folders,
            )

            # Determine main class
            main_class = self._get_main_class(target)

            # Determine project name and detect if this is a Maven/Gradle project
            # For Maven/Gradle projects, JDT LS uses artifactId from pom.xml,
            # NOT the directory name. Use configured project name or default.
            project_name = (
                self.config.projectName or JavaAdapterConfig.DEFAULT_PROJECT_NAME
            )

            # Resolve target directory for Maven/Gradle detection
            target_dir = JavaBuildSystemDetector.resolve_target_directory(
                target,
                build_root,
                cwd,
            )
            is_maven_gradle_project = JavaBuildSystemDetector.is_maven_gradle_project(
                target_dir,
            )

            # Resolve classpath based on project type
            if is_maven_gradle_project:
                classpath = await self._resolve_maven_gradle_classpath(
                    main_class=main_class,
                    project_name=project_name,
                    original_source=original_source,
                    target_dir=target_dir,
                )
            else:
                # Standalone .java file - use simple classpath (no JDT LS resolution)
                self.ctx.debug("Standalone .java file - using simple classpath")
                classpath = self._build_classpath(target)

            # Start debug session through JDT LS and get DAP port
            self.ctx.info("Starting debug session through JDT LS...")

            dap_port = await self._lsp_dap_bridge.start_debug_session(
                main_class=main_class,
                classpath=classpath,
                # Pass original .java file, not compiled .class
                target=original_source,
                project_name=project_name,
                vmargs=self.config.vmargs,
                args=args or [],
                # Skip reset/file opening for Maven/Gradle (already done above)
                skip_file_opening=is_maven_gradle_project,
            )

            # Update adapter port
            self.adapter_port = dap_port

            # Add test-classes to classpath for JUnit tests
            classpath = JavaClasspathBuilder.add_test_classes(
                classpath,
                project_root,
                main_class,
            )

            # Store launch configuration
            self._launch_config = self._build_launch_config(
                main_class=main_class,
                classpath=classpath,
                project_name=project_name,
                args=args,
                env=env,
                cwd=cwd,
            )

            # Create dummy process for base adapter compatibility
            self._dummy_process = await self._create_dummy_process()
            proc = self._dummy_process

            self.ctx.info(f"Java debug session ready on DAP port {dap_port}")

            context = await self.execute_hook(
                LifecycleHook.POST_LAUNCH,
                data={"process": proc, "port": dap_port},
            )

            return proc, dap_port

        except Exception as e:
            self.ctx.error(f"Failed to set up LSP-DAP bridge: {e}")
            msg = f"Failed to set up LSP-DAP bridge: {e}"
            raise AidbError(msg) from e

    async def attach_remote(
        self,
        host: str,
        port: int,
        timeout: int = 10000,
        project_name: str | None = None,
    ) -> tuple[Optional["asyncio.subprocess.Process"], int]:
        """Attach to a remote JVM process via JDT LS.

        This method delegates to the LSP-DAP bridge to handle remote attachment
        via JDWP (Java Debug Wire Protocol).

        Parameters
        ----------
        host : str
            The hostname or IP address of the remote JVM
        port : int
            The JDWP port of the remote JVM
        timeout : int
            Connection timeout in milliseconds (default: 10000)
        project_name : str, optional
            Project name for evaluation context

        Returns
        -------
        Tuple[Optional[asyncio.subprocess.Process], int]
            None for process (no process for attach) and the DAP port for
            connection

        Raises
        ------
        AidbError
            If the bridge is not available or connection fails
        """
        # Ensure LSP-DAP bridge is initialized for remote attach
        # (normally done in PRE_LAUNCH hook, but attach skips launch)
        if not self._lsp_dap_bridge:
            self.ctx.info("Initializing LSP-DAP bridge for remote attach...")
            from .hooks import JDTLSSetupHooks

            setup_hooks = JDTLSSetupHooks(self)
            await setup_hooks.ensure_bridge_initialized()

            # Start the bridge (launch JDT LS) - not done by ensure_bridge_initialized
            if self._lsp_dap_bridge:
                await self._lsp_dap_bridge.start()

        if not self._lsp_dap_bridge:
            msg = "JDT LS bridge not available. Remote attach requires JDT LS."
            raise AidbError(msg)

        self.ctx.info(f"Attaching to remote JVM at {host}:{port}")

        # Use the bridge to attach to remote JVM
        dap_port = await self._lsp_dap_bridge.attach_to_remote(
            host=host,
            port=port,
            project_name=project_name,
            timeout=timeout,
        )

        # Store attach config for DAP attach request (used by get_launch_configuration).
        # The java-debug adapter expects hostName and port in the attach request.
        self._launch_config = {
            "type": "java",
            "request": "attach",
            "hostName": host,
            "port": port,
            "timeout": timeout,
            "projectName": project_name or self.config.DEFAULT_PROJECT_NAME,
        }
        self.ctx.debug(f"Stored attach config: {self._launch_config}")

        # Return dummy process (None) and the DAP port. The first element is
        # expected by the API but not used for attach
        return None, dap_port

    def get_launch_configuration(self) -> dict[str, Any] | None:
        """Get launch configuration for DAP launch request.

        Java adapter uses JDT LS bridge to set up the DAP server, but the server
        still expects a standard DAP launch request with the resolved configuration.

        Returns
        -------
        dict[str, Any] | None
            Launch configuration with mainClass and classpath resolved by JDT LS,
            or None if launch() hasn't been called yet
        """
        if self._launch_config:
            self.ctx.debug(
                f"Returning stored launch config: {list(self._launch_config.keys())}",
            )
        return self._launch_config

    async def stop(self) -> None:
        """Stop the Java adapter and clean up debuggee processes.

        java-debug does not reliably terminate debuggees when DisconnectRequest is sent
        (due to attach detection bug), so we use the LSP bridge to clean up child
        processes.
        """
        # Send DisconnectRequest (best effort, may not work due to java-debug bug)
        await super().stop()

        # Clean up debuggee processes via LSP bridge
        if self._lsp_dap_bridge and self._lsp_dap_bridge.is_pooled():
            # For pooled bridges, just clean up children (debuggees)
            # The bridge itself stays alive for reuse
            await self._lsp_dap_bridge.cleanup_children()
            self.ctx.debug("Cleaned up debuggee processes from pooled bridge")
            # Non-pooled bridges clean up their children in their stop() method

        self.cleanup()

    def cleanup(self):
        """Clean up adapter resources."""
        super().cleanup()

    @property
    def connected(self) -> bool:
        """Check if the Java debug adapter is connected via JDT LS bridge.

        Returns
        -------
        bool
            `True` if adapter is connected, `False` otherwise
        """
        if self._lsp_dap_bridge:
            # Check if the JDT LS process is still running
            return bool(
                (
                    hasattr(self._lsp_dap_bridge, "process")
                    and self._lsp_dap_bridge.process
                )
                and self._lsp_dap_bridge.process.returncode is None,
            )
        return False

    @property
    def should_attempt_dap_reconnection_fallback(self) -> bool:
        """Check if DAP reconnection fallback should be attempted.

        This is only needed when using a pooled JDT LS bridge, as pooled
        bridges can experience race conditions during initialization.

        Returns
        -------
        bool
            True if reconnection fallback should be attempted
        """
        if not self.config.enable_dap_reconnection_fallback:
            return False

        # Only needed when actually using a pooled bridge
        if hasattr(self, "_lsp_dap_bridge") and self._lsp_dap_bridge:
            return self._lsp_dap_bridge.is_pooled()

        return False

    @property
    def should_send_disconnect_request(self) -> bool:
        """Skip disconnect for pooled bridges to avoid java-debug freeze.

        Sending DisconnectRequest to java-debug servers on pooled bridges
        causes the server to freeze/deadlock, as DAP disconnect has shutdown
        semantics. For pooled bridges, we skip the request and only close
        the transport.

        Returns
        -------
        bool
            False if using pooled bridge (skip disconnect), True otherwise
        """
        if self._lsp_dap_bridge:
            return not self._lsp_dap_bridge.is_pooled()
        return True

    # ----------------------
    # Hook Registration
    # ----------------------

    def _register_java_hooks(self) -> None:
        """Register Java-specific lifecycle hooks."""
        from .hooks import (
            JavaEnvironmentValidator,
            JDTLSCleanupHooks,
            JDTLSReadinessHooks,
            JDTLSSetupHooks,
        )

        # Instantiate hook handlers
        env_validator = JavaEnvironmentValidator(self)
        jdtls_setup = JDTLSSetupHooks(self)
        jdtls_ready = JDTLSReadinessHooks(self)
        jdtls_cleanup = JDTLSCleanupHooks(self)

        # Pre-launch hooks (high priority = run first)
        self.register_hook(
            LifecycleHook.PRE_LAUNCH,
            env_validator.validate_environment,
            priority=90,  # Very high priority - validate environment first
        )
        self.register_hook(
            LifecycleHook.PRE_LAUNCH,
            env_validator.validate_target,
            priority=85,  # High priority - validate target early
        )
        self.register_hook(
            LifecycleHook.PRE_LAUNCH,
            jdtls_setup.prepare_workspace,
            priority=80,  # Set up workspace before bridge
        )
        self.register_hook(
            LifecycleHook.PRE_LAUNCH,
            jdtls_setup.initialize_bridge,
            priority=70,  # Initialize bridge before launch
        )

        # Post-launch hooks (low priority = run later)
        self.register_hook(
            LifecycleHook.POST_LAUNCH,
            jdtls_ready.wait_for_ready,
            priority=20,  # Wait for JDT LS after launch
        )
        self.register_hook(
            LifecycleHook.POST_LAUNCH,
            jdtls_ready.enable_trace_logging,
            priority=15,  # Enable trace after JDT LS is ready
        )

        # Post-stop hooks
        self.register_hook(
            LifecycleHook.POST_STOP,
            jdtls_cleanup.collect_logs,
            priority=10,  # Collect logs after stop
        )
        self.register_hook(
            LifecycleHook.POST_STOP,
            jdtls_cleanup.cleanup_bridge,
            priority=20,  # Clean up bridge first
        )
        self.register_hook(
            LifecycleHook.POST_STOP,
            jdtls_cleanup.cleanup_workspace,
            priority=10,  # Clean up workspace last
        )

    # ----------------------
    # Process & Environment
    # ----------------------

    def _build_launch_config(
        self,
        main_class: str,
        classpath: list[str],
        project_name: str,
        args: list[str] | None,
        env: dict[str, str] | None,
        cwd: str | None,
    ) -> dict[str, Any]:
        """Build launch configuration for DAP request.

        Parameters
        ----------
        main_class : str
            Main class name
        classpath : list[str]
            Classpath entries
        project_name : str
            Project name
        args : list[str] | None
            Command line arguments
        env : dict[str, str] | None
            Environment variables
        cwd : str | None
            Working directory

        Returns
        -------
        dict[str, Any]
            Launch configuration dictionary
        """
        launch_config: dict[str, Any] = {
            "mainClass": main_class,
            "classPaths": classpath,
            "projectName": project_name,
            "vmArgs": " ".join(self.config.vmargs) if self.config.vmargs else "",
            "args": " ".join(args) if args else "",
        }
        if env:
            launch_config["env"] = env
        if cwd:
            launch_config["cwd"] = cwd
        return launch_config

    async def _create_dummy_process(self) -> "asyncio.subprocess.Process":
        """Create placeholder process for base adapter compatibility.

        Java debugging through JDT LS doesn't expose the actual Java process,
        so we create a dummy process that sleeps to satisfy the base adapter's
        process requirement.

        Returns
        -------
        asyncio.subprocess.Process
            A dummy process that sleeps
        """
        import asyncio
        import sys

        python_code = f"import time; time.sleep({SECONDS_PER_DAY})"
        return await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            python_code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    async def _resolve_maven_gradle_classpath(
        self,
        main_class: str,
        project_name: str,
        original_source: str | None,
        target_dir: Path,
    ) -> list[str]:
        """Resolve classpath for Maven/Gradle projects via JDT LS.

        Steps:
        1. Reset LSP session state (skip for pooled)
        2. Open target file in JDT LS
        3. Wait for compilation diagnostics
        4. Resolve classpath via JDT LS
        5. Flatten and augment classpath

        Parameters
        ----------
        main_class : str
            Main class name
        project_name : str
            Project name for JDT LS
        original_source : str | None
            Original .java source file path
        target_dir : Path
            Target directory for Maven/Gradle project

        Returns
        -------
        list[str]
            Resolved and flattened classpath entries
        """
        self.ctx.debug(f"Detected Maven/Gradle project at {target_dir}")

        # Bridge must exist at this point
        if self._lsp_dap_bridge is None:
            msg = "LSP-DAP bridge not initialized"
            raise AidbError(msg)

        # Reset LSP session state before file opening
        # (skip for pooled bridges - they maintain state across sessions)
        if self._lsp_dap_bridge.lsp_client:
            if not self._lsp_dap_bridge.is_pooled():
                self.ctx.debug(
                    "Resetting LSP session state before file opening",
                )
                await self._lsp_dap_bridge.lsp_client.reset_session_state()
            else:
                self.ctx.debug(
                    "Pooled bridge - skipping LSP session reset "
                    "before resolveClasspath",
                )

            # Open the target file in JDT LS
            if original_source and original_source.endswith(".java"):
                self.ctx.info(
                    f"Opening target file in JDT LS: {original_source}",
                )
                await self._lsp_dap_bridge.lsp_client.open_file(original_source)

                # Wait for JDT LS to complete compilation
                compilation_complete = (
                    await self._lsp_dap_bridge.lsp_client.wait_for_diagnostics(
                        file_path=original_source,
                        timeout=DEFAULT_WAIT_TIMEOUT_S,
                    )
                )

                if not compilation_complete:
                    self.ctx.warning(
                        f"JDT LS compilation timeout for {original_source}",
                    )
                else:
                    self.ctx.debug("JDT LS compilation complete")

        # Resolve classpath through JDT LS
        try:
            classpath = await self._lsp_dap_bridge.resolve_classpath(
                main_class=main_class,
                project_name=project_name,
            )
            if not classpath:
                msg = f"Failed to resolve classpath for {main_class}"
                raise AidbError(msg)
        except Exception as e:
            msg = f"Failed to resolve classpath through JDT LS: {e}"
            raise AidbError(msg) from e

        # Flatten classpath (JDT LS returns nested lists)
        classpath = JavaClasspathBuilder.flatten_classpath(classpath)

        # Add target/classes for Maven/Gradle projects
        classpath = JavaClasspathBuilder.add_target_classes(classpath, target_dir)
        if classpath and str(target_dir / "target" / "classes") == classpath[0]:
            self.ctx.debug(
                f"Added target/classes to classpath: {classpath[0]}",
            )

        return classpath

    async def _ensure_bridge_started(
        self,
        build_root: Path | None,
        project_root: Path | None,
        workspace_root: str | None,
        cwd: str | None,
        workspace_folders: list[tuple[Path, str]] | None,
    ) -> None:
        """Ensure LSP-DAP bridge is started based on pool status.

        Handles three cases:
        1. Pooled bridge already running -> register workspace folders
        2. No bridge process -> try production pool, then standalone
        3. Non-pooled with process -> log warning (unexpected)

        Parameters
        ----------
        build_root : Path | None
            Detected Maven/Gradle build root
        project_root : Path | None
            Project root directory
        workspace_root : str | None
            Workspace root from launch config
        cwd : str | None
            Current working directory
        workspace_folders : list[tuple[Path, str]] | None
            Workspace folders for JDT LS
        """
        # Bridge must exist at this point
        if self._lsp_dap_bridge is None:
            msg = "LSP-DAP bridge not initialized"
            raise AidbError(msg)

        # Determine bridge startup strategy based on pool status
        # Use is_pooled() as single source of truth (not process state)
        if (
            self._lsp_dap_bridge.is_pooled()
            and self._lsp_dap_bridge.process is not None
        ):
            # Reusing pooled bridge that's already started
            self.ctx.debug("Using already-started pooled JDT LS bridge")

            # Register workspace folders with pooled bridge
            if workspace_folders:
                self.ctx.info(
                    f"Registering {len(workspace_folders)} workspace "
                    f"folder(s) with pooled JDT LS bridge",
                )
                await self._lsp_dap_bridge.register_workspace_folders(
                    workspace_folders,
                )
        elif self._lsp_dap_bridge.process is None:
            # Need to start bridge (new pooled allocation or standalone)
            # Try production per-project pool first
            # (test pool already tried in initialize_bridge hook)
            pool_used = await self._try_production_pool(
                build_root=build_root,
                project_root=project_root,
                workspace_root=workspace_root,
                cwd=cwd,
                workspace_folders=workspace_folders,
            )

            if not pool_used:
                # Start JDT LS with java-debug plugin (standalone)
                self.ctx.info(
                    "Starting Eclipse JDT LS with java-debug plugin...",
                )
                await self._lsp_dap_bridge.start(
                    project_root,
                    session_id=self.session.id,
                    workspace_folders=workspace_folders,
                )
        else:
            # Non-pooled bridge with existing process - unexpected state
            self.ctx.warning(
                "Bridge has process but is not pooled - unexpected state",
            )

    async def _try_production_pool(
        self,
        build_root: Path | None,
        project_root: Path | None,
        workspace_root: str | None,
        cwd: str | None,
        workspace_folders: list[tuple[Path, str]] | None,
    ) -> bool:
        """Try to use production per-project pool for bridge.

        Parameters
        ----------
        build_root : Path | None
            Detected Maven/Gradle build root
        project_root : Path | None
            Project root directory
        workspace_root : str | None
            Workspace root from launch config
        cwd : str | None
            Current working directory
        workspace_folders : list[tuple[Path, str]] | None
            Workspace folders for JDT LS

        Returns
        -------
        bool
            True if production pool was used, False otherwise
        """
        use_pool = reader.read_bool("AIDB_JAVA_LSP_POOL", True)
        if not use_pool:
            return False

        # Need existing bridge configuration for pooling
        if self._lsp_dap_bridge is None:
            return False

        try:
            from aidb.adapters.lang.java.jdtls_project_pool import (
                get_jdtls_project_pool,
            )

            pool = await get_jdtls_project_pool(ctx=self.ctx)

            # Prefer detected build_root for pooling key,
            # else project_root, else workspace_root, else cwd
            project_path = (
                build_root
                or project_root
                or (Path(workspace_root) if workspace_root else None)
                or (Path(cwd) if cwd else Path())
            )

            proj_name = (
                workspace_folders[0][1]
                if workspace_folders
                else (project_path.name or JavaAdapterConfig.DEFAULT_PROJECT_NAME)
            )

            bridge = await pool.get_or_start_bridge(
                project_path=project_path,
                project_name=proj_name,
                jdtls_path=self._lsp_dap_bridge.jdtls_path,
                java_debug_jar=self._lsp_dap_bridge.java_debug_jar,
                java_command=self._lsp_dap_bridge.java_command,
                workspace_folders=workspace_folders,
            )
            self._lsp_dap_bridge = bridge
            self.ctx.debug("Using per-project pooled JDT LS bridge")
            return True

        except Exception as e:
            self.ctx.warning(
                f"Failed to get production pool: {e}, falling back to standalone",
            )
            return False

    def _get_process_name_pattern(self) -> str:
        """Get the process name pattern for Java debug server.

        Returns
        -------
        str
            Process name pattern for java-debug-server
        """
        return "java.*ProtocolServer"

    def _add_adapter_specific_vars(self, env: dict[str, str]) -> dict[str, str]:
        """Add Java-specific environment variables.

        Parameters
        ----------
        env : Dict[str, str]
            Current environment variables

        Returns
        -------
        Dict[str, str]
            Updated environment with Java-specific variables
        """
        # Add JAVA_HOME if configured
        if self.config.jdk_home:
            env["JAVA_HOME"] = self.config.jdk_home

        return env

    async def _build_launch_command(
        self,
        target: str,  # noqa: ARG002
        adapter_host: str,  # noqa: ARG002
        adapter_port: int,  # noqa: ARG002
        args: list[str] | None = None,  # noqa: ARG002
    ) -> list[str]:
        """Build launch command for Java adapter.

        Note: Java uses JDT.LS attach mode, not direct launch. This method
        returns an empty list as Java debugging is handled via attach to
        the JDT.LS language server process. See the JDT LS bridge methods
        for the actual connection logic.

        Returns
        -------
        list[str]
            Empty list - Java uses attach mode via JDT.LS, not direct launch
        """
        # Java uses attach mode via JDT.LS, not direct launch
        return []

    # ---------------------------------
    # Java Tooling & Classpath Helpers
    # ---------------------------------

    async def _get_java_executable(self) -> str:
        """Get the Java executable path.

        Returns
        -------
        str
            Path to java executable

        Raises
        ------
        AidbError
            If Java is not found
        """
        # Delegate to the toolchain
        return await self._toolchain.get_java_executable()

    def _get_javac_executable(self) -> str:
        """Get the javac compiler executable path."""
        # Delegate to the toolchain
        return self._toolchain.get_javac_executable()

    async def _compile_if_needed(self, target: str) -> str:
        """Compile Java source file if needed using the compilation manager.

        Parameters
        ----------
        target : str
            Path to target file

        Returns
        -------
        str
            Path to executable (compiled .class file or original)
        """
        if not self._compilation_manager:
            self._compilation_manager = JavaCompilationManager(self, self.ctx)
        return await self._compilation_manager.compile_if_needed(target)

    def _get_main_class(self, target: str) -> str:
        """Extract main class name from target.

        Parameters
        ----------
        target : str
            Path to .class file or .jar file

        Returns
        -------
        str
            Fully qualified main class name
        """
        # Delegate to the classpath builder
        return self._classpath_builder.extract_main_class(
            target=target,
            explicit_main_class=self.main_class,
        )
