"""Shared utilities for JDT LS bridge lifecycle management.

This module provides cross-loop-safe utilities for terminating JDT LS bridge processes.
When event loops change (e.g., in pytest with auto mode), we cannot use await on
processes bound to the old loop. Instead, we poll the underlying subprocess
synchronously.
"""

import asyncio

from aidb.common.constants import POLL_SLEEP_INTERVAL_S, PROCESS_TERMINATE_TIMEOUT_S


async def terminate_bridge_process_safe(proc, ctx) -> None:
    """Terminate JDT LS bridge process gracefully (cross-loop safe).

    Cannot use await proc.wait() because the process may be attached to an old,
    closed event loop. Instead, we poll the underlying Popen process synchronously.

    Parameters
    ----------
    proc : asyncio.subprocess.Process
        The JDT LS process to terminate
    ctx : Context
        Logging context for debug/warning messages
    """
    if not proc or proc.returncode is not None:
        return

    proc.terminate()

    # Poll for graceful termination without awaiting on the old loop
    import time as sync_time

    timeout_at = sync_time.time() + PROCESS_TERMINATE_TIMEOUT_S
    popen = getattr(proc, "_transport", None)
    if popen:
        popen = popen.get_extra_info("subprocess")

    while sync_time.time() < timeout_at:
        # Check returncode via Popen if available
        if popen and popen.poll() is not None:
            ctx.debug("Terminated JDT LS process from old event loop")
            break
        if proc.returncode is not None:
            ctx.debug("JDT LS process terminated (returncode check)")
            break
        await asyncio.sleep(POLL_SLEEP_INTERVAL_S)
    else:
        # Timeout - force kill
        ctx.warning("JDT LS didn't terminate gracefully, force-killing")
        proc.kill()
        await asyncio.sleep(POLL_SLEEP_INTERVAL_S)
