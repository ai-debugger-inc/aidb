"""Unit tests for download_artifact.py script."""

import json
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import download_artifact  # noqa: S106, S108, E402 - test fixtures not real credentials/paths
import pytest


class TestFindWorkflowRun:
    """Test the find_workflow_run function."""

    def test_find_successful_run(self):
        """Test finding a successful workflow run."""
        mock_response = MagicMock()
        mock_response.__enter__.return_value.read.return_value = json.dumps(
            {
                "workflow_runs": [
                    {
                        "id": 123456,
                        "conclusion": "success",
                        "head_sha": "abc123",
                    },
                ],
            },
        ).encode()

        with patch(
            "download_artifact.github_api_request",
            return_value=json.loads(
                mock_response.__enter__.return_value.read.return_value.decode(),
            ),
        ):
            result = download_artifact.find_workflow_run(
                owner="test-owner",
                repo="test-repo",
                workflow="test.yaml",
                commit="abc123",
                token="fake-token",
            )

        assert result == "123456"

    def test_no_successful_run(self):
        """Test when no successful run is found."""
        mock_response = MagicMock()
        mock_response.__enter__.return_value.read.return_value = json.dumps(
            {
                "workflow_runs": [
                    {
                        "id": 123456,
                        "conclusion": "failure",
                        "head_sha": "abc123",
                    },
                ],
            },
        ).encode()

        with patch(
            "download_artifact.github_api_request",
            return_value=json.loads(
                mock_response.__enter__.return_value.read.return_value.decode(),
            ),
        ):
            result = download_artifact.find_workflow_run(
                owner="test-owner",
                repo="test-repo",
                workflow="test.yaml",
                commit="abc123",
                token="fake-token",
            )

        assert result is None

    def test_multiple_runs_returns_first_success(self):
        """Test that first successful run is returned."""
        mock_response = MagicMock()
        mock_response.__enter__.return_value.read.return_value = json.dumps(
            {
                "workflow_runs": [
                    {
                        "id": 111111,
                        "conclusion": "success",
                        "head_sha": "abc123",
                    },
                    {
                        "id": 222222,
                        "conclusion": "success",
                        "head_sha": "abc123",
                    },
                ],
            },
        ).encode()

        with patch(
            "download_artifact.github_api_request",
            return_value=json.loads(
                mock_response.__enter__.return_value.read.return_value.decode(),
            ),
        ):
            result = download_artifact.find_workflow_run(
                owner="test-owner",
                repo="test-repo",
                workflow="test.yaml",
                commit="abc123",
                token="fake-token",
            )

        assert result == "111111"

    def test_custom_conclusion(self):
        """Test finding run with custom conclusion."""
        mock_response = MagicMock()
        mock_response.__enter__.return_value.read.return_value = json.dumps(
            {
                "workflow_runs": [
                    {
                        "id": 123456,
                        "conclusion": "cancelled",
                        "head_sha": "abc123",
                    },
                ],
            },
        ).encode()

        with patch(
            "download_artifact.github_api_request",
            return_value=json.loads(
                mock_response.__enter__.return_value.read.return_value.decode(),
            ),
        ):
            result = download_artifact.find_workflow_run(
                owner="test-owner",
                repo="test-repo",
                workflow="test.yaml",
                commit="abc123",
                token="fake-token",
                conclusion="cancelled",
            )

        assert result == "123456"

    def test_empty_workflow_runs(self):
        """Test when no workflow runs exist."""
        mock_response = MagicMock()
        mock_response.__enter__.return_value.read.return_value = json.dumps(
            {
                "workflow_runs": [],
            },
        ).encode()

        with patch(
            "download_artifact.github_api_request",
            return_value=json.loads(
                mock_response.__enter__.return_value.read.return_value.decode(),
            ),
        ):
            result = download_artifact.find_workflow_run(
                owner="test-owner",
                repo="test-repo",
                workflow="test.yaml",
                commit="abc123",
                token="fake-token",
            )

        assert result is None


class TestFindArtifact:
    """Test the find_artifact function."""

    def test_find_artifact_by_name(self):
        """Test finding artifact by name."""
        mock_response = MagicMock()
        mock_response.__enter__.return_value.read.return_value = json.dumps(
            {
                "artifacts": [
                    {
                        "id": 111,
                        "name": "test-artifact",
                        "size_in_bytes": 1024,
                    },
                ],
            },
        ).encode()

        with patch(
            "download_artifact.github_api_request",
            return_value=json.loads(
                mock_response.__enter__.return_value.read.return_value.decode(),
            ),
        ):
            result = download_artifact.find_artifact(
                owner="test-owner",
                repo="test-repo",
                run_id="123456",
                artifact_name="test-artifact",
                token="fake-token",
            )

        assert result is not None
        assert result["id"] == 111
        assert result["name"] == "test-artifact"

    def test_artifact_not_found(self):
        """Test when artifact is not found."""
        mock_response = MagicMock()
        mock_response.__enter__.return_value.read.return_value = json.dumps(
            {
                "artifacts": [
                    {
                        "id": 111,
                        "name": "different-artifact",
                        "size_in_bytes": 1024,
                    },
                ],
            },
        ).encode()

        with patch(
            "download_artifact.github_api_request",
            return_value=json.loads(
                mock_response.__enter__.return_value.read.return_value.decode(),
            ),
        ):
            result = download_artifact.find_artifact(
                owner="test-owner",
                repo="test-repo",
                run_id="123456",
                artifact_name="test-artifact",
                token="fake-token",
            )

        assert result is None

    def test_multiple_artifacts_returns_correct_one(self):
        """Test finding specific artifact among multiple."""
        mock_response = MagicMock()
        mock_response.__enter__.return_value.read.return_value = json.dumps(
            {
                "artifacts": [
                    {
                        "id": 111,
                        "name": "artifact-1",
                        "size_in_bytes": 1024,
                    },
                    {
                        "id": 222,
                        "name": "test-artifact",
                        "size_in_bytes": 2048,
                    },
                    {
                        "id": 333,
                        "name": "artifact-3",
                        "size_in_bytes": 4096,
                    },
                ],
            },
        ).encode()

        with patch(
            "download_artifact.github_api_request",
            return_value=json.loads(
                mock_response.__enter__.return_value.read.return_value.decode(),
            ),
        ):
            result = download_artifact.find_artifact(
                owner="test-owner",
                repo="test-repo",
                run_id="123456",
                artifact_name="test-artifact",
                token="fake-token",
            )

        assert result is not None
        assert result["id"] == 222
        assert result["size_in_bytes"] == 2048

    def test_empty_artifacts_list(self):
        """Test when no artifacts exist in run."""
        mock_response = MagicMock()
        mock_response.__enter__.return_value.read.return_value = json.dumps(
            {
                "artifacts": [],
            },
        ).encode()

        with patch(
            "download_artifact.github_api_request",
            return_value=json.loads(
                mock_response.__enter__.return_value.read.return_value.decode(),
            ),
        ):
            result = download_artifact.find_artifact(
                owner="test-owner",
                repo="test-repo",
                run_id="123456",
                artifact_name="test-artifact",
                token="fake-token",
            )

        assert result is None


class TestDownloadArtifact:
    """Test the download_artifact function."""

    def test_download_and_extract(self, tmp_path):
        """Test downloading and extracting artifact."""
        # Create a mock ZIP file
        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("file1.txt", "content1")
            zf.writestr("file2.txt", "content2")

        # Mock the API response to return our ZIP
        mock_response = MagicMock()
        mock_response.__enter__.return_value.read.return_value = zip_path.read_bytes()

        output_path = tmp_path / "output"

        with patch("urllib.request.urlopen", return_value=mock_response):
            download_artifact.download_artifact(
                owner="test-owner",
                repo="test-repo",
                artifact_id="123",
                output_path=output_path,
                token="fake-token",
            )

        # Verify extraction
        assert (output_path / "file1.txt").exists()
        assert (output_path / "file2.txt").exists()
        assert (output_path / "file1.txt").read_text() == "content1"
        assert (output_path / "file2.txt").read_text() == "content2"

        # Verify temp ZIP was cleaned up
        temp_zip = output_path.parent / "123.zip"
        assert not temp_zip.exists()

    def test_creates_output_directory(self, tmp_path):
        """Test that output directory is created if it doesn't exist."""
        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("file.txt", "content")

        mock_response = MagicMock()
        mock_response.__enter__.return_value.read.return_value = zip_path.read_bytes()

        output_path = tmp_path / "deep" / "nested" / "output"

        with patch("urllib.request.urlopen", return_value=mock_response):
            download_artifact.download_artifact(
                owner="test-owner",
                repo="test-repo",
                artifact_id="123",
                output_path=output_path,
                token="fake-token",
            )

        assert output_path.exists()
        assert (output_path / "file.txt").exists()


class TestMainFunction:
    """Test the main CLI function."""

    def test_missing_github_token(self):
        """Test that missing GITHUB_TOKEN causes exit."""
        with patch.dict("os.environ", {}, clear=True):
            with patch(
                "sys.argv",
                [
                    "download_artifact.py",
                    "--workflow",
                    "test.yaml",
                    "--commit",
                    "abc123",
                    "--name",
                    "test-artifact",
                    "--path",
                    "/tmp/output",
                ],
            ):
                with pytest.raises(SystemExit) as exc_info:
                    download_artifact.main()
                assert exc_info.value.code == 1

    def test_uses_github_repository_env(self):
        """Test that GITHUB_REPOSITORY is used when owner/repo not provided."""
        mock_env = {
            "GITHUB_TOKEN": "fake-token",
            "GITHUB_REPOSITORY": "test-owner/test-repo",
        }

        with patch.dict("os.environ", mock_env):
            with patch(
                "sys.argv",
                [
                    "download_artifact.py",
                    "--workflow",
                    "test.yaml",
                    "--commit",
                    "abc123",
                    "--name",
                    "test-artifact",
                    "--path",
                    "/tmp/output",
                ],
            ):
                with patch("download_artifact.find_workflow_run", return_value="123"):
                    with patch(
                        "download_artifact.find_artifact",
                        return_value={"id": 456, "size_in_bytes": 1024},
                    ):
                        with patch("download_artifact.download_artifact"):
                            with pytest.raises(SystemExit) as exc_info:
                                download_artifact.main()
                            assert exc_info.value.code == 0

    def test_invalid_github_repository_format(self):
        """Test that invalid GITHUB_REPOSITORY format causes exit."""
        mock_env = {
            "GITHUB_TOKEN": "fake-token",
            "GITHUB_REPOSITORY": "invalid-format",
        }

        with patch.dict("os.environ", mock_env):
            with patch(
                "sys.argv",
                [
                    "download_artifact.py",
                    "--workflow",
                    "test.yaml",
                    "--commit",
                    "abc123",
                    "--name",
                    "test-artifact",
                    "--path",
                    "/tmp/output",
                ],
            ):
                with pytest.raises(SystemExit) as exc_info:
                    download_artifact.main()
                assert exc_info.value.code == 1

    def test_no_workflow_run_found_fail(self):
        """Test failure when no workflow run found with --if-no-artifact-found=fail."""
        mock_env = {
            "GITHUB_TOKEN": "fake-token",
            "GITHUB_REPOSITORY": "test-owner/test-repo",
        }

        with patch.dict("os.environ", mock_env):
            with patch(
                "sys.argv",
                [
                    "download_artifact.py",
                    "--workflow",
                    "test.yaml",
                    "--commit",
                    "abc123",
                    "--name",
                    "test-artifact",
                    "--path",
                    "/tmp/output",
                    "--if-no-artifact-found",
                    "fail",
                ],
            ):
                with patch("download_artifact.find_workflow_run", return_value=None):
                    with pytest.raises(SystemExit) as exc_info:
                        download_artifact.main()
                    assert exc_info.value.code == 1

    def test_no_workflow_run_found_warn(self):
        """Test warning when no workflow run found with --if-no-artifact-found=warn."""
        mock_env = {
            "GITHUB_TOKEN": "fake-token",
            "GITHUB_REPOSITORY": "test-owner/test-repo",
        }

        with patch.dict("os.environ", mock_env):
            with patch(
                "sys.argv",
                [
                    "download_artifact.py",
                    "--workflow",
                    "test.yaml",
                    "--commit",
                    "abc123",
                    "--name",
                    "test-artifact",
                    "--path",
                    "/tmp/output",
                    "--if-no-artifact-found",
                    "warn",
                ],
            ):
                with patch("download_artifact.find_workflow_run", return_value=None):
                    with pytest.raises(SystemExit) as exc_info:
                        download_artifact.main()
                    assert exc_info.value.code == 0

    def test_no_workflow_run_found_ignore(self):
        """Test ignoring when no workflow run found with --if-no-artifact-
        found=ignore."""
        mock_env = {
            "GITHUB_TOKEN": "fake-token",
            "GITHUB_REPOSITORY": "test-owner/test-repo",
        }

        with patch.dict("os.environ", mock_env):
            with patch(
                "sys.argv",
                [
                    "download_artifact.py",
                    "--workflow",
                    "test.yaml",
                    "--commit",
                    "abc123",
                    "--name",
                    "test-artifact",
                    "--path",
                    "/tmp/output",
                    "--if-no-artifact-found",
                    "ignore",
                ],
            ):
                with patch("download_artifact.find_workflow_run", return_value=None):
                    with pytest.raises(SystemExit) as exc_info:
                        download_artifact.main()
                    assert exc_info.value.code == 0

    def test_no_artifact_found_fail(self):
        """Test failure when artifact not found with --if-no-artifact-found=fail."""
        mock_env = {
            "GITHUB_TOKEN": "fake-token",
            "GITHUB_REPOSITORY": "test-owner/test-repo",
        }

        with patch.dict("os.environ", mock_env):
            with patch(
                "sys.argv",
                [
                    "download_artifact.py",
                    "--workflow",
                    "test.yaml",
                    "--commit",
                    "abc123",
                    "--name",
                    "test-artifact",
                    "--path",
                    "/tmp/output",
                    "--if-no-artifact-found",
                    "fail",
                ],
            ):
                with patch("download_artifact.find_workflow_run", return_value="123"):
                    with patch("download_artifact.find_artifact", return_value=None):
                        with pytest.raises(SystemExit) as exc_info:
                            download_artifact.main()
                        assert exc_info.value.code == 1

    def test_no_artifact_found_warn(self):
        """Test warning when artifact not found with --if-no-artifact-found=warn."""
        mock_env = {
            "GITHUB_TOKEN": "fake-token",
            "GITHUB_REPOSITORY": "test-owner/test-repo",
        }

        with patch.dict("os.environ", mock_env):
            with patch(
                "sys.argv",
                [
                    "download_artifact.py",
                    "--workflow",
                    "test.yaml",
                    "--commit",
                    "abc123",
                    "--name",
                    "test-artifact",
                    "--path",
                    "/tmp/output",
                    "--if-no-artifact-found",
                    "warn",
                ],
            ):
                with patch("download_artifact.find_workflow_run", return_value="123"):
                    with patch("download_artifact.find_artifact", return_value=None):
                        with pytest.raises(SystemExit) as exc_info:
                            download_artifact.main()
                        assert exc_info.value.code == 0

    def test_successful_download(self, tmp_path):
        """Test successful artifact download."""
        mock_env = {
            "GITHUB_TOKEN": "fake-token",
            "GITHUB_REPOSITORY": "test-owner/test-repo",
        }

        output_path = tmp_path / "output"

        with patch.dict("os.environ", mock_env):
            with patch(
                "sys.argv",
                [
                    "download_artifact.py",
                    "--workflow",
                    "test.yaml",
                    "--commit",
                    "abc123",
                    "--name",
                    "test-artifact",
                    "--path",
                    str(output_path),
                ],
            ):
                with patch("download_artifact.find_workflow_run", return_value="123"):
                    with patch(
                        "download_artifact.find_artifact",
                        return_value={"id": 456, "size_in_bytes": 1024},
                    ):
                        with patch("download_artifact.download_artifact"):
                            with pytest.raises(SystemExit) as exc_info:
                                download_artifact.main()
                            assert exc_info.value.code == 0

    def test_explicit_owner_and_repo(self):
        """Test that explicit --owner and --repo override GITHUB_REPOSITORY."""
        mock_env = {
            "GITHUB_TOKEN": "fake-token",
            "GITHUB_REPOSITORY": "wrong-owner/wrong-repo",
        }

        with patch.dict("os.environ", mock_env):
            with patch(
                "sys.argv",
                [
                    "download_artifact.py",
                    "--owner",
                    "correct-owner",
                    "--repo",
                    "correct-repo",
                    "--workflow",
                    "test.yaml",
                    "--commit",
                    "abc123",
                    "--name",
                    "test-artifact",
                    "--path",
                    "/tmp/output",
                ],
            ):
                with patch(
                    "download_artifact.find_workflow_run",
                    return_value="123",
                ) as mock_find_run:
                    with patch(
                        "download_artifact.find_artifact",
                        return_value={"id": 456, "size_in_bytes": 1024},
                    ):
                        with patch("download_artifact.download_artifact"):
                            with pytest.raises(SystemExit):
                                download_artifact.main()

                            # Verify correct owner/repo were used (positional args)
                            assert mock_find_run.call_args[0][0] == "correct-owner"
                            assert mock_find_run.call_args[0][1] == "correct-repo"

    def test_custom_workflow_conclusion(self):
        """Test using custom workflow conclusion."""
        mock_env = {
            "GITHUB_TOKEN": "fake-token",
            "GITHUB_REPOSITORY": "test-owner/test-repo",
        }

        with patch.dict("os.environ", mock_env):
            with patch(
                "sys.argv",
                [
                    "download_artifact.py",
                    "--workflow",
                    "test.yaml",
                    "--commit",
                    "abc123",
                    "--name",
                    "test-artifact",
                    "--path",
                    "/tmp/output",
                    "--workflow-conclusion",
                    "cancelled",
                ],
            ):
                with patch(
                    "download_artifact.find_workflow_run",
                    return_value="123",
                ) as mock_find_run:
                    with patch(
                        "download_artifact.find_artifact",
                        return_value={"id": 456, "size_in_bytes": 1024},
                    ):
                        with patch("download_artifact.download_artifact"):
                            with pytest.raises(SystemExit):
                                download_artifact.main()

                            # Verify custom conclusion was used
                            assert mock_find_run.call_args[0][5] == "cancelled"
