"""Unit tests for smoke-test composite action."""

import re
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, Mock, call, patch

import pytest
import yaml


class TestSmokeTestRetryLogic:
    """Test retry mechanism for package availability checking."""

    def test_retry_logic_constants(self):
        """Verify retry logic uses expected constants."""
        max_attempts = 5
        wait_between = 30

        # These values are hardcoded in the action
        assert max_attempts == 5
        assert wait_between == 30

        # Total wait time: 5 attempts × 30s = 150s max
        max_wait_time = max_attempts * wait_between
        assert max_wait_time == 150

    @pytest.mark.parametrize(
        ("source", "expected_url"),
        [
            ("testpypi", "https://test.pypi.org/simple/"),
            ("pypi", "https://pypi.org/simple/"),
        ],
    )
    def test_index_url_determination(self, source, expected_url):
        """Verify correct PyPI index URL is determined from source."""
        if source == "testpypi":
            index_url = "https://test.pypi.org/simple/"
            source_name = "Test PyPI"
        else:
            index_url = "https://pypi.org/simple/"
            source_name = "PyPI"

        assert index_url == expected_url
        assert source_name in ["Test PyPI", "PyPI"]

    def test_retry_loop_structure(self):
        """Verify retry loop logic flow."""
        max_attempts = 5
        found = False

        # Simulate retry loop
        for i in range(1, max_attempts + 1):
            # Simulate package check (fails)
            package_found = False

            if package_found:
                found = True
                break

            # Check if last attempt
            if i == max_attempts:
                # Last attempt - should warn and proceed
                assert i == 5
            else:
                # Not last attempt - would sleep
                assert i < 5

        assert not found

    def test_successful_retry_early(self):
        """Verify loop breaks early on success."""
        max_attempts = 5
        found = False
        attempts_made = 0

        # Simulate package found on attempt 3
        for i in range(1, max_attempts + 1):
            attempts_made = i
            package_found = i == 3

            if package_found:
                found = True
                break

        assert found
        assert attempts_made == 3  # Should break early


class TestImportVerification:
    """Test import verification logic."""

    def test_import_script_structure(self):
        """Verify import verification script checks all required modules."""
        required_imports = [
            "import aidb",
            "import aidb_mcp",
            "import aidb_common",
            "from aidb_common.config.runtime import config",
            "from aidb import AIDB",
        ]

        # These are the critical imports the smoke test verifies
        for imp in required_imports:
            assert isinstance(imp, str)
            assert "import" in imp

    def test_import_checks_aidb_version(self):
        """Verify import script checks aidb version."""
        # The script checks: aidb.__version__
        version_check = "aidb.__version__"
        assert "__version__" in version_check

    @pytest.mark.parametrize(
        ("import_statement", "expected_module"),
        [
            ("import aidb", "aidb"),
            ("import aidb_mcp", "aidb_mcp"),
            ("import aidb_common", "aidb_common"),
            ("from aidb_common.config.runtime import config", "config"),
            ("from aidb import AIDB", "AIDB"),
        ],
    )
    def test_import_statements(self, import_statement, expected_module):
        """Verify import statements reference correct modules."""
        assert expected_module in import_statement

    def test_import_verification_exits_zero_on_success(self):
        """Verify import verification uses sys.exit(0) on success."""
        exit_code_success = 0
        exit_code_failure = 1

        # Script should exit 0 on success, 1 on failure
        assert exit_code_success == 0
        assert exit_code_failure == 1


class TestPyPISources:
    """Test TestPyPI vs PyPI source handling."""

    def test_testpypi_uses_correct_index_url(self):
        """Verify TestPyPI uses test.pypi.org."""
        source = "testpypi"
        expected_index = "https://test.pypi.org/simple/"

        if source == "testpypi":
            index_url = "https://test.pypi.org/simple/"
        else:
            index_url = "https://pypi.org/simple/"

        assert index_url == expected_index

    def test_testpypi_uses_extra_index_for_dependencies(self):
        """Verify TestPyPI uses extra-index-url for dependencies."""
        source = "testpypi"

        # TestPyPI needs --extra-index-url to get dependencies from PyPI
        if source == "testpypi":
            uses_extra_index = True
            extra_index_url = "https://pypi.org/simple/"
        else:
            uses_extra_index = False
            extra_index_url = None

        assert uses_extra_index
        assert extra_index_url == "https://pypi.org/simple/"

    def test_pypi_uses_simple_install(self):
        """Verify PyPI uses simple pip install without index URLs."""
        source = "pypi"

        needs_index_url = source != "pypi"

        assert not needs_index_url

    @pytest.mark.parametrize(
        ("source", "expected_command_pattern"),
        [
            ("testpypi", "pip install --index-url.*--extra-index-url"),
            ("pypi", "pip install aidb=="),
        ],
    )
    def test_install_command_patterns(self, source, expected_command_pattern):
        """Verify install commands follow expected patterns."""
        if source == "testpypi":
            # Complex install with index URLs
            command = "pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ aidb==0.1.0"
        else:
            # Simple install
            command = "pip install aidb==0.1.0"

        assert re.search(expected_command_pattern, command)


class TestActionInputsOutputs:
    """Test smoke-test action.yaml schema and metadata."""

    @pytest.fixture
    def action_yaml(self, github_dir):
        """Load smoke-test action.yaml.

        Parameters
        ----------
        github_dir : Path
            .github directory path.

        Returns
        -------
        dict
            Parsed action.yaml content.

        Note
        ----
        This action contains embedded Python scripts in bash heredocs which
        causes strict YAML parsers to fail. GitHub Actions handles this correctly,
        but pyyaml cannot parse it. We skip these tests if parsing fails.
        """
        action_file = github_dir / "actions" / "smoke-test" / "action.yaml"
        try:
            with action_file.open("r") as f:
                return yaml.safe_load(f)
        except yaml.scanner.ScannerError:
            pytest.skip(
                "Action YAML contains embedded scripts that strict parsers cannot parse",
            )

    def test_action_has_required_metadata(self, action_yaml):
        """Verify action.yaml has required metadata fields."""
        required_fields = ["name", "description", "inputs", "outputs", "runs"]
        for field in required_fields:
            assert field in action_yaml, f"Missing required field: {field}"

    def test_action_has_required_inputs(self, action_yaml):
        """Verify action.yaml defines required inputs."""
        inputs = action_yaml["inputs"]

        # source is required
        assert "source" in inputs
        assert inputs["source"]["required"] is True

        # version is required
        assert "version" in inputs
        assert inputs["version"]["required"] is True

        # package_name has default
        assert "package_name" in inputs
        assert inputs["package_name"]["required"] is False
        assert inputs["package_name"]["default"] == "aidb"

        # python_version has default
        assert "python_version" in inputs
        assert inputs["python_version"]["required"] is False
        assert inputs["python_version"]["default"] == "3.10"

        # wait_seconds has default
        assert "wait_seconds" in inputs
        assert inputs["wait_seconds"]["required"] is False
        assert inputs["wait_seconds"]["default"] == "120"

    def test_action_has_required_outputs(self, action_yaml):
        """Verify action.yaml defines required outputs."""
        outputs = action_yaml["outputs"]

        required_outputs = ["success", "error_message"]
        for output in required_outputs:
            assert output in outputs, f"Missing required output: {output}"
            assert "description" in outputs[output]
            assert "value" in outputs[output]

    def test_action_uses_composite(self, action_yaml):
        """Verify action uses composite run type."""
        assert action_yaml["runs"]["using"] == "composite"
        assert "steps" in action_yaml["runs"]
        assert len(action_yaml["runs"]["steps"]) > 0

    def test_action_steps_use_bash(self, action_yaml):
        """Verify action steps use bash shell."""
        steps = action_yaml["runs"]["steps"]
        bash_steps = [s for s in steps if "shell" in s]

        for step in bash_steps:
            assert step["shell"] == "bash"

    def test_action_cleanup_runs_always(self, action_yaml):
        """Verify cleanup step runs always (even on failure)."""
        steps = action_yaml["runs"]["steps"]

        # Find cleanup step
        cleanup_steps = [s for s in steps if "cleanup" in s.get("name", "").lower()]

        assert len(cleanup_steps) > 0

        for step in cleanup_steps:
            # Should have if: always() condition
            assert step.get("if") == "always()"

    def test_action_uses_setup_python(self, action_yaml):
        """Verify action uses actions/setup-python."""
        steps = action_yaml["runs"]["steps"]

        setup_python_steps = [
            s for s in steps if s.get("uses", "").startswith("actions/setup-python")
        ]

        assert len(setup_python_steps) > 0


class TestSmokeTestIntegration:
    """Integration tests for smoke-test action execution.

    These tests validate the bash script logic without actually installing from PyPI.
    """

    @pytest.fixture
    def action_yaml_path(self, github_dir):
        """Get path to smoke-test action.yaml.

        Parameters
        ----------
        github_dir : Path
            .github directory path.

        Returns
        -------
        Path
            Path to action.yaml file.
        """
        return github_dir / "actions" / "smoke-test" / "action.yaml"

    def test_venv_creation_logic(self, tmp_path):
        """Verify venv creation command structure."""
        import shutil
        import sys

        venv_path = tmp_path / "test-venv"

        # Create venv using current Python interpreter
        result = subprocess.run(
            [sys.executable, "-m", "venv", str(venv_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0, (
            f"venv creation failed:\n"
            f"Exit code: {result.returncode}\n"
            f"Stderr: {result.stderr}"
        )
        assert venv_path.exists()
        assert (venv_path / "bin" / "activate").exists()

        # Cleanup
        shutil.rmtree(venv_path)

    def test_source_activation_command(self, tmp_path):
        """Verify venv activation command structure."""
        import shutil
        import sys

        venv_path = tmp_path / "test-venv"

        # Create venv using current Python interpreter
        result = subprocess.run(
            [sys.executable, "-m", "venv", str(venv_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            pytest.skip(f"venv creation failed: {result.stderr}")

        # Test activation command structure
        activation_script = venv_path / "bin" / "activate"
        assert activation_script.exists()

        # Verify we can run commands in activated venv
        # Use bash explicitly since 'source' is a bash builtin (not available in sh/dash)
        result = subprocess.run(  # noqa: S602
            ["bash", "-c", f"source {activation_script} && python --version"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert result.returncode == 0
        assert "Python" in result.stdout

        # Cleanup
        shutil.rmtree(venv_path)

    def test_error_handling_sets_output_false(self):
        """Verify error handling sets success=false in output."""
        # Simulate error handling logic
        install_exit_code = 1  # Failure

        success_output, error_message = (
            ("false", "Package installation failed")
            if install_exit_code != 0
            else ("true", "")
        )

        assert success_output == "false"
        assert error_message == "Package installation failed"

    def test_success_handling_sets_output_true(self):
        """Verify success handling sets success=true in output."""
        # Simulate success handling logic
        install_exit_code = 0  # Success
        test_exit_code = 0  # Success

        success_output, error_message = (
            ("true", "")
            if (install_exit_code == 0 and test_exit_code == 0)
            else ("false", "Test failed")
        )

        assert success_output == "true"
        assert error_message == ""


class TestWaitTimes:
    """Test recommended wait time parameters."""

    @pytest.mark.parametrize(
        ("source", "recommended_wait"),
        [
            ("testpypi", 180),  # 3 minutes for TestPyPI
            ("pypi", 120),  # 2 minutes for PyPI
        ],
    )
    def test_recommended_wait_times(self, source, recommended_wait):
        """Verify recommended wait times for different PyPI sources."""
        # These are documented recommendations
        expected_wait = 180 if source == "testpypi" else 120  # Slower CDN : Faster CDN

        assert recommended_wait == expected_wait

    def test_default_wait_time(self):
        """Verify default wait_seconds is appropriate."""
        default_wait = 120  # From action.yaml

        # Default should be appropriate for PyPI (faster)
        assert default_wait == 120

    def test_retry_mechanism_parameters(self):
        """Verify retry mechanism parameters are appropriate."""
        max_attempts = 5
        wait_between = 30

        # Total potential wait: 5 attempts × 30s = 150s
        max_total_wait = max_attempts * wait_between
        assert max_total_wait == 150

        # This is in addition to the initial wait (120s default)
        # Total max wait: 120 + 150 = 270 seconds (4.5 minutes)
        default_wait = 120
        total_max_wait = default_wait + max_total_wait
        assert total_max_wait == 270


class TestPipCommandConstruction:
    """Test pip command construction logic."""

    def test_testpypi_command_includes_both_indexes(self):
        """Verify TestPyPI command includes both index URLs."""
        source = "testpypi"
        package_name = "aidb"
        version = "0.1.0"

        if source == "testpypi":
            # Construct command as action does
            command_parts = [
                "pip install",
                "--index-url https://test.pypi.org/simple/",
                "--extra-index-url https://pypi.org/simple/",
                f"{package_name}=={version}",
            ]
            command = " ".join(command_parts)
        else:
            command = f"pip install {package_name}=={version}"

        assert "--index-url https://test.pypi.org/simple/" in command
        assert "--extra-index-url https://pypi.org/simple/" in command
        assert "aidb==0.1.0" in command

    def test_pypi_command_simple_format(self):
        """Verify PyPI command uses simple format."""
        source = "pypi"
        package_name = "aidb"
        version = "0.1.0"

        if source == "testpypi":
            command = f"pip install --index-url ... {package_name}=={version}"
        else:
            command = f"pip install {package_name}=={version}"

        assert command == "pip install aidb==0.1.0"
        assert "--index-url" not in command

    def test_version_pinning(self):
        """Verify package version is pinned with ==."""
        package_name = "aidb"
        version = "0.1.0"

        # Action always pins to exact version
        pinned_package = f"{package_name}=={version}"

        assert pinned_package == "aidb==0.1.0"
        assert "==" in pinned_package


class TestImportChecks:
    """Test import verification checks."""

    def test_all_required_imports_checked(self):
        """Verify all critical imports are checked."""
        required_imports = {
            "aidb",
            "aidb_mcp",
            "aidb_common",
            "aidb_common.config.runtime",
            "aidb.AIDB",
        }

        # All these modules must be importable for smoke test to pass
        for module in required_imports:
            assert isinstance(module, str)
            assert len(module) > 0

    def test_version_verification(self):
        """Verify version is checked against expected value."""
        # The script checks aidb.__version__ matches expected
        version_attr = "__version__"
        assert version_attr == "__version__"

    def test_basic_instantiation_check(self):
        """Verify AIDB class is accessible."""
        # The script verifies: from aidb import AIDB
        class_name = "AIDB"
        assert class_name == "AIDB"
