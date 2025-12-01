"""Fixtures for CI/CD integration tests using act."""

import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def act_installed() -> bool:
    """Check if act is installed and available.

    Returns
    -------
    bool
        True if act is installed, False otherwise.

    Notes
    -----
    Tests requiring act should use this fixture with skipif:
        @pytest.mark.skipif(not act_installed, reason="act not installed")
    """
    return shutil.which("act") is not None


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Get the repository root directory.

    Returns
    -------
    Path
        Absolute path to repository root.
    """
    # Start from this file and traverse up to find repo root
    current = Path(__file__).resolve()
    while current.parent != current:
        if (current / ".git").exists() or (current / "pyproject.toml").exists():
            return current
        current = current.parent

    msg = "Could not find repository root"
    raise RuntimeError(msg)


@pytest.fixture(scope="session")
def workflows_dir(repo_root: Path) -> Path:
    """Get the workflows directory.

    Parameters
    ----------
    repo_root : Path
        Repository root path.

    Returns
    -------
    Path
        Path to .github/workflows directory.
    """
    return repo_root / ".github" / "workflows"


@pytest.fixture(scope="session")
def workflow_files(workflows_dir: Path) -> list[Path]:
    """Discover all workflow files in the repository.

    Parameters
    ----------
    workflows_dir : Path
        Path to workflows directory.

    Returns
    -------
    list[Path]
        List of workflow file paths (*.yaml).
    """
    workflows: list[Path] = []
    for pattern in ["**/*.yaml"]:
        workflows.extend(workflows_dir.glob(pattern))

    # Filter out hidden files and backups
    workflows = [w for w in workflows if not w.name.startswith(".")]

    return sorted(workflows)


@pytest.fixture
def act_runner(repo_root: Path, act_installed: bool) -> Callable:
    """Helper function for running act commands.

    Parameters
    ----------
    repo_root : Path
        Repository root path.
    act_installed : bool
        Whether act is installed.

    Returns
    -------
    Callable
        Function to run act commands with standardized interface.

    Notes
    -----
    Usage:
        result = act_runner(
            workflow_file=".github/workflows/test.yaml",
            job="test-job",
            event="workflow_dispatch",
            inputs={"suite": "cli"},
            dry_run=True
        )
    """

    def _run_act(
        workflow_file: str | Path,
        job: str | None = None,
        event: str = "workflow_dispatch",
        inputs: dict[str, str] | None = None,
        dry_run: bool = False,
        timeout: int = 300,
    ) -> subprocess.CompletedProcess:
        """Run act command with specified parameters.

        Parameters
        ----------
        workflow_file : str | Path
            Relative path to workflow file from repo root.
        job : str | None
            Specific job to run (if None, runs all jobs).
        event : str
            Event type to trigger (default: workflow_dispatch).
        inputs : dict[str, str] | None
            Input parameters for workflow_dispatch events.
        dry_run : bool
            If True, run act in dry-run mode (-n flag).
        timeout : int
            Timeout in seconds (default: 300).

        Returns
        -------
        subprocess.CompletedProcess
            Result of act command execution.
        """
        if not act_installed:
            pytest.skip("act is not installed")

        cmd = ["act", event, "-W", str(workflow_file)]

        if job:
            cmd.extend(["-j", job])

        if dry_run:
            cmd.extend(["-n", "-l"])

        if inputs:
            for key, value in inputs.items():
                cmd.append(f"--input={key}={value}")

        return subprocess.run(
            cmd,
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

    return _run_act


@pytest.fixture
def reusable_workflows(workflows_dir: Path) -> list[Path]:
    """Discover reusable workflow files.

    Parameters
    ----------
    workflows_dir : Path
        Path to workflows directory.

    Returns
    -------
    list[Path]
        List of reusable workflow file paths (under _reusable/).
    """
    reusable_dir = workflows_dir / "testing" / "_reusable"
    if not reusable_dir.exists():
        return []

    workflows: list[Path] = []
    for pattern in ["*.yaml"]:
        workflows.extend(reusable_dir.glob(pattern))

    return sorted(workflows)
