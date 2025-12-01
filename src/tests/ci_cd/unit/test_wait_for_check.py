"""Unit tests for wait_for_check.py script."""

import json
from unittest.mock import MagicMock, patch

import pytest
import wait_for_check


class TestGetCheckStatus:
    """Test the get_check_status function."""

    def test_check_found_success(self):
        """Test when check is found with success status."""
        mock_data = {
            "check_runs": [
                {
                    "name": "verify",
                    "status": "completed",
                    "conclusion": "success",
                },
            ],
        }

        with patch("wait_for_check.github_api_request", return_value=mock_data):
            result = wait_for_check.get_check_status(
                owner="test-owner",
                repo="test-repo",
                ref="abc123",
                check_name="verify",
                token="fake-token",
            )

        assert result == {"status": "completed", "conclusion": "success"}

    def test_check_found_failure(self):
        """Test when check is found with failure status."""
        mock_data = {
            "check_runs": [
                {
                    "name": "verify",
                    "status": "completed",
                    "conclusion": "failure",
                },
            ],
        }

        with patch("wait_for_check.github_api_request", return_value=mock_data):
            result = wait_for_check.get_check_status(
                owner="test-owner",
                repo="test-repo",
                ref="abc123",
                check_name="verify",
                token="fake-token",
            )

        assert result == {"status": "completed", "conclusion": "failure"}

    def test_check_in_progress(self):
        """Test when check is in progress."""
        mock_response = MagicMock()
        mock_response.__enter__.return_value.read.return_value = json.dumps(
            {
                "check_runs": [
                    {
                        "name": "verify",
                        "status": "in_progress",
                        "conclusion": None,
                    },
                ],
            },
        ).encode()

        with patch(
            "wait_for_check.github_api_request",
            return_value=json.loads(
                mock_response.__enter__.return_value.read.return_value.decode(),
            ),
        ):
            result = wait_for_check.get_check_status(
                owner="test-owner",
                repo="test-repo",
                ref="abc123",
                check_name="verify",
                token="fake-token",
            )

        assert result == {"status": "in_progress", "conclusion": None}

    def test_check_not_found(self):
        """Test when check is not found in response."""
        mock_response = MagicMock()
        mock_response.__enter__.return_value.read.return_value = json.dumps(
            {
                "check_runs": [
                    {
                        "name": "different-check",
                        "status": "completed",
                        "conclusion": "success",
                    },
                ],
            },
        ).encode()

        with patch(
            "wait_for_check.github_api_request",
            return_value=json.loads(
                mock_response.__enter__.return_value.read.return_value.decode(),
            ),
        ):
            result = wait_for_check.get_check_status(
                owner="test-owner",
                repo="test-repo",
                ref="abc123",
                check_name="verify",
                token="fake-token",
            )

        assert result == {"status": "not_found", "conclusion": None}

    def test_multiple_checks_returns_correct_one(self):
        """Test when multiple checks exist, returns the correct one."""
        mock_response = MagicMock()
        mock_response.__enter__.return_value.read.return_value = json.dumps(
            {
                "check_runs": [
                    {
                        "name": "test",
                        "status": "completed",
                        "conclusion": "success",
                    },
                    {
                        "name": "verify",
                        "status": "completed",
                        "conclusion": "failure",
                    },
                    {
                        "name": "build",
                        "status": "in_progress",
                        "conclusion": None,
                    },
                ],
            },
        ).encode()

        with patch(
            "wait_for_check.github_api_request",
            return_value=json.loads(
                mock_response.__enter__.return_value.read.return_value.decode(),
            ),
        ):
            result = wait_for_check.get_check_status(
                owner="test-owner",
                repo="test-repo",
                ref="abc123",
                check_name="verify",
                token="fake-token",
            )

        assert result == {"status": "completed", "conclusion": "failure"}


class TestWaitForCheck:
    """Test the wait_for_check function."""

    def test_immediate_success(self):
        """Test when check succeeds immediately."""
        mock_status = {"status": "completed", "conclusion": "success"}

        with patch("wait_for_check.get_check_status", return_value=mock_status):
            result = wait_for_check.wait_for_check(
                owner="test-owner",
                repo="test-repo",
                ref="abc123",
                check_name="verify",
                token="fake-token",
                timeout=60,
                poll_interval=1,
            )

        assert result is True

    def test_immediate_failure(self):
        """Test when check fails immediately."""
        mock_status = {"status": "completed", "conclusion": "failure"}

        with patch("wait_for_check.get_check_status", return_value=mock_status):
            result = wait_for_check.wait_for_check(
                owner="test-owner",
                repo="test-repo",
                ref="abc123",
                check_name="verify",
                token="fake-token",
                timeout=60,
                poll_interval=1,
            )

        assert result is False

    def test_eventual_success_after_in_progress(self):
        """Test when check eventually succeeds after being in progress."""
        mock_statuses = [
            {"status": "in_progress", "conclusion": None},
            {"status": "in_progress", "conclusion": None},
            {"status": "completed", "conclusion": "success"},
        ]

        with patch("wait_for_check.get_check_status", side_effect=mock_statuses):
            with patch("time.sleep"):  # Mock sleep to speed up test
                result = wait_for_check.wait_for_check(
                    owner="test-owner",
                    repo="test-repo",
                    ref="abc123",
                    check_name="verify",
                    token="fake-token",
                    timeout=60,
                    poll_interval=1,
                )

        assert result is True

    def test_eventual_failure_after_in_progress(self):
        """Test when check eventually fails after being in progress."""
        mock_statuses = [
            {"status": "in_progress", "conclusion": None},
            {"status": "in_progress", "conclusion": None},
            {"status": "completed", "conclusion": "failure"},
        ]

        with patch("wait_for_check.get_check_status", side_effect=mock_statuses):
            with patch("time.sleep"):  # Mock sleep to speed up test
                result = wait_for_check.wait_for_check(
                    owner="test-owner",
                    repo="test-repo",
                    ref="abc123",
                    check_name="verify",
                    token="fake-token",
                    timeout=60,
                    poll_interval=1,
                )

        assert result is False

    def test_timeout(self):
        """Test when check times out waiting for completion."""
        mock_status = {"status": "in_progress", "conclusion": None}

        with patch("wait_for_check.get_check_status", return_value=mock_status):
            with patch("time.sleep"):  # Mock sleep to speed up test
                with patch("time.time", side_effect=[0, 0, 61]):  # Simulate timeout
                    result = wait_for_check.wait_for_check(
                        owner="test-owner",
                        repo="test-repo",
                        ref="abc123",
                        check_name="verify",
                        token="fake-token",
                        timeout=60,
                        poll_interval=1,
                    )

        assert result is False

    def test_not_found_then_success(self):
        """Test when check is not found initially but then succeeds."""
        mock_statuses = [
            {"status": "not_found", "conclusion": None},
            {"status": "not_found", "conclusion": None},
            {"status": "completed", "conclusion": "success"},
        ]

        with patch("wait_for_check.get_check_status", side_effect=mock_statuses):
            with patch("time.sleep"):  # Mock sleep to speed up test
                result = wait_for_check.wait_for_check(
                    owner="test-owner",
                    repo="test-repo",
                    ref="abc123",
                    check_name="verify",
                    token="fake-token",
                    timeout=60,
                    poll_interval=1,
                )

        assert result is True

    def test_handles_transient_errors(self):
        """Test that transient errors don't stop polling."""
        mock_statuses = [
            Exception("Network error"),
            {"status": "in_progress", "conclusion": None},
            {"status": "completed", "conclusion": "success"},
        ]

        with patch("wait_for_check.get_check_status", side_effect=mock_statuses):
            with patch("time.sleep"):  # Mock sleep to speed up test
                result = wait_for_check.wait_for_check(
                    owner="test-owner",
                    repo="test-repo",
                    ref="abc123",
                    check_name="verify",
                    token="fake-token",
                    timeout=60,
                    poll_interval=1,
                )

        assert result is True

    @pytest.mark.parametrize(
        "conclusion",
        [
            "failure",
            "cancelled",
            "timed_out",
            "action_required",
            "neutral",
            "skipped",
        ],
    )
    def test_non_success_conclusions_return_false(self, conclusion):
        """Test that any non-success conclusion returns False."""
        mock_status = {"status": "completed", "conclusion": conclusion}

        with patch("wait_for_check.get_check_status", return_value=mock_status):
            result = wait_for_check.wait_for_check(
                owner="test-owner",
                repo="test-repo",
                ref="abc123",
                check_name="verify",
                token="fake-token",
                timeout=60,
                poll_interval=1,
            )

        assert result is False


class TestMainFunction:
    """Test the main CLI function."""

    def test_missing_github_token(self):
        """Test that missing GITHUB_TOKEN causes exit."""
        with patch.dict("os.environ", {}, clear=True):
            with patch(
                "sys.argv",
                ["wait_for_check.py", "--ref", "abc123", "--check-name", "verify"],
            ):
                with pytest.raises(SystemExit) as exc_info:
                    wait_for_check.main()
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
                ["wait_for_check.py", "--ref", "abc123", "--check-name", "verify"],
            ):
                with patch("wait_for_check.wait_for_check", return_value=True):
                    with pytest.raises(SystemExit) as exc_info:
                        wait_for_check.main()
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
                ["wait_for_check.py", "--ref", "abc123", "--check-name", "verify"],
            ):
                with pytest.raises(SystemExit) as exc_info:
                    wait_for_check.main()
                assert exc_info.value.code == 1

    def test_success_exit_code(self):
        """Test that successful check returns exit code 0."""
        mock_env = {
            "GITHUB_TOKEN": "fake-token",
            "GITHUB_REPOSITORY": "test-owner/test-repo",
        }

        with patch.dict("os.environ", mock_env):
            with patch(
                "sys.argv",
                ["wait_for_check.py", "--ref", "abc123", "--check-name", "verify"],
            ):
                with patch("wait_for_check.wait_for_check", return_value=True):
                    with pytest.raises(SystemExit) as exc_info:
                        wait_for_check.main()
                    assert exc_info.value.code == 0

    def test_failure_exit_code(self):
        """Test that failed check returns exit code 1."""
        mock_env = {
            "GITHUB_TOKEN": "fake-token",
            "GITHUB_REPOSITORY": "test-owner/test-repo",
        }

        with patch.dict("os.environ", mock_env):
            with patch(
                "sys.argv",
                ["wait_for_check.py", "--ref", "abc123", "--check-name", "verify"],
            ):
                with patch("wait_for_check.wait_for_check", return_value=False):
                    with pytest.raises(SystemExit) as exc_info:
                        wait_for_check.main()
                    assert exc_info.value.code == 1

    def test_custom_timeout_and_poll_interval(self):
        """Test that custom timeout and poll interval are passed through."""
        mock_env = {
            "GITHUB_TOKEN": "fake-token",
            "GITHUB_REPOSITORY": "test-owner/test-repo",
        }

        with patch.dict("os.environ", mock_env):
            with patch(
                "sys.argv",
                [
                    "wait_for_check.py",
                    "--ref",
                    "abc123",
                    "--check-name",
                    "verify",
                    "--timeout",
                    "300",
                    "--poll-interval",
                    "5",
                ],
            ):
                with patch(
                    "wait_for_check.wait_for_check",
                    return_value=True,
                ) as mock_wait:
                    with pytest.raises(SystemExit):
                        wait_for_check.main()

                    # Verify the function was called with correct arguments
                    # The function is called positionally, so check call_args
                    call_args, call_kwargs = mock_wait.call_args
                    assert call_args[5] == 300  # timeout is 6th positional arg
                    assert call_args[6] == 5  # poll_interval is 7th positional arg

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
                    "wait_for_check.py",
                    "--owner",
                    "correct-owner",
                    "--repo",
                    "correct-repo",
                    "--ref",
                    "abc123",
                    "--check-name",
                    "verify",
                ],
            ):
                with patch(
                    "wait_for_check.wait_for_check",
                    return_value=True,
                ) as mock_wait:
                    with pytest.raises(SystemExit):
                        wait_for_check.main()

                    # Verify the function was called with explicit owner/repo
                    assert mock_wait.call_args[0][0] == "correct-owner"
                    assert mock_wait.call_args[0][1] == "correct-repo"
