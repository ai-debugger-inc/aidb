"""JDT LS process manager for process lifecycle.

This module manages the Eclipse JDT Language Server process lifecycle, including
launching, monitoring, and cleanup operations.
"""

import asyncio
import os
import platform
import shlex
import shutil
import tempfile
import time
from pathlib import Path

from aidb.common.constants import MEDIUM_SLEEP_S, PROCESS_TERMINATE_TIMEOUT_S
from aidb.common.errors import AidbError
from aidb.patterns.base import Obj
from aidb.resources.process_tags import ProcessTags, ProcessType
from aidb_common.constants import Language


class JDTLSProcessManager(Obj):
    """Manager for JDT LS process lifecycle.

    Handles:
    - JDT LS process launching with proper command arguments
    - Process monitoring and health checking
    - Child process cleanup (debuggee processes)
    - Graceful and forced shutdown
    """

    def __init__(
        self,
        jdtls_path: Path,
        java_command: str = "java",
        ctx=None,
    ):
        """Initialize the JDT LS process manager.

        Parameters
        ----------
        jdtls_path : Path
            Path to the Eclipse JDT LS installation directory
        java_command : str
            Java executable command
        ctx : optional
            Context for logging
        """
        super().__init__(ctx)
        self.jdtls_path = jdtls_path
        self.java_command = java_command
        self.process: asyncio.subprocess.Process | None = None
        self.workspace: Path | None = None

    async def start_jdtls(
        self,
        workspace: Path,
        java_debug_jar: Path,
        session_id: str | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> asyncio.subprocess.Process:
        """Start the JDT LS process.

        Parameters
        ----------
        workspace : Path
            The workspace directory for JDT LS
        java_debug_jar : Path
            Path to the java-debug-server plugin JAR
        session_id : Optional[str]
            Session ID for process tagging
        extra_env : Optional[Dict[str, str]]
            Additional environment variables

        Returns
        -------
        asyncio.subprocess.Process
            The JDT LS process

        Raises
        ------
        AidbError
            If JDT LS fails to start
        """
        self.workspace = workspace

        # Build JDT LS command
        command = self._build_jdtls_command(workspace, java_debug_jar)

        self.ctx.info(f"Starting Eclipse JDT LS with command: {' '.join(command)}")

        # Optional environment diagnostics for CI-only investigations
        if os.environ.get("AIDB_JAVA_DIAG", "0") == "1":
            try:
                import resource

                uname = platform.uname()
                nofile = resource.getrlimit(resource.RLIMIT_NOFILE)
                diag_info = (
                    f"[DIAG] Kernel={uname.system} {uname.release} | "
                    f"Machine={uname.machine} | NOFILE={nofile}"
                )
                self.ctx.info(diag_info)
                # cgroups v2 (unified) paths
                cg_root = Path("/sys/fs/cgroup")
                mem_max = cg_root / "memory.max"
                cpu_max = cg_root / "cpu.max"
                for p in (mem_max, cpu_max):
                    try:
                        with p.open(encoding="utf-8") as fh:  # noqa: ASYNC230
                            val = fh.read().strip()
                        self.ctx.info(f"[DIAG] cgroup {p.name}={val}")
                    except Exception:
                        pass
                # Shared memory size
                try:
                    st = os.statvfs("/dev/shm")
                    shm_mb = (st.f_bsize * st.f_blocks) / (1024 * 1024)
                    self.ctx.info(f"[DIAG] /dev/shm size={shm_mb:.0f}MB")
                except Exception:
                    pass
            except Exception:
                # Best-effort diagnostics only
                pass

        # Prepare environment with AIDB process tags for orphan detection
        lsp_env = os.environ.copy()
        if session_id:
            lsp_env.update(
                {
                    ProcessTags.OWNER: ProcessTags.OWNER_VALUE,
                    ProcessTags.SESSION_ID: session_id,
                    ProcessTags.PROCESS_TYPE: ProcessType.LSP_SERVER,
                    ProcessTags.LANGUAGE: Language.JAVA.value,
                    ProcessTags.START_TIME: str(int(time.time())),
                },
            )
            self.ctx.debug(f"Tagged LSP server with session_id={session_id}")

        # Apply any additional environment variables
        if extra_env:
            lsp_env.update(extra_env)
            self.ctx.debug(f"Applied extra environment variables: {extra_env}")

        # Start JDT LS process
        try:
            self.process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=lsp_env,
            )
        except Exception as e:
            msg = f"Failed to start Eclipse JDT LS: {e}"
            raise AidbError(msg) from e

        return self.process

    async def stop_jdtls(self, *, force: bool = False) -> None:  # noqa: C901
        """Stop the JDT LS process.

        Parameters
        ----------
        force : bool, optional
            If True, force kill immediately without graceful shutdown
        """
        # Kill all child processes first (debuggees) before stopping JDT LS
        if self.process and self.process.returncode is None:
            try:
                import psutil

                parent = psutil.Process(self.process.pid)
                children = parent.children(recursive=True)

                if children:
                    self.ctx.debug(
                        f"Terminating {len(children)} child process(es) of JDT LS",
                    )

                    # Terminate children gracefully first
                    for child in children:
                        try:
                            self.ctx.debug(
                                f"Terminating child process "
                                f"{child.pid} ({child.name()})",
                            )
                            child.terminate()
                        except psutil.NoSuchProcess:
                            pass

                    # Give children time to terminate gracefully
                    await asyncio.sleep(MEDIUM_SLEEP_S)

                    # Force kill any remaining children
                    for child in children:
                        try:
                            if child.is_running():
                                self.ctx.debug(
                                    f"Force killing child process {child.pid}",
                                )
                                child.kill()
                        except psutil.NoSuchProcess:
                            pass
            except ImportError:
                self.ctx.warning(
                    "psutil not available - cannot clean up child processes",
                )
            except Exception as e:
                self.ctx.warning(f"Failed to clean up JDT LS children: {e}")

        # Terminate process (force kill if force=True)
        if self.process:
            try:
                if force:
                    # Fast path: immediate SIGKILL for evicted bridges
                    self.process.kill()
                    await self.process.wait()
                else:
                    # Graceful path: SIGTERM with reduced timeout
                    self.process.terminate()
                    try:
                        await asyncio.wait_for(
                            self.process.wait(),
                            timeout=PROCESS_TERMINATE_TIMEOUT_S,
                        )
                    except asyncio.TimeoutError:
                        self.ctx.warning("JDT LS process did not terminate, killing...")
                        self.process.kill()
                        await self.process.wait()

                # Close all subprocess transports to avoid ResourceWarnings
                from aidb_common.io.subprocess import close_subprocess_transports

                await close_subprocess_transports(self.process, self.ctx, "JDT LS")

            except Exception as e:
                self.ctx.warning(f"Error terminating JDT LS process: {e}")

        # Cleanup temporary workspace if created
        if self.workspace and str(self.workspace).startswith(tempfile.gettempdir()):
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    shutil.rmtree,
                    self.workspace,
                )
            except Exception as e:
                self.ctx.warning(f"Failed to cleanup workspace: {e}")

        self.process = None

    async def cleanup_children(self) -> None:  # noqa: C901
        """Clean up child processes without stopping JDT LS.

        This is used for pooled bridges to clean up debuggee processes while keeping the
        JDT LS process hot for reuse.

        CRITICAL: Only kills debuggee JVM processes, NOT the java-debug DAP server.
        """
        if not self.process or self.process.returncode is not None:
            self.ctx.debug("No JDT LS process to clean up children from")
            return

        try:
            import psutil

            parent = psutil.Process(self.process.pid)
            all_children = parent.children(recursive=True)

            if not all_children:
                self.ctx.debug("No child processes to clean up")
                return

            # Filter out java-debug server - only kill debuggee JVMs
            debuggees = []
            for child in all_children:
                try:
                    cmdline = child.cmdline()
                    # Skip java-debug server process (the DAP adapter)
                    if any(
                        "com.microsoft.java.debug.core.protocol.Server" in arg
                        for arg in cmdline
                    ):
                        self.ctx.debug(
                            f"Skipping java-debug server: PID {child.pid}",
                        )
                        continue
                    # This is a debuggee - mark for cleanup
                    debuggees.append(child)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            if not debuggees:
                self.ctx.debug("No debuggee processes to clean up")
                return

            self.ctx.info(
                f"Cleaning up {len(debuggees)} debuggee process(es) from pooled bridge",
            )

            # Terminate debuggees gracefully first
            for child in debuggees:
                try:
                    self.ctx.debug(
                        f"Terminating debuggee process {child.pid} ({child.name()})",
                    )
                    child.terminate()
                except psutil.NoSuchProcess:
                    pass
                except Exception as e:
                    self.ctx.debug(f"Error terminating child {child.pid}: {e}")

            # Give debuggees time to terminate gracefully
            await asyncio.sleep(MEDIUM_SLEEP_S)

            # Force kill any remaining debuggees
            for child in debuggees:
                try:
                    if child.is_running():
                        self.ctx.debug(f"Force killing debuggee process {child.pid}")
                        child.kill()
                except psutil.NoSuchProcess:
                    pass
                except Exception as e:
                    self.ctx.debug(f"Error killing child {child.pid}: {e}")

            self.ctx.debug("Child process cleanup complete")

        except ImportError:
            self.ctx.warning(
                "psutil not available - cannot clean up child processes",
            )
        except Exception as e:
            self.ctx.warning(f"Failed to clean up debuggee processes: {e}")

    def _build_jdtls_command(
        self,
        workspace: Path,
        java_debug_jar: Path,
    ) -> list[str]:
        """Build the command to launch JDT LS.

        Parameters
        ----------
        workspace : Path
            The workspace directory
        java_debug_jar : Path
            Path to the java-debug-server plugin JAR

        Returns
        -------
        List[str]
            The command arguments

        Raises
        ------
        AidbError
            If required files are not found
        """
        # Find the Equinox launcher JAR
        launcher_jar = self._find_equinox_launcher()
        if not launcher_jar:
            msg = f"Could not find Equinox launcher JAR in {self.jdtls_path}/plugins"
            raise AidbError(msg)

        # Determine platform-specific configuration
        config_dir = self._get_config_dir()
        if not config_dir.exists():
            msg = f"JDT LS configuration directory not found: {config_dir}"
            raise AidbError(msg)

        # Build the command
        cmd: list[str] = [
            self.java_command,
            # JDT LS system properties
            "-Declipse.application=org.eclipse.jdt.ls.core.id1",
            "-Dosgi.bundles.defaultStartLevel=4",
            "-Declipse.product=org.eclipse.jdt.ls.core.product",
            "-Dlog.level=ALL",
            # Add java-debug plugin to bundles - critical!
            f"-Dosgi.bundles.extra=reference:file:{java_debug_jar}",
            # JVM options for better performance
            "-Xmx1G",
            "--add-modules=ALL-SYSTEM",
            "--add-opens",
            "java.base/java.util=ALL-UNNAMED",
            "--add-opens",
            "java.base/java.lang=ALL-UNNAMED",
        ]

        # Respect explicit CPU count if provided (useful in cgroups)
        active_procs = os.environ.get("AIDB_JAVA_ACTIVE_PROCESSORS")
        if active_procs:
            cmd.append(f"-XX:ActiveProcessorCount={active_procs}")

        # Allow extra JVM options via environment for experimentation/tuning
        extra_jvm_opts = os.environ.get("AIDB_JAVA_EXTRA_JVM_OPTS")
        if extra_jvm_opts:
            try:
                cmd += shlex.split(extra_jvm_opts)
            except Exception:
                # Fallback simple split if shlex fails
                cmd += extra_jvm_opts.split()

        # Add diagnostic JVM logging/JFR when enabled (Linux CI focus)
        if os.environ.get("AIDB_JAVA_DIAG", "0") == "1":
            try:
                log_dir = Path(os.environ.get("AIDB_JAVA_DIAG_DIR", "/root/.aidb/log"))
                xlog_path = log_dir / "jdtls-xlog.txt"
                jfr_path = log_dir / "jdtls.jfr"
                cmd += [
                    # Container + OS introspection logs with timestamps/levels
                    f"-Xlog:os+container=trace,os+thread=info:file={xlog_path}:time,uptime,level,tags",
                    # Lightweight flight recording for post-mortem analysis
                    f"-XX:StartFlightRecording=filename={jfr_path},dumponexit=true,settings=profile",
                ]
            except Exception:
                # Best-effort only; never fail startup for diagnostics
                pass

        # Launch the Equinox OSGi container
        cmd += [
            "-jar",
            str(launcher_jar),
            # JDT LS configuration
            "-configuration",
            str(config_dir),
            "-data",
            str(workspace),
        ]

        return cmd

    def _find_equinox_launcher(self) -> Path | None:
        """Find the Equinox launcher JAR in the JDT LS plugins directory.

        Returns
        -------
        Optional[Path]
            Path to the launcher JAR if found
        """
        plugins_dir = self.jdtls_path / "plugins"
        if not plugins_dir.exists():
            return None

        # Look for org.eclipse.equinox.launcher_*.jar
        for jar_file in plugins_dir.glob("org.eclipse.equinox.launcher_*.jar"):
            return jar_file

        return None

    def _get_config_dir(self) -> Path:
        """Get the platform-specific JDT LS configuration directory.

        Returns
        -------
        Path
            Path to the configuration directory
        """
        system = platform.system().lower()

        if system == "darwin":
            config_name = "config_mac"
        elif system == "windows":
            config_name = "config_win"
        else:
            config_name = "config_linux"

        return self.jdtls_path / config_name

    def get_workspace_path(self) -> Path | None:
        """Get the workspace path used by JDT LS.

        Returns
        -------
        Optional[Path]
            The workspace path if available
        """
        return self.workspace if self.workspace else None

    def get_eclipse_log_path(self) -> Path | None:
        """Get the path to the Eclipse Platform log file.

        Returns
        -------
        Optional[Path]
            Path to the Eclipse log file if it exists
        """
        if not self.workspace:
            return None

        eclipse_log = self.workspace / ".metadata" / ".log"
        if eclipse_log.exists():
            return eclipse_log
        return None
