"""Development utility commands for AIDB CLI.

Personal development tools for maintaining code quality and generating protocol files.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click

from aidb.common.errors import AidbError
from aidb_cli.core.constants import (
    Icons,
    PreCommitEnvVars,
    PreCommitHooks,
)
from aidb_cli.core.decorators import handle_exceptions
from aidb_cli.core.paths import ProjectPaths
from aidb_logging import get_cli_logger

if TYPE_CHECKING:
    from aidb_cli.core.output import OutputStrategy

logger = get_cli_logger(__name__)


def _read_code_files_for_scenario(
    output: "OutputStrategy",
    scenario_dir: Path,
    generator: Any,
    supported_langs: list[str],
) -> tuple[dict[str, str], int]:
    """Read code files for a scenario.

    Parameters
    ----------
    output : OutputStrategy
        Output strategy for CLI messages
    scenario_dir : Path
        Directory containing scenario files
    generator : Generator
        Test program generator instance
    supported_langs : list[str]
        List of supported languages

    Returns
    -------
    tuple[dict[str, str], int]
        (code_files dict, invalid_count)
    """
    code_files = {}
    invalid_count = 0

    for lang in supported_langs:
        lang_generator = generator.get_generator(lang)
        if not lang_generator:
            continue

        ext = lang_generator.file_extension
        files = list(scenario_dir.glob(f"*{ext}"))

        if files:
            file_path = files[0]
            try:
                code_files[lang] = file_path.read_text()
                output.plain(f"  Found {lang}: {file_path.name}")
            except (OSError, UnicodeDecodeError) as e:
                output.error(
                    f"  {Icons.ERROR} {lang}: Failed to read {file_path.name}: {e}",
                )
                invalid_count += 1

    return code_files, invalid_count


def _validate_scenario_consistency(
    output: "OutputStrategy",
    code_files: dict[str, str],
    generator: Any,
) -> tuple[int, int]:
    """Validate cross-language consistency for a scenario.

    Parameters
    ----------
    output : OutputStrategy
        Output strategy for CLI messages
    code_files : dict[str, str]
        Dictionary of language to code
    generator : Generator
        Test program generator instance

    Returns
    -------
    tuple[int, int]
        (valid_count, invalid_count)
    """
    from aidb_cli.generators.core.types import GenerationResult

    if not code_files:
        return 0, 0

    if len(code_files) == 1:
        only_lang = list(code_files.keys())[0]
        output.info(
            f"  Single language ({only_lang}) - skipping consistency check",
        )
        return 1, 0

    mock_results = {
        lang: GenerationResult(
            success=True,
            code=code,
            markers=[],
            error=None,
        )
        for lang, code in code_files.items()
    }

    is_valid, errors = generator.validate_cross_language_consistency(mock_results)

    if is_valid:
        lang_count = len(code_files)
        output.success(
            f"  {Icons.SUCCESS} Marker consistency validated ({lang_count} languages)",
        )
        return 1, 0

    output.warning(f"  {Icons.WARNING} Marker consistency issues:")
    for error in errors:
        output.warning(f"    - {error}")
    return 0, 1


def _validate_generated_programs(
    output: "OutputStrategy",
    output_dir: Path,
    generator: Any,
    supported_langs: list[str],
) -> None:
    """Validate existing generated test programs.

    Parameters
    ----------
    output : OutputStrategy
        Output strategy for CLI messages
    output_dir : Path
        Directory containing generated programs
    generator : Generator
        Test program generator instance
    supported_langs : list[str]
        List of supported languages
    """
    if not output_dir.exists():
        output.error(f"Output directory not found: {output_dir}")
        return

    scenario_dirs = [d for d in output_dir.iterdir() if d.is_dir()]
    if not scenario_dirs:
        output.warning("No scenario directories found")
        return

    output.info(f"Found {len(scenario_dirs)} scenario(s) to validate")

    total_valid = 0
    total_invalid = 0

    for scenario_dir in scenario_dirs:
        scenario_id = scenario_dir.name
        output.plain(f"{Icons.INFO} Validating scenario: {scenario_id}")

        code_files, invalid_count = _read_code_files_for_scenario(
            output,
            scenario_dir,
            generator,
            supported_langs,
        )
        total_invalid += invalid_count

        if not code_files:
            output.warning(f"  No valid code files found in {scenario_id}")
            continue

        valid, invalid = _validate_scenario_consistency(output, code_files, generator)
        total_valid += valid
        total_invalid += invalid

    output.plain("")
    output.section("Validation Summary", Icons.INFO)
    output.info(f"Valid scenarios: {total_valid}")
    if total_invalid > 0:
        output.warning(f"Invalid scenarios: {total_invalid}")
    else:
        output.success("All scenarios validated successfully!")


def _terminate_process(proc: subprocess.Popen) -> None:
    """Terminate a subprocess gracefully, with fallback to kill."""
    proc.terminate()
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def _run_precommit_process(
    proc: subprocess.Popen,
    log_file: Path,
) -> int:
    """Stream subprocess output to console and log file.

    Returns the process return code.
    """
    with log_file.open("w", encoding="utf-8") as f:
        if proc.stdout is not None:
            for line in proc.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
                f.write(line)
                f.flush()
    return proc.wait()


@click.group(name="dev")
@click.pass_context
def group(ctx: click.Context) -> None:
    """Core development utilities.

    \b Commands for code quality (pre-commit), protocol generation (DAP), and cleaning
    development artifacts.
    """  # noqa: W605


@group.command(name="precommit")
@click.option(
    "--staged-only",
    is_flag=True,
    help="Run only on staged files (git pre-commit behavior)",
)
@click.option(
    "--run-vulture",
    is_flag=True,
    help="Run vulture for unused code detection (skipped by default)",
)
@click.pass_context
@handle_exceptions
def precommit(
    ctx: click.Context,
    staged_only: bool,
    run_vulture: bool,
) -> None:
    """Run pre-commit hooks.

    \b By default runs on all files. Use --staged-only to run only on staged files
    (normal git pre-commit behavior).

    \b Vulture (unused code detection) is skipped by default for faster iteration. Use
    --run-vulture to include it.
    """  # noqa: W605
    output = ctx.obj.output
    output.section("Pre-commit Hooks", Icons.ROCKET)

    local_dir = ctx.obj.repo_root / ".local"
    local_dir.mkdir(exist_ok=True)
    log_file = local_dir / "pre-commit.log"

    cmd = [str(ctx.obj.repo_root / "venv" / "bin" / "pre-commit"), "run"]
    mode_desc = "staged files" if staged_only else "all files"

    if not staged_only:
        cmd.append("--all-files")

    env = os.environ.copy()
    if not run_vulture:
        env[PreCommitEnvVars.SKIP] = PreCommitHooks.VULTURE

    output.info(f"Running on {mode_desc}...")

    proc = None
    try:
        proc = ctx.obj.command_executor.create_process(
            cmd,
            cwd=ctx.obj.repo_root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        returncode = _run_precommit_process(proc, log_file)
    except KeyboardInterrupt:
        if proc is not None:
            _terminate_process(proc)
        raise
    except FileNotFoundError:
        output.error("pre-commit not found in venv")
        output.plain("Run './dev-cli install setup' first")
        raise

    if returncode == 0:
        output.success("Pre-commit run successfully")
    else:
        output.error("Pre-commit failed")
        if not ctx.obj.verbose:
            output.plain("Run with --verbose to see detailed output")
        msg = "Pre-commit checks failed"
        raise AidbError(msg)
    output.info(f"Log stored at {log_file}")


@group.command(name="dap")
@click.pass_context
@handle_exceptions
def dap(ctx: click.Context) -> None:
    """Regenerate DAP protocol dataclasses.

    \b Runs the DAP protocol generator to update protocol dataclasses from the latest
    Debug Adapter Protocol specification.
    """  # noqa: W605
    output = ctx.obj.output
    output.section("DAP Protocol Regeneration", Icons.LOOP)

    dap_gen_script = (
        ctx.obj.repo_root / "src" / "aidb" / "dap" / "_util" / "_gen_protocol.py"
    )

    if not dap_gen_script.exists():
        msg = f"DAP generator script not found: {dap_gen_script}"
        raise FileNotFoundError(msg)

    try:
        ctx.obj.command_executor.execute(
            [
                str(ProjectPaths.venv_python(ctx.obj.repo_root)),
                str(dap_gen_script),
            ],
            cwd=ctx.obj.repo_root,
            check=True,
            verbose=ctx.obj.verbose,
            verbose_debug=ctx.obj.verbose_debug,
        )

        output.success("DAP protocol dataclasses regenerated successfully")

    except AidbError as e:
        msg = f"DAP generation failed: {e}"
        raise AidbError(msg) from e
    except FileNotFoundError:
        output.error("Python interpreter not found in venv")
        output.plain("Run './dev-cli install setup' first")
        raise
    except Exception as e:
        msg = f"Error running DAP generator: {e}"
        raise AidbError(msg) from e


def _get_cache_patterns() -> list[str]:
    """Get list of cache file patterns to clean.

    Returns
    -------
    list[str]
        List of glob patterns for cache files
    """
    return [
        "**/__pycache__",
        "**/*.pyc",
        "**/*.pyo",
        "**/*.pyd",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "htmlcov",
        ".coverage*",
        "*.egg-info",
    ]


def _get_build_dirs() -> list[str]:
    """Get list of build directory names to clean.

    Returns
    -------
    list[str]
        List of build directory names
    """
    return [
        "build",
        "dist",
        ".tox",
    ]


def _clean_cache_files(
    output: "OutputStrategy",
    repo_root: Path,
    verbose: bool,
) -> list[str]:
    """Clean cache files matching patterns.

    Parameters
    ----------
    output : OutputStrategy
        Output strategy for CLI messages
    repo_root : Path
        Repository root directory
    verbose : bool
        Whether to show verbose warnings

    Returns
    -------
    list[str]
        List of cleaned item paths relative to repo_root
    """
    import shutil

    cleaned_items = []
    for pattern in _get_cache_patterns():
        for path in repo_root.glob(pattern):
            if path.exists():
                try:
                    if path.is_dir():
                        shutil.rmtree(path)
                    else:
                        path.unlink()
                    cleaned_items.append(str(path.relative_to(repo_root)))
                except OSError as e:
                    if verbose:
                        output.warning(f"Could not remove {path}: {e}")
    return cleaned_items


def _clean_build_dirs(
    output: "OutputStrategy",
    repo_root: Path,
    verbose: bool,
) -> list[str]:
    """Clean build directories.

    Parameters
    ----------
    output : OutputStrategy
        Output strategy for CLI messages
    repo_root : Path
        Repository root directory
    verbose : bool
        Whether to show verbose warnings

    Returns
    -------
    list[str]
        List of cleaned directory names
    """
    import shutil

    cleaned_items = []
    for dir_name in _get_build_dirs():
        build_path = repo_root / dir_name
        if build_path.exists():
            try:
                shutil.rmtree(build_path)
                cleaned_items.append(dir_name)
            except (OSError, shutil.Error) as e:
                if verbose:
                    output.warning(f"Could not remove {build_path}: {e}")
    return cleaned_items


@group.command()
@click.pass_context
@handle_exceptions
def clean(ctx: click.Context) -> None:
    """Clean development artifacts and caches.

    \b Removes build artifacts, Python cache files, test artifacts, and other
    development- related temporary files.
    """  # noqa: W605
    output = ctx.obj.output
    output.section("Cleaning Development Artifacts", Icons.CLEAN)

    repo_root = ctx.obj.repo_root
    verbose = ctx.obj.verbose

    cleaned_items = []
    cleaned_items.extend(_clean_cache_files(output, repo_root, verbose))
    cleaned_items.extend(_clean_build_dirs(output, repo_root, verbose))

    if cleaned_items:
        output.success(f"Cleaned {len(cleaned_items)} items")
        if verbose:
            for item in cleaned_items:
                output.plain(f"  Removed: {item}")
    else:
        output.plain("No artifacts to clean")


def _clean_output_dir(output: "OutputStrategy", output_dir: Path) -> None:
    """Clean the output directory before generation.

    Parameters
    ----------
    output : OutputStrategy
        Output strategy for CLI messages
    output_dir : Path
        Output directory to clean
    """
    if output_dir.exists():
        output.info("Cleaning generated files...")
        import shutil

        shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)


def _report_generation_results(
    output: "OutputStrategy",
    scenario_id: str,
    lang_results: dict[str, Any],
) -> tuple[int, int]:
    """Report generation results for a scenario.

    Parameters
    ----------
    output : OutputStrategy
        Output strategy for CLI messages
    scenario_id : str
        Scenario identifier
    lang_results : dict[str, Any]
        Dictionary of language to generation result

    Returns
    -------
    tuple[int, int]
        (generated_count, failed_count)
    """
    output.plain(f"  Scenario: {scenario_id}")

    generated = 0
    failed = 0

    for lang, result in lang_results.items():
        if result.success:
            marker_count = len(result.markers)
            output.success(
                f"    {Icons.SUCCESS} {lang}: Generated ({marker_count} markers)",
            )
            generated += 1
        else:
            output.error(f"    {Icons.ERROR} {lang}: {result.error}")
            failed += 1

    return generated, failed


def _validate_generation_consistency(
    output: "OutputStrategy",
    lang_results: dict[str, Any],
    generator: Any,
) -> None:
    """Validate cross-language consistency of generation results.

    Parameters
    ----------
    output : OutputStrategy
        Output strategy for CLI messages
    lang_results : dict[str, Any]
        Dictionary of language to generation result
    generator : Generator
        Test program generator instance
    """
    success_results = {lang: res for lang, res in lang_results.items() if res.success}
    if len(success_results) <= 1:
        return

    is_valid, errors = generator.validate_cross_language_consistency(success_results)
    if not is_valid:
        output.warning(f"    {Icons.WARNING} Marker consistency issues:")
        for error in errors:
            output.warning(f"      - {error}")


def _process_scenario_file(
    output: "OutputStrategy",
    yaml_file: Path,
    generator: Any,
    scenario_filter: str | None,
    target_languages: list[str] | None,
    file_output_dir: Path | None,
) -> tuple[int, int]:
    """Process a single scenario YAML file.

    Parameters
    ----------
    output : OutputStrategy
        Output strategy for CLI messages
    yaml_file : Path
        Path to scenario YAML file
    generator : Generator
        Test program generator instance
    scenario_filter : str | None
        Filter to specific scenario
    target_languages : list[str] | None
        Target languages to generate
    file_output_dir : Path | None
        Output directory (None for dry-run)

    Returns
    -------
    tuple[int, int]
        (generated_count, failed_count)
    """
    output.plain(f"{Icons.INFO} Processing {yaml_file.name}...")

    try:
        results = generator.generate_from_file(
            yaml_file=yaml_file,
            scenario_filter=scenario_filter,
            languages=target_languages,
            output_dir=file_output_dir,
        )

        total_generated = 0
        total_failed = 0

        for scenario_id, lang_results in results.items():
            generated, failed = _report_generation_results(
                output,
                scenario_id,
                lang_results,
            )
            total_generated += generated
            total_failed += failed

            _validate_generation_consistency(output, lang_results, generator)

        return total_generated, total_failed

    except Exception as e:
        output.error(f"Failed to process {yaml_file.name}: {e}")
        return 0, 1


@group.command(name="gen-test-programs")
@click.option(
    "--scenario",
    "-s",
    help="Generate specific scenario (default: all)",
)
@click.option(
    "--language",
    "-l",
    multiple=True,
    help="Generate for specific language(s) (default: all)",
)
@click.option(
    "--validate",
    is_flag=True,
    help="Validate existing generated files",
)
@click.option(
    "--clean",
    "do_clean",
    is_flag=True,
    help="Remove all generated files before generating",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be generated without writing files",
)
@click.pass_context
@handle_exceptions
def gen_test_programs(
    ctx: click.Context,
    scenario: str,
    language: tuple,
    validate: bool,
    do_clean: bool,
    dry_run: bool,
) -> None:
    """Generate test programs for debug adapter testing.

    \b This command generates deterministic test programs with embedded markers for
    testing debug adapters across multiple languages.
    """  # noqa: W605
    from pathlib import Path

    from aidb_cli.generators.core.generator import Generator

    output = ctx.obj.output
    output.section("Test Program Generator", Icons.ROCKET)

    scenarios_dir = Path(__file__).parent.parent / "generators" / "scenarios"
    gen_output_dir = (
        ctx.obj.repo_root / "src" / "tests" / "_assets" / "test_programs" / "generated"
    )

    generator = Generator()
    supported_langs = generator.get_supported_languages()

    output.info(f"Supported languages: {', '.join(supported_langs)}")

    if do_clean:
        _clean_output_dir(output, gen_output_dir)

    target_languages = list(language) if language else None

    if validate:
        output.info("Validating existing generated files...")
        _validate_generated_programs(output, gen_output_dir, generator, supported_langs)
        return

    scenario_files = list(scenarios_dir.glob("*.yaml"))
    if not scenario_files:
        output.error(f"No scenario files found in {scenarios_dir}")
        return

    output.info(f"Found {len(scenario_files)} scenario file(s)")

    total_generated = 0
    total_failed = 0

    for yaml_file in scenario_files:
        generated, failed = _process_scenario_file(
            output,
            yaml_file,
            generator,
            scenario,
            target_languages,
            None if dry_run else gen_output_dir,
        )
        total_generated += generated
        total_failed += failed

    output.plain("")
    output.section("Generation Summary", Icons.INFO)
    output.info(f"Generated: {total_generated} programs")
    if total_failed > 0:
        output.warning(f"Failed: {total_failed} programs")

    if not dry_run and total_generated > 0:
        output.success(f"Generated files saved to: {gen_output_dir}")
