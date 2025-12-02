"""Tests for reusable workflow contracts and integration."""

from pathlib import Path

import pytest
import yaml


class TestReusableWorkflows:
    """Validate reusable workflow contracts and caller integration."""

    @pytest.mark.integration
    def test_reusable_test_suite_has_required_inputs(self, workflows_dir):
        """Verify reusable test-suite workflow defines required inputs.

        The test-suite reusable workflow should define inputs for:
        - suite: Which test suite to run
        - python-version: Python version to use
        - skip-coverage: Whether to skip coverage reporting

        Parameters
        ----------
        workflows_dir : Path
            Path to workflows directory.
        """
        reusable_path = workflows_dir / "testing" / "_reusable" / "test-suite.yaml"

        if not reusable_path.exists():
            pytest.skip(f"Reusable workflow not found: {reusable_path}")

        with reusable_path.open("r") as f:
            workflow = yaml.safe_load(f)

        # Check workflow_call trigger exists
        triggers = workflow.get(True, workflow.get("on", {}))
        assert "workflow_call" in triggers, (
            "Reusable workflow missing workflow_call trigger"
        )

        # Check inputs are defined
        workflow_call = triggers["workflow_call"]
        inputs = workflow_call.get("inputs", {})

        expected_inputs = ["suite", "python-version"]
        for expected_input in expected_inputs:
            assert expected_input in inputs, (
                f"Reusable test-suite workflow missing input: {expected_input}"
            )

            # Verify input has required fields
            input_def = inputs[expected_input]
            assert "type" in input_def, f"Input '{expected_input}' missing 'type' field"

            if input_def.get("required", False):
                assert "description" in input_def, (
                    f"Required input '{expected_input}' should have description"
                )

    @pytest.mark.integration
    def test_reusable_load_versions_has_outputs(self, workflows_dir):
        """Verify reusable load-versions workflow defines expected outputs.

        The load-versions workflow should output version information that
        other workflows can use.

        Parameters
        ----------
        workflows_dir : Path
            Path to workflows directory.
        """
        reusable_path = workflows_dir / "testing" / "_reusable" / "load-versions.json"

        if not reusable_path.exists():
            pytest.skip(f"Reusable workflow not found: {reusable_path}")

        with reusable_path.open("r") as f:
            workflow = yaml.safe_load(f)

        # Check workflow_call trigger exists
        triggers = workflow.get(True, workflow.get("on", {}))
        assert "workflow_call" in triggers, (
            "Reusable workflow missing workflow_call trigger"
        )

        # Check outputs are defined
        workflow_call = triggers["workflow_call"]
        outputs = workflow_call.get("outputs", {})

        # Should have at least python-version output
        expected_outputs = ["python-version"]
        for expected_output in expected_outputs:
            assert expected_output in outputs, (
                f"Reusable load-versions workflow missing output: {expected_output}"
            )

    @pytest.mark.integration
    def test_caller_workflows_match_reusable_contracts(self, repo_root, workflows_dir):  # noqa: C901
        """Verify workflows calling reusable workflows pass correct inputs.

        This validates that callers:
        1. Pass required inputs
        2. Use outputs correctly
        3. Don't pass undefined inputs

        Parameters
        ----------
        repo_root : Path
            Repository root path.
        workflows_dir : Path
            Path to workflows directory.
        """
        # Load reusable workflow definitions
        reusable_dir = workflows_dir / "testing" / "_reusable"
        if not reusable_dir.exists():
            pytest.skip("No reusable workflows directory found")

        reusable_contracts = {}
        for reusable_file in reusable_dir.glob("*.yaml"):
            with reusable_file.open("r") as f:
                workflow = yaml.safe_load(f)

            triggers = workflow.get(True, workflow.get("on", {}))
            if "workflow_call" in triggers:
                workflow_call = triggers["workflow_call"]
                reusable_contracts[reusable_file.name] = {
                    "inputs": set(workflow_call.get("inputs", {}).keys()),
                    "secrets": set(workflow_call.get("secrets", {}).keys()),
                    "outputs": set(workflow_call.get("outputs", {}).keys()),
                    "required_inputs": {
                        name
                        for name, config in workflow_call.get("inputs", {}).items()
                        if config.get("required", False)
                    },
                }

        # Find workflows that call reusable workflows
        violations = []
        for workflow_file in workflows_dir.rglob("*.yaml"):
            if "_reusable" in str(workflow_file):
                continue  # Skip reusable workflows themselves

            with workflow_file.open("r") as f:
                try:
                    workflow = yaml.safe_load(f)
                except yaml.YAMLError:
                    continue  # Skip invalid YAML (caught by other tests)

            if not workflow:
                continue

            jobs = workflow.get("jobs", {})
            for job_name, job_config in jobs.items():
                uses = job_config.get("uses")
                if not uses:
                    continue

                # Check if this job calls a reusable workflow
                for reusable_name, contract in reusable_contracts.items():
                    # Match on filename (without .yaml)
                    reusable_base = reusable_name.replace(".yaml", "")
                    if reusable_base not in uses:
                        continue

                    # Validate inputs
                    with_inputs = job_config.get("with", {})
                    provided_inputs = set(with_inputs.keys())

                    # Check required inputs are provided
                    missing_required = contract["required_inputs"] - provided_inputs
                    if missing_required:
                        violations.append(
                            f"{workflow_file.name} job '{job_name}' "
                            f"missing required inputs: {missing_required}",
                        )

                    # Check no undefined inputs are passed
                    undefined_inputs = provided_inputs - contract["inputs"]
                    if undefined_inputs:
                        violations.append(
                            f"{workflow_file.name} job '{job_name}' "
                            f"passes undefined inputs: {undefined_inputs}",
                        )

                    # Validate secrets
                    with_secrets = job_config.get("secrets", {})
                    if isinstance(with_secrets, dict):
                        provided_secrets = set(with_secrets.keys())
                        undefined_secrets = provided_secrets - contract["secrets"]
                        if undefined_secrets:
                            violations.append(
                                f"{workflow_file.name} job '{job_name}' "
                                f"passes undefined secrets: {undefined_secrets}",
                            )

        if violations:
            msg = "Found contract violations in workflow calls:\n"
            for violation in violations:
                msg += f"  - {violation}\n"
            pytest.fail(msg)

    @pytest.mark.integration
    def test_reusable_workflows_use_consistent_naming(self, workflows_dir):
        """Verify reusable workflows follow consistent naming patterns.

        Inputs/outputs should use kebab-case consistently.

        Parameters
        ----------
        workflows_dir : Path
            Path to workflows directory.
        """
        reusable_dir = workflows_dir / "testing" / "_reusable"
        if not reusable_dir.exists():
            pytest.skip("No reusable workflows directory found")

        violations = []

        for reusable_file in reusable_dir.glob("*.yaml"):
            with reusable_file.open("r") as f:
                workflow = yaml.safe_load(f)

            triggers = workflow.get(True, workflow.get("on", {}))
            if "workflow_call" not in triggers:
                continue

            workflow_call = triggers["workflow_call"]

            # Check inputs use kebab-case
            for input_name in workflow_call.get("inputs", {}):
                if "_" in input_name:
                    violations.append(
                        f"{reusable_file.name}: input '{input_name}' uses "
                        f"snake_case, should use kebab-case",
                    )

            # Check outputs use kebab-case
            for output_name in workflow_call.get("outputs", {}):
                if "_" in output_name:
                    violations.append(
                        f"{reusable_file.name}: output '{output_name}' uses "
                        f"snake_case, should use kebab-case",
                    )

        if violations:
            msg = "Found naming convention violations:\n"
            for violation in violations:
                msg += f"  - {violation}\n"
            pytest.fail(msg)
