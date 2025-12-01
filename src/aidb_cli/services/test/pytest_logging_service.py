"""Service for managing pytest log output and session isolation."""

import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from aidb_cli.managers.base.service import BaseService
from aidb_logging import get_cli_logger

if TYPE_CHECKING:
    import click

    from aidb_cli.services.command_executor import CommandExecutor

logger = get_cli_logger(__name__)


class PytestLoggingService(BaseService):
    """Manages pytest log directories with session isolation and cleanup.

    Responsibilities
    ----------------
    - Generate unique session IDs for test runs
    - Create session-specific log directories
    - Cleanup old session directories (keep N most recent)
    - Provide log file paths for pytest configuration
    - Handle both local and container test log directories
    """

    def __init__(
        self,
        repo_root: Path,
        command_executor: Optional["CommandExecutor"] = None,
        ctx: Optional["click.Context"] = None,
        skip_session_logging: bool = False,
    ) -> None:
        """Initialize pytest logging service.

        Parameters
        ----------
        repo_root : Path
            Repository root directory
        command_executor : CommandExecutor | None, optional
            Command executor instance
        ctx : click.Context | None, optional
            CLI context for accessing centralized environment
        skip_session_logging : bool, optional
            If True, skip session-isolated logging (useful for unit tests)
        """
        super().__init__(repo_root, command_executor, ctx)
        self.base_log_dir = repo_root / "pytest-logs"
        self.container_cache_dir = repo_root / ".cache" / "container-data"

        # Allow environment variable override for test mode
        self.skip_session_logging = skip_session_logging or os.getenv(
            "AIDB_SKIP_SESSION_LOGS",
            "",
        ).lower() in ("1", "true", "yes")

    def generate_session_id(
        self,
        suite: str | None,
        timestamp: str | None = None,
    ) -> str:
        """Generate session ID for test run.

        Format: {suite}-{YYYYMMDD-HHMMSS}

        Examples
        --------
        - cli-20251028-052613
        - local-20251028-143022

        Parameters
        ----------
        suite : str | None
            Test suite name (or None for local tests)
        timestamp : str | None, optional
            Timestamp string in YYYYMMDD-HHMMSS format. If provided, uses this
            timestamp instead of generating a new one. This ensures timestamp
            consistency across the test session lifecycle.

        Returns
        -------
        str
            Session ID
        """
        suite_name = suite or "local"
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        return f"{suite_name}-{timestamp}"

    def create_session_directory(
        self,
        session_id: str,
        base_dir: Path | None = None,
    ) -> Path:
        """Create session-specific log directory.

        Parameters
        ----------
        session_id : str
            Session ID from generate_session_id()
        base_dir : Path | None, optional
            Base directory for session (defaults to pytest-logs)

        Returns
        -------
        Path
            Path to session directory
        """
        if base_dir is None:
            base_dir = self.base_log_dir

        # If session logging is disabled, return base dir without creating subdirectory
        if self.skip_session_logging:
            base_dir.mkdir(parents=True, exist_ok=True)
            self.log_debug(
                "Session logging disabled, using base directory: %s",
                base_dir,
            )
            return base_dir

        session_dir = base_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        self.log_debug("Created pytest session directory: %s", session_dir)
        return session_dir

    def get_pytest_log_file_path(self, session_dir: Path) -> Path:
        """Get path for pytest-captured.log in session directory.

        Parameters
        ----------
        session_dir : Path
            Session directory path

        Returns
        -------
        Path
            Path to pytest-captured.log
        """
        return session_dir / "pytest-captured.log"

    def get_test_results_path(self, session_dir: Path) -> Path:
        """Get path for test-results.log in session directory.

        Parameters
        ----------
        session_dir : Path
            Session directory path

        Returns
        -------
        Path
            Path to test-results.log
        """
        return session_dir / "test-results.log"

    def cleanup_old_sessions(self, base_dir: Path, keep_count: int = 10) -> int:
        """Keep only the N most recent pytest session directories.

        Parses timestamps from directory names, sorts chronologically,
        and deletes all except the most recent sessions.

        Parameters
        ----------
        base_dir : Path
            Base directory containing session directories
        keep_count : int, optional
            Number of sessions to keep (default: 10)

        Returns
        -------
        int
            Number of sessions deleted
        """
        if not base_dir.exists():
            return 0

        # Pattern: {suite}-YYYYMMDD-HHMMSS
        pattern = re.compile(r"^(.+)-(\d{8}-\d{6})$")
        sessions = []

        for entry in base_dir.iterdir():
            if not entry.is_dir():
                continue
            match = pattern.match(entry.name)
            if match:
                suite, timestamp_str = match.groups()
                try:
                    timestamp = datetime.strptime(
                        timestamp_str,
                        "%Y%m%d-%H%M%S",
                    ).replace(tzinfo=timezone.utc)
                    sessions.append((timestamp, entry))
                except ValueError:
                    self.log_debug("Skipping malformed directory: %s", entry.name)
                    continue

        # Sort by timestamp (newest first)
        sessions.sort(reverse=True, key=lambda x: x[0])

        # Delete all except the keep_count newest
        deleted_count = 0
        for _, session_dir in sessions[keep_count:]:
            try:
                shutil.rmtree(session_dir)
                self.log_debug("Cleaned up old pytest session: %s", session_dir.name)
                deleted_count += 1
            except OSError as e:
                self.log_warning(
                    "Failed to cleanup pytest session %s: %s",
                    session_dir.name,
                    e,
                )

        if deleted_count > 0:
            self.log_debug(
                "Cleaned up %d old pytest session(s) in %s",
                deleted_count,
                base_dir,
            )

        return deleted_count

    def cleanup_all_locations(self, keep_count: int = 10) -> dict[str, int]:
        """Cleanup old sessions across all log locations.

        Cleans up session directories in:
        - Local pytest-logs directory
        - Session-scoped container directories under .cache/container-data/{container}/

        Parameters
        ----------
        keep_count : int, optional
            Number of sessions to keep per location (default: 10)

        Returns
        -------
        dict[str, int]
            Mapping of location -> number of sessions deleted
        """
        # Skip cleanup when session logging is disabled
        if self.skip_session_logging:
            self.log_debug("Session logging disabled, skipping cleanup")
            return {}

        cleanup_results = {}

        # Clean local pytest-logs
        local_deleted = self.cleanup_old_sessions(self.base_log_dir, keep_count)
        if local_deleted > 0:
            cleanup_results["local"] = local_deleted

        # Clean container session directories
        # Structure: .cache/container-data/{container}/{session-id}/
        if self.container_cache_dir.exists():
            for container_dir in self.container_cache_dir.iterdir():
                if not container_dir.is_dir():
                    continue

                # Clean session-scoped directories directly under container
                # These contain session-id directories like "mcp-20251108-143022"
                deleted = self.cleanup_old_sessions(container_dir, keep_count)
                if deleted > 0:
                    cleanup_results[f"container:{container_dir.name}"] = deleted

        return cleanup_results
