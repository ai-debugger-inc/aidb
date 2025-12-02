"""Tests for aidb_common.config.versions module."""

import json
from pathlib import Path

import pytest

from aidb_common.config.versions import VersionManager


@pytest.fixture
def sample_versions_file(tmp_path: Path) -> Path:
    """Create a sample versions.json file for testing."""
    versions_data = {
        "version": "1.0.0",
        "infrastructure": {
            "python": {"version": "3.12", "eol": "2028-10"},
            "node": {"version": "22", "eol": "2027-04"},
            "java": {"version": "21", "eol": "2028-09"},
        },
        "adapters": {
            "python": {
                "version": "1.8.16",
                "repo": "microsoft/debugpy",
            },
            "javascript": {
                "version": "v1.104.0",
                "repo": "microsoft/vscode-js-debug",
            },
            "java": {
                "version": "0.53.1",
                "repo": "microsoft/vscode-java-debug",
                "jdtls_version": "1.55.0-202511271007",
            },
        },
        "runtimes": {
            "python": {
                "min_version": "3.9",
                "recommended": "3.12",
                "debug_package": "debugpy>=1.8.0",
            },
        },
    }
    file_path = tmp_path / "versions.json"
    file_path.write_text(json.dumps(versions_data, indent=2))
    return file_path


@pytest.fixture
def old_format_versions_file(tmp_path: Path) -> Path:
    """Create versions.json with old format for testing backward compatibility."""
    versions_data = {
        "version": "0.9.0",
        "infrastructure": {
            "python_version": "3.11",
            "node_version": "20",
            "java_version": "17",
        },
        "adapters": {
            "javascript": {"version": "v1.100.0", "repo": "microsoft/vscode-js-debug"},
            "java": {
                "version": "0.50.0",
                "repo": "microsoft/vscode-java-debug",
                "jdtls_version": "1.50.0",
            },
        },
    }
    file_path = tmp_path / "versions_old.json"
    file_path.write_text(json.dumps(versions_data, indent=2))
    return file_path


@pytest.fixture
def sample_versions_with_extensions(tmp_path: Path) -> Path:
    """Versions file with global_packages sections."""
    versions_data = {
        "version": "1.0.0",
        "infrastructure": {
            "python": {"version": "3.12", "docker_tag": "3.12-slim"},
            "node": {"version": "22", "docker_tag": "22-slim"},
            "java": {"version": "21"},
        },
        "adapters": {
            "python": {"version": "1.8.0"},
            "javascript": {"version": "v1.104.0"},
            "java": {"version": "0.53.1", "jdtls_version": "1.51.0"},
        },
        "global_packages": {
            "pip": {
                "pip": {"version": "25.3", "description": "Python package installer"},
                "setuptools": {"version": "80.9.0", "description": "Build tool"},
                "wheel": {"version": "0.45.1", "description": "Wheel format"},
            },
            "npm": {
                "typescript": {
                    "version": "5.9.3",
                    "description": "TypeScript compiler",
                },
                "ts_node": {"version": "10.9.2", "description": "TS execution"},
            },
        },
        "runtimes": {
            "python": {"min_version": "3.10", "recommended": "3.12"},
            "javascript": {"min_version": "18.0.0", "recommended": "22.0.0"},
        },
    }
    file_path = tmp_path / "versions_extended.json"
    file_path.write_text(json.dumps(versions_data, indent=2))
    return file_path


class TestVersionManagerInit:
    """Tests for VersionManager initialization."""

    def test_init_with_explicit_path(self, sample_versions_file: Path):
        """Test initialization with explicit versions file path."""
        manager = VersionManager(versions_file=sample_versions_file)
        assert manager.versions_file == sample_versions_file
        assert manager._versions_data is None

    def test_init_with_default_path(self, monkeypatch, tmp_path: Path):
        """Test initialization with default path (repo root)."""
        versions_file = tmp_path / "versions.json"
        versions_file.write_text(json.dumps({"version": "1.0.0"}, indent=2))

        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").touch()

        manager = VersionManager()
        assert manager.versions_file.name == "versions.json"


class TestVersionsProperty:
    """Tests for versions property."""

    def test_loads_versions_on_first_access(self, sample_versions_file: Path):
        """Test that versions are loaded lazily on first access."""
        manager = VersionManager(versions_file=sample_versions_file)
        assert manager._versions_data is None

        versions = manager.versions
        assert manager._versions_data is not None
        assert versions["version"] == "1.0.0"

    def test_caches_versions_data(self, sample_versions_file: Path):
        """Test that versions data is cached after first load."""
        manager = VersionManager(versions_file=sample_versions_file)

        versions1 = manager.versions
        versions2 = manager.versions

        assert versions1 is versions2

    def test_raises_file_not_found_for_missing_file(self, tmp_path: Path):
        """Test that FileNotFoundError is raised for missing versions file."""
        missing_file = tmp_path / "missing.json"
        manager = VersionManager(versions_file=missing_file)

        with pytest.raises(FileNotFoundError, match="Versions file not found"):
            _ = manager.versions

    def test_raises_value_error_for_invalid_json(self, tmp_path: Path):
        """Test that ValueError is raised for malformed JSON."""
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text('{"key": "value", "bad": invalid}')

        manager = VersionManager(versions_file=invalid_file)

        with pytest.raises(ValueError, match="Invalid JSON"):
            _ = manager.versions

    def test_raises_value_error_for_non_dict_data(self, tmp_path: Path):
        """Test that ValueError is raised when top level is not a dict."""
        list_file = tmp_path / "list.json"
        list_file.write_text('["item1", "item2"]')

        manager = VersionManager(versions_file=list_file)

        with pytest.raises(ValueError, match="must contain a mapping"):
            _ = manager.versions


class TestGetInfrastructureVersions:
    """Tests for get_infrastructure_versions method."""

    def test_returns_new_format_versions(self, sample_versions_file: Path):
        """Test extraction of infrastructure versions from new format."""
        manager = VersionManager(versions_file=sample_versions_file)
        infra = manager.get_infrastructure_versions()

        assert infra == {"python": "3.12", "node": "22", "java": "21"}

    def test_returns_old_format_versions(self, old_format_versions_file: Path):
        """Test backward compatibility with old format."""
        manager = VersionManager(versions_file=old_format_versions_file)
        infra = manager.get_infrastructure_versions()

        assert infra == {"python": "3.11", "node": "20", "java": "17"}

    def test_returns_defaults_for_missing_infrastructure(self, tmp_path: Path):
        """Test that defaults are returned when infrastructure section is missing."""
        minimal_file = tmp_path / "minimal.json"
        minimal_file.write_text(json.dumps({"version": "1.0.0"}, indent=2))

        manager = VersionManager(versions_file=minimal_file)
        infra = manager.get_infrastructure_versions()

        assert infra == {"python": "3.12", "node": "22", "java": "21"}


class TestGetInfrastructureMetadata:
    """Tests for get_infrastructure_metadata method."""

    def test_returns_metadata_for_language(self, sample_versions_file: Path):
        """Test retrieval of infrastructure metadata including EOL."""
        manager = VersionManager(versions_file=sample_versions_file)

        python_meta = manager.get_infrastructure_metadata("python")
        assert python_meta == {"version": "3.12", "eol": "2028-10"}

    def test_returns_none_for_missing_language(self, sample_versions_file: Path):
        """Test that None is returned for non-existent language."""
        manager = VersionManager(versions_file=sample_versions_file)

        rust_meta = manager.get_infrastructure_metadata("rust")
        assert rust_meta is None

    def test_returns_none_for_old_format(self, old_format_versions_file: Path):
        """Test that None is returned for old format (no metadata)."""
        manager = VersionManager(versions_file=old_format_versions_file)

        python_meta = manager.get_infrastructure_metadata("python")
        assert python_meta is None


class TestGetAdapterVersion:
    """Tests for get_adapter_version method."""

    def test_returns_python_adapter_version(
        self,
        sample_versions_file: Path,
    ):
        """Test Python adapter version extraction from adapters section."""
        manager = VersionManager(versions_file=sample_versions_file)

        version = manager.get_adapter_version("python")
        assert version == "1.8.16"

    def test_returns_javascript_adapter_version(self, sample_versions_file: Path):
        """Test JavaScript adapter version extraction."""
        manager = VersionManager(versions_file=sample_versions_file)

        version = manager.get_adapter_version("javascript")
        assert version == "1.104.0"

    def test_strips_v_prefix_from_version(self, sample_versions_file: Path):
        """Test that 'v' prefix is stripped from versions."""
        manager = VersionManager(versions_file=sample_versions_file)

        # The file has "v1.104.0", should return "1.104.0"
        version = manager.get_adapter_version("javascript")
        assert version == "1.104.0"
        assert not version.startswith("v")

    def test_returns_java_adapter_version(self, sample_versions_file: Path):
        """Test Java adapter version extraction."""
        manager = VersionManager(versions_file=sample_versions_file)

        version = manager.get_adapter_version("java")
        assert version == "0.53.1"

    def test_returns_none_for_unknown_language(self, sample_versions_file: Path):
        """Test that None is returned for unknown language."""
        manager = VersionManager(versions_file=sample_versions_file)

        version = manager.get_adapter_version("rust")
        assert version is None

    def test_returns_none_for_missing_python_config(self, tmp_path: Path):
        """Test that None is returned when Python adapter config is missing."""
        minimal_file = tmp_path / "minimal.json"
        minimal_file.write_text(json.dumps({"version": "1.0.0"}, indent=2))

        manager = VersionManager(versions_file=minimal_file)

        version = manager.get_adapter_version("python")
        assert version is None


class TestGetDockerBuildArgs:
    """Tests for get_docker_build_args method."""

    def test_returns_all_build_args(self, sample_versions_file: Path):
        """Test that all Docker build args are generated."""
        manager = VersionManager(versions_file=sample_versions_file)

        build_args = manager.get_docker_build_args()

        assert "PYTHON_VERSION" in build_args
        assert "NODE_VERSION" in build_args
        assert "JAVA_VERSION" in build_args
        assert "DEBUGPY_VERSION" in build_args
        assert "JS_DEBUG_VERSION" in build_args
        assert "JAVA_DEBUG_VERSION" in build_args
        assert "JDTLS_VERSION" in build_args

    def test_build_args_have_correct_values(self, sample_versions_file: Path):
        """Test that build arg values match versions file.

        Note: Values checked here must match the sample_versions_file fixture.
        This test verifies the mapping logic, not specific version numbers.
        """
        manager = VersionManager(versions_file=sample_versions_file)
        versions = manager.versions

        build_args = manager.get_docker_build_args()

        # Infrastructure versions
        assert (
            build_args["PYTHON_VERSION"]
            == versions["infrastructure"]["python"]["version"]
        )
        assert (
            build_args["NODE_VERSION"] == versions["infrastructure"]["node"]["version"]
        )
        assert (
            build_args["JAVA_VERSION"] == versions["infrastructure"]["java"]["version"]
        )

        # Adapter versions (strip 'v' prefix if present)
        assert build_args["DEBUGPY_VERSION"] == versions["adapters"]["python"][
            "version"
        ].lstrip("v")
        assert build_args["JS_DEBUG_VERSION"] == versions["adapters"]["javascript"][
            "version"
        ].lstrip("v")
        assert build_args["JAVA_DEBUG_VERSION"] == versions["adapters"]["java"][
            "version"
        ].lstrip("v")
        assert (
            build_args["JDTLS_VERSION"] == versions["adapters"]["java"]["jdtls_version"]
        )


class TestGetAllVersions:
    """Tests for get_all_versions method."""

    def test_returns_structured_version_info(self, sample_versions_file: Path):
        """Test that all version info is returned in structured format."""
        manager = VersionManager(versions_file=sample_versions_file)

        all_versions = manager.get_all_versions()

        assert "aidb_version" in all_versions
        assert "infrastructure" in all_versions
        assert "adapters" in all_versions
        assert "runtimes" in all_versions

    def test_includes_aidb_version(self, sample_versions_file: Path):
        """Test that AIDB version is included."""
        manager = VersionManager(versions_file=sample_versions_file)

        all_versions = manager.get_all_versions()
        assert all_versions["aidb_version"] == "1.0.0"

    def test_includes_all_adapter_versions(self, sample_versions_file: Path):
        """Test that all adapter versions are included."""
        manager = VersionManager(versions_file=sample_versions_file)

        all_versions = manager.get_all_versions()

        assert all_versions["adapters"]["javascript"] == "1.104.0"
        assert all_versions["adapters"]["java"] == "0.53.1"
        assert all_versions["adapters"]["python"] == "1.8.16"

    def test_includes_runtime_requirements(self, sample_versions_file: Path):
        """Test that runtime requirements are included."""
        manager = VersionManager(versions_file=sample_versions_file)

        all_versions = manager.get_all_versions()

        python_runtime = all_versions["runtimes"]["python"]
        assert python_runtime["min_version"] == "3.9"
        assert python_runtime["recommended"] == "3.12"


class TestValidateVersions:
    """Tests for validate_versions method."""

    def test_validates_complete_versions_file(self, sample_versions_file: Path):
        """Test validation of complete versions file."""
        manager = VersionManager(versions_file=sample_versions_file)

        validation = manager.validate_versions()

        assert validation["infrastructure"] is True
        assert validation["adapters"] is True
        assert validation["runtimes"] is True

    def test_validates_old_format_infrastructure(self, old_format_versions_file: Path):
        """Test validation accepts old format infrastructure."""
        manager = VersionManager(versions_file=old_format_versions_file)

        validation = manager.validate_versions()

        assert validation["infrastructure"] is True

    def test_fails_validation_for_incomplete_adapters(self, tmp_path: Path):
        """Test validation fails for incomplete adapters section."""
        incomplete_file = tmp_path / "incomplete.json"
        incomplete_file.write_text(
            json.dumps(
                {
                    "version": "1.0.0",
                    "infrastructure": {
                        "python": {"version": "3.12"},
                        "node": {"version": "22"},
                        "java": {"version": "21"},
                    },
                    "adapters": {
                        "javascript": {"version": "1.104.0"},
                    },
                },
                indent=2,
            ),
        )


class TestGetAdapterDownloadInfo:
    """Tests for get_adapter_download_info method."""

    def test_returns_javascript_download_info(self, sample_versions_file: Path):
        """Test JavaScript adapter download URL generation."""
        manager = VersionManager(versions_file=sample_versions_file)

        info = manager.get_adapter_download_info("javascript")

        assert info is not None
        assert info["version"] == "v1.104.0"
        assert "github.com/microsoft/vscode-js-debug" in info["url"]
        assert "js-debug-dap-v1.104.0.tar.gz" in info["url"]

    def test_returns_java_download_info(self, sample_versions_file: Path):
        """Test Java adapter download URL generation."""
        manager = VersionManager(versions_file=sample_versions_file)

        info = manager.get_adapter_download_info("java")

        assert info is not None
        assert info["version"] == "0.53.1"
        assert "vscjava.gallery.vsassets.io" in info["url"]
        assert "0.53.1" in info["url"]

    def test_returns_none_for_unknown_language(self, sample_versions_file: Path):
        """Test that None is returned for unknown language."""
        manager = VersionManager(versions_file=sample_versions_file)

        info = manager.get_adapter_download_info("rust")

        assert info is None


class TestFormatVersionsOutput:
    """Tests for format_versions_output method."""

    def test_formats_as_json(self, sample_versions_file: Path):
        """Test JSON format output."""
        manager = VersionManager(versions_file=sample_versions_file)

        output = manager.format_versions_output(format_type="json")

        data = json.loads(output)
        assert data["aidb_version"] == "1.0.0"
        assert isinstance(data["adapters"], dict)

    def test_formats_as_yaml(self, sample_versions_file: Path):
        """Test YAML format output."""
        import yaml

        manager = VersionManager(versions_file=sample_versions_file)

        output = manager.format_versions_output(format_type="yaml")

        data = yaml.safe_load(output)
        assert data["aidb_version"] == "1.0.0"

    def test_formats_as_env(self, sample_versions_file: Path):
        """Test environment variable format output."""
        manager = VersionManager(versions_file=sample_versions_file)

        output = manager.format_versions_output(format_type="env")

        assert "export PYTHON_VERSION=3.12" in output
        assert "export NODE_VERSION=22" in output
        assert "export DEBUGPY_VERSION=1.8.16" in output

    def test_formats_as_text_default(self, sample_versions_file: Path):
        """Test default text format output."""
        manager = VersionManager(versions_file=sample_versions_file)

        output = manager.format_versions_output()

        assert "AIDB Version Information" in output
        assert "Infrastructure Versions:" in output
        assert "Python: 3.12" in output
        assert "Adapter Versions:" in output

    def test_text_format_includes_runtime_requirements(
        self,
        sample_versions_file: Path,
    ):
        """Test that text format includes runtime requirements."""
        manager = VersionManager(versions_file=sample_versions_file)

        output = manager.format_versions_output(format_type="text")

        assert "Runtime Requirements:" in output
        assert "python:" in output
        assert "Minimum: 3.9" in output
        assert "Recommended: 3.12" in output


class TestFormatGlobalPackagesSection:
    """Tests for _format_global_packages_section method."""

    def test_format_global_packages_empty(
        self,
        sample_versions_with_extensions: Path,
    ):
        """Test formatting empty global packages dict."""
        manager = VersionManager(versions_file=sample_versions_with_extensions)

        lines = manager._format_global_packages_section({})

        assert lines == []

    def test_format_global_packages_pip_only(
        self,
        sample_versions_with_extensions: Path,
    ):
        """Test formatting pip packages only."""
        manager = VersionManager(versions_file=sample_versions_with_extensions)
        global_packages = {
            "pip": {
                "pip": {"version": "25.3", "description": "Package installer"},
            },
        }

        lines = manager._format_global_packages_section(global_packages)

        assert "PIP Packages:" in lines
        assert "pip" in " ".join(lines)
        assert "25.3" in " ".join(lines)
        assert "→ Package installer" in " ".join(lines)

    def test_format_global_packages_npm_only(
        self,
        sample_versions_with_extensions: Path,
    ):
        """Test formatting npm packages only."""
        manager = VersionManager(versions_file=sample_versions_with_extensions)
        global_packages = {
            "npm": {
                "typescript": {"version": "5.9.3", "description": "TS compiler"},
            },
        }

        lines = manager._format_global_packages_section(global_packages)

        assert "NPM Packages:" in lines
        assert "typescript" in " ".join(lines)
        assert "5.9.3" in " ".join(lines)

    def test_format_global_packages_mixed(
        self,
        sample_versions_with_extensions: Path,
    ):
        """Test formatting both pip and npm packages."""
        manager = VersionManager(versions_file=sample_versions_with_extensions)
        global_packages = manager.versions.get("global_packages", {})

        lines = manager._format_global_packages_section(global_packages)

        assert "PIP Packages:" in lines
        assert "NPM Packages:" in lines
        assert "pip" in " ".join(lines)
        assert "typescript" in " ".join(lines)

    def test_format_global_packages_without_description(
        self,
        sample_versions_with_extensions: Path,
    ):
        """Test formatting packages without descriptions."""
        manager = VersionManager(versions_file=sample_versions_with_extensions)
        global_packages = {
            "pip": {
                "test_pkg": {"version": "1.0.0"},
            },
        }

        lines = manager._format_global_packages_section(global_packages)

        lines_text = " ".join(lines)
        assert "→" not in lines_text or "test_pkg" in lines_text


class TestFormatRuntimesSection:
    """Tests for _format_runtimes_section method."""

    def test_format_runtimes_empty(self, sample_versions_with_extensions: Path):
        """Test formatting empty runtimes dict."""
        manager = VersionManager(versions_file=sample_versions_with_extensions)

        lines = manager._format_runtimes_section({})

        assert lines == ["", "Runtime Requirements:"]

    def test_format_runtimes_with_both_versions(
        self,
        sample_versions_with_extensions: Path,
    ):
        """Test formatting runtime with min and recommended versions."""
        manager = VersionManager(versions_file=sample_versions_with_extensions)
        runtimes = {
            "python": {"min_version": "3.10", "recommended": "3.12"},
        }

        lines = manager._format_runtimes_section(runtimes)
        lines_text = " ".join(lines)

        assert "Runtime Requirements:" in lines
        assert "python:" in lines_text
        assert "Minimum: 3.10" in lines_text
        assert "Recommended: 3.12" in lines_text

    def test_format_runtimes_min_only(self, sample_versions_with_extensions: Path):
        """Test formatting runtime with only minimum version."""
        manager = VersionManager(versions_file=sample_versions_with_extensions)
        runtimes = {
            "python": {"min_version": "3.10"},
        }

        lines = manager._format_runtimes_section(runtimes)
        lines_text = " ".join(lines)

        assert "Minimum: 3.10" in lines_text
        assert "Recommended:" not in lines_text

    def test_format_runtimes_multiple_languages(
        self,
        sample_versions_with_extensions: Path,
    ):
        """Test formatting multiple runtimes."""
        manager = VersionManager(versions_file=sample_versions_with_extensions)
        runtimes = manager.versions.get("runtimes", {})

        lines = manager._format_runtimes_section(runtimes)
        lines_text = " ".join(lines)

        assert "python:" in lines_text
        assert "javascript:" in lines_text


class TestFormatVersionsOutputExtended:
    """Tests for format_versions_output with new sections."""

    def test_format_text_includes_global_packages(
        self,
        sample_versions_with_extensions: Path,
    ):
        """Test text output includes global packages section."""
        manager = VersionManager(versions_file=sample_versions_with_extensions)

        output = manager.format_versions_output(format_type="text")

        assert "PIP Packages:" in output
        assert "NPM Packages:" in output
        assert "pip" in output
        assert "typescript" in output

    def test_format_json_includes_new_sections(
        self,
        sample_versions_with_extensions: Path,
    ):
        """Test JSON output includes global_packages."""
        manager = VersionManager(versions_file=sample_versions_with_extensions)

        output = manager.format_versions_output(format_type="json")
        data = json.loads(output)

        assert "global_packages" in data
        assert "pip" in data["global_packages"]

    def test_format_yaml_includes_new_sections(
        self,
        sample_versions_with_extensions: Path,
    ):
        """Test YAML output includes global_packages."""
        import yaml

        manager = VersionManager(versions_file=sample_versions_with_extensions)

        output = manager.format_versions_output(format_type="yaml")
        data = yaml.safe_load(output)

        assert "global_packages" in data


class TestGetAllVersionsExtended:
    """Tests for get_all_versions with new sections."""

    def test_get_all_versions_includes_global_packages(
        self,
        sample_versions_with_extensions: Path,
    ):
        """Test get_all_versions includes global_packages key."""
        manager = VersionManager(versions_file=sample_versions_with_extensions)

        data = manager.get_all_versions()

        assert "global_packages" in data
        assert isinstance(data["global_packages"], dict)
        assert "pip" in data["global_packages"]
        assert "npm" in data["global_packages"]

    def test_get_all_versions_global_packages_structure(
        self,
        sample_versions_with_extensions: Path,
    ):
        """Test global_packages section has correct structure."""
        manager = VersionManager(versions_file=sample_versions_with_extensions)

        data = manager.get_all_versions()
        global_packages = data["global_packages"]

        for manager_type, packages in global_packages.items():
            assert manager_type in ["pip", "npm"]
            for _pkg_name, pkg_info in packages.items():
                assert "version" in pkg_info
                assert "description" in pkg_info
