"""Custom logging handlers for aidb_logging package."""

import logging
import os
import sys
import threading
from pathlib import Path


class HalvingFileHandler(logging.FileHandler):
    """File handler that halves the log file when it exceeds the size limit.

    When the log file exceeds max_bytes, keeps the last half of the file to preserve
    recent history while preventing unbounded growth.
    """

    def __init__(
        self,
        filename: str,
        mode: str = "a",
        max_bytes: int = 100 * 1024 * 1024,  # 100MB default
        encoding: str | None = None,
        delay: bool = False,
    ) -> None:
        """Initialize the HalvingFileHandler.

        Parameters
        ----------
        filename : str
            Path to the log file
        mode : str
            File opening mode (default: "a" for append)
        max_bytes : int
            Maximum file size in bytes before halving (default: 100MB)
        encoding : str, optional
            File encoding
        delay : bool
            If True, defer file opening until first emit (default: False)
        """
        super().__init__(filename, mode, encoding, delay)
        self.max_bytes = max_bytes
        self.filename = self.baseFilename
        self._rotation_lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a record, halving the file if it exceeds the size limit.

        Parameters
        ----------
        record : logging.LogRecord
            The log record to emit
        """
        # Check if file/directory was deleted and reopen if needed
        self._reopen_if_needed()
        super().emit(record)
        self.flush()
        self._halve_file_if_needed()

    def _reopen_if_needed(self) -> None:
        """Reopen the file if it or its directory was deleted."""
        try:
            file_path = Path(self.filename)

            # If parent directory doesn't exist, recreate it
            if not file_path.parent.exists():
                file_path.parent.mkdir(parents=True, exist_ok=True)

            # If file doesn't exist, close and reopen to recreate it
            if not file_path.exists():
                if self.stream:
                    self.stream.close()
                self.stream = self._open()
        except Exception:  # noqa: S110
            # Silently ignore - emit() will handle any issues
            # Cannot log here to avoid recursion in log handling
            pass

    def _halve_file_if_needed(self) -> None:
        """Check file size and halve if necessary (thread-safe)."""
        try:
            file_path = Path(self.filename)

            # If file doesn't exist, skip rotation check
            # (FileHandler will recreate it on next write)
            if not file_path.exists():
                # Ensure parent directory exists for next write
                file_path.parent.mkdir(parents=True, exist_ok=True)
                return

            # Quick check without lock first
            file_size = file_path.stat().st_size
            if file_size <= self.max_bytes:
                return

            # Need to rotate - acquire lock
            with self._rotation_lock:
                # Double-check file still exists and size after acquiring lock
                if not file_path.exists():
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    return

                file_size = file_path.stat().st_size
                if file_size > self.max_bytes:
                    self._halve_file()
        except FileNotFoundError:
            # File was deleted between exists() check and stat() - this is fine
            # FileHandler will recreate it on next write
            Path(self.filename).parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            # Only warn for actual rotation failures, not missing files
            sys.stderr.write(
                f"Warning: Failed to check/rotate log file {self.filename}: {e}\n",
            )

    def _halve_file(self) -> None:
        """Halve the log file by keeping only the last 50%."""
        try:
            with Path(self.filename).open("rb") as f:
                f.seek(-self.max_bytes // 2, os.SEEK_END)
                # Skip to the next newline to avoid partial lines
                f.readline()
                data = f.read()

            with Path(self.filename).open("wb") as f:
                f.write(data)

        except Exception as e:
            # Log to stderr to avoid recursion in log handling
            sys.stderr.write(
                f"Warning: Failed to halve log file {self.filename}: {e}\n",
            )


class DualStreamHandler(logging.Handler):
    """Handler that outputs to both stdout and stderr based on log level.

    INFO and below go to stdout, WARNING and above go to stderr. This is useful for
    tools that need to separate normal output from errors.
    """

    def __init__(self) -> None:
        """Initialize the dual stream handler."""
        super().__init__()
        self.stdout_handler = logging.StreamHandler(sys.stdout)
        self.stderr_handler = logging.StreamHandler(sys.stderr)

    def setFormatter(self, formatter: logging.Formatter | None) -> None:  # noqa: N802
        """Set formatter for both handlers.

        Parameters
        ----------
        formatter : logging.Formatter
            The formatter to use
        """
        super().setFormatter(formatter)
        self.stdout_handler.setFormatter(formatter)
        self.stderr_handler.setFormatter(formatter)

    def emit(self, record: logging.LogRecord) -> None:
        """Emit record to appropriate stream based on level.

        Parameters
        ----------
        record : logging.LogRecord
            The log record to emit
        """
        if record.levelno >= logging.WARNING:
            self.stderr_handler.emit(record)
        else:
            self.stdout_handler.emit(record)

    def close(self) -> None:
        """Close underlying stream handlers and this handler."""
        try:
            self.stdout_handler.close()
        finally:
            try:
                self.stderr_handler.close()
            finally:
                super().close()
