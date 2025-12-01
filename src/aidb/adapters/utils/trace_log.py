"""Trace log management for debug adapters."""

import os
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from aidb.patterns import Obj

if TYPE_CHECKING:
    from aidb.interfaces.context import IContext


class AdapterTraceLogManager(Obj):
    """Manages trace log files for debug adapters with size control."""

    def __init__(
        self,
        ctx: Optional["IContext"] = None,
        max_bytes: int = 10 * 1024 * 1024,
    ):
        """Initialize trace log manager.

        Parameters
        ----------
        ctx : IContext, optional
            Application context
        max_bytes : int
            Maximum log file size before halving (default 10MB for JSON logs)
        """
        super().__init__(ctx)
        self.max_bytes = max_bytes
        self._current_log_path: str | None = None
        # Keep 5 previous traces (current + 5 = 6 total files)
        self._rotation_count: int = 5

    def get_trace_log_path(
        self,
        adapter_name: str,
        extension: str = "log.json",
    ) -> str:
        """Generate and return a trace log path with rotation.

        Parameters
        ----------
        adapter_name : str
            Name of the adapter (e.g., "javascript")
        extension : str
            File extension for the log file (default: "log.json"). Examples:
            "log", "log.json".

        Returns
        -------
        str
            Path to the current trace log file
        """
        # Ensure adapter trace directory exists
        trace_dir = self._get_adapter_trace_dir(adapter_name)

        # Normalize extension (allow with or without leading dot)
        ext = extension.lstrip(".") if extension else "log.json"

        # Stable current filename (no timestamp)
        base_filename = f"{adapter_name}.{ext}"
        current_path = str(trace_dir / base_filename)

        # Rotate existing logs before starting a new one
        self._rotate_logs(trace_dir, base_filename)

        # Record and return the current path
        self._current_log_path = current_path
        return self._current_log_path

    def check_and_halve_log(self) -> None:
        """Check log size and halve if needed (for post-session processing)."""
        if not self._current_log_path or not Path(self._current_log_path).exists():
            return

        try:
            if Path(self._current_log_path).stat().st_size > self.max_bytes:
                # For JSON logs, we need to be smarter about halving
                self._halve_json_log(self._current_log_path)
        except Exception as e:
            self.ctx.warning(f"Failed to halve trace log: {e}")

    def _halve_json_log(self, log_path: str) -> None:
        """Halve a JSON lines log file, keeping the most recent entries."""
        try:
            # Read all lines
            with Path(log_path).open() as f:
                lines = f.readlines()

            # Keep the last half of entries
            half_point = len(lines) // 2
            kept_lines = lines[half_point:]

            # Write back
            with Path(log_path).open("w") as f:
                f.writelines(kept_lines)

            self.ctx.debug(
                f"Halved trace log from {len(lines)} to {len(kept_lines)} entries",
            )
        except Exception:
            # Fall back to binary halving if JSON parsing fails
            with Path(log_path).open("rb") as f:
                f.seek(-self.max_bytes // 2, os.SEEK_END)
                data = f.read()
            with Path(log_path).open("wb") as f:
                f.write(data)

    def _get_adapter_trace_dir(self, adapter_name: str) -> Path:
        """Return the per-adapter trace directory path and ensure it exists."""
        # Base adapter_traces directory under log/
        base_dir = Path(self.ctx.get_storage_path("log/adapter_traces", ""))
        adapter_dir = base_dir / adapter_name
        adapter_dir.mkdir(parents=True, exist_ok=True)
        return adapter_dir

    def _rotate_logs(self, trace_dir: Path, base_filename: str) -> None:
        """Rotate logs keeping the last N files.

        Rotation scheme:
            base -> base.1
            base.1 -> base.2
            ... up to base.N (oldest dropped)
        """
        try:
            # Drop the oldest if it exists
            oldest = trace_dir / f"{base_filename}.{self._rotation_count}"
            if oldest.exists():
                oldest.unlink(missing_ok=True)

            # Shift existing files up (N-1 down to 1)
            for i in range(self._rotation_count - 1, 0, -1):
                src = trace_dir / f"{base_filename}.{i}"
                dst = trace_dir / f"{base_filename}.{i + 1}"
                if src.exists():
                    src.rename(dst)

            # Finally, rotate current to .1 if it exists
            current = trace_dir / base_filename
            rotated_first = trace_dir / f"{base_filename}.1"
            if current.exists():
                current.rename(rotated_first)
        except Exception as e:
            self.ctx.warning(f"Failed to rotate trace logs for {base_filename}: {e}")

    def get_current_log_path(self) -> str | None:
        """Get the path to the current trace log file.

        Returns
        -------
        Optional[str]
            Path to the current trace log file if available
        """
        return self._current_log_path
