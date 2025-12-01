"""Tests for GitHub Actions workflow syntax validation using act."""

from pathlib import Path

import pytest
import yaml


class TestWorkflowSyntax:
    """Validate workflow syntax and structure."""

    @pytest.mark.integration
    def test_all_workflows_parse_successfully(
        self,
        act_runner,
        workflow_files,
        act_installed,
        repo_root,
    ):
        """Verify all workflow files have valid syntax via act dry-run.

        This test runs `act -n -l` on each workflow to validate:
        - YAML syntax is correct
        - Workflow structure is valid
        - Jobs and steps are properly defined
        - Act can parse the workflow

        Parameters
        ----------
        act_runner : Callable
            Fixture for running act commands.
        workflow_files : list[Path]
            List of all workflow files.
        act_installed : bool
            Whether act is installed.
        repo_root : Path
            Repository root path.
        """
        if not act_installed:
            pytest.skip("act is not installed")

        failures = []

        for workflow in workflow_files:
            # Skip reusable workflows entirely - act cannot validate workflow_call triggers
            if "_reusable" in str(workflow):
                continue

            # Get relative path from repo root for better error messages
            rel_path = workflow.relative_to(repo_root)

            result = act_runner(workflow_file=rel_path, dry_run=True)

            # Act returns non-zero for syntax errors
            if result.returncode != 0:
                failures.append(
                    {
                        "workflow": str(rel_path),
                        "returncode": result.returncode,
                        "stderr": result.stderr,
                        "stdout": result.stdout,
                    },
                )

        if failures:
            msg = f"Found {len(failures)} workflow(s) with syntax errors:\n\n"
            for failure in failures:
                msg += f"Workflow: {failure['workflow']}\n"
                msg += f"Exit code: {failure['returncode']}\n"
                msg += f"Error output:\n{failure['stderr']}\n"
                if failure["stdout"]:
                    msg += f"Standard output:\n{failure['stdout']}\n"
                msg += "\n" + "-" * 80 + "\n\n"
            pytest.fail(msg)

    @pytest.mark.integration
    def test_all_workflows_are_valid_yaml(self, workflow_files):
        """Verify all workflow files are valid YAML.

        This is a fast sanity check before running act.

        Parameters
        ----------
        workflow_files : list[Path]
            List of all workflow files.
        """
        failures = []

        for workflow in workflow_files:
            try:
                with workflow.open("r") as f:
                    yaml.safe_load(f)
            except yaml.YAMLError as e:
                rel_path = workflow.relative_to(workflow.parents[3])
                failures.append({"workflow": str(rel_path), "error": str(e)})

        if failures:
            msg = f"Found {len(failures)} workflow(s) with YAML syntax errors:\n\n"
            for failure in failures:
                msg += f"Workflow: {failure['workflow']}\n"
                msg += f"Error: {failure['error']}\n\n"
            pytest.fail(msg)

    @pytest.mark.integration
    def test_reusable_workflows_have_workflow_call_trigger(self, reusable_workflows):
        """Verify reusable workflows have workflow_call trigger.

        Reusable workflows must use the workflow_call trigger to be callable
        from other workflows.

        Parameters
        ----------
        reusable_workflows : list[Path]
            List of reusable workflow files.
        """
        if not reusable_workflows:
            pytest.skip("No reusable workflows found")

        failures = []

        for workflow in reusable_workflows:
            with workflow.open("r") as f:
                content = yaml.safe_load(f)

            if not content:
                continue

            # Check if workflow_call is in the 'on' triggers (YAML parses 'on:' as boolean True)
            triggers = content.get(True, content.get("on", {}))

            # 'on' can be a dict or a list
            has_workflow_call = False
            if isinstance(triggers, (dict, list)):
                has_workflow_call = "workflow_call" in triggers

            if not has_workflow_call:
                rel_path = workflow.relative_to(workflow.parents[3])
                failures.append(str(rel_path))

        if failures:
            msg = "Found reusable workflow(s) without workflow_call trigger:\n"
            for workflow in failures:
                msg += f"  - {workflow}\n"
            pytest.fail(msg)

    @pytest.mark.integration
    def test_workflows_have_name_field(self, workflow_files):
        """Verify all workflows have a name field for better identification.

        Parameters
        ----------
        workflow_files : list[Path]
            List of all workflow files.
        """
        missing_name = []

        for workflow in workflow_files:
            with workflow.open("r") as f:
                content = yaml.safe_load(f)

            if not content:
                continue

            if "name" not in content:
                rel_path = workflow.relative_to(workflow.parents[3])
                missing_name.append(str(rel_path))

        if missing_name:
            msg = "Found workflow(s) without 'name' field:\n"
            for workflow in missing_name:
                msg += f"  - {workflow}\n"
            msg += "\nAdd a 'name' field for better workflow identification in GitHub Actions UI."
            pytest.fail(msg)
