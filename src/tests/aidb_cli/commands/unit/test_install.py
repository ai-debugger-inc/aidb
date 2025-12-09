"""Tests for install commands."""

from pathlib import Path
from unittest.mock import Mock, PropertyMock, patch

import pytest
from click.testing import CliRunner

from aidb.common.errors import AidbError
from aidb_cli.cli import cli


class TestInstallCommands:
    """Test install commands."""

    def test_setup_default(self, cli_runner, mock_repo_root):
        """Test install setup with default options (no verbose, no completion)."""
        install_script = mock_repo_root / "scripts/install/src/install.sh"
        install_script.parent.mkdir(parents=True, exist_ok=True)
        install_script.touch()

        mock_command_executor = Mock()
        mock_result = Mock()
        mock_result.returncode = 0
        mock_command_executor.execute.return_value = mock_result

        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch(
                "aidb_cli.cli.Context.command_executor",
                new_callable=PropertyMock,
                return_value=mock_command_executor,
            ):
                result = cli_runner.invoke(cli, ["install", "setup"])
                assert result.exit_code == 0
                assert "Installing AIDB" in result.output
                assert "Installation complete" in result.output
                assert "Optional: enable shell completion" in result.output

                mock_command_executor.execute.assert_called_once()
                call_args = mock_command_executor.execute.call_args[0][0]
                assert "install.sh" in call_args[0]
                assert "-v" not in call_args

    def test_setup_with_verbose(self, cli_runner, mock_repo_root):
        """Test install setup with --verbose flag."""
        install_script = mock_repo_root / "scripts/install/src/install.sh"
        install_script.parent.mkdir(parents=True, exist_ok=True)
        install_script.touch()

        mock_command_executor = Mock()
        mock_result = Mock()
        mock_result.returncode = 0
        mock_command_executor.execute.return_value = mock_result

        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch(
                "aidb_cli.cli.Context.command_executor",
                new_callable=PropertyMock,
                return_value=mock_command_executor,
            ):
                result = cli_runner.invoke(cli, ["install", "setup", "--verbose"])
                assert result.exit_code == 0

                call_args = mock_command_executor.execute.call_args[0][0]
                assert "-v" in call_args

    def test_setup_with_completion(self, cli_runner, mock_repo_root):
        """Test install setup with --completion flag."""
        install_script = mock_repo_root / "scripts/install/src/install.sh"
        install_script.parent.mkdir(parents=True, exist_ok=True)
        install_script.touch()

        dev_cli = mock_repo_root / "dev-cli"
        dev_cli.touch()

        mock_command_executor = Mock()
        install_result = Mock()
        install_result.returncode = 0
        completion_result = Mock()
        completion_result.returncode = 0
        mock_command_executor.execute.side_effect = [install_result, completion_result]

        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch(
                "aidb_cli.cli.Context.command_executor",
                new_callable=PropertyMock,
                return_value=mock_command_executor,
            ):
                result = cli_runner.invoke(cli, ["install", "setup", "--completion"])
                assert result.exit_code == 0
                assert "Installing shell completion" in result.output
                assert "Shell completion installed" in result.output

                assert mock_command_executor.execute.call_count == 2
                completion_call = mock_command_executor.execute.call_args_list[1][0][0]
                assert "dev-cli" in completion_call[0]
                assert "completion" in completion_call
                assert "install" in completion_call
                assert "--yes" in completion_call

    def test_setup_with_completion_shell(self, cli_runner, mock_repo_root):
        """Test install setup with --completion and --completion-shell."""
        install_script = mock_repo_root / "scripts/install/src/install.sh"
        install_script.parent.mkdir(parents=True, exist_ok=True)
        install_script.touch()

        dev_cli = mock_repo_root / "dev-cli"
        dev_cli.touch()

        mock_command_executor = Mock()
        install_result = Mock()
        install_result.returncode = 0
        completion_result = Mock()
        completion_result.returncode = 0
        mock_command_executor.execute.side_effect = [install_result, completion_result]

        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch(
                "aidb_cli.cli.Context.command_executor",
                new_callable=PropertyMock,
                return_value=mock_command_executor,
            ):
                result = cli_runner.invoke(
                    cli,
                    [
                        "install",
                        "setup",
                        "--completion",
                        "--completion-shell",
                        "bash",
                    ],
                )
                assert result.exit_code == 0

                completion_call = mock_command_executor.execute.call_args_list[1][0][0]
                assert "--shell" in completion_call
                assert "bash" in completion_call

    def test_setup_with_all_completion_options(self, cli_runner, mock_repo_root):
        """Test install setup with all completion options."""
        install_script = mock_repo_root / "scripts/install/src/install.sh"
        install_script.parent.mkdir(parents=True, exist_ok=True)
        install_script.touch()

        dev_cli = mock_repo_root / "dev-cli"
        dev_cli.touch()

        rc_file = mock_repo_root / ".bashrc"

        mock_command_executor = Mock()
        install_result = Mock()
        install_result.returncode = 0
        completion_result = Mock()
        completion_result.returncode = 0
        mock_command_executor.execute.side_effect = [install_result, completion_result]

        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch(
                "aidb_cli.cli.Context.command_executor",
                new_callable=PropertyMock,
                return_value=mock_command_executor,
            ):
                result = cli_runner.invoke(
                    cli,
                    [
                        "install",
                        "setup",
                        "--completion",
                        "--completion-shell",
                        "bash",
                        "--completion-rc-file",
                        str(rc_file),
                        "--completion-no-backup",
                        "--completion-also-bashrc",
                    ],
                )
                assert result.exit_code == 0

                completion_call = mock_command_executor.execute.call_args_list[1][0][0]
                assert "--shell" in completion_call
                assert "bash" in completion_call
                assert "--rc-file" in completion_call
                assert str(rc_file) in completion_call
                assert "--no-backup" in completion_call
                assert "--also-bashrc" in completion_call

    def test_setup_install_failure(self, cli_runner, mock_repo_root):
        """Test install setup handles install script failure."""
        install_script = mock_repo_root / "scripts/install/src/install.sh"
        install_script.parent.mkdir(parents=True, exist_ok=True)
        install_script.touch()

        mock_command_executor = Mock()
        mock_result = Mock()
        mock_result.returncode = 1
        mock_command_executor.execute.return_value = mock_result

        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch(
                "aidb_cli.cli.Context.command_executor",
                new_callable=PropertyMock,
                return_value=mock_command_executor,
            ):
                result = cli_runner.invoke(cli, ["install", "setup"])
                assert result.exit_code == 1
                assert "Installation failed" in result.output

    def test_setup_completion_failure_shows_info(self, cli_runner, mock_repo_root):
        """Test install setup shows info message on completion install failure."""
        install_script = mock_repo_root / "scripts/install/src/install.sh"
        install_script.parent.mkdir(parents=True, exist_ok=True)
        install_script.touch()

        dev_cli = mock_repo_root / "dev-cli"
        dev_cli.touch()

        mock_command_executor = Mock()
        install_result = Mock()
        install_result.returncode = 0
        completion_result = Mock()
        completion_result.returncode = 1
        mock_command_executor.execute.side_effect = [install_result, completion_result]

        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch(
                "aidb_cli.cli.Context.command_executor",
                new_callable=PropertyMock,
                return_value=mock_command_executor,
            ):
                result = cli_runner.invoke(cli, ["install", "setup", "--completion"])
                assert result.exit_code == 0
                assert (
                    "Shell completion install returned a non-zero status"
                    in result.output
                )
                assert "./dev-cli completion install" in result.output

    def test_setup_missing_install_script(self, cli_runner, mock_repo_root):
        """Test install setup raises FileNotFoundError when script is missing."""
        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch("aidb_cli.commands.install.normalize_path") as mock_normalize:
                mock_path = mock_repo_root / "scripts/install/src/install.sh"
                mock_normalize.return_value = mock_path
                result = cli_runner.invoke(cli, ["install", "setup"])
                # FileNotFoundError converted to ExitCode.NOT_FOUND (2) by handle_exceptions
                assert result.exit_code == 2
                assert "File not found" in result.output

    def test_debug_always_verbose(self, cli_runner, mock_repo_root):
        """Test install debug always includes -v flag."""
        install_script = mock_repo_root / "scripts/install/src/install.sh"
        install_script.parent.mkdir(parents=True, exist_ok=True)
        install_script.touch()

        mock_command_executor = Mock()
        mock_result = Mock()
        mock_result.returncode = 0
        mock_command_executor.execute.return_value = mock_result

        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch(
                "aidb_cli.cli.Context.command_executor",
                new_callable=PropertyMock,
                return_value=mock_command_executor,
            ):
                result = cli_runner.invoke(cli, ["install", "debug"])
                assert result.exit_code == 0

                call_args = mock_command_executor.execute.call_args[0][0]
                assert "-v" in call_args

    def test_debug_with_completion(self, cli_runner, mock_repo_root):
        """Test install debug with completion options."""
        install_script = mock_repo_root / "scripts/install/src/install.sh"
        install_script.parent.mkdir(parents=True, exist_ok=True)
        install_script.touch()

        dev_cli = mock_repo_root / "dev-cli"
        dev_cli.touch()

        mock_command_executor = Mock()
        install_result = Mock()
        install_result.returncode = 0
        completion_result = Mock()
        completion_result.returncode = 0
        mock_command_executor.execute.side_effect = [install_result, completion_result]

        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch(
                "aidb_cli.cli.Context.command_executor",
                new_callable=PropertyMock,
                return_value=mock_command_executor,
            ):
                result = cli_runner.invoke(cli, ["install", "debug", "--completion"])
                assert result.exit_code == 0
                assert "Shell completion installed" in result.output

    def test_debug_failure(self, cli_runner, mock_repo_root):
        """Test install debug handles failure."""
        install_script = mock_repo_root / "scripts/install/src/install.sh"
        install_script.parent.mkdir(parents=True, exist_ok=True)
        install_script.touch()

        mock_command_executor = Mock()
        mock_result = Mock()
        mock_result.returncode = 1
        mock_command_executor.execute.return_value = mock_result

        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch(
                "aidb_cli.cli.Context.command_executor",
                new_callable=PropertyMock,
                return_value=mock_command_executor,
            ):
                result = cli_runner.invoke(cli, ["install", "debug"])
                assert result.exit_code == 1
                assert "Debug installation failed" in result.output

    def test_debug_missing_script(self, cli_runner, mock_repo_root):
        """Test install debug raises error when script missing."""
        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch("aidb_cli.commands.install.normalize_path") as mock_normalize:
                mock_path = mock_repo_root / "scripts/install/src/install.sh"
                mock_normalize.return_value = mock_path
                result = cli_runner.invoke(cli, ["install", "debug"])
                # FileNotFoundError converted to ExitCode.NOT_FOUND (2) by handle_exceptions
                assert result.exit_code == 2
                assert "File not found" in result.output

    def test_reinstall_removes_venv(self, cli_runner, mock_repo_root):
        """Test install reinstall removes venv directory."""
        install_script = mock_repo_root / "scripts/install/src/install.sh"
        install_script.parent.mkdir(parents=True, exist_ok=True)
        install_script.touch()

        venv_path = mock_repo_root / "venv"
        venv_path.mkdir()

        mock_command_executor = Mock()
        mock_result = Mock()
        mock_result.returncode = 0
        mock_command_executor.execute.return_value = mock_result

        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch(
                "aidb_cli.cli.Context.command_executor",
                new_callable=PropertyMock,
                return_value=mock_command_executor,
            ):
                with patch(
                    "aidb_cli.commands.install.normalize_path",
                ) as mock_normalize:
                    mock_normalize.return_value = install_script
                    with patch("shutil.rmtree") as mock_rmtree:
                        result = cli_runner.invoke(
                            cli,
                            ["install", "reinstall"],
                            input="y\n",
                        )
                        assert result.exit_code == 0
                        assert "Removing existing virtual environment" in result.output
                        assert "Reinstalling AIDB" in result.output
                        # rmtree was called with venv path
                        assert mock_rmtree.call_count == 1
                        called_path = mock_rmtree.call_args[0][0]
                        assert called_path.name == "venv"

    def test_reinstall_with_completion(self, cli_runner, mock_repo_root):
        """Test install reinstall with completion options."""
        install_script = mock_repo_root / "scripts/install/src/install.sh"
        install_script.parent.mkdir(parents=True, exist_ok=True)
        install_script.touch()

        dev_cli = mock_repo_root / "dev-cli"
        dev_cli.touch()

        venv_path = mock_repo_root / "venv"
        venv_path.mkdir()

        mock_command_executor = Mock()
        install_result = Mock()
        install_result.returncode = 0
        completion_result = Mock()
        completion_result.returncode = 0
        mock_command_executor.execute.side_effect = [install_result, completion_result]

        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch(
                "aidb_cli.cli.Context.command_executor",
                new_callable=PropertyMock,
                return_value=mock_command_executor,
            ):
                with patch("shutil.rmtree"):
                    result = cli_runner.invoke(
                        cli,
                        ["install", "reinstall", "--completion"],
                        input="y\n",
                    )
                    assert result.exit_code == 0
                    assert "Shell completion installed" in result.output

    def test_reinstall_venv_removal_failure(self, cli_runner, mock_repo_root):
        """Test install reinstall handles venv removal failure."""
        install_script = mock_repo_root / "scripts/install/src/install.sh"
        install_script.parent.mkdir(parents=True, exist_ok=True)
        install_script.touch()

        venv_path = mock_repo_root / "venv"
        venv_path.mkdir()

        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch("shutil.rmtree", side_effect=OSError("Permission denied")):
                result = cli_runner.invoke(cli, ["install", "reinstall"], input="y\n")
                assert result.exit_code == 1
                assert "Failed to remove existing venv" in result.output

    def test_reinstall_install_failure(self, cli_runner, mock_repo_root):
        """Test install reinstall handles install script failure."""
        install_script = mock_repo_root / "scripts/install/src/install.sh"
        install_script.parent.mkdir(parents=True, exist_ok=True)
        install_script.touch()

        venv_path = mock_repo_root / "venv"
        venv_path.mkdir()

        mock_command_executor = Mock()
        mock_result = Mock()
        mock_result.returncode = 1
        mock_command_executor.execute.return_value = mock_result

        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch(
                "aidb_cli.cli.Context.command_executor",
                new_callable=PropertyMock,
                return_value=mock_command_executor,
            ):
                with patch("shutil.rmtree"):
                    result = cli_runner.invoke(
                        cli,
                        ["install", "reinstall"],
                        input="y\n",
                    )
                    assert result.exit_code == 1
                    assert "Reinstallation failed" in result.output

    def test_reinstall_confirmation_abort(self, cli_runner, mock_repo_root):
        """Test install reinstall can be aborted at confirmation prompt."""
        install_script = mock_repo_root / "scripts/install/src/install.sh"
        install_script.parent.mkdir(parents=True, exist_ok=True)
        install_script.touch()

        mock_command_executor = Mock()

        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch(
                "aidb_cli.cli.Context.command_executor",
                new_callable=PropertyMock,
                return_value=mock_command_executor,
            ):
                result = cli_runner.invoke(cli, ["install", "reinstall"], input="n\n")
                assert result.exit_code == 1
                mock_command_executor.execute.assert_not_called()

    def test_reinstall_no_venv_skips_removal(self, cli_runner, mock_repo_root):
        """Test install reinstall succeeds even when venv doesn't exist in temp
        location."""
        install_script = mock_repo_root / "scripts/install/src/install.sh"
        install_script.parent.mkdir(parents=True, exist_ok=True)
        install_script.touch()

        # Don't create venv directory in mock_repo_root

        mock_command_executor = Mock()
        mock_result = Mock()
        mock_result.returncode = 0
        mock_command_executor.execute.return_value = mock_result

        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch(
                "aidb_cli.cli.Context.command_executor",
                new_callable=PropertyMock,
                return_value=mock_command_executor,
            ):
                with patch(
                    "aidb_cli.commands.install.normalize_path",
                ) as mock_normalize:
                    mock_normalize.return_value = install_script
                    with patch("shutil.rmtree"):
                        result = cli_runner.invoke(
                            cli,
                            ["install", "reinstall"],
                            input="y\n",
                        )
                        assert result.exit_code == 0
                        assert "Reinstalling AIDB" in result.output
                        # rmtree is mocked so no actual deletion occurs

    def test_reinstall_missing_script(self, cli_runner, mock_repo_root):
        """Test install reinstall raises error when script missing."""
        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch("aidb_cli.commands.install.normalize_path") as mock_normalize:
                mock_path = mock_repo_root / "scripts/install/src/install.sh"
                mock_normalize.return_value = mock_path
                result = cli_runner.invoke(cli, ["install", "reinstall"], input="y\n")
                # FileNotFoundError converted to ExitCode.NOT_FOUND (2) by handle_exceptions
                assert result.exit_code == 2
                assert "File not found" in result.output

    def test_install_help(self, cli_runner):
        """Test install command help text."""
        result = cli_runner.invoke(cli, ["install", "--help"])
        assert result.exit_code == 0
        assert "Installation and setup commands" in result.output
        assert "setup" in result.output
        assert "debug" in result.output
        assert "reinstall" in result.output
