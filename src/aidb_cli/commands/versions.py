"""Version management commands for AIDB CLI."""

from typing import TYPE_CHECKING

import click

from aidb_cli.core.constants import ExitCode, Icons
from aidb_cli.core.decorators import handle_exceptions
from aidb_cli.core.param_types import LanguageParamType

if TYPE_CHECKING:
    from aidb_cli.cli import Context


@click.group(name="versions")
@click.pass_context
def group(ctx: click.Context) -> None:
    """Manage and display version information."""


@group.command(name="show")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["text", "json", "yaml", "env"]),
    default="text",
    help="Output format for version information",
)
@click.pass_context
@handle_exceptions
def show_versions(ctx: click.Context, fmt: str) -> None:
    """Display all version information from versions.yaml.

    \b This shows the current versions for infrastructure (Python, Node, Java),
    adapters, and runtime requirements.
    """  # noqa: W605
    cli_output = ctx.obj.output
    cli_output.section("Version Information", Icons.PACKAGE)

    aidb_ctx: Context = ctx.obj
    version_output = aidb_ctx.config_manager.get_versions(fmt)
    cli_output.plain(version_output)


@group.command(name="validate")
@click.pass_context
@handle_exceptions
def validate_versions(ctx: click.Context) -> None:
    """Validate that all required version fields are present.

    \b Checks that versions.yaml has all required sections and fields.
    """  # noqa: W605
    cli_output = ctx.obj.output
    aidb_ctx: Context = ctx.obj
    results = aidb_ctx.config_manager.validate_versions()

    all_valid = all(results.values())

    cli_output.section("Version Configuration Validation", Icons.CHECK)

    for section, is_valid in results.items():
        icon = f"{Icons.SUCCESS}" if is_valid else f"{Icons.ERROR}"
        cli_output.plain(f"{icon} {section.capitalize()}")

    cli_output.plain("")
    if all_valid:
        cli_output.success("All version configurations are valid!")
    else:
        cli_output.error("Some version configurations are missing or invalid.")
        cli_output.plain("Check versions.yaml for missing sections.")
        ctx.exit(ExitCode.GENERAL_ERROR)


@group.command(name="docker")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["text", "json", "env"]),
    default="text",
    help="Output format for Docker build args",
)
@click.pass_context
@handle_exceptions
def docker_versions(ctx: click.Context, fmt: str) -> None:
    """Display Docker build arguments derived from versions.yaml.

    \b Shows the exact build arguments that will be used for Docker builds.
    """  # noqa: W605
    cli_output = ctx.obj.output
    aidb_ctx: Context = ctx.obj
    build_args = aidb_ctx.config_manager.get_docker_build_args()

    if fmt == "json":
        import json

        cli_output.plain(json.dumps(build_args, indent=2))
    elif fmt == "env":
        for key, value in build_args.items():
            cli_output.plain(f"export {key}={value}")
    else:  # text
        cli_output.section("Docker Build Arguments", Icons.BUILD)
        for key, value in sorted(build_args.items()):
            cli_output.plain(f"{key:25s} = {value}")


@group.command(name="check-consistency")
@click.pass_context
@handle_exceptions
def check_consistency(ctx: click.Context) -> None:
    """Check version consistency across Docker files.

    \b Runs the validation script to ensure versions in Dockerfiles and docker-
    compose.yaml match versions.yaml.
    """  # noqa: W605
    cli_output = ctx.obj.output
    cli_output.section("Version Consistency Check", Icons.CHECK)

    aidb_ctx: Context = ctx.obj

    validation_script = aidb_ctx.repo_root / "scripts/utils/validate_docker_versions.py"

    if not validation_script.exists():
        cli_output.error("Validation script not found at:")
        cli_output.plain(f"   {validation_script}")
        return

    result = ctx.obj.command_executor.execute(
        ["python", str(validation_script)],
        cwd=aidb_ctx.repo_root,
        check=False,
        verbose=ctx.obj.verbose,
        verbose_debug=ctx.obj.verbose_debug,
    )

    if result.returncode == 0:
        cli_output.success("\nVersion check passed!")
    else:
        cli_output.error("\nVersion inconsistencies detected!")
        cli_output.plain("Run './dev-cli versions show' to see the expected versions.")
        ctx.exit(ExitCode.GENERAL_ERROR)


@group.command(name="info")
@click.argument("language", type=LanguageParamType())
@click.pass_context
@handle_exceptions
def adapter_info(ctx: click.Context, language: str) -> None:
    """Show version information for a specific adapter.

    \b Displays the configured version and download information for the specified
    language adapter.
    """  # noqa: W605
    cli_output = ctx.obj.output
    aidb_ctx: Context = ctx.obj

    supported = aidb_ctx.build_manager.get_supported_languages()
    if language not in supported:
        cli_output.error(f"Unsupported language: {language}")
        cli_output.plain(f"Supported languages: {', '.join(supported)}")
        ctx.exit(1)

    version = aidb_ctx.config_manager.get_adapter_version(language)
    info = aidb_ctx.build_manager.get_adapter_info(language)

    cli_output.section(
        f"{language.capitalize()} Adapter Information",
        Icons.PACKAGE,
    )

    if version:
        cli_output.plain(f"Configured Version: {version}")
    else:
        cli_output.plain("Configured Version: Not configured")

    cli_output.plain(f"Build Status: {info['status']}")
    cli_output.plain(f"Type: {info['type']}")

    if info.get("version") and info["version"] != "not installed":
        cli_output.plain(f"Installed Version: {info['version']}")

    if info.get("location") and info["location"] != "not installed":
        cli_output.plain(f"Location: {info['location']}")
