"""Unit tests for version_management CLI entry point."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(
    0,
    str(Path(__file__).parent.parent.parent.parent.parent / ".github" / "scripts"),
)

from _test_helpers import create_mock_versions_config
from version_management.cli import main, parse_arguments
from version_management.orchestrator import SectionType


class TestCLIArgumentParsing:
    """Test CLI argument parsing functionality."""

    def test_requires_config_argument(self):
        """Verify CLI exits when --config argument is missing."""
        with patch("sys.argv", ["cli.py"]):
            with pytest.raises(SystemExit) as exc_info:
                parse_arguments()
            assert exc_info.value.code != 0

    def test_section_argument_validation(self):
        """Verify section argument accepts valid choices."""
        test_cases = [
            (["cli.py", "--config", "versions.yaml"], SectionType.ALL),
            (
                ["cli.py", "--config", "versions.yaml", "--section", "infrastructure"],
                SectionType.INFRASTRUCTURE,
            ),
            (
                ["cli.py", "--config", "versions.yaml", "--section", "adapters"],
                SectionType.ADAPTERS,
            ),
            (
                ["cli.py", "--config", "versions.yaml", "--section", "all"],
                SectionType.ALL,
            ),
        ]

        for argv, expected_section in test_cases:
            with patch("sys.argv", argv):
                args = parse_arguments()
                assert args.section == expected_section

    def test_default_section_is_all(self):
        """Verify default section value when not specified."""
        with patch("sys.argv", ["cli.py", "--config", "versions.yaml"]):
            args = parse_arguments()
            assert args.section == SectionType.ALL

    def test_boolean_flags(self):
        """Verify --update and --output-github boolean flags work."""
        test_cases = [
            (["cli.py", "--config", "versions.yaml"], False, False),
            (["cli.py", "--config", "versions.yaml", "--update"], True, False),
            (["cli.py", "--config", "versions.yaml", "--output-github"], False, True),
            (
                ["cli.py", "--config", "versions.yaml", "--update", "--output-github"],
                True,
                True,
            ),
        ]

        for argv, expected_update, expected_github in test_cases:
            with patch("sys.argv", argv):
                args = parse_arguments()
                assert args.update == expected_update
                assert args.output_github == expected_github


class TestCLIFileValidation:
    """Test CLI file validation functionality."""

    def test_exits_when_config_missing(self, tmp_path, capsys):
        """Verify CLI exits with code 1 when config file doesn't exist."""
        missing_config = tmp_path / "nonexistent.yaml"

        with patch("sys.argv", ["cli.py", "--config", str(missing_config)]):
            exit_code = main()

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Error: Config file not found" in captured.out

    @patch("version_management.cli.VersionUpdateOrchestrator")
    def test_handles_invalid_yaml(self, mock_orchestrator_class, tmp_path, capsys):
        """Verify CLI handles invalid YAML gracefully."""
        invalid_yaml = tmp_path / "invalid.yaml"
        invalid_yaml.write_text("invalid: yaml: content: [[[")

        mock_orchestrator = mock_orchestrator_class.return_value
        mock_orchestrator.check_all_updates.side_effect = Exception("YAML parse error")

        with patch("sys.argv", ["cli.py", "--config", str(invalid_yaml)]):
            exit_code = main()

        assert exit_code == 2
        captured = capsys.readouterr()
        assert "Error:" in captured.out
        assert "YAML parse error" in captured.out


class TestCLIOrchestration:
    """Test CLI orchestration integration."""

    @patch("version_management.cli.GitHubActionsReporter")
    @patch("version_management.cli.ConsoleReporter")
    @patch("version_management.cli.VersionUpdateOrchestrator")
    def test_calls_orchestrator_with_correct_args(
        self,
        mock_orchestrator_class,
        mock_console,
        mock_github,
        tmp_path,
    ):
        """Verify CLI calls orchestrator with correct configuration and section."""
        config_path = tmp_path / "versions.yaml"
        config_path.write_text("version: 1.0.0\ninfrastructure: {}")

        mock_orchestrator = mock_orchestrator_class.return_value
        mock_orchestrator.check_all_updates.return_value = {}

        mock_reporter = mock_console.return_value
        mock_reporter.generate_report.return_value = "No updates"

        with patch(
            "sys.argv",
            ["cli.py", "--config", str(config_path), "--section", "infrastructure"],
        ):
            exit_code = main()

        mock_orchestrator_class.assert_called_once_with(
            config_path,
            SectionType.INFRASTRUCTURE,
        )
        mock_orchestrator.check_all_updates.assert_called_once()
        assert exit_code == 0

    @patch("version_management.cli.ConsoleReporter")
    @patch("version_management.cli.VersionUpdateOrchestrator")
    def test_exit_code_on_no_updates(
        self,
        mock_orchestrator_class,
        mock_console,
        tmp_path,
    ):
        """Verify exit code 0 when no updates are found."""
        config_path = tmp_path / "versions.yaml"
        config_path.write_text("version: 1.0.0\ninfrastructure: {}")

        mock_orchestrator = mock_orchestrator_class.return_value
        mock_orchestrator.check_all_updates.return_value = {}

        mock_reporter = mock_console.return_value
        mock_reporter.generate_report.return_value = "No updates"

        with patch("sys.argv", ["cli.py", "--config", str(config_path)]):
            exit_code = main()

        assert exit_code == 0

    @patch("version_management.cli.ConsoleReporter")
    @patch("version_management.cli.VersionUpdateOrchestrator")
    def test_exit_code_on_updates_found(
        self,
        mock_orchestrator_class,
        mock_console,
        tmp_path,
    ):
        """Verify exit code 1 when updates are found."""
        config_path = tmp_path / "versions.yaml"
        config_path.write_text("version: 1.0.0\ninfrastructure: {}")

        mock_orchestrator = mock_orchestrator_class.return_value
        mock_orchestrator.check_all_updates.return_value = {
            "infrastructure": {
                "python": {
                    "old_version": "3.11.0",
                    "new_version": "3.12.1",
                    "type": "stable",
                },
            },
        }

        mock_reporter = mock_console.return_value
        mock_reporter.generate_report.return_value = "Updates available"

        with patch("sys.argv", ["cli.py", "--config", str(config_path)]):
            exit_code = main()

        assert exit_code == 1


class TestCLIReporting:
    """Test CLI reporter selection and output."""

    @patch("version_management.cli.ConsoleReporter")
    @patch("version_management.cli.VersionUpdateOrchestrator")
    def test_uses_console_reporter_by_default(
        self,
        mock_orchestrator_class,
        mock_console_class,
        tmp_path,
    ):
        """Verify ConsoleReporter is used when --output-github is not set."""
        config_path = tmp_path / "versions.yaml"
        config_path.write_text("version: 1.0.0\ninfrastructure: {}")

        mock_orchestrator = mock_orchestrator_class.return_value
        mock_orchestrator.check_all_updates.return_value = {}

        mock_reporter = mock_console_class.return_value
        mock_reporter.generate_report.return_value = "No updates"

        with patch("sys.argv", ["cli.py", "--config", str(config_path)]):
            main()

        mock_console_class.assert_called_once()
        mock_reporter.generate_report.assert_called_once()
        mock_reporter.output.assert_called_once()

    @patch("version_management.cli.GitHubActionsReporter")
    @patch("version_management.cli.VersionUpdateOrchestrator")
    def test_uses_github_reporter_with_flag(
        self,
        mock_orchestrator_class,
        mock_github_class,
        tmp_path,
    ):
        """Verify GitHubActionsReporter is used with --output-github flag."""
        config_path = tmp_path / "versions.yaml"
        config_path.write_text("version: 1.0.0\ninfrastructure: {}")

        mock_orchestrator = mock_orchestrator_class.return_value
        mock_orchestrator.check_all_updates.return_value = {}

        mock_reporter = mock_github_class.return_value
        mock_reporter.generate_report.return_value = "No updates"

        with patch(
            "sys.argv",
            ["cli.py", "--config", str(config_path), "--output-github"],
        ):
            main()

        mock_github_class.assert_called_once()
        mock_reporter.generate_report.assert_called_once()
        mock_reporter.output.assert_called_once()


class TestCLIConfigUpdates:
    """Test CLI configuration update functionality."""

    @patch("version_management.cli.ConfigUpdater")
    @patch("version_management.cli.ConsoleReporter")
    @patch("version_management.cli.VersionUpdateOrchestrator")
    def test_applies_updates_when_flag_set(
        self,
        mock_orchestrator_class,
        mock_console,
        mock_updater_class,
        tmp_path,
        capsys,
    ):
        """Verify updates are applied and saved when --update flag is set."""
        config_path = tmp_path / "versions.yaml"
        config_path.write_text("version: 1.0.0\ninfrastructure: {}")

        mock_orchestrator = mock_orchestrator_class.return_value
        updates = {
            "infrastructure": {
                "python": {
                    "old_version": "3.11.0",
                    "new_version": "3.12.1",
                    "type": "stable",
                },
            },
        }
        mock_orchestrator.check_all_updates.return_value = updates

        mock_reporter = mock_console.return_value
        mock_reporter.generate_report.return_value = "Updates available"

        mock_updater = mock_updater_class.return_value

        with patch("sys.argv", ["cli.py", "--config", str(config_path), "--update"]):
            exit_code = main()

        mock_updater_class.assert_called_once_with(config_path)
        mock_updater.apply_updates.assert_called_once_with(updates)
        mock_updater.save.assert_called_once()

        captured = capsys.readouterr()
        assert f"Updated {config_path}" in captured.out
        assert exit_code == 1


class TestCLIErrorHandling:
    """Test CLI exception handling and resilience."""

    @patch("version_management.cli.VersionUpdateOrchestrator")
    def test_handles_keyboard_interrupt_gracefully(
        self,
        mock_orchestrator_class,
        tmp_path,
        capsys,
    ):
        """Verify Ctrl+C exits cleanly with appropriate message."""
        config_path = tmp_path / "versions.yaml"
        config_path.write_text("infrastructure:\n  python: {version: '3.11'}")

        # Simulate KeyboardInterrupt during orchestration
        mock_orchestrator_class.return_value.check_all_updates.side_effect = (
            KeyboardInterrupt()
        )

        with patch("sys.argv", ["cli.py", "--config", str(config_path)]):
            exit_code = main()

        # Should exit with 130 (standard for SIGINT)
        assert exit_code == 130

        # Should print user-friendly message
        captured = capsys.readouterr()
        assert "Interrupted by user" in captured.out

    @patch("version_management.cli.VersionUpdateOrchestrator")
    def test_handles_unexpected_exceptions(
        self,
        mock_orchestrator_class,
        tmp_path,
        capsys,
    ):
        """Verify unexpected errors are reported cleanly."""
        config_path = tmp_path / "versions.yaml"
        config_path.write_text("infrastructure:\n  python: {version: '3.11'}")

        # Simulate unexpected exception
        mock_orchestrator_class.return_value.check_all_updates.side_effect = (
            RuntimeError("Network connection failed")
        )

        with patch("sys.argv", ["cli.py", "--config", str(config_path)]):
            exit_code = main()

        # Should exit with error code 2
        assert exit_code == 2

        # Should print error message (not full stack trace)
        captured = capsys.readouterr()
        assert "Error:" in captured.out
        assert "Network connection failed" in captured.out

    @patch("version_management.cli.should_auto_merge")
    @patch("version_management.cli.ConsoleReporter")
    @patch("version_management.cli.VersionUpdateOrchestrator")
    def test_auto_merge_decision_included_in_output(
        self,
        mock_orchestrator_class,
        mock_console,
        mock_auto_merge,
        tmp_path,
    ):
        """Verify auto-merge flag is calculated and passed to reporter."""
        config_path = tmp_path / "versions.yaml"
        config_path.write_text("infrastructure:\n  python: {version: '3.11'}")

        updates = {
            "infrastructure": {
                "python": {
                    "current": "3.11.0",
                    "latest": "3.11.1",
                    "update_type": "patch",
                },
            },
        }
        mock_orchestrator_class.return_value.check_all_updates.return_value = updates

        # Mock auto_merge to return True (patch updates only)
        mock_auto_merge.return_value = True

        mock_reporter = mock_console.return_value
        mock_reporter.generate_report.return_value = "Auto-merge: Yes"

        with patch("sys.argv", ["cli.py", "--config", str(config_path)]):
            exit_code = main()

        # Verify should_auto_merge was called
        mock_auto_merge.assert_called_once_with(updates)

        # Verify auto_merge=True passed to reporter
        mock_reporter.output.assert_called_once()
        call_args = mock_reporter.output.call_args
        assert call_args[0][2] is True  # auto_merge is third positional arg

        assert exit_code == 1  # Updates found
