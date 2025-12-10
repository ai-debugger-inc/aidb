"""Docker commands for AIDB CLI.

Handles Docker-based testing, building, and management operations.
"""

from pathlib import Path

import click

from aidb_cli.core.constants import Icons
from aidb_cli.core.decorators import handle_exceptions
from aidb_cli.core.param_types import (
    DockerProfileParamType,
)
from aidb_logging import get_cli_logger

logger = get_cli_logger(__name__)


@click.group(name="docker")
@click.pass_context
def group(ctx: click.Context) -> None:
    """Docker infrastructure management.

    \b Commands for building images and managing Docker resources. For running tests,
    use './dev-cli test run' which handles Docker automatically.
    """  # noqa: W605
    # Managers are singletons available through context


"""
Dynamic choices for suites, languages, and profiles are provided by
`aidb_cli.param_types` with shell completion. This removes static lists
and brittle compose text scanning.
"""


@group.command()
@click.option(
    "--profile",
    "-p",
    type=DockerProfileParamType(),
    default=None,
    help="Docker profile to build (default: all profiles with deduplication)",
)
@click.option(
    "--no-cache",
    is_flag=True,
    help="Build without cache",
)
@click.option(
    "--check-rebuild",
    is_flag=True,
    help="Check what images need rebuilding without building",
)
@click.option(
    "--skip-rebuild-check",
    is_flag=True,
    help="Skip intelligent rebuild detection and build everything",
)
@click.pass_context
@handle_exceptions
def build(
    ctx: click.Context,
    profile: str | None,
    no_cache: bool,
    check_rebuild: bool,
    skip_rebuild_check: bool,
) -> None:
    """Build Docker images with intelligent rebuild detection.

    \b Builds the Docker images used for testing and development. By default, uses
    intelligent rebuild detection to only rebuild images when source files change.

    \b When no profile is specified, builds all profiles with automatic deduplication to
    avoid conflicts from shared images.

    \b Examples:   ./dev-cli docker build                    # Build only what changed
    ./dev-cli docker build --check-rebuild    # Check what needs rebuilding   ./dev-cli
    docker build --no-cache         # Force rebuild everything   ./dev-cli docker build
    -p python          # Build only Python profile
    """  # noqa: W605
    output = ctx.obj.output
    if check_rebuild:
        output.section("Checking Docker Image Rebuild Status", Icons.INFO)
    else:
        output.section("Building Docker Images", Icons.BUILD)

    # Use the new build service for consistent behavior
    from aidb_cli.services.docker.docker_build_service import DockerBuildService

    build_service = DockerBuildService(
        ctx.obj.repo_root,
        ctx.obj.command_executor,
        ctx.obj.resolved_env,
    )
    exit_code = build_service.build_images(
        profile=profile,
        no_cache=no_cache,
        verbose=ctx.obj.verbose,
        auto_rebuild=not skip_rebuild_check,
        check_only=check_rebuild,
    )

    if exit_code != 0:
        ctx.exit(exit_code)


@group.command(name="build-base")
@click.option(
    "--tag",
    "-t",
    default="latest",
    help="Tag for the base test image (default: latest)",
)
@click.option(
    "--no-cache",
    is_flag=True,
    help="Build without cache",
)
@click.pass_context
@handle_exceptions
def build_base(ctx: click.Context, tag: str, no_cache: bool) -> None:
    """Build the base test image used by language-specific images.

    \b This builds src/tests/_docker/dockerfiles/Dockerfile.test.base and tags it as
    aidb-test-base:<tag>.
    """  # noqa: W605
    output = ctx.obj.output
    output.section("Building Base Test Image", Icons.BUILD)

    from aidb_cli.services.docker.docker_build_service import DockerBuildService

    build_service = DockerBuildService(
        ctx.obj.repo_root,
        ctx.obj.command_executor,
        ctx.obj.resolved_env,
    )
    rc = build_service.build_base_image(
        no_cache=no_cache,
        tag=tag,
        verbose=ctx.obj.verbose,
    )
    if rc != 0:
        output.error("Base image build failed")
        ctx.exit(rc)
    output.success(f"Built aidb-test-base:{tag}")


@group.command()
@click.option(
    "--all",
    "all_resources",
    is_flag=True,
    help=("Remove all AIDB Docker resources (containers, volumes, networks, images)"),
)
@click.option(
    "--volumes-only",
    is_flag=True,
    help="Only remove volumes",
)
@click.option(
    "--orphaned",
    is_flag=True,
    help="Remove orphaned volumes and containers",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be removed without actually removing it",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Skip confirmation prompts",
)
@click.pass_context
@handle_exceptions
def cleanup(
    ctx: click.Context,
    all_resources: bool,
    volumes_only: bool,
    orphaned: bool,
    dry_run: bool,
    force: bool,
) -> None:
    """Advanced Docker resource cleanup for AIDB.

    \b Uses Docker labels to safely identify and remove only AIDB-managed resources.
    Provides options for selective cleanup with safety confirmations.
    """  # noqa: W605
    output = ctx.obj.output
    output.section("Docker Resource Cleanup", Icons.CLEAN)

    from aidb_cli.managers.docker import DockerCleanupManager

    cleanup_manager = DockerCleanupManager(ctx.obj.command_executor)

    try:
        resources_to_remove = cleanup_manager.find_aidb_resources(
            all_resources=all_resources,
            volumes_only=volumes_only,
            orphaned_only=orphaned,
        )

        if not any(resources_to_remove.values()):
            output.success("No AIDB resources found to clean up")
            return

        cleanup_manager.display_resources(resources_to_remove)

        if dry_run:
            output.plain("Dry run complete - no resources were removed")
            return

        # Confirmation prompt
        if not force:
            count = cleanup_manager.count_resources(resources_to_remove)
            prompt = f"{Icons.WARNING} Remove {count} AIDB resources?"
            if not click.confirm(prompt):
                output.error("Cleanup cancelled")
                return

        # Execute cleanup
        results = cleanup_manager.cleanup_resources(resources_to_remove)
        cleanup_manager.display_cleanup_results(results)

    except Exception as e:
        output.error(f"Cleanup failed: {e}")
        logger.error("Docker cleanup error: %s", e)
        # Surface as AidbError to get a clean exit via decorator
        from aidb.common.errors import AidbError

        msg = f"Cleanup failed: {e}"
        raise AidbError(msg) from e


@group.command()
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output path for .env file (default: .env.build in repo root)",
)
@click.pass_context
@handle_exceptions
def env(ctx: click.Context, output: Path) -> None:
    """Generate .env file with Docker build arguments.

    \b Creates a .env file with all the build arguments needed for Docker builds,
    derived from versions.json.
    """  # noqa: W605
    cli_output = ctx.obj.output
    cli_output.section("Docker Build Environment", Icons.DOCKER)

    build_manager = ctx.obj.build_manager

    try:
        env_file = build_manager.generate_env_file(output_path=output)
        cli_output.success(f"Generated .env file: {env_file}")

        if ctx.obj.verbose:
            cli_output.plain("\nContents:")
            with env_file.open() as f:
                for line in f:
                    if not line.startswith("#"):
                        cli_output.plain(f"  {line.rstrip()}")

    except Exception as e:
        cli_output.error(f"Failed to generate .env file: {e}")
        ctx.exit(1)


@group.command()
@click.pass_context
@handle_exceptions
def status(ctx: click.Context) -> None:
    """Show Docker environment status.

    \b Displays information about Docker availability and test environment.
    """  # noqa: W605
    output = ctx.obj.output
    test_manager = ctx.obj.test_manager
    status_info = test_manager.get_test_status()

    output.section("Docker Environment Status", Icons.DOCKER)

    # Docker availability
    docker_version = status_info.get("docker_version", "not available")
    if status_info["docker_available"]:
        output.success(f"Docker: {docker_version}")
    else:
        output.error(f"Docker: {docker_version}", to_stderr=False)

    # Compose file
    if status_info["compose_file_exists"]:
        output.success("Compose file: found")
    else:
        output.error("Compose file: missing", to_stderr=False)

    # Adapters
    output.plain("")
    output.subsection("Adapter Status")
    for lang, built in status_info["adapters_built"].items():
        status_text = "built" if built else "not built"
        if built:
            output.success(f"  {lang}: {status_text}")
        else:
            output.error(f"  {lang}: {status_text}", to_stderr=False)

    # Repository root
    output.plain("")
    output.plain(f"Repository root: {status_info['repo_root']}")

    # Overall status
    overall_ok = (
        status_info["docker_available"]
        and status_info["compose_file_exists"]
        and any(status_info["adapters_built"].values())
    )

    output.plain("")
    if overall_ok:
        output.success("Docker environment is ready for testing")
    else:
        output.warning("Docker environment has issues")
        if not status_info["docker_available"]:
            output.plain("   Install Docker to enable testing")
        if not any(status_info["adapters_built"].values()):
            output.plain("   Run './dev-cli adapters build' to build debug adapters")


@group.command(name="compose")
@click.option(
    "--generate",
    "-g",
    is_flag=True,
    help="Generate docker-compose.yaml from templates",
)
@click.option(
    "--validate",
    is_flag=True,
    help="Validate docker-compose.yaml syntax",
)
@click.option(
    "--regenerate",
    "-r",
    is_flag=True,
    help="Force regenerate and validate",
)
@click.pass_context
@handle_exceptions
def compose(
    ctx: click.Context,
    generate: bool,
    validate: bool,
    regenerate: bool,
) -> None:
    """Docker Compose file management.

    \b
    Manages the docker-compose.yaml file used for containerized testing.
    Without flags, shows the current status.

    \b
    Examples:
        ./dev-cli docker compose                # Show status
        ./dev-cli docker compose --generate     # Generate from templates
        ./dev-cli docker compose --validate     # Validate syntax
        ./dev-cli docker compose --regenerate   # Force regenerate + validate
    """  # noqa: W605
    cli_output = ctx.obj.output
    from aidb_cli.services.docker import ComposeGeneratorService

    generator = ComposeGeneratorService(ctx.obj.repo_root)

    # Regenerate implies generate + validate
    if regenerate:
        generate = True
        validate = True

    # Generate compose file
    if generate:
        cli_output.section("Generating Compose File", Icons.BUILD)
        was_generated, generated_path = generator.generate(force=True)

        if was_generated:
            cli_output.success(f"Generated: {generated_path}")
        else:
            cli_output.error("Failed to generate compose file")
            ctx.exit(1)

    # Validate compose file
    if validate:
        if not generate:
            cli_output.section("Compose File Validation", Icons.MAGNIFYING)

            # Check if regeneration is needed
            needs_regen = generator.needs_regeneration()
            if needs_regen:
                cli_output.warning("Compose file needs regeneration")
                cli_output.plain("Run with --regenerate to update")
                ctx.exit(1)
            cli_output.success("Compose file is up-to-date")

        is_valid, errors = generator.validate_generated_file()

        if is_valid:
            cli_output.success("Compose file is valid YAML")
        else:
            cli_output.error("Compose file validation failed:")
            for error in errors:
                cli_output.error(f"  {error}", to_stderr=False)
            ctx.exit(1)

    # Default: show status
    if not generate and not validate:
        cli_output.section("Compose File Status", Icons.MAGNIFYING)

        needs_regen = generator.needs_regeneration()

        if needs_regen:
            cli_output.warning("Compose file needs regeneration")
            cli_output.plain("")
            cli_output.plain(
                "Templates, language configs, or version files have changed.",
            )
            cli_output.plain("Run './dev-cli docker compose --generate' to update")
        else:
            cli_output.success("Compose file is up-to-date")

        output_file = generator.output_file
        if output_file.exists():
            cli_output.plain("")
            cli_output.plain(f"Location: {output_file}")
        else:
            cli_output.plain("")
            cli_output.warning("Compose file does not exist")
            cli_output.plain("Run './dev-cli docker compose --generate' to create")
