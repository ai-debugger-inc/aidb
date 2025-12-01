"""Unit tests for build-adapter.py script."""

import contextlib
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pytest
from _script_loader import load_script_module
from _test_helpers import create_mock_versions_config, mock_script_environment


@pytest.fixture
def build_adapter_module():
    """Load build-adapter script as module."""
    return load_script_module("build-adapter")


@pytest.fixture
def mock_builder():
    """Mock adapter builder."""
    builder = Mock()
    builder.build_adapter.return_value = (
        Path("/tmp/adapter.tar.gz"),  # noqa: S108
        "abc123def456",
    )
    return builder


class TestPlatformDetection:
    """Test platform and architecture detection logic."""

    def test_darwin_x64_detection(self, build_adapter_module, mock_builder):
        """Verify Darwin x64 is correctly detected."""
        config = create_mock_versions_config()

        with mock_script_environment(
            platform="Darwin",
            machine="x86_64",
            yaml_data=config,
        ):
            with patch.object(
                build_adapter_module,
                "get_builder",
                return_value=mock_builder,
            ):
                with patch("tarfile.open"):
                    with patch("sys.argv", ["build-adapter.py", "javascript"]):
                        with contextlib.suppress(SystemExit):
                            build_adapter_module.main()

                        build_adapter_module.get_builder.assert_called_once()
                        call_args = build_adapter_module.get_builder.call_args[0]
                        assert call_args[2] == "darwin"
                        assert call_args[3] == "x64"

    def test_linux_arm64_detection(self, build_adapter_module, mock_builder):
        """Verify Linux ARM64 is correctly detected."""
        config = create_mock_versions_config()

        with mock_script_environment(
            platform="Linux",
            machine="aarch64",
            yaml_data=config,
        ):
            with patch.object(
                build_adapter_module,
                "get_builder",
                return_value=mock_builder,
            ):
                with patch("tarfile.open"):
                    with patch("sys.argv", ["build-adapter.py", "javascript"]):
                        with contextlib.suppress(SystemExit):
                            build_adapter_module.main()

                        call_args = build_adapter_module.get_builder.call_args[0]
                        assert call_args[2] == "linux"
                        assert call_args[3] == "arm64"

    def test_windows_x64_detection(self, build_adapter_module, mock_builder):
        """Verify Windows x64 is correctly detected."""
        config = create_mock_versions_config()

        with mock_script_environment(
            platform="Windows",
            machine="AMD64",
            yaml_data=config,
        ):
            with patch.object(
                build_adapter_module,
                "get_builder",
                return_value=mock_builder,
            ):
                with patch("tarfile.open"):
                    with patch("sys.argv", ["build-adapter.py", "javascript"]):
                        with contextlib.suppress(SystemExit):
                            build_adapter_module.main()

                        call_args = build_adapter_module.get_builder.call_args[0]
                        assert call_args[2] == "windows"
                        assert call_args[3] == "x64"

    def test_explicit_platform_overrides_detection(
        self,
        build_adapter_module,
        mock_builder,
    ):
        """Verify explicit platform/arch arguments override auto-detection."""
        config = create_mock_versions_config()

        with mock_script_environment(
            platform="Darwin",
            machine="x86_64",
            yaml_data=config,
        ):
            with patch.object(
                build_adapter_module,
                "get_builder",
                return_value=mock_builder,
            ):
                with patch("tarfile.open"):
                    with patch(
                        "sys.argv",
                        [
                            "build-adapter.py",
                            "javascript",
                            "--platform",
                            "linux",
                            "--arch",
                            "arm64",
                        ],
                    ):
                        with contextlib.suppress(SystemExit):
                            build_adapter_module.main()

                        call_args = build_adapter_module.get_builder.call_args[0]
                        assert call_args[2] == "linux"
                        assert call_args[3] == "arm64"


class TestPlatformValidation:
    """Test platform/architecture validation."""

    def test_validation_passes_for_supported_platform(
        self,
        build_adapter_module,
        mock_builder,
        capsys,
    ):
        """Verify validation passes for supported platform/arch combo."""
        config = create_mock_versions_config()

        with mock_script_environment(yaml_data=config):
            with patch.object(
                build_adapter_module,
                "get_builder",
                return_value=mock_builder,
            ):
                with patch("tarfile.open"):
                    with patch(
                        "sys.argv",
                        [
                            "build-adapter.py",
                            "javascript",
                            "--platform",
                            "darwin",
                            "--arch",
                            "arm64",
                        ],
                    ):
                        with contextlib.suppress(SystemExit):
                            build_adapter_module.main()

                        build_adapter_module.get_builder.assert_called_once()

    def test_validation_fails_for_unsupported_platform(
        self,
        build_adapter_module,
        capsys,
    ):
        """Verify validation fails for unsupported platform/arch combo."""
        config = create_mock_versions_config()

        with mock_script_environment(yaml_data=config):
            with patch(
                "sys.argv",
                [
                    "build-adapter.py",
                    "javascript",
                    "--platform",
                    "freebsd",
                    "--arch",
                    "x64",
                ],
            ):
                with pytest.raises(SystemExit) as exc_info:
                    build_adapter_module.main()

                assert exc_info.value.code == 1
                captured = capsys.readouterr()
                assert "Unsupported platform" in captured.err

    def test_validation_checks_both_platform_and_arch(
        self,
        build_adapter_module,
        capsys,
    ):
        """Verify validation checks both platform and arch match."""
        config = create_mock_versions_config()

        with mock_script_environment(yaml_data=config):
            with patch(
                "sys.argv",
                [
                    "build-adapter.py",
                    "javascript",
                    "--platform",
                    "darwin",
                    "--arch",
                    "riscv64",
                ],
            ):
                with pytest.raises(SystemExit) as exc_info:
                    build_adapter_module.main()

                assert exc_info.value.code == 1
                captured = capsys.readouterr()
                assert "darwin-riscv64" in captured.err


class TestConfigurationLoading:
    """Test versions.json configuration loading."""

    def test_successful_config_loading(self, build_adapter_module, mock_builder):
        """Verify successful loading of versions.json."""
        config = create_mock_versions_config()

        with mock_script_environment(yaml_data=config):
            with patch.object(
                build_adapter_module,
                "get_builder",
                return_value=mock_builder,
            ):
                with patch("tarfile.open"):
                    with patch(
                        "sys.argv",
                        [
                            "build-adapter.py",
                            "javascript",
                            "--platform",
                            "linux",
                            "--arch",
                            "x64",
                        ],
                    ):
                        with contextlib.suppress(SystemExit):
                            build_adapter_module.main()

                        build_adapter_module.get_builder.assert_called_once()

    def test_error_when_versions_file_missing(
        self,
        build_adapter_module,
        tmp_path,
        capsys,
    ):
        """Verify error when versions.json file doesn't exist."""
        nonexistent_file = tmp_path / "nonexistent.json"

        with patch(
            "sys.argv",
            [
                "build-adapter.py",
                "javascript",
                "--versions-file",
                str(nonexistent_file),
            ],
        ):
            with pytest.raises(SystemExit) as exc_info:
                build_adapter_module.main()

            assert exc_info.value.code == 1
            captured = capsys.readouterr()
            assert "Versions file not found" in captured.err

    def test_custom_versions_file_path(
        self,
        build_adapter_module,
        tmp_path,
        mock_builder,
    ):
        """Verify custom versions file path via --versions-file."""
        config = create_mock_versions_config()
        custom_file = tmp_path / "custom-versions.json"
        custom_file.write_text('{"platforms": []}')

        with mock_script_environment(yaml_data=config):
            with patch.object(
                build_adapter_module,
                "get_builder",
                return_value=mock_builder,
            ):
                with patch("tarfile.open"):
                    with patch(
                        "sys.argv",
                        [
                            "build-adapter.py",
                            "javascript",
                            "--versions-file",
                            str(custom_file),
                            "--platform",
                            "linux",
                            "--arch",
                            "x64",
                        ],
                    ):
                        with contextlib.suppress(SystemExit):
                            build_adapter_module.main()

                        build_adapter_module.get_builder.assert_called_once()


class TestCommandLineArguments:
    """Test command-line argument handling."""

    def test_list_flag_shows_available_adapters(self, build_adapter_module, capsys):
        """Verify --list flag shows available adapters."""
        config = create_mock_versions_config()
        mock_builders = {"javascript": Mock(), "java": Mock(), "python": Mock()}

        with patch.dict(
            build_adapter_module.__dict__,
            {"ADAPTER_BUILDERS": mock_builders},
        ):
            with mock_script_environment(yaml_data=config):
                with patch("sys.argv", ["build-adapter.py", "--list"]):
                    build_adapter_module.main()

                    captured = capsys.readouterr()
                    assert "Available adapters:" in captured.out
                    assert "javascript" in captured.out
                    assert "java" in captured.out
                    assert "python" in captured.out

    def test_validate_only_flag(self, build_adapter_module, capsys):
        """Verify --validate-only flag."""
        config = create_mock_versions_config()

        with mock_script_environment(yaml_data=config):
            with patch("sys.argv", ["build-adapter.py", "--validate-only"]):
                build_adapter_module.main()

                captured = capsys.readouterr()
                assert "Configuration validation passed" in captured.out

    def test_error_when_adapter_missing_without_flags(self, build_adapter_module):
        """Verify error when adapter argument missing without --list or --validate-
        only."""
        config = create_mock_versions_config()

        with mock_script_environment(yaml_data=config):
            with patch("sys.argv", ["build-adapter.py"]):
                with pytest.raises(SystemExit) as exc_info:
                    build_adapter_module.main()

                # argparse exits with code 2 for usage errors
                assert exc_info.value.code == 2

    def test_successful_build_with_adapter_argument(
        self,
        build_adapter_module,
        mock_builder,
        capsys,
    ):
        """Verify successful build with adapter argument."""
        config = create_mock_versions_config()

        with mock_script_environment(yaml_data=config):
            with patch.object(
                build_adapter_module,
                "get_builder",
                return_value=mock_builder,
            ):
                with patch("tarfile.open"):
                    with patch(
                        "sys.argv",
                        [
                            "build-adapter.py",
                            "javascript",
                            "--platform",
                            "linux",
                            "--arch",
                            "x64",
                        ],
                    ):
                        with contextlib.suppress(SystemExit):
                            build_adapter_module.main()

                        captured = capsys.readouterr()
                        assert "Successfully built adapter" in captured.out
                        assert "adapter.tar.gz" in captured.out
                        assert "abc123def456" in captured.out


class TestAdapterBuilderIntegration:
    """Test adapter builder integration."""

    def test_get_builder_called_with_correct_arguments(
        self,
        build_adapter_module,
        mock_builder,
    ):
        """Verify get_builder() is called with correct arguments."""
        config = create_mock_versions_config()

        with mock_script_environment(yaml_data=config):
            with patch.object(
                build_adapter_module,
                "get_builder",
                return_value=mock_builder,
            ) as mock_get_builder:
                with patch("tarfile.open"):
                    with patch(
                        "sys.argv",
                        [
                            "build-adapter.py",
                            "javascript",
                            "--platform",
                            "darwin",
                            "--arch",
                            "arm64",
                        ],
                    ):
                        with contextlib.suppress(SystemExit):
                            build_adapter_module.main()

                        mock_get_builder.assert_called_once_with(
                            "javascript",
                            config,
                            "darwin",
                            "arm64",
                        )

    def test_build_adapter_executed(
        self,
        build_adapter_module,
        mock_builder,
    ):
        """Verify build_adapter() is executed."""
        config = create_mock_versions_config()

        with mock_script_environment(yaml_data=config):
            with patch.object(
                build_adapter_module,
                "get_builder",
                return_value=mock_builder,
            ):
                with patch("tarfile.open"):
                    with patch(
                        "sys.argv",
                        [
                            "build-adapter.py",
                            "javascript",
                            "--platform",
                            "linux",
                            "--arch",
                            "x64",
                        ],
                    ):
                        with contextlib.suppress(SystemExit):
                            build_adapter_module.main()

                        mock_builder.build_adapter.assert_called_once()

    def test_successful_build_returns_tarball_and_checksum(
        self,
        build_adapter_module,
        mock_builder,
        capsys,
    ):
        """Verify successful build output includes tarball path and checksum."""
        config = create_mock_versions_config()

        with mock_script_environment(yaml_data=config):
            with patch.object(
                build_adapter_module,
                "get_builder",
                return_value=mock_builder,
            ):
                with patch("tarfile.open"):
                    with patch(
                        "sys.argv",
                        [
                            "build-adapter.py",
                            "javascript",
                            "--platform",
                            "linux",
                            "--arch",
                            "x64",
                        ],
                    ):
                        with contextlib.suppress(SystemExit):
                            build_adapter_module.main()

                        captured = capsys.readouterr()
                        assert "/tmp/adapter.tar.gz" in captured.out  # noqa: S108
                        assert "abc123def456" in captured.out


class TestCacheExtraction:
    """Test cache directory extraction."""

    def test_cache_directory_created(
        self,
        build_adapter_module,
        mock_builder,
        tmp_path,
    ):
        """Verify cache directory is created."""
        config = create_mock_versions_config()
        mock_tarfile = Mock()
        mock_tarfile.getmembers.return_value = []

        with mock_script_environment(yaml_data=config):
            with patch.object(
                build_adapter_module,
                "get_builder",
                return_value=mock_builder,
            ):
                with patch("tarfile.open", return_value=mock_tarfile):
                    with patch(
                        "sys.argv",
                        [
                            "build-adapter.py",
                            "javascript",
                            "--platform",
                            "linux",
                            "--arch",
                            "x64",
                        ],
                    ):
                        with contextlib.suppress(SystemExit):
                            build_adapter_module.main()

                        # Cache dir should be .cache/adapters/javascript
                        cache_dir = Path(".cache/adapters/javascript")
                        assert cache_dir.exists()

    def test_top_level_directory_stripped_during_extraction(
        self,
        build_adapter_module,
        mock_builder,
    ):
        """Verify top-level directory is stripped during extraction."""
        config = create_mock_versions_config()

        # Create mock tarfile members
        member1 = Mock()
        member1.name = "adapter-dir/file1.txt"
        member2 = Mock()
        member2.name = "adapter-dir/subdir/file2.txt"

        mock_tarfile = Mock()
        mock_tarfile.getmembers.return_value = [member1, member2]
        mock_tarfile.__enter__ = Mock(return_value=mock_tarfile)
        mock_tarfile.__exit__ = Mock(return_value=False)

        with mock_script_environment(yaml_data=config):
            with patch.object(
                build_adapter_module,
                "get_builder",
                return_value=mock_builder,
            ):
                with patch("tarfile.open", return_value=mock_tarfile):
                    with patch(
                        "sys.argv",
                        [
                            "build-adapter.py",
                            "javascript",
                            "--platform",
                            "linux",
                            "--arch",
                            "x64",
                        ],
                    ):
                        with contextlib.suppress(SystemExit):
                            build_adapter_module.main()

                        # Verify names were stripped
                        assert member1.name == "file1.txt"
                        assert member2.name == "subdir/file2.txt"

    def test_macos_resource_fork_files_filtered(
        self,
        build_adapter_module,
        mock_builder,
    ):
        """Verify macOS resource fork files (._*) are filtered out."""
        config = create_mock_versions_config()

        # Create mock tarfile members with resource forks
        member1 = Mock()
        member1.name = "adapter-dir/file.txt"
        member2 = Mock()
        member2.name = "adapter-dir/._file.txt"  # Resource fork - should skip
        member3 = Mock()
        member3.name = "adapter-dir/subdir/._hidden.txt"  # Resource fork - should skip

        mock_tarfile = Mock()
        mock_tarfile.getmembers.return_value = [member1, member2, member3]
        mock_tarfile.__enter__ = Mock(return_value=mock_tarfile)
        mock_tarfile.__exit__ = Mock(return_value=False)

        with mock_script_environment(yaml_data=config):
            with patch.object(
                build_adapter_module,
                "get_builder",
                return_value=mock_builder,
            ):
                with patch("tarfile.open", return_value=mock_tarfile):
                    with patch(
                        "sys.argv",
                        [
                            "build-adapter.py",
                            "javascript",
                            "--platform",
                            "linux",
                            "--arch",
                            "x64",
                        ],
                    ):
                        with contextlib.suppress(SystemExit):
                            build_adapter_module.main()

                        # Only member1 should have been extracted
                        assert mock_tarfile.extract.call_count == 1
                        extracted_member = mock_tarfile.extract.call_args[0][0]
                        assert extracted_member == member1
