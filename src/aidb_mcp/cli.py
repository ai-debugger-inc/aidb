"""AIDB MCP Server CLI.

Designed to be spawned as a subprocess by Claude CLI or other MCP clients.
Communicates over stdio - stdin for requests, stdout for responses.

Set `AIDB_LOG_LEVEL=DEBUG` to enable verbose debug logs for all AIDB components.
Set `AIDB_MCP_LOG_LEVEL=DEBUG` to enable verbose debug logs for MCP only.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys

from aidb_common.config import config
from aidb_logging import get_mcp_logger as get_logger
from aidb_logging import setup_root_logger

from .server.app import AidbMCPServer


def _setup_logging(verbose: bool = False) -> None:
    # Check MCP-specific log level first, then fall back to global AIDB_LOG_LEVEL
    mcp_level = config.get_mcp_log_level().upper()
    global_level = config.get_log_level().upper()

    # MCP-specific takes precedence if set
    if mcp_level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
        level = getattr(logging, mcp_level)
        log_source = "mcp_environment"
    elif global_level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
        level = getattr(logging, global_level)
        log_source = "global_environment"
    else:
        level = logging.DEBUG if verbose else logging.INFO
        log_source = "verbose_flag" if verbose else "default"

    setup_root_logger("mcp")
    logging.getLogger("aidb_mcp").setLevel(level)

    logger = get_logger(__name__)
    logger.info(
        "Logging configured",
        extra={
            "level": logging.getLevelName(level),
            "source": log_source,
            "mcp_level": mcp_level or None,
            "global_level": global_level or None,
            "verbose_flag": verbose,
        },
    )


async def _run_server(verbose: bool = False) -> None:
    _setup_logging(verbose)
    log = get_logger(__name__)
    log.info(
        "Starting AIDB MCP Server (subprocess mode)",
        extra={
            "python_version": (
                f"{sys.version_info.major}.{sys.version_info.minor}."
                f"{sys.version_info.micro}"
            ),
            "platform": sys.platform,
            "verbose": verbose,
            "mode": "subprocess",
        },
    )

    srv = AidbMCPServer()
    try:
        await srv.run()
        log.info("MCP Server shut down")
    except (asyncio.CancelledError, EOFError):
        # Normal shutdown when parent closes stdin
        log.info("Parent process disconnected, shutting down")
    except Exception as e:
        log.exception(
            "MCP Server encountered an error",
            extra={"error": str(e)},
        )
        raise


# Global flag for clean shutdown
_shutdown_requested = False


def main() -> None:
    """Run the AIDB MCP server CLI in subprocess mode."""
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "AIDB MCP Server (subprocess mode): Designed to be spawned by "
            "Claude CLI or other MCP clients. Communicates over stdio."
        ),
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logs")
    args = parser.parse_args()

    logger = get_logger(__name__)

    # Install signal handlers BEFORE asyncio.run() to ensure clean exit
    def handle_signal(sig, _frame):
        global _shutdown_requested
        if not _shutdown_requested:
            _shutdown_requested = True
            logger.info("Received signal %s, initiating graceful shutdown", sig)
            # Use os._exit() to force immediate termination with code 0
            # sys.exit() doesn't work properly inside signal handlers with asyncio
            os._exit(0)

    # Register handlers before asyncio takes over
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    try:
        logger.debug("CLI starting in subprocess mode", extra={"cli_args": vars(args)})
        asyncio.run(_run_server(args.verbose))
    except SystemExit as e:
        # Clean shutdown from signal handler
        if e.code == 0:
            logger.info("Clean shutdown")
        sys.exit(e.code)
    except (KeyboardInterrupt, EOFError):
        # Normal shutdown - parent closed connection
        logger.info("Connection closed, shutting down")
        sys.exit(0)
    except Exception as e:
        logger.exception("Unexpected error in main %s", extra={"error": str(e)})
        sys.exit(1)


if __name__ == "__main__":
    main()
