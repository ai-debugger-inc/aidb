"""Unit tests for TestExecutionService."""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from aidb_cli.services.test.test_execution_service import TestExecutionService


class TestTestExecutionService:
    """Test the TestExecutionService."""

    @pytest.fixture
    def mock_command_executor(self):
        """Create a mock command executor."""
        executor = Mock()
        executor.execute = Mock()
        executor.should_stream = Mock(return_value=True)
        return executor

    @pytest.fixture
    def execution_service(self, tmp_path, mock_command_executor):
        """Create a TestExecutionService instance with mocks."""
        # Create mock docker-compose file
        compose_dir = tmp_path / "src" / "tests" / "docker"
        compose_dir.mkdir(parents=True, exist_ok=True)
        compose_file = compose_dir / "docker-compose.yaml"
        compose_file.write_text("version: '3'")

        return TestExecutionService(
            repo_root=tmp_path,
            command_executor=mock_command_executor,
            skip_session_logging=True,
        )

    def test_build_docker_command_basic(self, execution_service, tmp_path):
        """Test building basic docker command."""
        cmd = execution_service.build_docker_command(profile="cli")

        assert cmd[0] == "docker"
        assert cmd[1] == "compose"
        assert "--project-directory" in cmd
        assert str(tmp_path) in cmd
        assert "-f" in cmd
        assert "--project-name" in cmd
        # Check that a project name follows --project-name
        proj_name_idx = cmd.index("--project-name")
        assert proj_name_idx + 1 < len(cmd)
        assert "--profile" in cmd
        assert "cli" in cmd
        assert "up" in cmd

    def test_build_docker_command_with_build(self, execution_service):
        """Test building docker command with build flag."""
        cmd = execution_service.build_docker_command(
            profile="cli",
            build=True,
        )

        assert "build" in cmd
        assert "up" not in cmd

    def test_build_docker_command_with_service(self, execution_service):
        """Test building docker command with specific service."""
        cmd = execution_service.build_docker_command(
            profile="cli",
            service="test-runner",
        )

        assert "up" in cmd
        assert "test-runner" in cmd

    def test_build_docker_command_with_override_command(self, execution_service):
        """Test building docker command with command override."""
        cmd = execution_service.build_docker_command(
            profile="cli",
            service="test-runner",
            command="pytest -v",
        )

        assert "up" in cmd
        assert "test-runner" in cmd
        assert "--" in cmd
        assert "pytest -v" in cmd

    def test_build_docker_command_detached(self, execution_service):
        """Test building docker command in detached mode."""
        cmd = execution_service.build_docker_command(
            profile="cli",
            detach=True,
        )

        assert "up" in cmd
        assert "-d" in cmd

    def test_prepare_test_environment_basic(self, execution_service, tmp_path):
        """Test preparing basic test environment."""
        env = execution_service.prepare_test_environment(
            suite="cli",
            language="python",
        )

        assert env["TEST_SUITE"] == "cli"
        assert env["TEST_LANGUAGE"] == "python"
        assert env["REPO_ROOT"] == str(tmp_path)

    def test_prepare_test_environment_with_options(self, execution_service):
        """Test preparing test environment with additional options."""
        env = execution_service.prepare_test_environment(
            suite="cli",
            language="python",
            markers="unit",
            pattern="test_foo",
            pytest_args="-vv",
            parallel=4,
        )

        assert env["TEST_SUITE"] == "cli"
        assert env["TEST_LANGUAGE"] == "python"
        assert env["TEST_MARKERS"] == "unit"
        assert env["TEST_PATTERN"] == "test_foo"
        assert env["PYTEST_ADDOPTS"] == "-vv"
        assert env["PYTEST_PARALLEL"] == "4"

    @patch("subprocess.Popen")
    @patch(
        "aidb_cli.services.docker.docker_image_checksum_service.DockerImageChecksumService",
    )
    @patch("aidb_cli.services.test.test_execution_service.DockerBuildService")
    def test_run_tests_success(
        self,
        mock_build_service_class,
        mock_checksum_service_class,
        mock_popen,
        execution_service,
        mock_command_executor,
    ):
        """Test successful test execution."""
        # Mock the build service
        mock_build_service = Mock()
        mock_build_service_class.return_value = mock_build_service

        # Mock the checksum service (no rebuild needed)
        mock_checksum_service = Mock()
        mock_checksum_service.check_all_images.return_value = {
            "base": (False, "Up to date"),
            "runtime": (False, "Up to date"),
        }
        mock_checksum_service_class.return_value = mock_checksum_service

        # Mock log streaming subprocess
        mock_logs_proc = Mock()
        mock_logs_proc.terminate = Mock()
        mock_logs_proc.wait = Mock()
        mock_popen.return_value = mock_logs_proc

        # Mock command executor responses
        ps_result = Mock(returncode=0, stdout="")
        mock_command_executor.execute.side_effect = [
            ps_result,  # docker compose ps
            Mock(returncode=0),  # docker compose up -d
            Mock(returncode=0, stdout="0"),  # docker wait <container>
        ]

        exit_code = execution_service.run_tests(
            suite="cli",
            profile="cli",
            env_vars={"TEST_PATTERN": "test_foo"},
        )

        assert exit_code == 0
        assert mock_command_executor.execute.call_count == 3

    @patch("subprocess.Popen")
    @patch(
        "aidb_cli.services.docker.docker_image_checksum_service.DockerImageChecksumService",
    )
    @patch("aidb_cli.services.test.test_execution_service.DockerBuildService")
    def test_run_tests_failure(
        self,
        mock_build_service_class,
        mock_checksum_service_class,
        mock_popen,
        execution_service,
        mock_command_executor,
    ):
        """Test failed test execution."""
        # Mock the build service
        mock_build_service = Mock()
        mock_build_service_class.return_value = mock_build_service

        # Mock the checksum service (no rebuild needed)
        mock_checksum_service = Mock()
        mock_checksum_service.check_all_images.return_value = {
            "base": (False, "Up to date"),
            "runtime": (False, "Up to date"),
        }
        mock_checksum_service_class.return_value = mock_checksum_service

        # Mock log streaming subprocess
        mock_logs_proc = Mock()
        mock_logs_proc.terminate = Mock()
        mock_logs_proc.wait = Mock()
        mock_popen.return_value = mock_logs_proc

        # Mock command executor responses - tests fail
        ps_result = Mock(returncode=0, stdout="")
        mock_command_executor.execute.side_effect = [
            ps_result,  # docker compose ps
            Mock(returncode=0),  # docker compose up -d
            Mock(returncode=0, stdout="1"),  # docker wait (exit code 1 in stdout)
        ]

        exit_code = execution_service.run_tests(
            suite="cli",
            profile="cli",
        )

        assert exit_code == 1

    @patch("subprocess.Popen")
    @patch(
        "aidb_cli.services.docker.docker_image_checksum_service.DockerImageChecksumService",
    )
    @patch("aidb_cli.services.test.test_execution_service.DockerBuildService")
    def test_run_tests_with_build(
        self,
        mock_build_service_class,
        mock_checksum_service_class,
        mock_popen,
        execution_service,
        mock_command_executor,
    ):
        """Test test execution with build flag."""
        # Mock the build service
        mock_build_service = Mock()
        mock_build_service.build_images = Mock(return_value=0)
        mock_build_service_class.return_value = mock_build_service

        # Mock the checksum service (rebuild needed but --build flag is set)
        mock_checksum_service = Mock()
        mock_checksum_service.check_all_images.return_value = {
            "base": (True, "Dependencies changed"),
            "runtime": (True, "Dependencies changed"),
        }
        mock_checksum_service.needs_rebuild.return_value = (False, "Up to date")
        mock_checksum_service.mark_built = Mock()
        mock_checksum_service_class.return_value = mock_checksum_service

        # Mock log streaming subprocess
        mock_logs_proc = Mock()
        mock_logs_proc.terminate = Mock()
        mock_logs_proc.wait = Mock()
        mock_popen.return_value = mock_logs_proc

        # Mock command executor responses
        ps_result = Mock(returncode=0, stdout="")
        mock_command_executor.execute.side_effect = [
            ps_result,  # docker compose ps
            Mock(returncode=0),  # docker compose up -d
            Mock(returncode=0, stdout="0"),  # docker wait <container>
        ]

        exit_code = execution_service.run_tests(
            suite="cli",
            profile="cli",
            build=True,
        )

        assert exit_code == 0
        # Verify build_images was called
        mock_build_service.build_images.assert_called_once()

    @patch(
        "aidb_cli.services.docker.docker_image_checksum_service.DockerImageChecksumService",
    )
    @patch("aidb_cli.services.test.test_execution_service.DockerBuildService")
    def test_run_tests_build_failure(
        self,
        mock_build_service_class,
        mock_checksum_service_class,
        execution_service,
        mock_command_executor,
    ):
        """Test test execution when build fails."""
        # Mock the build service to fail
        mock_build_service = Mock()
        mock_build_service.build_images = Mock(return_value=1)
        mock_build_service_class.return_value = mock_build_service

        # Mock the checksum service (rebuild needed)
        mock_checksum_service = Mock()
        mock_checksum_service.check_all_images.return_value = {
            "base": (True, "Dependencies changed"),
            "runtime": (True, "Dependencies changed"),
        }
        mock_checksum_service.needs_rebuild.return_value = (False, "Up to date")
        mock_checksum_service.mark_built = Mock()
        mock_checksum_service_class.return_value = mock_checksum_service

        exit_code = execution_service.run_tests(
            suite="cli",
            profile="cli",
            build=True,
        )

        assert exit_code == 1
        # Should not have called execute for test running
        mock_command_executor.execute.assert_not_called()

    @patch("subprocess.Popen")
    @patch(
        "aidb_cli.services.docker.docker_image_checksum_service.DockerImageChecksumService",
    )
    @patch("aidb_cli.services.test.test_execution_service.DockerBuildService")
    def test_run_tests_runtime_image_missing(
        self,
        mock_build_service_class,
        mock_checksum_service_class,
        mock_popen,
        execution_service,
        mock_command_executor,
    ):
        """Test test execution when Docker fails to start due to missing image."""
        # Mock the build service
        mock_build_service = Mock()
        mock_build_service_class.return_value = mock_build_service

        # Mock the checksum service (no rebuild needed)
        mock_checksum_service = Mock()
        mock_checksum_service.check_all_images.return_value = {
            "base": (False, "Up to date"),
            "runtime": (False, "Up to date"),
        }
        mock_checksum_service_class.return_value = mock_checksum_service

        # Mock log streaming subprocess
        mock_logs_proc = Mock()
        mock_logs_proc.terminate = Mock()
        mock_logs_proc.wait = Mock()
        mock_popen.return_value = mock_logs_proc

        # Mock docker ps (service not running) and docker compose up fails
        ps_result = Mock(returncode=0, stdout="")
        mock_command_executor.execute.side_effect = [
            ps_result,  # docker compose ps
            Mock(returncode=1),  # docker compose up fails
            Mock(returncode=0, stdout="1"),  # docker wait (if somehow reached)
        ]

        exit_code = execution_service.run_tests(
            suite="cli",
            profile="cli",
        )

        assert exit_code == 1

    @patch("subprocess.Popen")
    @patch(
        "aidb_cli.services.docker.docker_image_checksum_service.DockerImageChecksumService",
    )
    @patch("aidb_cli.services.test.test_execution_service.DockerBuildService")
    @patch.dict("os.environ", {"IS_GITHUB": "false"}, clear=False)
    def test_run_tests_auto_rebuild(
        self,
        mock_build_service_class,
        mock_checksum_service_class,
        mock_popen,
        execution_service,
        mock_command_executor,
    ):
        """Test automatic rebuild when checksum service detects changes."""
        # Mock the build service
        mock_build_service = Mock()
        mock_build_service.build_images = Mock(return_value=0)
        mock_build_service_class.return_value = mock_build_service

        # Mock the checksum service (rebuild needed, no --build flag)
        mock_checksum_service = Mock()
        mock_checksum_service.check_all_images.return_value = {
            "base": (True, "Dependencies changed"),
            "runtime": (False, "Up to date"),
        }
        mock_checksum_service.needs_rebuild.return_value = (False, "Up to date")
        mock_checksum_service.mark_built = Mock()
        mock_checksum_service_class.return_value = mock_checksum_service

        # Mock log streaming subprocess
        mock_logs_proc = Mock()
        mock_logs_proc.terminate = Mock()
        mock_logs_proc.wait = Mock()
        mock_popen.return_value = mock_logs_proc

        # Mock command executor responses
        ps_result = Mock(returncode=0, stdout="")
        mock_command_executor.execute.side_effect = [
            ps_result,  # docker compose ps
            Mock(returncode=0),  # docker compose up -d
            Mock(returncode=0, stdout="0"),  # docker wait <container>
        ]

        exit_code = execution_service.run_tests(
            suite="cli",
            profile="cli",
            build=False,  # No explicit build flag
        )

        assert exit_code == 0
        # Verify build_images was called automatically
        mock_build_service.build_images.assert_called_once()

    @patch(
        "aidb_cli.services.docker.service_dependency_service.ServiceDependencyService",
    )
    def test_run_tests_suite_service_mapping(
        self,
        mock_dep_service_class,
        execution_service,
        mock_command_executor,
    ):
        """Test that suite names map to correct service names."""
        # Mock ServiceDependencyService to return service list and container name
        mock_dep_service = Mock()
        mock_dep_service.get_services_by_profile.return_value = ["mcp-test-runner"]
        mock_dep_service.get_container_name.return_value = "aidb-mcp-test"
        mock_dep_service_class.return_value = mock_dep_service

        with patch("subprocess.Popen") as mock_popen:
            with patch(
                "aidb_cli.services.docker.docker_image_checksum_service.DockerImageChecksumService",
            ) as mock_checksum_service_class:
                with patch(
                    "aidb_cli.services.test.test_execution_service.DockerBuildService",
                ) as mock_build_service_class:
                    mock_build_service = Mock()
                    mock_build_service_class.return_value = mock_build_service

                    # Mock the checksum service (no rebuild needed)
                    mock_checksum_service = Mock()
                    mock_checksum_service.check_all_images.return_value = {
                        "base": (False, "Up to date"),
                        "runtime": (False, "Up to date"),
                    }
                    mock_checksum_service_class.return_value = mock_checksum_service

                    # Mock log streaming subprocess
                    mock_logs_proc = Mock()
                    mock_logs_proc.terminate = Mock()
                    mock_logs_proc.wait = Mock()
                    mock_popen.return_value = mock_logs_proc

                    ps_result = Mock(returncode=0, stdout="")
                    mock_command_executor.execute.side_effect = [
                        ps_result,  # docker compose ps
                        Mock(returncode=0),  # docker compose up -d
                        Mock(returncode=0, stdout="0"),  # docker wait
                    ]

                    execution_service.run_tests(
                        suite="mcp",
                        profile="mcp",
                    )

                    # Check that the wait command uses the correct container name
                    wait_call = mock_command_executor.execute.call_args_list[2]
                    wait_cmd = wait_call[0][0]
                    # Should be "docker wait aidb-mcp-test" not "docker compose wait"
                    assert "docker" in wait_cmd
                    assert "wait" in wait_cmd
                    assert "aidb-mcp-test" in wait_cmd

    @patch("aidb_cli.services.test.test_execution_service.StreamHandler")
    def test_run_local_tests_success(
        self,
        mock_stream_service_class,
        execution_service,
        mock_command_executor,
        tmp_path,
    ):
        """Test successful local test execution."""
        suite_path = tmp_path / "tests"
        suite_path.mkdir()

        # Mock StreamHandler.run_with_streaming
        mock_stream_service = Mock()
        mock_stream_service_class.return_value = mock_stream_service
        mock_result = Mock(
            returncode=0,
            stdout="All tests passed",
            stderr="",
        )
        mock_stream_service.run_with_streaming.return_value = mock_result

        # Mock should_stream to return True (use streaming path)
        mock_command_executor.should_stream.return_value = True

        exit_code = execution_service.run_local_tests(
            suite_path=suite_path,
            pytest_args=["-v", "-x"],
        )

        assert exit_code == 0
        # Verify streaming service was called
        assert mock_stream_service.run_with_streaming.called

    @patch("aidb_cli.services.test.test_execution_service.subprocess.Popen")
    def test_run_local_tests_failure(
        self,
        mock_popen,
        execution_service,
        mock_command_executor,
        tmp_path,
    ):
        """Test failed local test execution."""
        suite_path = tmp_path / "tests"
        suite_path.mkdir()

        # Mock should_stream to return False (use non-streaming path)
        mock_command_executor.should_stream.return_value = False

        # Mock Popen to simulate test failure
        mock_process = Mock()
        mock_process.stdout = iter(["Test failures\n"])
        mock_process.wait.return_value = 1
        mock_popen.return_value = mock_process

        exit_code = execution_service.run_local_tests(suite_path=suite_path)

        assert exit_code == 1
        # Verify Popen was called
        assert mock_popen.called

    def test_clean_test_environment_success(
        self,
        execution_service,
        mock_command_executor,
    ):
        """Test successful test environment cleanup."""
        mock_command_executor.execute.return_value = Mock(returncode=0)

        exit_code = execution_service.clean_test_environment()

        assert exit_code == 0
        # Verify cleanup command was correct
        call_args = mock_command_executor.execute.call_args
        cmd = call_args[0][0]
        assert "docker" in cmd
        assert "compose" in cmd
        assert "down" in cmd
        assert "--volumes" in cmd
        assert "--remove-orphans" in cmd

    def test_clean_test_environment_failure(
        self,
        execution_service,
        mock_command_executor,
    ):
        """Test failed test environment cleanup."""
        mock_command_executor.execute.return_value = Mock(returncode=1)

        exit_code = execution_service.clean_test_environment()

        assert exit_code == 1

    def test_run_shell(self, execution_service, mock_command_executor):
        """Test opening interactive shell."""
        mock_command_executor.execute.return_value = Mock(returncode=0)

        exit_code = execution_service.run_shell(profile="shell")

        assert exit_code == 0
        # Verify shell command
        call_args = mock_command_executor.execute.call_args
        cmd = call_args[0][0]
        assert "shell" in cmd
        assert "/bin/bash" in cmd

    def test_build_docker_images_success(
        self,
        execution_service,
        mock_command_executor,
    ):
        """Test successful Docker image build."""
        mock_command_executor.execute.return_value = Mock(returncode=0)

        exit_code = execution_service.build_docker_images(
            profile="cli",
            verbose=True,
        )

        assert exit_code == 0
        # Verify build command
        call_args = mock_command_executor.execute.call_args
        cmd = call_args[0][0]
        assert "build" in cmd
        assert "cli" in cmd

    def test_build_docker_images_failure(
        self,
        execution_service,
        mock_command_executor,
    ):
        """Test failed Docker image build."""
        mock_command_executor.execute.return_value = Mock(returncode=1)

        exit_code = execution_service.build_docker_images(profile="cli")

        assert exit_code == 1

    @patch.dict("os.environ", {"IS_GITHUB": "true"}, clear=False)
    @patch("subprocess.Popen")
    def test_ensure_test_images_skips_checksum_in_ci(
        self,
        mock_popen,
        execution_service,
        mock_command_executor,
    ):
        """Test that checksum service is skipped in CI (IS_GITHUB=true).

        When IS_GITHUB=true and build=False, the _ensure_test_images method should
        return early without instantiating the checksum service. This uses pre-pulled
        GHCR images instead of rebuilding.
        """
        # Mock log streaming subprocess
        mock_logs_proc = Mock()
        mock_logs_proc.terminate = Mock()
        mock_logs_proc.wait = Mock()
        mock_popen.return_value = mock_logs_proc

        # Mock command executor responses
        ps_result = Mock(returncode=0, stdout="")
        mock_command_executor.execute.side_effect = [
            ps_result,  # docker compose ps
            Mock(returncode=0),  # docker compose up -d
            Mock(returncode=0, stdout="0"),  # docker wait <container>
        ]

        # Should NOT patch checksum service - we want to verify it's NOT called
        # If checksum service was instantiated, it would fail without the mock
        exit_code = execution_service.run_tests(
            suite="cli",
            profile="cli",
            build=False,  # No explicit build flag
        )

        assert exit_code == 0

    @patch.dict("os.environ", {"IS_GITHUB": "true"}, clear=False)
    @patch("subprocess.Popen")
    @patch(
        "aidb_cli.services.docker.docker_image_checksum_service.DockerImageChecksumService",
    )
    @patch("aidb_cli.services.test.test_execution_service.DockerBuildService")
    def test_ensure_test_images_builds_in_ci_when_build_flag_set(
        self,
        mock_build_service_class,
        mock_checksum_service_class,
        mock_popen,
        execution_service,
        mock_command_executor,
    ):
        """Test that build is executed even in CI when --build flag is set.

        When IS_GITHUB=true but build=True, the checksum service should still be used
        and images should be built.
        """
        # Mock the build service
        mock_build_service = Mock()
        mock_build_service.build_images = Mock(return_value=0)
        mock_build_service_class.return_value = mock_build_service

        # Mock the checksum service
        mock_checksum_service = Mock()
        mock_checksum_service.check_all_images.return_value = {
            "base": (False, "Up to date"),
            "runtime": (False, "Up to date"),
        }
        mock_checksum_service_class.return_value = mock_checksum_service

        # Mock log streaming subprocess
        mock_logs_proc = Mock()
        mock_logs_proc.terminate = Mock()
        mock_logs_proc.wait = Mock()
        mock_popen.return_value = mock_logs_proc

        # Mock command executor responses
        ps_result = Mock(returncode=0, stdout="")
        mock_command_executor.execute.side_effect = [
            ps_result,  # docker compose ps
            Mock(returncode=0),  # docker compose up -d
            Mock(returncode=0, stdout="0"),  # docker wait <container>
        ]

        exit_code = execution_service.run_tests(
            suite="cli",
            profile="cli",
            build=True,  # Explicit build flag
        )

        assert exit_code == 0
        # Verify build_images was called despite IS_GITHUB=true
        mock_build_service.build_images.assert_called_once()

    @patch.dict("os.environ", {}, clear=False)
    @patch("subprocess.Popen")
    @patch(
        "aidb_cli.services.docker.docker_image_checksum_service.DockerImageChecksumService",
    )
    @patch("aidb_cli.services.test.test_execution_service.DockerBuildService")
    def test_ensure_test_images_uses_checksum_locally(
        self,
        mock_build_service_class,
        mock_checksum_service_class,
        mock_popen,
        execution_service,
        mock_command_executor,
    ):
        """Test that checksum service is used locally (IS_GITHUB not set).

        When IS_GITHUB is not set (local development), the checksum service should be
        used to determine if images need rebuilding.
        """
        # Ensure IS_GITHUB is not set
        import os

        os.environ.pop("IS_GITHUB", None)

        # Mock the build service
        mock_build_service = Mock()
        mock_build_service_class.return_value = mock_build_service

        # Mock the checksum service (no rebuild needed)
        mock_checksum_service = Mock()
        mock_checksum_service.check_all_images.return_value = {
            "base": (False, "Up to date"),
            "runtime": (False, "Up to date"),
        }
        mock_checksum_service_class.return_value = mock_checksum_service

        # Mock log streaming subprocess
        mock_logs_proc = Mock()
        mock_logs_proc.terminate = Mock()
        mock_logs_proc.wait = Mock()
        mock_popen.return_value = mock_logs_proc

        # Mock command executor responses
        ps_result = Mock(returncode=0, stdout="")
        mock_command_executor.execute.side_effect = [
            ps_result,  # docker compose ps
            Mock(returncode=0),  # docker compose up -d
            Mock(returncode=0, stdout="0"),  # docker wait <container>
        ]

        exit_code = execution_service.run_tests(
            suite="cli",
            profile="cli",
            build=False,
        )

        assert exit_code == 0
        # Verify checksum service was instantiated and used
        mock_checksum_service_class.assert_called_once()
        mock_checksum_service.check_all_images.assert_called_once()
