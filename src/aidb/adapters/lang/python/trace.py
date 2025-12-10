"""Debugpy trace log management for Python adapter."""

import contextlib
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from aidb.patterns import Obj
from aidb_common.constants import Language

if TYPE_CHECKING:
    from aidb.interfaces.context import IContext


class PythonTraceManager(Obj):
    """Manages debugpy's trace log files with proper rotation.

    Debugpy creates three types of log files with PID suffixes:
        - debugpy.adapter-{PID}.log: Adapter-level debugging
        - debugpy.pydevd.{PID}.log: PyDev debugger internals
        - debugpy.server-{PID}.log: Debug server operations

    This manager handles:
        1. Cleaning up old PID-based logs on startup
        2. Rotating logs to maintain history (current + 5 historical)
        3. Preserving debugpy's log type separation
    """

    def __init__(
        self,
        ctx: Optional["IContext"] = None,
        trace_dir: str | None = None,
        max_rotations: int = 5,
    ):
        """Initialize the debugpy log manager.

        Parameters
        ----------
        ctx : IContext, optional
            Application context for logging and storage paths
        trace_dir : str, optional
            Directory where debugpy logs are stored. If not provided, uses the
            context's storage path for adapter_traces/python
        max_rotations : int
            Number of historical logs to keep per type (default: 5)
        """
        super().__init__(ctx)

        # Determine trace directory
        if trace_dir:
            self.trace_dir = Path(trace_dir)
        else:
            # Use context storage path if available (under log/)
            base_dir = Path(self.ctx.get_storage_path("log/adapter_traces", ""))
            self.trace_dir = base_dir / Language.PYTHON.value
            self.trace_dir.mkdir(parents=True, exist_ok=True)

        self.max_rotations = max_rotations
        self.log_types = ["adapter", "pydevd", "server"]
        self.ctx.debug(
            f"PythonTraceManager initialized with trace_dir: {self.trace_dir}",
        )

    def cleanup_old_pid_logs(self) -> int:
        """Clean up old PID-based debugpy log files.

        Called on startup to remove accumulated PID-based logs from previous
        sessions.

        Returns
        -------
        int
            Number of files cleaned up
        """
        cleaned = 0
        try:
            # Pattern matches debugpy.*.log files with PIDs
            patterns = [
                "debugpy.adapter-*.log",
                "debugpy.pydevd.*.log",
                "debugpy.server-*.log",
            ]

            for pattern in patterns:
                for log_file in self.trace_dir.glob(pattern):
                    try:
                        # Check if filename contains a PID (number after last
                        # dash/dot)
                        if "adapter" in log_file.name or "server" in log_file.name:
                            name_parts = log_file.stem.split("-")
                        else:  # pydevd
                            name_parts = log_file.stem.split(".")

                        if name_parts and name_parts[-1].isdigit():
                            log_file.unlink()
                            cleaned += 1
                            self.ctx.debug(f"Removed old debugpy log: {log_file.name}")
                    except Exception as e:
                        self.ctx.debug(f"Could not remove {log_file.name}: {e}")

            if cleaned > 0:
                self.ctx.info(f"Cleaned up {cleaned} old debugpy PID-based log files")

        except Exception as e:
            self.ctx.warning(f"Failed to clean up old debugpy logs: {e}")

        return cleaned

    def rotate_logs_on_start(self) -> None:
        """Rotate existing normalized logs before starting a new session.

        This ensures we preserve history across sessions by rotating:
            - python.adapter.log -> python.adapter.log.1
            - python.pydevd.log -> python.pydevd.log.1
            - python.server.log -> python.server.log.1
        """
        for log_type in self.log_types:
            base_name = f"python.{log_type}.log"
            log_path = self.trace_dir / base_name
            if log_path.exists():
                self._rotate_single_log(log_path)
                self.ctx.debug(f"Rotated existing {base_name}")

    def consolidate_session_logs(self) -> None:
        """Consolidate PID-based logs into normalized logs.

        Called after a session ends to:
            1. Find all PID-based logs from the session
            2. Combine them by type into normalized log files
            3. Clean up the PID-based files
        """
        try:
            consolidated_any = False

            # Process each log type separately
            for log_type in self.log_types:
                if self._consolidate_log_type(log_type):
                    consolidated_any = True

            if consolidated_any:
                self.ctx.info("Consolidated debugpy session logs into rotated format")

        except Exception as e:
            self.ctx.warning(f"Failed to consolidate debugpy logs: {e}")

    def _consolidate_log_type(self, log_type: str) -> bool:
        """Consolidate all PID-based logs of a specific type.

        Parameters
        ----------
        log_type : str
            Type of log to consolidate ("adapter", "pydevd", or "server")

        Returns
        -------
        bool
            True if any logs were consolidated
        """
        # Find all PID-based logs of this type
        if log_type == "adapter":
            pattern = "debugpy.adapter-*.log"
        elif log_type == "pydevd":
            pattern = "debugpy.pydevd.*.log"
        else:  # server
            pattern = "debugpy.server-*.log"

        pid_logs = sorted(
            self.trace_dir.glob(pattern),
            key=lambda p: p.stat().st_mtime,  # Sort by modification time
        )

        if not pid_logs:
            return False

        # Target normalized log file
        target_path = self.trace_dir / f"python.{log_type}.log"

        # If a current log exists, rotate it first
        if target_path.exists():
            self._rotate_single_log(target_path)

        # Combine all PID logs into the target
        try:
            with target_path.open("w") as outfile:
                for pid_log in pid_logs:
                    try:
                        # Add a header to identify the source
                        outfile.write(f"\n# === From {pid_log.name} ===\n")
                        with pid_log.open() as infile:
                            outfile.write(infile.read())
                    except Exception as e:
                        self.ctx.debug(f"Could not read {pid_log.name}: {e}")
                        continue

            self.ctx.debug(
                f"Consolidated {len(pid_logs)} {log_type} logs into {target_path.name}",
            )

            # Clean up the PID-based files after successful consolidation
            for pid_log in pid_logs:
                with contextlib.suppress(Exception):
                    pid_log.unlink()

            return True

        except Exception as e:
            self.ctx.warning(f"Failed to consolidate {log_type} logs: {e}")
            return False

    def _rotate_single_log(self, log_path: Path) -> None:
        """Rotate a single log file maintaining N historical versions.

        Rotation pattern:
            - current -> .1
            - .1 -> .2
            - .2 -> .3
            - etc.
            - .N is deleted

        Parameters
        ----------
        log_path : Path
            Path to the log file to rotate
        """
        try:
            # Remove the oldest if it exists
            oldest = log_path.parent / f"{log_path.name}.{self.max_rotations}"
            if oldest.exists():
                oldest.unlink()

            # Shift existing numbered logs up
            for i in range(self.max_rotations - 1, 0, -1):
                src = log_path.parent / f"{log_path.name}.{i}"
                dst = log_path.parent / f"{log_path.name}.{i + 1}"
                if src.exists():
                    src.rename(dst)

            # Rotate current to .1
            if log_path.exists():
                rotated = log_path.parent / f"{log_path.name}.1"
                log_path.rename(rotated)

        except Exception as e:
            self.ctx.debug(f"Could not rotate {log_path.name}: {e}")
