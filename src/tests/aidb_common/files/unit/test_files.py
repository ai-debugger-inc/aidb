"""Tests for aidb_common.io.files module."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml

from aidb_common.io.files import (
    FileOperationError,
    atomic_write,
    ensure_dir,
    safe_read_json,
    safe_read_yaml,
    safe_write_json,
    safe_write_yaml,
)


class TestSafeReadJson:
    """Tests for safe_read_json function."""

    def test_reads_valid_json(self, sample_json_file: Path):
        """Test reading a valid JSON file."""
        data = safe_read_json(sample_json_file)
        assert data == {"key": "value", "number": 42}

    def test_raises_error_on_missing_file(self, tmp_path: Path):
        """Test that missing file raises FileOperationError."""
        missing_file = tmp_path / "missing.json"
        with pytest.raises(FileOperationError, match="does not exist"):
            safe_read_json(missing_file)

    def test_raises_error_on_malformed_json(self, malformed_json_file: Path):
        """Test that malformed JSON raises FileOperationError."""
        with pytest.raises(FileOperationError, match="Invalid JSON"):
            safe_read_json(malformed_json_file)

    def test_returns_empty_dict_for_non_dict_json(self, tmp_path: Path):
        """Test that non-dict JSON returns empty dict."""
        json_file = tmp_path / "list.json"
        json_file.write_text(json.dumps([1, 2, 3]))
        data = safe_read_json(json_file)
        assert data == {}

    def test_handles_unicode_decode_error(self, tmp_path: Path):
        """Test handling of unicode decode errors."""
        json_file = tmp_path / "bad_encoding.json"
        json_file.write_bytes(b"\xff\xfe invalid utf-8")
        with pytest.raises(FileOperationError, match="Invalid JSON"):
            safe_read_json(json_file)


class TestSafeWriteJson:
    """Tests for safe_write_json function."""

    def test_writes_json_atomically(self, tmp_path: Path):
        """Test atomic JSON writing."""
        json_file = tmp_path / "output.json"
        data = {"test": "data", "number": 123}

        safe_write_json(json_file, data)

        assert json_file.exists()
        with json_file.open() as f:
            loaded = json.load(f)
        assert loaded == data

    def test_creates_parent_directory(self, tmp_path: Path):
        """Test that parent directories are created."""
        json_file = tmp_path / "subdir" / "output.json"
        data = {"test": "data"}

        safe_write_json(json_file, data)

        assert json_file.exists()
        assert json_file.parent.exists()

    def test_overwrites_existing_file(self, tmp_path: Path):
        """Test that existing files are overwritten."""
        json_file = tmp_path / "output.json"
        json_file.write_text("old data")

        new_data = {"new": "data"}
        safe_write_json(json_file, new_data)

        with json_file.open() as f:
            loaded = json.load(f)
        assert loaded == new_data

    def test_cleans_up_temp_file_on_error(self, tmp_path: Path):
        """Test that temp files are cleaned up on errors."""
        json_file = tmp_path / "output.json"

        class UnserializableObject:
            pass

        with pytest.raises(FileOperationError):
            safe_write_json(json_file, {"obj": UnserializableObject()})

        temp_files = [f for f in tmp_path.glob("*.json") if f != json_file]
        assert len(temp_files) == 0


class TestSafeReadYaml:
    """Tests for safe_read_yaml function."""

    def test_reads_valid_yaml(self, tmp_path: Path):
        """Test reading a valid YAML file."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("key: value\nnumber: 42")

        data = safe_read_yaml(yaml_file)
        assert data == {"key": "value", "number": 42}

    def test_raises_error_on_missing_file(self, tmp_path: Path):
        """Test that missing file raises FileOperationError."""
        missing_file = tmp_path / "missing.yaml"
        with pytest.raises(FileOperationError, match="does not exist"):
            safe_read_yaml(missing_file)

    def test_raises_error_on_malformed_yaml(self, tmp_path: Path):
        """Test that malformed YAML raises FileOperationError."""
        yaml_file = tmp_path / "malformed.yaml"
        yaml_file.write_text("key: value\n  bad: indentation:\n    invalid")

        with pytest.raises(FileOperationError, match="Invalid YAML"):
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


class TestAtomicWrite:
    """Tests for atomic_write function."""

    def test_writes_content_atomically(self, tmp_path: Path):
        """Test atomic content writing."""
        file_path = tmp_path / "output.txt"
        content = "test content\nline 2"

        atomic_write(file_path, content)

        assert file_path.exists()
        assert file_path.read_text() == content

    def test_creates_parent_directory(self, tmp_path: Path):
        """Test that parent directories are created."""
        file_path = tmp_path / "subdir" / "output.txt"
        content = "test content"

        atomic_write(file_path, content)

        assert file_path.exists()
        assert file_path.parent.exists()

    def test_overwrites_existing_file(self, tmp_path: Path):
        """Test that existing files are overwritten."""
        file_path = tmp_path / "output.txt"
        file_path.write_text("old content")

        new_content = "new content"
        atomic_write(file_path, new_content)

        assert file_path.read_text() == new_content

    def test_preserves_file_suffix(self, tmp_path: Path):
        """Test that file suffix is preserved in temp file."""
        file_path = tmp_path / "output.custom"
        content = "test"

        atomic_write(file_path, content)

        assert file_path.exists()
        assert file_path.read_text() == content
        assert file_path.suffix == ".custom"


class TestEnsureDir:
    """Tests for ensure_dir function."""

    def test_creates_directory(self, tmp_path: Path):
        """Test directory creation."""
        new_dir = tmp_path / "newdir"
        result = ensure_dir(new_dir)

        assert new_dir.exists()
        assert new_dir.is_dir()
        assert result == new_dir

    def test_creates_parent_directories(self, tmp_path: Path):
        """Test that parent directories are created."""
        nested_dir = tmp_path / "parent" / "child" / "grandchild"
        result = ensure_dir(nested_dir)

        assert nested_dir.exists()
        assert result == nested_dir

    def test_succeeds_if_directory_exists(self, tmp_path: Path):
        """Test that existing directories don't raise errors."""
        existing_dir = tmp_path / "existing"
        existing_dir.mkdir()

        result = ensure_dir(existing_dir)

        assert result == existing_dir
        assert existing_dir.exists()

    def test_raises_error_on_permission_denied(self, tmp_path: Path):
        """Test handling of permission errors."""
        new_dir = tmp_path / "newdir"

        with patch.object(Path, "mkdir", side_effect=OSError("Permission denied")):
            with pytest.raises(FileOperationError, match="Cannot create directory"):
                ensure_dir(new_dir)


class TestFileOperationError:
    """Tests for FileOperationError exception."""

    def test_is_exception(self):
        """Test that FileOperationError is an exception."""
        assert issubclass(FileOperationError, Exception)

    def test_can_be_raised_with_message(self):
        """Test that error can be raised with message."""
        msg = "test message"
        with pytest.raises(FileOperationError, match="test message"):
            raise FileOperationError(msg)

    def test_preserves_cause(self):
        """Test that exception cause is preserved."""

        def raise_with_cause():
            try:
                json.loads("{invalid")
            except json.JSONDecodeError as e:
                msg = "Wrapped error"
                raise FileOperationError(msg) from e

        with pytest.raises(FileOperationError) as exc_info:
            raise_with_cause()

        assert exc_info.value.__cause__ is not None
        assert isinstance(exc_info.value.__cause__, json.JSONDecodeError)
