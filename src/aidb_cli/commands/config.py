"""Configuration commands for AIDB CLI.

Handles configuration file management and settings.
"""

import click

from aidb_cli.core.constants import ExitCode, Icons
from aidb_cli.core.decorators import handle_exceptions
from aidb_cli.core.yaml import YamlOperationError, safe_read_yaml
from aidb_logging import get_cli_logger

logger = get_cli_logger(__name__)


@click.group(name="config")
@click.pass_context
def group(ctx: click.Context) -> None:
    """Manage AIDB configuration settings."""
    # Managers are singletons available through context


@group.command()
@click.option(
    "--format",
    "-f",
    "format_type",
    type=click.Choice(["yaml", "json", "text"]),
    default="yaml",
    help="Output format",
)
@click.option(
    "--type",
    "-t",
    "config_type",
    type=click.Choice(["merged", "user", "project", "versions"]),
    default="merged",
    help="Which configuration to show",
)
@click.pass_context
@handle_exceptions
def show(ctx: click.Context, format_type: str, config_type: str) -> None:
    """Show current configuration.

    \b By default shows the merged configuration from all sources. Use --type to show
    specific configuration files.
    """  # noqa: W605
    output = ctx.obj.output
    output.section("Configuration Overview", Icons.CONFIG)

    config_manager = ctx.obj.config_manager
    # Add a short header so generic tests can detect intent
    output.plain(
        f"Configuration (type: {config_type}, format: {format_type})",
    )
    config_manager.show_config(format_type=format_type, config_type=config_type)


@group.command(name="set")
@click.argument("key_path")
@click.argument("value")
@click.option(
    "--scope",
    type=click.Choice(["user", "project"]),
    default="user",
    help="Where to save the configuration",
)
@click.pass_context
@handle_exceptions
def set_config(ctx: click.Context, key_path: str, value: str, scope: str) -> None:
    """Set a configuration value.

    \b KEY_PATH should use dot notation (e.g., 'adapters.auto_build'). VALUE will be
    parsed as YAML (supports strings, booleans, numbers).
    """  # noqa: W605
    output = ctx.obj.output
    output.section("Setting Configuration", Icons.CONFIG)

    import yaml

    config_manager = ctx.obj.config_manager

    # Parse value as YAML to support different types
    try:
        parsed_value = yaml.safe_load(value)
    except yaml.YAMLError:
        # If YAML parsing fails, treat as string
        parsed_value = value

    success = config_manager.set_config_value(
        key_path=key_path,
        value=parsed_value,
        save_to=scope,
    )

    if success:
        output.success(
            f"Set {key_path} = {parsed_value} ({scope} config)",
        )
    else:
        output.error("Failed to set configuration")
        ctx.exit(1)


@group.command()
@click.argument("key_path")
@click.pass_context
@handle_exceptions
def get(ctx: click.Context, key_path: str) -> None:
    """Get a configuration value.

    \b KEY_PATH should use dot notation (e.g., 'adapters.auto_build').
    """  # noqa: W605
    output = ctx.obj.output
    output.section("Configuration Value", Icons.CONFIG)

    config_manager = ctx.obj.config_manager
    value = config_manager.get_config_value(key_path)

    if value is not None:
        output.plain(str(value))
    else:
        output.error(f"Configuration key '{key_path}' not found")
        ctx.exit(1)


@group.command()
@click.option(
    "--scope",
    type=click.Choice(["user", "project"]),
    default="user",
    help="Where to create the configuration file",
)
@click.pass_context
@handle_exceptions
def init(ctx: click.Context, scope: str) -> None:
    """Initialize default configuration file.

    \b Creates a default .aidb.yaml configuration file with common settings.
    """  # noqa: W605
    output = ctx.obj.output
    output.section("Initializing Configuration", Icons.CONFIG)

    config_manager = ctx.obj.config_manager

    success = config_manager.create_default_config(save_to=scope)

    if not success:
        ctx.exit(1)


@group.command()
@click.pass_context
@handle_exceptions
def paths(ctx: click.Context) -> None:
    """Show configuration file paths.

    \b Displays the locations where AIDB looks for configuration files.
    """  # noqa: W605
    output = ctx.obj.output
    config_manager = ctx.obj.config_manager

    output.section("Configuration File Paths", Icons.GEAR)

    if config_manager.user_config.exists():
        output.success(f"User config: {config_manager.user_config}")
    else:
        output.error(f"User config: {config_manager.user_config}", to_stderr=False)

    if config_manager.project_config.exists():
        output.success(f"Project config: {config_manager.project_config}")
    else:
        output.error(
            f"Project config: {config_manager.project_config}",
            to_stderr=False,
        )

    if config_manager.versions_file.exists():
        output.success(f"Versions file: {config_manager.versions_file}")
    else:
        output.error(f"Versions file: {config_manager.versions_file}", to_stderr=False)

    output.plain("")
    output.subsection("Configuration Loading Priority")
    output.plain(
        "1. Default values (built-in)\n"
        "2. User config (~/.config/aidb/config.yaml)\n"
        "3. Project config (.aidb.yaml)\n"
        "4. Environment variables\n"
        "5. Command line arguments",
    )


@group.command()
@click.pass_context
@handle_exceptions
def validate(ctx: click.Context) -> None:
    """Validate configuration files.

    \b Checks that all configuration files are valid and consistent.
    """  # noqa: W605
    output = ctx.obj.output
    config_manager = ctx.obj.config_manager

    version_results = config_manager.validate_versions()
    all_valid = all(version_results.values())

    output.section("Configuration Validation", Icons.CHECK)

    for section, is_valid in version_results.items():
        if is_valid:
            output.success(f"versions.json {section}")
        else:
            output.error(f"versions.json {section}", to_stderr=False)

    user_valid = True
    if config_manager.user_config.exists():
        try:
            safe_read_yaml(config_manager.user_config)
            output.success("User config syntax")
        except YamlOperationError as e:
            output.error(f"User config syntax: {e}", to_stderr=False)
            user_valid = False
    else:
        output.plain("No user config file")

    project_valid = True
    if config_manager.project_config.exists():
        try:
            safe_read_yaml(config_manager.project_config)
            output.success("Project config syntax")
        except YamlOperationError as e:
            output.error(f"Project config syntax: {e}", to_stderr=False)
            project_valid = False
    else:
        output.plain("No project config file")

    output.plain("")
    if all_valid and user_valid and project_valid:
        output.success("All configurations are valid!")
    else:
        output.error("Some configuration issues found.", to_stderr=False)
        output.plain(
            "Fix the issues above or run 'aidb config init' to create defaults.",
        )
        ctx.exit(ExitCode.GENERAL_ERROR)
