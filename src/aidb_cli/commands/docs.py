"""Documentation commands for AIDB CLI."""

import click

from aidb.common.errors import AidbError
from aidb_cli.core.constants import Icons
from aidb_cli.core.decorators import handle_exceptions
from aidb_cli.services.docs.docs_builder_service import DocsBuilderService
from aidb_cli.services.docs.docs_server_service import DocsServerService
from aidb_logging import get_cli_logger

logger = get_cli_logger(__name__)


@click.group(name="docs")
@click.pass_context
def group(ctx: click.Context) -> None:
    """Documentation building and serving commands."""


@group.command()
@click.pass_context
@handle_exceptions
def build(ctx: click.Context) -> None:
    """Build documentation (public site) via Docker compose.

    Always rebuilds the Docker image to ensure dependencies are up-to-date.
    """
    output = ctx.obj.output
    output.section("Building Documentation", Icons.BUILD)

    builder = DocsBuilderService(ctx.obj.repo_root, ctx.obj.command_executor)
    try:
        builder.build_docs(DocsBuilderService.PUBLIC, rebuild=True)
        output.success("Docs built successfully")
    except AidbError as e:
        if ctx.obj.verbose:
            output.plain(f"Build failed: {e}")
        msg = "Documentation build failed"
        raise AidbError(msg) from e
    except FileNotFoundError:
        output.error("Docker or docker-compose not found")
        raise
    except Exception as e:
        msg = f"Error building docs: {e}"
        raise AidbError(msg) from e


@group.command()
@click.option("--port", "-p", type=int, help="Port to serve on")
@click.option("--build-first", is_flag=True, help="Build docs before serving")
@click.pass_context
@handle_exceptions
def serve(ctx: click.Context, port: int | None, build_first: bool) -> None:
    """Serve documentation via Docker compose."""
    output = ctx.obj.output
    output.section("Starting Documentation Server", Icons.ROCKET)

    server = DocsServerService(ctx.obj.repo_root, ctx.obj.command_executor)
    server.serve_docs(DocsBuilderService.PUBLIC, port, build_first)

    final_port = port or DocsBuilderService.PUBLIC.default_port
    output.success(f"Docs server started at http://localhost:{final_port}")


@group.command()
@click.pass_context
@handle_exceptions
def stop(ctx: click.Context) -> None:
    """Stop documentation server via Docker compose."""
    output = ctx.obj.output
    output.section("Stopping Documentation Server", Icons.STOP)

    server = DocsServerService(ctx.obj.repo_root, ctx.obj.command_executor)
    try:
        server.stop_docs()
        output.success("Docs server stopped")
    except AidbError as e:
        output.error(f"Failed to stop docs: {e}")
        raise


@group.command()
@click.pass_context
@handle_exceptions
def status(ctx: click.Context) -> None:
    """Show status of documentation servers."""
    output = ctx.obj.output
    output.section("Documentation Server Status", Icons.INFO)

    server = DocsServerService(ctx.obj.repo_root, ctx.obj.command_executor)
    server.show_all_status()


@group.command(name="open")
@click.option("--port", "-p", type=int, help="Port if starting server")
@click.pass_context
@handle_exceptions
def open_docs(ctx: click.Context, port: int | None) -> None:
    """Open documentation in browser (starts if needed)."""
    server = DocsServerService(ctx.obj.repo_root, ctx.obj.command_executor)
    server.open_docs(DocsBuilderService.PUBLIC, port)


@group.command()
@click.option("--repl", is_flag=True, help="Start REPL after tests")
@click.pass_context
@handle_exceptions
def test(ctx: click.Context, repl: bool) -> None:
    """Run documentation tests via Docker compose."""
    output = ctx.obj.output
    output.section("Running Documentation Tests", Icons.TEST)

    builder = DocsBuilderService(ctx.obj.repo_root, ctx.obj.command_executor)
    try:
        cmd = [
            "docker",
            "compose",
            "-f",
            str(builder.compose_file),
            "run",
            "--rm",
            "aidb-docs-test",
        ]
        builder.command_executor.execute(cmd, cwd=builder.repo_root, check=True)
        output.success("Documentation tests passed")

        if repl:
            cmd.append("--repl")
            builder.command_executor.execute(cmd, cwd=builder.repo_root, check=False)
    except Exception as e:
        output.error(f"Documentation tests failed: {e}")
        raise
