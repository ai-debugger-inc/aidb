import asyncio
from pathlib import Path

import pytest


class FakeBridge:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.started = False
        self.stopped = False
        self.process = object()  # pretend running
        self.lsp_client = object()

    async def start(self, *args, **kwargs):
        self.started = True

    async def stop(self, *, force: bool = False):
        self.stopped = True


class StubCtx:
    def info(self, *args, **kwargs):
        pass

    def debug(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass


@pytest.mark.asyncio
async def test_per_project_pool_reuse_and_lru(tmp_path, monkeypatch):
    # Import module under test
    from aidb.adapters.lang.java import jdtls_project_pool as pool_mod

    # Patch bridge to a fake
    monkeypatch.setattr(pool_mod, "JavaLSPDAPBridge", FakeBridge)

    ctx = StubCtx()
    pool = pool_mod.JDTLSProjectPool(ctx=ctx, capacity=2)

    proj1 = tmp_path / "proj1"
    proj2 = tmp_path / "proj2"
    proj3 = tmp_path / "proj3"
    for p in (proj1, proj2, proj3):
        p.mkdir()

    # Start proj1
    b1 = await pool.get_or_start_bridge(
        project_path=proj1,
        project_name="p1",
        jdtls_path=Path("/opt/jdtls"),
        java_debug_jar=Path("/opt/java-debug.jar"),
    )
    assert isinstance(b1, FakeBridge)
    assert b1.started

    # Reuse proj1 (should not create new)
    b1_again = await pool.get_or_start_bridge(
        project_path=proj1,
        project_name="p1",
        jdtls_path=Path("/opt/jdtls"),
        java_debug_jar=Path("/opt/java-debug.jar"),
    )
    assert b1_again is b1

    # Add proj2 (capacity now full: proj1, proj2)
    b2 = await pool.get_or_start_bridge(
        project_path=proj2,
        project_name="p2",
        jdtls_path=Path("/opt/jdtls"),
        java_debug_jar=Path("/opt/java-debug.jar"),
    )
    assert isinstance(b2, FakeBridge)
    assert b2.started
    assert not b1.stopped

    # Access proj1 again to make it MRU
    b1_touch = await pool.get_or_start_bridge(
        project_path=proj1,
        project_name="p1",
        jdtls_path=Path("/opt/jdtls"),
        java_debug_jar=Path("/opt/java-debug.jar"),
    )
    assert b1_touch is b1

    # Add proj3 (should evict LRU -> proj2)
    b3 = await pool.get_or_start_bridge(
        project_path=proj3,
        project_name="p3",
        jdtls_path=Path("/opt/jdtls"),
        java_debug_jar=Path("/opt/java-debug.jar"),
    )
    assert isinstance(b3, FakeBridge)
    assert b3.started

    # proj2 should have been evicted and stopped
    assert b2.stopped is True

    # proj1 should still be active (not stopped)
    assert b1.stopped is False
