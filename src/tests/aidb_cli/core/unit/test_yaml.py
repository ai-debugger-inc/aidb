"""Tests for aidb_cli.core.yaml module."""

from pathlib import Path

import pytest
import yaml

from aidb_cli.core.yaml import (
    YamlOperationError,
    safe_read_yaml,
    safe_write_yaml,
)


class TestSafeReadYaml:
    """Tests for safe_read_yaml function."""

    def test_reads_valid_yaml(self, tmp_path: Path):
        """Test reading a valid YAML file."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("key: value\nnumber: 42")

        data = safe_read_yaml(yaml_file)
        assert data == {"key": "value", "number": 42}

    def test_raises_error_on_missing_file(self, tmp_path: Path):
        """Test that missing file raises YamlOperationError."""
        missing_file = tmp_path / "missing.yaml"
        with pytest.raises(YamlOperationError, match="does not exist"):
            safe_read_yaml(missing_file)

    def test_raises_error_on_malformed_yaml(self, tmp_path: Path):
        """Test that malformed YAML raises YamlOperationError."""
        yaml_file = tmp_path / "malformed.yaml"
        yaml_file.write_text("key: value\n  bad: indentation:\n    invalid")

        with pytest.raises(YamlOperationError, match="Invalid YAML"):
            safe_read_yaml(yaml_file)

    def test_returns_empty_dict_for_empty_yaml(self, tmp_path: Path):
        """Test that empty YAML returns empty dict."""
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text("")

        data = safe_read_yaml(yaml_file)
        assert data == {}


class TestSafeWriteYaml:
    """Tests for safe_write_yaml function."""

    def test_writes_yaml_atomically(self, tmp_path: Path):
        """Test atomic YAML writing."""
        yaml_file = tmp_path / "output.yaml"
        data = {"test": "data", "number": 123}

        safe_write_yaml(yaml_file, data)

        assert yaml_file.exists()
        loaded = yaml.safe_load(yaml_file.read_text())
        assert loaded == data

    def test_creates_parent_directory(self, tmp_path: Path):
        """Test that parent directories are created."""
        yaml_file = tmp_path / "subdir" / "output.yaml"
        data = {"test": "data"}

        safe_write_yaml(yaml_file, data)

        assert yaml_file.exists()
        assert yaml_file.parent.exists()

    def test_overwrites_existing_file(self, tmp_path: Path):
        """Test that existing files are overwritten."""
        yaml_file = tmp_path / "output.yaml"
        yaml_file.write_text("old: data")

        new_data = {"new": "data"}
        safe_write_yaml(yaml_file, new_data)

        loaded = yaml.safe_load(yaml_file.read_text())
        assert loaded == new_data

    def test_writes_sorted_keys(self, tmp_path: Path):
        """Test that keys are sorted in output."""
        yaml_file = tmp_path / "output.yaml"
        data = {"zebra": 1, "apple": 2, "banana": 3}

        safe_write_yaml(yaml_file, data)

        content = yaml_file.read_text()
        assert content.index("apple") < content.index("banana") < content.index("zebra")


class TestYamlOperationError:
    """Tests for YamlOperationError exception."""

    def test_is_exception(self):
        """Test that YamlOperationError is an exception."""
        assert issubclass(YamlOperationError, Exception)

    def test_can_be_raised_with_message(self):
        """Test that error can be raised with message."""
        msg = "test message"
        with pytest.raises(YamlOperationError, match="test message"):
            raise YamlOperationError(msg)

    def test_preserves_cause(self):
        """Test that exception cause is preserved."""

        def raise_with_cause():
            try:
                yaml.safe_load("invalid: yaml:\n  bad: indent")
            except yaml.YAMLError as e:
                msg = "Wrapped error"
                raise YamlOperationError(msg) from e

        with pytest.raises(YamlOperationError) as exc_info:
            raise_with_cause()

        assert exc_info.value.__cause__ is not None
        assert isinstance(exc_info.value.__cause__, yaml.YAMLError)
