"""Orphan process detection and cleanup for AIDB.

This module provides utilities to detect and clean up orphaned AIDB processes based on
environment variable tagging. This provides defense-in-depth protection against process
leaks when normal session cleanup fails.
"""

import time

import psutil

from aidb.common.constants import DEFAULT_WAIT_TIMEOUT_S, PROCESS_TERMINATE_TIMEOUT_S
from aidb.resources.process_tags import ProcessTags
from aidb_logging import get_logger

logger = get_logger(__name__)


class OrphanProcessCleaner:
    """Detects and cleans up orphaned AIDB processes.

    Uses environment variable markers (AIDB_OWNER, AIDB_SESSION_ID, etc.) to safely
    identify AIDB-spawned processes and determine which are orphaned (no longer
    associated with an active session).

    Safety features:
    - Only targets processes with AIDB_OWNER=aidb
    - Cross-references with active sessions
    - Age threshold prevents killing newly-started processes
    - Graceful termination with SIGKILL escalation
    """

    def __init__(
        self,
        min_age_seconds: float = 60.0,
        ctx: object | None = None,
    ):
        """Initialize the orphan process cleaner.

        Parameters
        ----------
        min_age_seconds : float, optional
            Minimum age in seconds for a process to be considered orphaned.
            This prevents race conditions with newly-started processes.
            Default: 60 seconds
        ctx : optional
            Context for logging (if None, uses module logger)
        """
        self.min_age_seconds = min_age_seconds
        self.ctx = ctx
        self._log_trace = (
            ctx.trace
            if ctx and hasattr(ctx, "trace")
            else (
                lambda msg: logger.log(5, msg)  # TRACE level = 5
            )
        )
        self._log = ctx.debug if ctx and hasattr(ctx, "debug") else logger.debug
        self._log_info = ctx.info if ctx and hasattr(ctx, "info") else logger.info
        self._log_warning = (
            ctx.warning if ctx and hasattr(ctx, "warning") else logger.warning
        )
        self._log_error = ctx.error if ctx and hasattr(ctx, "error") else logger.error

    def find_orphaned_processes(
        self,
        active_session_ids: set[str] | None = None,
    ) -> list[psutil.Process]:
        """Find orphaned AIDB processes.

        A process is considered orphaned if ALL conditions are met:
        1. It has AIDB_OWNER=aidb env var (identifies as AIDB-owned)
        2. Its AIDB_SESSION_ID is NOT in active_session_ids (session ended)
        3. It has been running for > min_age_seconds (prevents race conditions)

        CRITICAL: This method ALWAYS checks active sessions before marking a process
        as orphaned. Even if a process is >60s old, it will NOT be killed if its
        session is still active (e.g., waiting at a breakpoint).

        Example scenario:
        - Session A launches at t=0, hits breakpoint at t=5, waits
        - Session B launches at t=70 (triggers orphan cleanup)
        - Session A's processes are >60s old BUT session_id is in active_session_ids
        - Result: Session A's processes are SKIPPED (protected)

        Parameters
        ----------
        active_session_ids : Optional[Set[str]]
            Set of active session IDs. If None, fetches from SessionRegistry

        Returns
        -------
        List[psutil.Process]
            List of orphaned processes (session ended + age > threshold)
        """
        if active_session_ids is None:
            active_session_ids = self._get_active_session_ids()

        orphans = []
        current_time = time.time()
        pool_resource_count = 0

        n_active = len(active_session_ids)
        self._log_trace(f"Scanning for orphans (active sessions: {n_active})")

        for proc in psutil.process_iter(["pid", "name", "cmdline", "create_time"]):
            try:
                # Get process environment variables
                env = proc.environ()

                # Check if it's an AIDB-owned process
                if env.get(ProcessTags.OWNER) != ProcessTags.OWNER_VALUE:
                    continue

                # Skip pool resources (test infrastructure that persists across tests)
                if env.get(ProcessTags.IS_POOL_RESOURCE) == "true":
                    pool_resource_count += 1
                    continue

                # Extract session ID
                session_id = env.get(ProcessTags.SESSION_ID)
                if not session_id:
                    self._log(
                        f"Process {proc.pid} has AIDB_OWNER but no SESSION_ID "
                        "- skipping",
                    )
                    continue

                # CRITICAL SAFETY CHECK: Verify session is not active
                # This prevents killing processes from sessions that are still running
                # (e.g., waiting at a breakpoint for >60s)
                if session_id in active_session_ids:
                    process_type = env.get(ProcessTags.PROCESS_TYPE, "unknown")
                    self._log(
                        f"Process {proc.pid} (session={session_id}, "
                        f"type={process_type}) belongs to ACTIVE session - skipping",
                    )
                    continue

                # Check age threshold
                process_age = current_time - proc.info["create_time"]
                if process_age < self.min_age_seconds:
                    self._log(
                        f"Process {proc.pid} (session={session_id}) is too young "
                        f"({process_age:.1f}s < {self.min_age_seconds}s) - skipping",
                    )
                    continue

                # This is an orphan!
                process_type = env.get(ProcessTags.PROCESS_TYPE, "unknown")
                language = env.get(ProcessTags.LANGUAGE, "unknown")
                self._log(
                    f"Found orphaned process: PID={proc.pid}, session={session_id}, "
                    f"type={process_type}, language={language}, age={process_age:.1f}s",
                )
                orphans.append(proc)

            except (psutil.NoSuchProcess, psutil.AccessDenied, PermissionError):
                # Process disappeared or we can't access it - skip it
                continue
            except Exception as e:
                # Unexpected error - log but continue scanning
                self._log_warning(f"Unexpected error inspecting process: {e}")
                continue

        # Log pool resource summary at TRACE level
        if pool_resource_count > 0:
            self._log_trace(f"Skipped {pool_resource_count} pool resources")

        # Only log if orphans were found
        if len(orphans) > 0:
            self._log(f"Found {len(orphans)} orphaned processes")

        return orphans

    def cleanup_orphaned_processes(
        self,
        active_session_ids: set[str] | None = None,
    ) -> tuple[int, int]:
        """Find and terminate orphaned AIDB processes.

        Parameters
        ----------
        active_session_ids : Optional[Set[str]]
            Set of active session IDs. If None, fetches from SessionRegistry

        Returns
        -------
        Tuple[int, int]
            (terminated_count, failed_count)
        """
        orphans = self.find_orphaned_processes(active_session_ids)

        if not orphans:
            return (0, 0)

        self._log_info(f"Cleaning up {len(orphans)} orphaned processes...")

        terminated = 0
        failed = 0

        for proc in orphans:
            try:
                # Get process info for logging
                try:
                    env = proc.environ()
                    session_id = env.get(ProcessTags.SESSION_ID, "unknown")
                    process_type = env.get(ProcessTags.PROCESS_TYPE, "unknown")
                except Exception:
                    session_id = "unknown"
                    process_type = "unknown"

                # Terminate gracefully first
                self._log_info(
                    f"Terminating orphaned process PID={proc.pid} "
                    f"(session={session_id}, type={process_type})",
                )
                proc.terminate()

                # Wait for graceful termination
                try:
                    proc.wait(timeout=DEFAULT_WAIT_TIMEOUT_S)
                    self._log(f"Process {proc.pid} terminated gracefully")
                    terminated += 1
                except psutil.TimeoutExpired:
                    # Force kill if still running
                    self._log_warning(
                        f"Process {proc.pid} did not terminate gracefully, "
                        "force killing",
                    )
                    proc.kill()
                    try:
                        proc.wait(timeout=PROCESS_TERMINATE_TIMEOUT_S)
                        self._log(f"Process {proc.pid} force killed")
                        terminated += 1
                    except psutil.TimeoutExpired:
                        self._log_error(
                            f"Process {proc.pid} could not be killed "
                            "(may be in uninterruptible state)",
                        )
                        failed += 1

            except psutil.NoSuchProcess:
                # Process already terminated - count as success
                self._log(
                    f"Process {getattr(proc, 'pid', 'unknown')} already terminated",
                )
                terminated += 1
            except psutil.AccessDenied as e:
                self._log_error(f"Access denied terminating process {proc.pid}: {e}")
                failed += 1
            except Exception as e:
                self._log_error(
                    f"Error terminating process {getattr(proc, 'pid', 'unknown')}: {e}",
                )
                failed += 1

        self._log_info(
            f"Orphan cleanup complete: {terminated} terminated, {failed} failed",
        )
        return (terminated, failed)

    def _get_active_session_ids(self) -> set[str]:
        """Get set of active session IDs from SessionRegistry.

        Returns
        -------
        Set[str]
            Set of active session IDs
        """
        try:
            from aidb.session.registry import SessionRegistry

            registry = SessionRegistry()
            sessions = registry.get_all_sessions()
            active_ids = {session.id for session in sessions}
            self._log(f"Found {len(active_ids)} active sessions in registry")
            return active_ids
        except Exception as e:
            self._log_error(f"Failed to get active sessions from registry: {e}")
            return set()
