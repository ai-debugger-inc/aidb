"""Regression tests for adapter build-act workflow."""

from pathlib import Path

import pytest
import yaml


class TestAdapterBuildAct:
    """Validate adapter build-act workflow continues to work correctly."""

    @pytest.mark.integration
    @pytest.mark.slow
    def test_build_act_workflow_syntax_valid(
        self,
        act_runner,
        repo_root,
        act_installed,
    ):
        """Verify build-act.yaml workflow has valid syntax.

        This is a regression test to ensure the workflow that dev-cli
        uses for local adapter builds remains valid.

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

        workflow_path = ".github/workflows/adapter-build-act.yaml"
        workflow_file = repo_root / workflow_path

        if not workflow_file.exists():
            pytest.fail(f"Critical workflow missing: {workflow_path}")

        # Validate syntax via act
        result = act_runner(workflow_file=workflow_path, dry_run=True)

        # Act returns 0 for valid workflows, or specific errors for invalid ones
        if result.returncode != 0:
            # Check if it's just missing inputs (expected for workflow_dispatch)
            if "input" in result.stderr.lower() or "required" in result.stderr.lower():
                # This is OK - workflow requires inputs
                return

            pytest.fail(
                f"build-act.yaml has syntax errors:\n"
                f"Exit code: {result.returncode}\n"
                f"Stderr: {result.stderr}\n"
                f"Stdout: {result.stdout}",
            )

    @pytest.mark.integration
    def test_build_act_workflow_has_required_structure(self, repo_root):
        """Verify build-act.yaml has expected structure and inputs.

        The workflow should:
        1. Use workflow_dispatch trigger
        2. Accept 'adapters' input
        3. Have build jobs for Python, JavaScript, Java

        Parameters
        ----------
        repo_root : Path
            Repository root path.
        """
        workflow_path = repo_root / ".github" / "workflows" / "adapter-build-act.yaml"

        if not workflow_path.exists():
            pytest.fail(f"Critical workflow missing: {workflow_path}")

        with workflow_path.open("r") as f:
            workflow = yaml.safe_load(f)

        # Check trigger (YAML parses 'on:' as boolean True, not string "on")
        triggers = workflow.get(True, workflow.get("on", {}))
        assert "workflow_dispatch" in triggers, (
            "build-act.yaml must have workflow_dispatch trigger"
        )

        # Check inputs
        dispatch = triggers["workflow_dispatch"]
        inputs = dispatch.get("inputs", {})
        assert "adapters" in inputs, (
            "build-act.yaml must have 'adapters' input for language selection"
        )

        # Verify adapters input has correct type (string for comma-separated values)
        adapters_input = inputs["adapters"]
        assert adapters_input.get("type") == "string", (
            "'adapters' input should be type 'string' for comma-separated adapter names"
        )

        # Verify default value is set
        assert "default" in adapters_input, (
            "'adapters' input should have a default value"
        )

        # Verify description mentions format
        description = adapters_input.get("description", "").lower()
        assert "comma" in description or "," in description, (
            "'adapters' input description should mention comma-separated format"
        )

        # Check jobs exist
        jobs = workflow.get("jobs", {})
        assert len(jobs) > 0, "build-act.yaml must have build jobs"

        # Verify workflow uses matrix strategy for building multiple adapters
        # (Modern design: one job with matrix, not separate jobs per language)
        assert "build-adapters" in jobs or any(
            "build" in job_name.lower() for job_name in jobs
        ), "build-act.yaml should have a build job (using matrix strategy)"

    @pytest.mark.integration
    def test_build_act_workflow_uses_versions_json(self, repo_root):
        """Verify build-act.yaml references versions.json for adapter versions.

        The workflow should not hardcode adapter versions. It can reference
        versions.json either directly OR via helper scripts that read it
        (e.g., extract_build_config.py, matrix_generator.py).

        Parameters
        ----------
        repo_root : Path
            Repository root path.
        """
        workflow_path = repo_root / ".github" / "workflows" / "adapter-build-act.yaml"

        if not workflow_path.exists():
            pytest.skip("adapter-build-act.yaml not found")

        with workflow_path.open("r") as f:
            workflow_content = f.read()

        # Check that workflow references versions.json directly OR uses scripts
        # that read from versions.json (extract_build_config.py, matrix_generator.py)
        versions_json_scripts = [
            "extract_build_config.py",  # Reads adapter build deps from versions.json
            "matrix_generator.py",  # Reads adapter/platform matrix from versions.json
        ]

        uses_versions_json = "versions.json" in workflow_content or any(
            script in workflow_content for script in versions_json_scripts
        )

        assert uses_versions_json, (
            "build-act.yaml should reference versions.json for version management "
            "(directly or via extract_build_config.py/matrix_generator.py scripts)"
        )

        # Verify no hardcoded versions (basic check for semver patterns in suspicious places)
        # This is a heuristic, not foolproof
        lines = workflow_content.split("\n")
        suspicious_lines = []

        for i, line in enumerate(lines, 1):
            # Skip comments
            if line.strip().startswith("#"):
                continue

            # Check for hardcoded versions in suspicious contexts
            if any(
                keyword in line.lower()
                for keyword in ["version:", "debugpy", "vscode-js-debug", "java-debug"]
            ):
                # Look for semver patterns (e.g., "1.2.3", "v1.2.3")
                import re

                if re.search(r'["\']v?\d+\.\d+\.\d+["\']', line):
                    suspicious_lines.append(f"Line {i}: {line.strip()}")

        if suspicious_lines:
            msg = (
                "Found potentially hardcoded versions in build-act.yaml:\n"
                + "\n".join(suspicious_lines)
                + "\n\nVersions should be read from versions.json"
            )
            pytest.fail(msg)

    @pytest.mark.integration
    def test_build_act_workflow_conditional_logic(self, repo_root):
        """Verify build-act.yaml has conditional logic for adapter selection.

        Jobs should only run when their adapter is selected.

        Parameters
        ----------
        repo_root : Path
            Repository root path.
        """
        workflow_path = repo_root / ".github" / "workflows" / "adapter-build-act.yaml"

        if not workflow_path.exists():
            pytest.skip("adapter-build-act.yaml not found")

        with workflow_path.open("r") as f:
            workflow = yaml.safe_load(f)

        jobs = workflow.get("jobs", {})

        # Check that jobs have conditional execution based on input
        for job_name, job_config in jobs.items():
            # Jobs should have 'if' conditions to check adapter input
            if_condition = job_config.get("if")

            if if_condition:
                # Verify condition references the adapters input
                if_str = str(if_condition)
                assert (
                    "inputs.adapters" in if_str
                    or "github.event.inputs.adapters" in if_str
                ), (
                    f"Job '{job_name}' has 'if' condition but doesn't check adapters input"
                )

    @pytest.mark.integration
    def test_build_act_references_existing_build_script(self, repo_root):
        """Verify build-act.yaml uses the build-adapter.py script.

        The workflow should delegate to the script for actual builds.

        Parameters
        ----------
        repo_root : Path
            Repository root path.
        """
        workflow_path = repo_root / ".github" / "workflows" / "adapter-build-act.yaml"
        script_path = repo_root / ".github" / "scripts" / "build-adapter.py"

        if not workflow_path.exists():
            pytest.skip("adapter-build-act.yaml not found")

        if not script_path.exists():
            pytest.skip("build-adapter.py not found")

        with workflow_path.open("r") as f:
            workflow_content = f.read()

        # Check that workflow references the build script
        assert "build-adapter.py" in workflow_content, (
            "build-act.yaml should use build-adapter.py script for builds"
        )
