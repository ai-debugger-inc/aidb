"""Java compilation management for the Java debug adapter."""

import asyncio
import subprocess
import sys
import tempfile
from pathlib import Path

from aidb.adapters.base.adapter import CompilationStatus
from aidb.common.constants import JAVA_COMPILATION_TIMEOUT_S
from aidb.common.errors import AidbError, CompilationError
from aidb.patterns.base import Obj
from aidb_common.config import config


class JavaCompilationManager(Obj):
    """Manages Java source compilation for debugging.

    This class handles the compilation of single Java source files, checking if
    compilation is needed, and managing temporary compilation directories.
    """

    def __init__(self, adapter, ctx=None):
        """Initialize the compilation manager.

        Parameters
        ----------
        adapter : JavaAdapter
            The Java adapter instance
        ctx : optional
            Context for logging
        """
        super().__init__(ctx or adapter.ctx)
        self.adapter = adapter
        self.config = adapter.config
        self._temp_compile_dir: str | None = None

    def cleanup(self):
        """Clean up temporary compilation directory."""
        if self._temp_compile_dir and Path(self._temp_compile_dir).exists():
            try:
                import shutil

                shutil.rmtree(self._temp_compile_dir)
                self.ctx.debug(f"Cleaned up temp compile dir: {self._temp_compile_dir}")
            except Exception as e:
                self.ctx.warning(f"Failed to clean up temp dir: {e}")
            finally:
                self._temp_compile_dir = None

    async def compile_if_needed(self, target: str) -> str:
        """Compile Java source file if needed.

        Only compiles single .java files without dependencies. For projects with
        dependencies, use Maven or Gradle.

        Parameters
        ----------
        target : str
            Path to target file

        Returns
        -------
        str
            Path to executable (compiled .class file or original if already
            compiled)

        Raises
        ------
        AidbError
            If compilation fails
        """
        # Use adapter's method to check compilation status first
        status = self.adapter.check_compilation_status(target)

        # Check if compilation is actually needed
        if not self._check_if_compilation_needed(target, status):
            return status.executable_path if status.is_compiled else target

        # Check if auto-compilation is enabled
        auto_compile = self.config.auto_compile or config.is_java_auto_compile_enabled()

        if not auto_compile:
            msg = (
                f"{status.error_message}\n"
                f"Suggested command: {status.compile_command}\n"
                f"Or enable auto_compile in JavaAdapterConfig "
                f"or set AIDB_JAVA_AUTO_COMPILE=true"
            )
            raise CompilationError(
                msg,
                details={
                    "target": target,
                    "suggested_command": status.compile_command,
                    "auto_compile": False,
                },
            )

        # Prepare compilation environment
        temp_dir, class_file = self._prepare_compilation_environment(target)

        # Build and execute compilation command
        cmd = self._build_javac_command(target, temp_dir)

        self.ctx.info(f"Compiling Java source: {' '.join(cmd)}")

        try:
            # Use asyncio to run subprocess
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=JAVA_COMPILATION_TIMEOUT_S,
            )
            stdout = stdout_bytes.decode("utf-8") if stdout_bytes else ""
            stderr = stderr_bytes.decode("utf-8") if stderr_bytes else ""

            if proc.returncode != 0:
                msg = f"Java compilation failed:\n{stderr}"
                raise CompilationError(
                    msg,
                    details={
                        "command": " ".join(cmd),
                        "returncode": proc.returncode,
                        "stderr": stderr,
                        "stdout": stdout,
                        "target": target,
                    },
                )

            if not Path(class_file).exists():
                msg = f"Compilation succeeded but class file not found: {class_file}"
                raise CompilationError(
                    msg,
                    details={
                        "expected_file": class_file,
                        "temp_dir": temp_dir,
                        "command": " ".join(cmd),
                    },
                )

            self.ctx.info(f"Successfully compiled to: {class_file}")
            return class_file

        except subprocess.TimeoutExpired as e:
            msg = "Java compilation timed out after 30 seconds"
            raise CompilationError(
                msg,
                details={"command": " ".join(cmd), "timeout": 30, "target": target},
            ) from e
        except CompilationError:
            raise  # Re-raise our own errors
        except Exception as e:
            msg = f"Unexpected compilation error: {e}"
            raise CompilationError(
                msg,
                details={
                    "original_error": str(e),
                    "error_type": type(e).__name__,
                    "target": target,
                },
            ) from e

    def _check_if_compilation_needed(
        self,
        target: str,
        status: CompilationStatus,
    ) -> bool:
        """Check if compilation is needed for the target file.

        Parameters
        ----------
        target : str
            Path to target file
        status : CompilationStatus
            Compilation status from check_compilation_status

        Returns
        -------
        bool
            True if compilation is needed, False otherwise
        """
        if not target.endswith(".java"):
            return False

        # If already compiled and up-to-date, no compilation needed
        if status.is_compiled:
            class_file = status.executable_path
            if Path(class_file).exists():
                src_mtime = Path(target).stat().st_mtime
                class_mtime = Path(class_file).stat().st_mtime
                if class_mtime > src_mtime:
                    self.ctx.debug(f"Using existing compiled class: {class_file}")
                    return False
        return True

    def _prepare_compilation_environment(self, target: str) -> tuple[str, str]:
        """Prepare temporary directory and paths for compilation.

        Parameters
        ----------
        target : str
            Path to source file

        Returns
        -------
        Tuple[str, str]
            (temp_dir, class_file) paths
        """
        temp_dir = tempfile.mkdtemp(prefix="java_compile_")
        class_name = Path(target).stem
        class_file = str(Path(temp_dir) / f"{class_name}.class")

        # Store temp dir for cleanup later
        self._temp_compile_dir = temp_dir

        return temp_dir, class_file

    def _build_javac_command(self, target: str, temp_dir: str) -> list[str]:
        """Build the javac compilation command.

        Parameters
        ----------
        target : str
            Path to source file
        temp_dir : str
            Temporary directory for output

        Returns
        -------
        List[str]
            Command arguments for javac
        """
        javac_cmd = self._get_javac_executable()

        # Build compilation command with output directory
        cmd = [
            javac_cmd,
            "-g",  # -g for debug symbols
            "-d",
            temp_dir,  # -d for output dir
        ]

        # Add classpath if specified
        if self.adapter.classpath:
            separator = ";" if sys.platform == "win32" else ":"
            cp = separator.join(self.adapter.classpath)
            cmd.extend(["-cp", cp])

        cmd.append(target)
        return cmd

    def _get_javac_executable(self) -> str:
        """Get the javac executable path.

        Returns
        -------
        str
            Path to javac executable

        Raises
        ------
        AidbError
            If javac is not found
        """
        # Check if jdk_home is specified in config
        if hasattr(self.adapter, "config") and self.adapter.config.jdk_home:
            javac_path = Path(self.adapter.config.jdk_home) / "bin" / "javac"
            if javac_path.exists():
                return str(javac_path)

        # Check JAVA_HOME environment variable
        java_home = config.get_java_home()
        if java_home:
            javac_path = Path(java_home) / "bin" / "javac"
            if javac_path.exists():
                return str(javac_path)

        # Try to find javac in PATH
        import shutil

        javac = shutil.which("javac")
        if javac:
            return javac

        msg = "javac not found. Please install a JDK and set JAVA_HOME"
        raise AidbError(msg)
