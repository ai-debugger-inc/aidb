"""Session-scoped Java test program precompilation.

This fixture compiles all Java test programs once at session startup, eliminating per-
test compilation overhead (~2.5s × 102 tests = 255s saved).
"""

__all__ = [
    # Classes
    "JavaPrecompilationManager",
    # Fixtures
    "java_precompilation_manager",
]

import logging
import subprocess
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

logger = logging.getLogger(__name__)


class JavaPrecompilationManager:
    """Manages session-scoped precompilation of Java test programs."""

    def __init__(self, session_tmp: Path):
        """Initialize precompilation manager.

        Parameters
        ----------
        session_tmp : Path
            Session-scoped temporary directory for compiled artifacts
        """
        self.session_tmp = session_tmp
        self.compiled_programs: dict[str, Path] = {}
        self.compilation_errors: dict[str, str] = {}

    def precompile_all(self, test_programs_dir: Path, java_command: str = "javac"):
        """Precompile all Java test programs.

        Parameters
        ----------
        test_programs_dir : Path
            Directory containing generated test programs
        java_command : str
            Java compiler command (default: javac)

        Returns
        -------
        dict[str, Path]
            Mapping of scenario_id -> compiled output directory
        """
        logger.info("Starting session-scoped Java test program precompilation")

        # Find all TestProgram.java files
        java_files = list(test_programs_dir.glob("*/TestProgram.java"))
        logger.info(f"Found {len(java_files)} Java test programs to precompile")

        compiled_count = 0
        failed_count = 0

        for java_file in java_files:
            scenario_id = java_file.parent.name
            try:
                compiled_dir = self._compile_program(
                    java_file,
                    scenario_id,
                    java_command,
                )
                self.compiled_programs[scenario_id] = compiled_dir
                compiled_count += 1
            except Exception as e:
                error_msg = f"Precompilation failed for {scenario_id}: {e}"
                logger.warning(error_msg)
                self.compilation_errors[scenario_id] = str(e)
                failed_count += 1

        logger.info(
            f"Precompilation complete: {compiled_count} succeeded, {failed_count} failed",
        )

        return self.compiled_programs

    def _compile_program(
        self,
        java_file: Path,
        scenario_id: str,
        java_command: str,
    ) -> Path:
        """Compile a single Java test program.

        Parameters
        ----------
        java_file : Path
            Path to TestProgram.java
        scenario_id : str
            Scenario identifier
        java_command : str
            Java compiler command

        Returns
        -------
        Path
            Directory containing compiled .class files

        Raises
        ------
        RuntimeError
            If compilation fails
        """
        # Create output directory for this scenario
        output_dir = self.session_tmp / scenario_id
        output_dir.mkdir(parents=True, exist_ok=True)

        # Compile with debugging symbols enabled (-g flag)
        cmd = [
            java_command,
            "-g",  # Generate debugging info
            "-d",
            str(output_dir),  # Output directory
            str(java_file),  # Source file
        ]

        logger.debug(f"Compiling {scenario_id}: {' '.join(cmd)}")

        try:
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )

            # Check that .class file was created
            class_file = output_dir / "TestProgram.class"
            if not class_file.exists():
                msg = f"Compilation succeeded but {class_file} not found"
                raise RuntimeError(msg)

            # Symlink .class file back to source directory
            # This allows the compilation check to find the precompiled file
            source_dir = java_file.parent
            target_class_file = source_dir / "TestProgram.class"

            # Remove existing .class file if present
            if target_class_file.exists():
                target_class_file.unlink()

            # Create symlink from source dir to compiled file
            try:
                target_class_file.symlink_to(class_file)
                logger.debug(f"Symlinked {target_class_file} -> {class_file}")
            except (OSError, NotImplementedError):
                # Fallback to copy if symlink fails (e.g., on Windows)
                import shutil

                shutil.copy2(class_file, target_class_file)
                logger.debug(f"Copied {class_file} to {target_class_file}")

            logger.debug(f"Successfully compiled {scenario_id} to {output_dir}")
            return output_dir

        except subprocess.CalledProcessError as e:
            error_msg = f"Compilation failed: {e.stderr}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e
        except subprocess.TimeoutExpired as e:
            error_msg = f"Compilation timeout after {e.timeout}s"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def get_compiled_path(self, scenario_id: str) -> Path | None:
        """Get compiled output directory for a scenario.

        Parameters
        ----------
        scenario_id : str
            Scenario identifier

        Returns
        -------
        Path | None
            Path to compiled output directory, or None if not compiled
        """
        return self.compiled_programs.get(scenario_id)

    def has_compilation_error(self, scenario_id: str) -> bool:
        """Check if scenario had compilation error.

        Parameters
        ----------
        scenario_id : str
            Scenario identifier

        Returns
        -------
        bool
            True if compilation failed
        """
        return scenario_id in self.compilation_errors

    def get_compilation_error(self, scenario_id: str) -> str | None:
        """Get compilation error message for scenario.

        Parameters
        ----------
        scenario_id : str
            Scenario identifier

        Returns
        -------
        str | None
            Error message if compilation failed, None otherwise
        """
        return self.compilation_errors.get(scenario_id)


@pytest.fixture(scope="session")
def java_precompilation_manager(
    tmp_path_factory,
) -> Generator[JavaPrecompilationManager, None, None]:
    """Session-scoped fixture that precompiles all Java test programs.

    This fixture runs once at the start of the test session and compiles
    all Java test programs to eliminate per-test compilation overhead.

    Parameters
    ----------
    tmp_path_factory : TempPathFactory
        pytest temp path factory for session-scoped temp directories

    Returns
    -------
    JavaPrecompilationManager
        Manager with precompiled programs

    Notes
    -----
    Precompilation saves ~240 seconds (2.5s × 102 tests) from the test suite.
    """
    # Create session-scoped temp directory for compiled artifacts
    session_tmp = tmp_path_factory.mktemp("java_precompiled")

    # Create manager
    manager = JavaPrecompilationManager(session_tmp)

    # Check if javac is available before attempting precompilation
    # (e.g., in JavaScript/Python containers, javac won't be installed)
    try:
        result = subprocess.run(
            ["javac", "-version"],
            capture_output=True,
            timeout=5,
            check=False,
        )
        javac_available = result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        javac_available = False

    if javac_available:
        # Find test programs directory
        test_programs_dir = (
            Path(__file__).parent.parent / "_assets" / "test_programs" / "generated"
        )

        # Clean up any stale .class symlinks from previous runs
        # (e.g., from host runs that created symlinks pointing to host temp dirs)
        import os

        for java_file in test_programs_dir.glob("*/TestProgram.java"):
            class_file = java_file.with_suffix(".class")
            if class_file.is_symlink():
                # Check if symlink is broken (target doesn't exist)
                try:
                    class_file.resolve(strict=True)
                except (FileNotFoundError, RuntimeError):
                    # Broken symlink - remove it
                    logger.debug(
                        "Removing stale .class symlink: %s -> %s",
                        class_file,
                        class_file.readlink(),
                    )
                    class_file.unlink()

        # Precompile all programs
        manager.precompile_all(test_programs_dir)
    else:
        logger.info(
            "Java compiler (javac) not available - skipping precompilation "
            "(running in non-Java container or Java not installed)",
        )

    # Log summary
    logger.info(
        "Java precompilation session initialized: %d programs compiled to %s",
        len(manager.compiled_programs),
        session_tmp,
    )

    # Set environment variable to disable auto-compilation for tests
    # This prevents recompilation of precompiled programs
    import os

    os.environ["AIDB_JAVA_AUTO_COMPILE"] = "false"
    logger.info("Disabled Java auto-compilation for precompiled test programs")

    yield manager

    # Cleanup: restore auto-compilation setting
    if "AIDB_JAVA_AUTO_COMPILE" in os.environ:
        del os.environ["AIDB_JAVA_AUTO_COMPILE"]
