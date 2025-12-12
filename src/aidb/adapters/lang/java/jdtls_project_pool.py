"""Per-project JDT LS pooling with LRU eviction.

This module manages a pool of Eclipse JDT LS instances keyed by project path. Each
unique Maven/Gradle project gets its own dedicated JDT LS process, which is reused
across sessions for that project. The pool enforces an LRU eviction policy to bound
memory usage.
"""

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from aidb.interfaces import IContext

from aidb.adapters.lang.java.lsp.bridge_cleanup import terminate_bridge_process_safe
from aidb.adapters.lang.java.lsp.lsp_bridge import JavaLSPDAPBridge
from aidb.resources.process_tags import ProcessTags


@dataclass
class _PoolEntry:
    key: str
    bridge: JavaLSPDAPBridge
    last_used: float
    loop_id: int  # id(loop) when bridge was created


class JDTLSProjectPool:
    """LRU pool of JDT LS instances keyed by project path."""

    def __init__(self, ctx: IContext, capacity: int = 5):
        self.ctx = ctx
        self.capacity = max(1, int(capacity))
        self._entries: OrderedDict[str, _PoolEntry] = OrderedDict()
        self._lock = asyncio.Lock()
        self._created = 0
        self._evicted = 0

    def _make_key(self, project_path: Path) -> str:
        try:
            return str(project_path.resolve())
        except Exception:
            return str(project_path)

    async def get_or_start_bridge(
        self,
        *,
        project_path: Path,
        project_name: str,
        jdtls_path: Path,
        java_debug_jar: Path,
        java_command: str = "java",
        workspace_folders: list[tuple[Path, str]] | None = None,
    ) -> JavaLSPDAPBridge:
        """Get an existing bridge for project or start a new one.

        Starts JDT LS with workspaceFolders during initialize for correctness.

        Handles event loop changes (common in pytest with asyncio_mode="auto"):
        - If current loop matches stored loop: reuse bridge (fast)
        - If current loop differs from stored loop: restart bridge (safe)
        """
        key = self._make_key(project_path)
        self.ctx.debug(
            f"[POOL] Looking up project: {project_name} at {project_path}",
        )
        self.ctx.debug(f"[POOL] Pool key: {key}")
        self.ctx.debug(f"[POOL] Current pool entries: {list(self._entries.keys())}")

        async with self._lock:
            # Check for existing entry
            if key in self._entries:
                self.ctx.debug(f"[POOL] Cache HIT for {key}")
                entry = self._entries.pop(key)
                current_loop = asyncio.get_event_loop()
                current_loop_id = id(current_loop)

                # Detect event loop mismatch (happens in pytest with auto mode)
                if current_loop_id != entry.loop_id:
                    self.ctx.warning(
                        f"Event loop mismatch for {project_name}: "
                        f"stored={entry.loop_id}, current={current_loop_id}. "
                        f"Restarting bridge on new loop (common in tests).",
                    )
                    # Don't call bridge.stop() - its LSP streams are bound to the old
                    # (now closed) event loop. Calling stop() would fail with
                    # "Event loop is closed" when trying to send shutdown messages.
                    # Instead, terminate the process directly.
                    try:
                        await terminate_bridge_process_safe(
                            entry.bridge.process,
                            self.ctx,
                        )
                    except Exception as e:
                        self.ctx.warning(f"Error terminating old bridge: {e}")

                    # Fall through to create fresh bridge on current loop
                    # (This is safer than trying to rebind asyncio subprocess streams)
                else:
                    # Same loop - safe to reuse without restarting
                    entry.last_used = time.time()
                    self._entries[key] = entry
                    self.ctx.info(
                        f"[POOL] Reusing JDT LS for project: {project_name} "
                        f"({project_path}) on loop {current_loop_id} - saved ~10s!",
                    )
                    # Log lightweight stats on reuse
                    self.ctx.info(f"[POOL] Pool stats: {self.get_pool_stats()}")
                    return entry.bridge

            # Create new bridge
            self.ctx.debug(f"[POOL] Cache MISS for {key} - creating new bridge")
            bridge = JavaLSPDAPBridge(
                jdtls_path=jdtls_path,
                java_debug_jar=java_debug_jar,
                java_command=java_command,
                ctx=self.ctx,
            )
            # Set _is_pooled flag - SINGLE SOURCE OF TRUTH for pool detection.
            # Check via bridge.is_pooled() rather than:
            # - Querying pool registries (expensive)
            # - Checking bridge.process state (ambiguous)
            # Flag propagates to children (debug_session_manager, lsp_client).
            bridge._is_pooled = True

            self.ctx.info(
                f"Starting JDT LS for project: {project_name} ({project_path})",
            )
            await bridge.start(
                project_root=project_path,
                session_id=f"jdtls-project-{project_name}",
                extra_env={
                    ProcessTags.IS_POOL_RESOURCE: "true",
                },
                workspace_folders=workspace_folders,
            )

            # Capture current event loop ID for this bridge
            current_loop = asyncio.get_event_loop()
            current_loop_id = id(current_loop)

            # Insert and mark as most-recently used
            self._entries[key] = _PoolEntry(
                key=key,
                bridge=bridge,
                last_used=time.time(),
                loop_id=current_loop_id,  # Track which loop created this bridge
            )
            self._created += 1
            stats = self.get_pool_stats()
            self.ctx.info(
                f"JDTLSProjectPool created on loop {current_loop_id} -> {stats}",
            )

            # Evict if over capacity
            await self._evict_if_needed(skip_key=key)

            return bridge

    async def _evict_if_needed(self, *, skip_key: str | None = None) -> None:
        while len(self._entries) > self.capacity:
            # Pop least-recently used
            old_key, entry = next(iter(self._entries.items()))
            if skip_key and old_key == skip_key:
                # Move current and continue
                self._entries.move_to_end(old_key)
                continue

            self._entries.pop(old_key)
            try:
                self.ctx.info(f"Evicting JDT LS for project: {old_key}")
                await entry.bridge.stop(force=True)
            except Exception as e:
                self.ctx.warning(f"Error stopping evicted JDT LS ({old_key}): {e}")
            finally:
                self._evicted += 1
                self.ctx.info(f"JDTLSProjectPool evicted -> {self.get_pool_stats()}")

    async def shutdown(self) -> None:
        """Shut down all pooled JDT LS instances."""
        async with self._lock:
            while self._entries:
                _key, entry = self._entries.popitem(last=False)
                try:
                    await entry.bridge.stop()
                except Exception as e:
                    self.ctx.warning(f"Error stopping JDT LS during shutdown: {e}")

    def get_pool_stats(self) -> dict[str, Any]:
        """Return current pool statistics including event loop tracking."""
        projects = [Path(k).name for k in self._entries]
        # Get current loop ID for comparison
        try:
            current_loop_id = id(asyncio.get_event_loop())
        except RuntimeError:
            current_loop_id = None

        # Count entries on current vs different loops
        same_loop_count = 0
        diff_loop_count = 0
        for entry in self._entries.values():
            if current_loop_id and entry.loop_id == current_loop_id:
                same_loop_count += 1
            else:
                diff_loop_count += 1

        return {
            "capacity": self.capacity,
            "active": len(self._entries),
            "created": self._created,
            "evicted": self._evicted,
            "projects": projects,
            "current_loop_id": current_loop_id,
            "same_loop_count": same_loop_count,
            "diff_loop_count": diff_loop_count,
        }


# Process-wide singleton accessors
_project_pool: JDTLSProjectPool | None = None
_project_pool_lock = asyncio.Lock()


async def get_jdtls_project_pool(
    ctx: IContext,
    capacity: int | None = None,
) -> JDTLSProjectPool:
    """Get or create the process-wide JDT LS project pool.

    Parameters
    ----------
    ctx : IContext
        Context for logging
    capacity : int, optional
        Maximum pool size (default from config)

    Returns
    -------
    JDTLSProjectPool
        The singleton pool instance
    """
    global _project_pool
    async with _project_pool_lock:
        if _project_pool is None:
            from aidb_common.config import config

            cap = capacity if capacity is not None else config.get_java_lsp_pool_max()
            _project_pool = JDTLSProjectPool(ctx=ctx, capacity=cap)
            ctx.info(
                f"Created per-project JDT LS pool (capacity={_project_pool.capacity})",
            )
        return _project_pool


async def shutdown_jdtls_project_pool() -> None:
    """Shut down the per-project JDT LS pool if initialized."""
    global _project_pool
    async with _project_pool_lock:
        if _project_pool:
            await _project_pool.shutdown()
            _project_pool = None


def get_jdtls_project_pool_sync() -> JDTLSProjectPool | None:
    """Get the pool instance synchronously (if initialized).

    Returns
    -------
    JDTLSProjectPool, optional
        Pool instance if initialized, None otherwise
    """
    return _project_pool
