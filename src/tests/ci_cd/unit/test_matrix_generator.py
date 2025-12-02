"""Unit tests for matrix_generator.py script."""

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from _script_loader import load_script_module


class TestMatrixGeneration:
    """Test core matrix generation logic."""

    @pytest.fixture
    def matrix_generator(self):
        """Load matrix_generator.py as a module.

        Returns
        -------
        ModuleType
            The loaded matrix_generator module.
        """
        return load_script_module("utils/matrix_generator")

    @pytest.fixture
    def simple_versions_config(self, tmp_path):
        """Create a simple versions.json for testing.

        Parameters
        ----------
        tmp_path : Path
            Pytest temporary directory.

        Returns
        -------
        Path
            Path to temporary versions.json file.
        """
        config = {
            "version": "1.0.0",
            "infrastructure": {
                "python": {"version": "3.11"},
                "node": {"version": "20"},
                "java": {"version": "21"},
            },
            "adapters": {
                "python": {
                    "version": "1.2.3",
                    "enabled": True,
                },
                "javascript": {
                    "version": "4.5.6",
                    "enabled": True,
                },
                "java": {
                    "version": "7.8.9",
                    "enabled": True,
                },
            },
            "platforms": [
                {"platform": "linux", "arch": "x64", "os": "ubuntu-latest"},
                {"platform": "darwin", "arch": "x64", "os": "macos-15"},
                {"platform": "darwin", "arch": "arm64", "os": "macos-14"},
            ],
        }

        versions_file = tmp_path / "versions.json"
        with versions_file.open("w") as f:
            json.dump(config, f, indent=2)

        return versions_file

    def test_generate_matrix_returns_dict(
        self,
        matrix_generator,
        simple_versions_config,
    ):
        """Verify generate_matrix returns a dict with include key."""
        result = matrix_generator.generate_matrix("gha", str(simple_versions_config))

        assert isinstance(result, dict)
        assert "include" in result
        assert isinstance(result["include"], list)

    def test_generate_matrix_includes_all_enabled_adapters(
        self,
        matrix_generator,
        simple_versions_config,
    ):
        """Verify matrix includes entries for all enabled adapters."""
        result = matrix_generator.generate_matrix("gha", str(simple_versions_config))
        adapters = {entry["adapter"] for entry in result["include"]}

        assert "python" in adapters
        assert "javascript" in adapters
        assert "java" in adapters

    def test_generate_matrix_respects_disabled_adapters(
        self,
        matrix_generator,
        tmp_path,
    ):
        """Verify disabled adapters are excluded from matrix."""
        config = {
            "version": "1.0.0",
            "adapters": {
                "python": {"version": "1.0", "enabled": True},
                "javascript": {"version": "2.0", "enabled": False},  # Disabled
                "java": {"version": "3.0", "enabled": True},
            },
            "platforms": [
                {"platform": "linux", "arch": "x64", "os": "ubuntu-latest"},
            ],
        }

        versions_file = tmp_path / "versions.json"
        with versions_file.open("w") as f:
            json.dump(config, f)

        result = matrix_generator.generate_matrix("gha", str(versions_file))
        adapters = {entry["adapter"] for entry in result["include"]}

        assert "python" in adapters
        assert "javascript" not in adapters
        assert "java" in adapters

    def test_generate_matrix_includes_platform_fields(
        self,
        matrix_generator,
        simple_versions_config,
    ):
        """Verify each matrix entry has required platform fields."""
        result = matrix_generator.generate_matrix("gha", str(simple_versions_config))

        required_fields = ["adapter", "platform", "arch", "os"]
        for entry in result["include"]:
            for field in required_fields:
                assert field in entry, f"Missing field '{field}' in entry: {entry}"

    def test_generate_matrix_gha_creates_entries_for_all_platforms(
        self,
        matrix_generator,
        simple_versions_config,
    ):
        """Verify GHA mode creates entries for all platforms."""
        result = matrix_generator.generate_matrix("gha", str(simple_versions_config))

        # Python and JavaScript should have entries for all 3 platforms
        python_entries = [e for e in result["include"] if e["adapter"] == "python"]
        js_entries = [e for e in result["include"] if e["adapter"] == "javascript"]

        # Each adapter should have 3 entries (one per platform)
        assert len(python_entries) == 3
        assert len(js_entries) == 3

        # Verify platforms are correct
        python_platforms = {(e["platform"], e["arch"]) for e in python_entries}
        expected_platforms = {("linux", "x64"), ("darwin", "x64"), ("darwin", "arm64")}
        assert python_platforms == expected_platforms

    def test_generate_matrix_preserves_os_from_config(
        self,
        matrix_generator,
        simple_versions_config,
    ):
        """Verify OS values from config are preserved in matrix."""
        result = matrix_generator.generate_matrix("gha", str(simple_versions_config))

        # Find linux entry
        linux_entry = next(
            e
            for e in result["include"]
            if e["platform"] == "linux" and e["adapter"] == "python"
        )
        assert linux_entry["os"] == "ubuntu-latest"

        # Find darwin x64 entry
        darwin_x64_entry = next(
            e
            for e in result["include"]
            if e["platform"] == "darwin"
            and e["arch"] == "x64"
            and e["adapter"] == "python"
        )
        assert darwin_x64_entry["os"] == "macos-15"

        # Find darwin arm64 entry
        darwin_arm64_entry = next(
            e
            for e in result["include"]
            if e["platform"] == "darwin"
            and e["arch"] == "arm64"
            and e["adapter"] == "python"
        )
        assert darwin_arm64_entry["os"] == "macos-14"


class TestJavaSpecialCase:
    """Test Java universal platform handling."""

    @pytest.fixture
    def matrix_generator(self):
        """Load matrix_generator.py as a module."""
        return load_script_module("utils/matrix_generator")

    @pytest.fixture
    def versions_with_java(self, tmp_path):
        """Create versions.json with Java adapter.

        Parameters
        ----------
        tmp_path : Path
            Pytest temporary directory.

        Returns
        -------
        Path
            Path to temporary versions.json file.
        """
        config = {
            "version": "1.0.0",
            "adapters": {
                "java": {"version": "1.0.0", "enabled": True},
            },
            "platforms": [
                {"platform": "linux", "arch": "x64", "os": "ubuntu-latest"},
                {"platform": "darwin", "arch": "x64", "os": "macos-15"},
                {"platform": "darwin", "arch": "arm64", "os": "macos-14"},
            ],
        }

        versions_file = tmp_path / "versions.json"
        with versions_file.open("w") as f:
            json.dump(config, f, indent=2)

        return versions_file

    def test_java_creates_single_universal_entry(
        self,
        matrix_generator,
        versions_with_java,
    ):
        """Verify Java adapter creates only one universal platform entry."""
        result = matrix_generator.generate_matrix("gha", str(versions_with_java))

        java_entries = [e for e in result["include"] if e["adapter"] == "java"]

        # Java should only have 1 entry (universal)
        assert len(java_entries) == 1

    def test_java_uses_linux_x64_platform(self, matrix_generator, versions_with_java):
        """Verify Java universal build uses linux/x64."""
        result = matrix_generator.generate_matrix("gha", str(versions_with_java))

        java_entry = next(e for e in result["include"] if e["adapter"] == "java")

        assert java_entry["platform"] == "linux"
        assert java_entry["arch"] == "x64"
        assert java_entry["os"] == "ubuntu-latest"

    def test_mixed_adapters_java_universal_others_multi_platform(
        self,
        matrix_generator,
        tmp_path,
    ):
        """Verify Java gets single entry while others get multi-platform entries."""
        config = {
            "version": "1.0.0",
            "adapters": {
                "python": {"version": "1.0.0", "enabled": True},
                "java": {"version": "1.0.0", "enabled": True},
            },
            "platforms": [
                {"platform": "linux", "arch": "x64", "os": "ubuntu-latest"},
                {"platform": "darwin", "arch": "x64", "os": "macos-15"},
            ],
        }

        versions_file = tmp_path / "versions.json"
        with versions_file.open("w") as f:
            json.dump(config, f)

        result = matrix_generator.generate_matrix("gha", str(versions_file))

        java_entries = [e for e in result["include"] if e["adapter"] == "java"]
        python_entries = [e for e in result["include"] if e["adapter"] == "python"]

        assert len(java_entries) == 1  # Java: universal
        assert len(python_entries) == 2  # Python: multi-platform


class TestWorkflowModes:
    """Test ACT vs GHA workflow mode differences."""

    @pytest.fixture
    def matrix_generator(self):
        """Load matrix_generator.py as a module."""
        return load_script_module("utils/matrix_generator")

    @pytest.fixture
    def multi_platform_config(self, tmp_path):
        """Create versions.json with multiple platforms.

        Parameters
        ----------
        tmp_path : Path
            Pytest temporary directory.

        Returns
        -------
        Path
            Path to temporary versions.json file.
        """
        config = {
            "version": "1.0.0",
            "adapters": {
                "python": {"version": "1.0.0", "enabled": True},
            },
            "platforms": [
                {"platform": "linux", "arch": "x64", "os": "ubuntu-latest"},
                {"platform": "darwin", "arch": "x64", "os": "macos-15"},
                {"platform": "darwin", "arch": "arm64", "os": "macos-14"},
            ],
        }

        versions_file = tmp_path / "versions.json"
        with versions_file.open("w") as f:
            json.dump(config, f, indent=2)

        return versions_file

    def test_gha_mode_builds_all_platforms(
        self,
        matrix_generator,
        multi_platform_config,
    ):
        """Verify GHA mode includes all platforms."""
        result = matrix_generator.generate_matrix("gha", str(multi_platform_config))

        python_entries = [e for e in result["include"] if e["adapter"] == "python"]
        assert len(python_entries) == 3

    @patch("platform.system")
    @patch("platform.machine")
    def test_act_mode_builds_only_host_platform(
        self,
        mock_machine,
        mock_system,
        matrix_generator,
        multi_platform_config,
    ):
        """Verify ACT mode builds only for host platform."""
        # Mock host platform as linux/x64
        mock_system.return_value = "Linux"
        mock_machine.return_value = "x86_64"

        result = matrix_generator.generate_matrix("act", str(multi_platform_config))

        python_entries = [e for e in result["include"] if e["adapter"] == "python"]

        # Should only have 1 entry for host platform
        assert len(python_entries) == 1
        assert python_entries[0]["platform"] == "linux"
        assert python_entries[0]["arch"] == "x64"

    @patch.dict(
        os.environ,
        {
            "AIDB_USE_HOST_PLATFORM": "1",
            "AIDB_BUILD_PLATFORM": "darwin",
            "AIDB_BUILD_ARCH": "arm64",
        },
    )
    def test_act_mode_respects_aidb_environment_vars(
        self,
        matrix_generator,
        multi_platform_config,
    ):
        """Verify ACT mode uses AIDB environment variables when set."""
        result = matrix_generator.generate_matrix("act", str(multi_platform_config))

        python_entries = [e for e in result["include"] if e["adapter"] == "python"]

        # Should use values from AIDB_ env vars
        assert len(python_entries) == 1
        assert python_entries[0]["platform"] == "darwin"
        assert python_entries[0]["arch"] == "arm64"

    @patch("platform.system")
    @patch("platform.machine")
    def test_act_mode_platform_detection_darwin(
        self,
        mock_machine,
        mock_system,
        matrix_generator,
        multi_platform_config,
    ):
        """Verify ACT mode correctly detects Darwin platform."""
        mock_system.return_value = "Darwin"
        mock_machine.return_value = "arm64"

        result = matrix_generator.generate_matrix("act", str(multi_platform_config))

        python_entries = [e for e in result["include"] if e["adapter"] == "python"]

        assert len(python_entries) == 1
        assert python_entries[0]["platform"] == "darwin"
        assert python_entries[0]["arch"] == "arm64"


class TestOutputFormats:
    """Test different output formats for matrix generator."""

    @pytest.fixture
    def matrix_generator_script(self, repo_root):
        """Get path to matrix_generator.py script.

        Parameters
        ----------
        repo_root : Path
            Repository root path.

        Returns
        -------
        Path
            Path to matrix_generator.py script.
        """
        return repo_root / ".github" / "scripts" / "utils" / "matrix_generator.py"

    @pytest.fixture
    def simple_versions(self, tmp_path):
        """Create a minimal versions.json for output testing.

        Parameters
        ----------
        tmp_path : Path
            Pytest temporary directory.

        Returns
        -------
        Path
            Path to temporary versions.json file.
        """
        config = {
            "version": "1.0.0",
            "adapters": {
                "python": {"version": "1.0.0", "enabled": True},
            },
            "platforms": [
                {"platform": "linux", "arch": "x64", "os": "ubuntu-latest"},
            ],
        }

        versions_file = tmp_path / "versions.json"
        with versions_file.open("w") as f:
            json.dump(config, f, indent=2)

        return versions_file

    @pytest.mark.integration
    def test_json_format_output(
        self,
        matrix_generator_script,
        simple_versions,
        repo_root,
    ):
        """Verify --format json produces valid JSON output."""
        python_exe = repo_root / "venv" / "bin" / "python"
        if not python_exe.exists():
            python_exe = "python3"

        result = subprocess.run(
            [
                str(python_exe),
                str(matrix_generator_script),
                "--workflow",
                "gha",
                "--versions-file",
                str(simple_versions),
                "--format",
                "json",
            ],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0
        matrix_data = json.loads(result.stdout)

        assert "include" in matrix_data
        assert len(matrix_data["include"]) > 0

    @pytest.mark.integration
    def test_github_format_output(
        self,
        matrix_generator_script,
        simple_versions,
        repo_root,
    ):
        """Verify --format github produces GITHUB_OUTPUT format."""
        python_exe = repo_root / "venv" / "bin" / "python"
        if not python_exe.exists():
            python_exe = "python3"

        result = subprocess.run(
            [
                str(python_exe),
                str(matrix_generator_script),
                "--workflow",
                "gha",
                "--versions-file",
                str(simple_versions),
                "--format",
                "github",
            ],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0

        # Should have format: matrix={"include":[...]}
        assert result.stdout.startswith("matrix=")

        # Extract JSON and validate
        json_str = result.stdout.removeprefix("matrix=").strip()
        matrix_data = json.loads(json_str)

        assert "include" in matrix_data
        assert len(matrix_data["include"]) > 0

    @pytest.mark.integration
    def test_script_exits_on_missing_file(self, matrix_generator_script, repo_root):
        """Verify script exits with error for missing versions file."""
        python_exe = repo_root / "venv" / "bin" / "python"
        if not python_exe.exists():
            python_exe = "python3"

        result = subprocess.run(
            [
                str(python_exe),
                str(matrix_generator_script),
                "--versions-file",
                "/nonexistent/versions.json",
            ],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode != 0
        assert "not found" in result.stderr.lower()


class TestRealVersionsYaml:
    """Test matrix generation with actual project versions.json."""

    @pytest.fixture
    def matrix_generator(self):
        """Load matrix_generator.py as a module."""
        return load_script_module("utils/matrix_generator")

    def test_generate_from_real_versions_json(
        self,
        matrix_generator,
        repo_root,
    ):
        """Verify matrix generation works with real versions.json."""
        versions_file = repo_root / "versions.json"

        if not versions_file.exists():
            pytest.skip("versions.json not found in repository root")

        result = matrix_generator.generate_matrix("gha", str(versions_file))

        # Should have valid matrix structure
        assert "include" in result
        assert len(result["include"]) > 0

        # All entries should have required fields
        required_fields = ["adapter", "platform", "arch", "os"]
        for entry in result["include"]:
            for field in required_fields:
                assert field in entry

    def test_real_versions_java_is_universal(
        self,
        matrix_generator,
        repo_root,
    ):
        """Verify Java adapter in real versions.json creates single entry."""
        versions_file = repo_root / "versions.json"

        if not versions_file.exists():
            pytest.skip("versions.json not found in repository root")

        result = matrix_generator.generate_matrix("gha", str(versions_file))

        java_entries = [e for e in result["include"] if e["adapter"] == "java"]

        # Java should always be universal (single entry)
        if len(java_entries) > 0:
            assert len(java_entries) == 1
            assert java_entries[0]["platform"] == "linux"
            assert java_entries[0]["arch"] == "x64"
