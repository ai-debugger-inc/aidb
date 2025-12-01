"""Tests for dynamic matrix expansion integration with workflows."""

import json
import subprocess
from pathlib import Path

import pytest
import yaml


class TestMatrixExpansion:
    """Validate dynamic matrix generation integrates correctly with workflows."""

    @pytest.mark.integration
    def test_adapter_matrix_configuration_valid(self, repo_root):
        """Verify adapter matrix configuration is valid.

        Parameters
        ----------
        repo_root : Path
            Repository root path.
        """
        versions_file = repo_root / "versions.json"

        if not versions_file.exists():
            pytest.skip("versions.json not found")

        with versions_file.open("r") as f:
            versions = yaml.safe_load(f)

        # Check adapters configuration
        adapters = versions.get("adapters", {})
        assert len(adapters) > 0, "No adapters defined in versions.json"

        # Verify each adapter has required fields
        for lang, adapter_config in adapters.items():
            assert "version" in adapter_config, (
                f"Adapter '{lang}' missing 'version' field"
            )
            # Accept either 'repo' (short form) or 'repository' (full URL)
            assert "repo" in adapter_config or "repository" in adapter_config, (
                f"Adapter '{lang}' missing 'repo' or 'repository' field"
            )

        # Check platforms configuration
        platforms = versions.get("platforms", [])
        assert len(platforms) > 0, "No platforms defined in versions.json"

        for platform in platforms:
            assert "os" in platform, "Platform missing 'os' field"
            assert "arch" in platform, "Platform missing 'arch' field"

    @pytest.mark.integration
    @pytest.mark.slow
    def test_adapter_build_workflow_uses_matrix(
        self,
        act_runner,
        repo_root,
        act_installed,
    ):
        """Verify adapter build workflow correctly uses adapter/platform matrix.

        Parameters
        ----------
        act_runner : Callable
            Fixture for running act commands.
        repo_root : Path
            Repository root path.
        act_installed : bool
            Whether act is installed.
        """
        if not act_installed:
            pytest.skip("act is not installed")

        workflow_path = ".github/workflows/adapter-build.yaml"
        workflow_file = repo_root / workflow_path

        if not workflow_file.exists():
            pytest.skip(f"Workflow not found: {workflow_path}")

        # Load workflow to check structure
        with workflow_file.open("r") as f:
            workflow = yaml.safe_load(f)

        jobs = workflow.get("jobs", {})

        # Look for build job with matrix strategy
        has_matrix = False
        for job_name, job_config in jobs.items():
            if "build" in job_name.lower() and "strategy" in job_config:
                strategy = job_config["strategy"]
                if "matrix" in strategy:
                    has_matrix = True
                    matrix = strategy["matrix"]

                    # Verify matrix structure
                    # Can be either:
                    # 1. Dynamic matrix: ${{fromJson(needs.*.outputs.matrix)}}
                    # 2. Static matrix with expected dimensions
                    if isinstance(matrix, str):
                        # Dynamic matrix from job output
                        assert "fromJson" in matrix, "String matrix should use fromJson"
                        assert "matrix" in matrix, (
                            "Dynamic matrix should reference matrix output"
                        )
                    else:
                        # Static matrix should have expected fields
                        assert (
                            "include" in matrix
                            or "adapter" in matrix
                            or "language" in matrix
                        ), "Static matrix missing expected dimensions"

        if not has_matrix:
            pytest.skip("No matrix strategy found in adapter build workflow")

        # Use act to validate workflow parses correctly
        result = act_runner(workflow_file=workflow_path, dry_run=True)

        # Act may return non-zero for missing inputs, but should not have parse errors
        assert "error parsing" not in result.stderr.lower(), (
            f"Workflow has parsing errors:\n{result.stderr}"
        )
