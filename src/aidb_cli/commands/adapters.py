"""Adapter commands for AIDB CLI.

Handles debug adapter building, listing, and management.
"""

from builtins import list as builtin_list

import click

from aidb.adapters.downloader import AdapterDownloader
from aidb.session.adapter_registry import AdapterRegistry
from aidb_cli.core.constants import Icons
from aidb_cli.core.decorators import handle_exceptions
from aidb_cli.core.param_types import LanguageParamType
from aidb_cli.services.adapter import AdapterMetadataService
from aidb_logging import get_cli_logger

logger = get_cli_logger(__name__)


def get_supported_languages():
    """Get supported languages from adapter registry."""
    try:
        registry = AdapterRegistry()
        return registry.get_languages()
    except Exception:
        # Fallback to default if registry fails
        from aidb_cli.core.constants import SUPPORTED_LANGUAGES

        return SUPPORTED_LANGUAGES


@click.group(name="adapters")
@click.pass_context
def group(ctx: click.Context) -> None:
    """Debug adapter management commands."""
    # No need to initialize anything - managers are singletons available through context


@group.command()
@click.option(
    "--language",
    "-l",
    type=LanguageParamType(),
    multiple=True,
    help=(
        "Specific language(s) to build (default: all). Choices resolved dynamically."
    ),
)
@click.option(
    "--install",
    "-i",
    is_flag=True,
    help="Also install built adapters to ~/.aidb/adapters/ for runtime use",
)
@click.option(
    "--use-host-platform",
    is_flag=True,
    help="Build for host platform instead of container platform (linux)",
)
@click.pass_context
@handle_exceptions
def build(
    ctx: click.Context,
    language: tuple[str, ...],
    install: bool,
    use_host_platform: bool,
) -> None:
    """Build debug adapters locally using act (GitHub Actions locally).

    This command builds adapters in containers using 'act' to run the
    build-act.yaml workflow. Adapters are built into {repo}/.cache/adapters/.

    If --install is passed, the built adapters are also copied to
    ~/.aidb/adapters/ for use in runtime debugging sessions.

    By default, builds target the container platform (linux). Use --use-host-platform
    to build for your actual host platform (darwin-arm64, linux-x64, etc.).

    \b
    Examples
    --------
    ./dev-cli adapters build
    ./dev-cli adapters build --language python
    ./dev-cli adapters build --use-host-platform
    ./dev-cli adapters build --install
    ./dev-cli adapters build --language javascript --install --use-host-platform
    """  # noqa: W605
    output = ctx.obj.output
    build_manager = ctx.obj.build_manager

    languages = builtin_list(language) if language else None
    if languages:
        supported = build_manager.get_supported_languages()
        invalid = [lang for lang in languages if lang not in supported]
        if invalid:
            output.error(f"Unsupported languages: {', '.join(invalid)}")
            output.plain(f"Supported languages: {', '.join(supported)}")
            ctx.exit(1)
    else:
        languages = build_manager.get_supported_languages()

    # Display header showing what's being built
    lang_list = ", ".join(languages)
    if language:
        # User specified specific language(s)
        output.section(f"Building debug adapters for: {lang_list}")
    else:
        # Building all adapters
        output.section(f"Building ALL debug adapters: {lang_list}")

    # Update environment with build platform settings if requested
    if use_host_platform:
        import platform

        build_env_updates = {
            "AIDB_USE_HOST_PLATFORM": "1",
            "AIDB_BUILD_PLATFORM": platform.system().lower(),
            "AIDB_BUILD_ARCH": platform.machine().lower(),
        }
        ctx.obj.env_manager.update(build_env_updates, source="adapter_build_command")
        logger.debug("Adapter build environment updates: %s", build_env_updates)

    # Build adapters locally using act
    from aidb_cli.services.adapter import AdapterService

    adapter_service = build_manager.get_service(AdapterService)

    # Either -v or -vvv enables verbose output
    is_verbose = ctx.obj.verbose or ctx.obj.verbose_debug
    success = adapter_service.build_locally(
        languages=languages,
        verbose=is_verbose,
        resolved_env=ctx.obj.resolved_env,
    )

    if not success:
        ctx.exit(1)

    # Install if requested
    if install:
        output.plain("")
        output.section("Installing adapters to ~/.aidb/adapters/")
        install_success = adapter_service.install_adapters(
            languages=languages,
            verbose=is_verbose,
        )
        if not install_success:
            ctx.exit(1)


@group.command()
@click.pass_context
@handle_exceptions
def list(ctx: click.Context) -> None:  # noqa: A001
    """List available debug adapters and their status."""
    output = ctx.obj.output
    output.section("Available Debug Adapters", Icons.LIST)
    _list_adapters_with_metadata(ctx)


@group.command()
@click.argument("language", type=LanguageParamType())
@click.pass_context
@handle_exceptions
def info(ctx: click.Context, language: str) -> None:
    """Show detailed information about a specific adapter."""
    output = ctx.obj.output
    output.section(f"{language.capitalize()} Adapter Information", Icons.INFO)
    _show_adapter_info_with_metadata(ctx, language)


@group.command()
@click.option(
    "--language",
    "-l",
    type=LanguageParamType(),
    multiple=True,
    help=(
        "Specific language(s) to download (default: all). Choices resolved dynamically."
    ),
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Force re-download even if adapters are cached",
)
@click.option(
    "--install",
    "-i",
    is_flag=True,
    help="Also install downloaded adapters to ~/.aidb/adapters/ for runtime use",
)
@click.pass_context
@handle_exceptions
def download(  # noqa: C901
    ctx: click.Context,
    language: tuple[str, ...],
    force: bool,
    install: bool,
) -> None:
    """Download debug adapters from GitHub releases.

    This command downloads pre-built adapters from GitHub releases and extracts
    them to {repo}/.cache/adapters/.

    If --install is passed, the downloaded adapters are also copied to
    ~/.aidb/adapters/ for use in runtime debugging sessions.

    \b
    Examples
    --------
    ./dev-cli adapters download
    ./dev-cli adapters download --language python
    ./dev-cli adapters download --install
    ./dev-cli adapters download --language javascript --install
    """  # noqa: W605
    output = ctx.obj.output
    build_manager = ctx.obj.build_manager

    languages_to_download = builtin_list(language) if language else None
    if languages_to_download:
        supported = build_manager.get_supported_languages()
        invalid = [lang for lang in languages_to_download if lang not in supported]
        if invalid:
            output.error(f"Unsupported languages: {', '.join(invalid)}")
            output.plain(f"Supported languages: {', '.join(supported)}")
            ctx.exit(1)
    else:
        languages_to_download = build_manager.get_supported_languages()

    # Display header
    lang_list = ", ".join(languages_to_download)
    output.section(f"Downloading debug adapters for: {lang_list}")

    # Use AdapterDownloader to download, but extract to repo cache
    downloader = AdapterDownloader()
    import shutil

    from aidb_cli.core.paths import CachePaths

    repo_cache = CachePaths.repo_cache(build_manager.repo_root)
    repo_cache.mkdir(parents=True, exist_ok=True)

    success_count = 0
    for lang in languages_to_download:
        try:
            # Check if already exists and not forcing
            cache_dir = repo_cache / lang
            if cache_dir.exists() and not force:
                output.success(f"{lang} adapter already in cache")
                success_count += 1
                continue

            output.info(f"Downloading {lang} adapter from GitHub releases...")

            # Download adapter (this downloads to temp and returns result)
            result = downloader.download_adapter(
                language=lang,
                version=None,
                force=True,  # Always force since we're managing cache ourselves
            )

            if not result.success:
                output.error(f"Failed to download {lang}: {result.message}")
                continue

            # The adapter was downloaded to ~/.aidb/adapters/{lang}
            # We need to copy it to repo cache
            source_dir = downloader.install_dir / lang
            if source_dir.exists():
                # Remove existing cache if present
                if cache_dir.exists():
                    shutil.rmtree(cache_dir)

                # Copy to repo cache
                shutil.copytree(source_dir, cache_dir)

                # Clean up the ~/.aidb/adapters/ copy since we don't want it there yet
                # (unless --install was passed)
                if not install:
                    shutil.rmtree(source_dir)

                output.success(f"Downloaded {lang} adapter to cache")
                success_count += 1
            else:
                output.error(f"Downloaded {lang} but source not found")

        except Exception as e:
            logger.error("Download failed for %s: %s", lang, e)
            output.error(f"Download failed for {lang}: {e}")

    # Summary
    if success_count == len(languages_to_download):
        output.success(f"Downloaded {success_count} adapter(s) to {repo_cache}")
    elif success_count > 0:
        output.warning(
            f"Downloaded {success_count}/{len(languages_to_download)} adapter(s)",
        )
    else:
        output.error("Failed to download any adapters")
        ctx.exit(1)

    # Install if requested
    if install:
        output.plain("")
        output.section("Installing adapters to ~/.aidb/adapters/")
        from aidb_cli.services.adapter import AdapterService

        adapter_service = build_manager.get_service(AdapterService)
        # Either -v or -vvv enables verbose output
        is_verbose = ctx.obj.verbose or ctx.obj.verbose_debug
        install_success = adapter_service.install_adapters(
            languages=languages_to_download,
            verbose=is_verbose,
        )
        if not install_success:
            ctx.exit(1)


@group.command()
@click.option(
    "--user-only",
    is_flag=True,
    help="Only clean user cache, not repo cache",
)
@click.confirmation_option(prompt="This will remove all cached adapters. Continue?")
@click.pass_context
@handle_exceptions
def clean(ctx: click.Context, user_only: bool) -> None:
    """Clean the adapter cache directory.

    By default, cleans the repo cache ({repo}/.cache/adapters/).
    Use --user-only to preserve the repo cache.

    \b
    Examples
    --------
    ./dev-cli adapters clean
    ./dev-cli adapters clean --user-only
    """  # noqa: W605
    output = ctx.obj.output
    output.section("Cleaning Adapter Cache", Icons.CLEAN)

    build_manager = ctx.obj.build_manager

    success = build_manager.clean_adapter_cache(user_only=user_only)
    if not success:
        ctx.exit(1)


@group.command()
@click.pass_context
@handle_exceptions
def status(ctx: click.Context) -> None:
    """Show status of installed runtime debug adapters.

    Lists all installed debug adapters from ~/.aidb/adapters/ with their
    versions and locations. This shows adapters available for runtime
    debugging sessions.

    \b
    Examples
    --------
    ./dev-cli adapters status
    """  # noqa: W605
    output = ctx.obj.output
    downloader = AdapterDownloader()

    installed = downloader.list_installed_adapters()

    if not installed:
        output.warning("No runtime debug adapters are installed")
        output.plain(
            "Use './dev-cli adapters download --install' to download "
            "and install adapters",
        )
        output.plain(
            "Or use './dev-cli adapters build --install' to build and install adapters",
        )
        return

    output.section("Installed Debug Adapters")

    for adapter_name, adapter_info in installed.items():
        version = adapter_info.get("version", "unknown")
        path = adapter_info.get("path", "unknown")

        output.success(adapter_name)
        output.plain(f"    Version: {version}")
        output.plain(f"    Path:    {path}")
        output.plain("")

    output.plain(f"Total: {len(installed)} adapters installed")


def _get_metadata_service(ctx: click.Context) -> AdapterMetadataService:
    """Get or create metadata service instance.

    Parameters
    ----------
    ctx : click.Context
        Click context

    Returns
    -------
    AdapterMetadataService
        Metadata service instance
    """
    if not hasattr(ctx.obj, "metadata_service"):
        from pathlib import Path

        repo_root = Path.cwd()
        ctx.obj.metadata_service = AdapterMetadataService(repo_root)
    return ctx.obj.metadata_service


def _list_adapters_with_metadata(ctx: click.Context) -> None:
    """List adapters with metadata information."""
    build_manager = ctx.obj.build_manager
    metadata_service = _get_metadata_service(ctx)

    languages = build_manager.get_supported_languages()
    built_list, missing_list = build_manager.check_adapters_built(languages)

    metadata_service.display_adapter_list_with_metadata(
        languages,
        built_list,
        missing_list,
    )


def _show_adapter_info_with_metadata(ctx: click.Context, language: str) -> None:
    """Show detailed adapter information with metadata."""
    output = ctx.obj.output
    build_manager = ctx.obj.build_manager
    metadata_service = _get_metadata_service(ctx)

    supported = build_manager.get_supported_languages()
    if language not in supported:
        output.error(f"Unsupported language: {language}")
        output.plain(f"Supported languages: {', '.join(supported)}")
        ctx.exit(1)

    # Check if adapter is built
    built_list, _ = build_manager.check_adapters_built([language])
    if language not in built_list:
        output.error(f"Adapter for {language} is not built")
        output.plain(f"Run './dev-cli adapters build -l {language}' to build it")
        ctx.exit(1)

    adapter_info = build_manager.get_adapter_info(language)

    metadata_service.display_adapter_info_with_metadata(language, adapter_info)
