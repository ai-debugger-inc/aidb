"""CLI entrypoint for AIDB MCP server."""

from __future__ import annotations

import asyncio
import sys

from aidb_logging import get_mcp_logger as get_logger
from aidb_mcp.server.app import AidbMCPServer

logger = get_logger(__name__)


def _print_help() -> None:
    help_text = (
        "AIDB MCP Server\n\n"
        "Usage:\n"
        "  python -m aidb_mcp [options]\n\n"
        "Options:\n"
        "  -h, --help     Show this message and exit\n"
    )
    print(help_text)


def _maybe_handle_cli_flags() -> None:
    args = sys.argv[1:]
    if any(arg in ("-h", "--help") for arg in args):
        _print_help()
        raise SystemExit(0)


async def _async_main() -> None:
    _maybe_handle_cli_flags()
    server = AidbMCPServer()

    try:
        await server.run()
    except asyncio.CancelledError:
        logger.info("Server shutting down")
    except Exception as e:
        logger.exception("Server crashed with error: %s", e)
        raise
    finally:
        try:
            # Cleanly shutdown per-project JDT LS pool
            from aidb.adapters.lang.java.jdtls_project_pool import (
                shutdown_jdtls_project_pool,
            )

            await shutdown_jdtls_project_pool()
        except Exception as e:  # pragma: no cover - defensive cleanup
            logger.debug("JDT LS project pool shutdown skipped: %s", e)
        logger.info("Server shutdown complete")


def main() -> None:
    """Run the MCP server."""
    asyncio.run(_async_main())
