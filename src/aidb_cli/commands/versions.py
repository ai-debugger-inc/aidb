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
    """Display all version information from versions.json.

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

    \b Checks that versions.json has all required sections and fields.
    """  # noqa: W605
    cli_output = ctx.obj.output
    aidb_ctx: Context = ctx.obj
    results = aidb_ctx.config_manager.validate_versions()

    all_valid = all(results.values())

    cli_output.section("Version Configuration Validation", Icons.CHECK)

    for section, is_valid in results.items():
        if is_valid:
            cli_output.success(section.capitalize())
        else:
            cli_output.error(section.capitalize(), to_stderr=False)

    cli_output.plain("")
    if all_valid:
        cli_output.success("All version configurations are valid!")
    else:
        cli_output.error("Some version configurations are missing or invalid.")
        cli_output.plain("Check versions.json for missing sections.")
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
    """Display Docker build arguments derived from versions.json.

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

    \b Validates that version defaults in Dockerfiles and docker-compose.yaml match the
    values defined in versions.json.
    """  # noqa: W605
    from aidb_cli.services.version import VersionConsistencyService

    cli_output = ctx.obj.output
    aidb_ctx: Context = ctx.obj

    cli_output.section("Version Consistency Check", Icons.CHECK)

    service = VersionConsistencyService(aidb_ctx.repo_root)
    report = service.check_all()

    # Group mismatches by file
    files_with_issues: dict[str, list] = {}
    for mismatch in report.mismatches:
        if mismatch.file not in files_with_issues:
            files_with_issues[mismatch.file] = []
        files_with_issues[mismatch.file].append(mismatch)

    # Display results for each file
    for file_path in report.files_checked:
        cli_output.plain(f"\nChecking {file_path}...")

        if file_path in files_with_issues:
            for mismatch in files_with_issues[file_path]:
                if mismatch.severity == "warning":
                    cli_output.warning(f"  {mismatch.message}")
                else:
                    cli_output.error(f"  {mismatch.message}", to_stderr=False)
                cli_output.plain(f"      at line {mismatch.line}")
        else:
            cli_output.success("  All versions match")

    # Summary
    cli_output.plain("")
    if report.error_count == 0 and report.warning_count == 0:
        cli_output.success("Version consistency check passed!")
    else:
        parts = []
        if report.error_count > 0:
            parts.append(f"{report.error_count} mismatch(es)")
        if report.warning_count > 0:
            parts.append(f"{report.warning_count} warning(s)")
        cli_output.plain(f"Summary: {', '.join(parts)}")

        if report.has_errors:
            cli_output.error("Version inconsistencies detected!")
            cli_output.plain("Update the file defaults to match versions.json.")
            ctx.exit(ExitCode.GENERAL_ERROR)


@group.command(name="info")
@click.argument("language", type=LanguageParamType(), required=False, default=None)
@click.pass_context
@handle_exceptions
def adapter_info(ctx: click.Context, language: str | None) -> None:
    """Show version information for adapters.

    \b Displays the configured version and download information for the specified
    language adapter. If no language is provided, shows info for all adapters.
    """  # noqa: W605
    cli_output = ctx.obj.output
    aidb_ctx: Context = ctx.obj

    supported = aidb_ctx.build_manager.get_supported_languages()

    if language is not None:
        if language not in supported:
            cli_output.error(f"Unsupported language: {language}")
            cli_output.plain(f"Supported languages: {', '.join(supported)}")
            ctx.exit(1)
        languages = [language]
    else:
        languages = sorted(supported)

    for lang in languages:
        _display_adapter_info(cli_output, aidb_ctx, lang)


def _display_adapter_info(cli_output, aidb_ctx: "Context", language: str) -> None:
    """Display version information for a single adapter."""
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

    if info.get("version"):
        cli_output.plain(f"Installed Version: {info['version']}")

    if info.get("path"):
        cli_output.plain(f"Path: {info['path']}")
