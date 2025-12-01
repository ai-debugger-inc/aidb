"""Unit tests for ConfigLoader class."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(
    0,
    str(Path(__file__).parent.parent.parent.parent.parent / ".github" / "scripts"),
)

from version_management.config.loader import ConfigLoader


class TestConfigLoader:
    """Test ConfigLoader functionality."""

    def test_load_valid_json(self, tmp_path):
        """Verify loading a well-formed JSON file."""
        config_file = tmp_path / "versions.json"
        config_data = {
            "version": "1.0.0",
            "infrastructure": {
                "python": {"version": "3.12.0"},
            },
        }

        # Write test config
        with config_file.open("w") as f:
            json.dump(config_data, f, indent=2)

        # Load and verify
        loaded_config = ConfigLoader.load(config_file)

        assert loaded_config["version"] == "1.0.0"
        assert "infrastructure" in loaded_config
        assert loaded_config["infrastructure"]["python"]["version"] == "3.12.0"

    def test_load_preserves_nested_structure(self, tmp_path):
        """Verify nested dictionary structure is preserved when loading."""
        config_file = tmp_path / "versions.json"
        config_data = {
            "version": "1.0.0",
            "adapters": {
                "javascript": {
                    "version": "v1.86.0",
                    "source": "microsoft/vscode-js-debug",
                },
                "java": {
                    "version": "0.55.0",
                    "source": "microsoft/java-debug",
                },
            },
        }

        with config_file.open("w") as f:
            json.dump(config_data, f, indent=2)

        loaded_config = ConfigLoader.load(config_file)

        # Verify structure
        assert loaded_config == config_data
        assert (
            loaded_config["adapters"]["javascript"]["source"]
            == "microsoft/vscode-js-debug"
        )

    def test_load_missing_file_raises_error(self, tmp_path):
        """Verify FileNotFoundError raised for missing file."""
        missing_file = tmp_path / "nonexistent.yaml"

        with pytest.raises(FileNotFoundError):
            ConfigLoader.load(missing_file)

    def test_load_invalid_json_raises_error(self, tmp_path):
        """Verify json.JSONDecodeError raised for malformed JSON."""
        invalid_file = tmp_path / "invalid.json"

        # Write malformed JSON
        with invalid_file.open("w") as f:
            f.write('{"version": "1.0.0", "invalid": [unmatched}')

        with pytest.raises(json.JSONDecodeError):
            ConfigLoader.load(invalid_file)

    def test_save_writes_to_file(self, tmp_path):
        """Verify saving configuration creates valid JSON file."""
        config_file = tmp_path / "versions.json"
        config_data = {
            "version": "1.0.0",
            "infrastructure": {
                "python": {"version": "3.12.0"},
            },
        }

        ConfigLoader.save(config_file, config_data)

        # Verify file exists
        assert config_file.exists()

        # Verify content is valid YAML
        with config_file.open() as f:
            loaded_data = json.load(f)

        assert loaded_data == config_data

    def test_save_preserves_structure(self, tmp_path):
        """Verify JSON format options are preserved when saving."""
        config_file = tmp_path / "versions.json"
        config_data = {
            "version": "1.0.0",
            "zebra": "should not be first",
            "adapters": {
                "javascript": {"version": "v1.86.0"},
            },
        }

        ConfigLoader.save(config_file, config_data)

        # Read raw file content
        content = config_file.read_text()

        # Verify using pretty-print format (should have newlines and indentation)
        assert "\n" in content, "JSON should be pretty-printed with newlines"
        assert "  " in content, "JSON should be indented"

        # Verify keys not sorted alphabetically (zebra should appear after version)
        lines = content.split("\n")
        version_line = next(i for i, line in enumerate(lines) if '"version"' in line)
        zebra_line = next(i for i, line in enumerate(lines) if '"zebra"' in line)
        assert version_line < zebra_line

    def test_save_overwrites_existing_file(self, tmp_path):
        """Verify saving overwrites existing file content."""
        config_file = tmp_path / "versions.json"

        # Write initial content
        initial_data = {"version": "1.0.0"}
        ConfigLoader.save(config_file, initial_data)

        # Overwrite with new content
        new_data = {"version": "2.0.0", "new_key": "new_value"}
        ConfigLoader.save(config_file, new_data)

        # Verify new content
        with config_file.open() as f:
            loaded_data = json.load(f)

        assert loaded_data == new_data
        assert loaded_data["version"] == "2.0.0"
        assert "new_key" in loaded_data

    def test_round_trip_preserves_data(self, tmp_path):
        """Verify save then load preserves data integrity."""
        config_file = tmp_path / "versions.json"
        original_data = {
            "version": "1.0.0",
            "infrastructure": {
                "python": {"version": "3.12.0", "docker_tag": "3.12.0"},
                "node": {"version": "20.10.0", "docker_tag": "20.10.0"},
            },
            "adapters": {
                "javascript": {"version": "v1.86.0"},
            },
            "global_packages": {
                "pip": {"setuptools": {"version": "69.0.0"}},
                "npm": {"typescript": {"version": "5.3.3"}},
            },
        }

        # Save then load
        ConfigLoader.save(config_file, original_data)
        loaded_data = ConfigLoader.load(config_file)

        # Verify complete data integrity
        assert loaded_data == original_data
        assert loaded_data["infrastructure"]["python"]["docker_tag"] == "3.12.0"
        assert (
            loaded_data["global_packages"]["pip"]["setuptools"]["version"] == "69.0.0"
        )
