"""Unit tests for AdapterBuilder.download_file retry logic."""

import urllib.error
from pathlib import Path
from unittest.mock import patch

import pytest
from adapters.base import AdapterBuilder, BuildError


class ConcreteBuilder(AdapterBuilder):
    """Concrete implementation for testing base class methods."""

    @property
    def adapter_name(self) -> str:
        return "test"

    def get_adapter_config(self) -> dict:
        return {}

    def clone_repository(self) -> Path:
        return Path()

    def build(self) -> Path:
        return Path()

    def package(self) -> Path:
        return Path()


@pytest.fixture
def builder():
    """Create a ConcreteBuilder instance."""
    versions = {"adapters": {"test": {"version": "1.0.0"}}}
    return ConcreteBuilder(versions, "linux", "x64")


class TestDownloadFileSuccess:
    """Test successful download scenarios."""

    def test_succeeds_on_first_attempt(self, builder, tmp_path):
        """Verify download succeeds without retries when server responds."""
        dest = tmp_path / "artifact.tar.gz"
        dest.write_bytes(b"fake content")

        with patch("urllib.request.urlretrieve") as mock_retrieve:
            mock_retrieve.side_effect = lambda url, path: dest.write_bytes(
                b"downloaded",
            )

            result = builder.download_file(
                url="https://example.com/artifact.tar.gz",
                dest=dest,
                description="test artifact",
            )

            assert result == dest
            assert mock_retrieve.call_count == 1

    def test_succeeds_after_transient_failure(self, builder, tmp_path):
        """Verify download retries and succeeds after a transient 502."""
        dest = tmp_path / "artifact.tar.gz"

        call_count = 0

        def side_effect(url, path):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise urllib.error.HTTPError(
                    url,
                    502,
                    "Bad Gateway",
                    {},
                    None,
                )
            Path(path).write_bytes(b"downloaded")

        with (
            patch("urllib.request.urlretrieve", side_effect=side_effect),
            patch("time.sleep") as mock_sleep,
        ):
            result = builder.download_file(
                url="https://example.com/artifact.tar.gz",
                dest=dest,
                description="test artifact",
                backoff_base=1.0,
            )

            assert result == dest
            assert call_count == 3
            assert mock_sleep.call_count == 2
            # Exponential backoff: 1*2^0=1, 1*2^1=2
            mock_sleep.assert_any_call(1.0)
            mock_sleep.assert_any_call(2.0)


class TestDownloadFileFailure:
    """Test download failure scenarios."""

    def test_raises_build_error_after_all_retries_exhausted(
        self,
        builder,
        tmp_path,
    ):
        """Verify BuildError raised after max retries with descriptive message."""
        dest = tmp_path / "artifact.tar.gz"

        with (
            patch(
                "urllib.request.urlretrieve",
                side_effect=urllib.error.HTTPError(
                    "https://example.com/a.tar.gz",
                    502,
                    "Bad Gateway",
                    {},
                    None,
                ),
            ),
            patch("time.sleep"),
        ):
            with pytest.raises(BuildError, match="after 4 attempts"):
                builder.download_file(
                    url="https://example.com/a.tar.gz",
                    dest=dest,
                    description="test artifact",
                    backoff_base=1.0,
                )

    def test_retries_on_connection_reset(self, builder, tmp_path):
        """Verify retries on OSError (e.g., connection reset)."""
        dest = tmp_path / "artifact.tar.gz"

        call_count = 0

        def side_effect(url, path):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                msg = "Connection reset by peer"
                raise OSError(msg)
            Path(path).write_bytes(b"downloaded")

        with (
            patch("urllib.request.urlretrieve", side_effect=side_effect),
            patch("time.sleep"),
        ):
            result = builder.download_file(
                url="https://example.com/artifact.tar.gz",
                dest=dest,
                description="test artifact",
                backoff_base=1.0,
            )

            assert result == dest
            assert call_count == 2

    def test_retries_on_url_error(self, builder, tmp_path):
        """Verify retries on URLError (e.g., DNS failure)."""
        dest = tmp_path / "artifact.tar.gz"

        call_count = 0

        def side_effect(url, path):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                msg = "Name resolution failed"
                raise urllib.error.URLError(msg)
            Path(path).write_bytes(b"downloaded")

        with (
            patch("urllib.request.urlretrieve", side_effect=side_effect),
            patch("time.sleep"),
        ):
            result = builder.download_file(
                url="https://example.com/artifact.tar.gz",
                dest=dest,
                description="test artifact",
                backoff_base=1.0,
            )

            assert result == dest
            assert call_count == 2


class TestDownloadFileBackoff:
    """Test exponential backoff behavior."""

    def test_exponential_backoff_delays(self, builder, tmp_path):
        """Verify backoff doubles each attempt with correct base."""
        dest = tmp_path / "artifact.tar.gz"

        with (
            patch(
                "urllib.request.urlretrieve",
                side_effect=urllib.error.URLError("fail"),
            ),
            patch("time.sleep") as mock_sleep,
        ):
            with pytest.raises(BuildError):
                builder.download_file(
                    url="https://example.com/artifact.tar.gz",
                    dest=dest,
                    description="test artifact",
                    max_retries=3,
                    backoff_base=5.0,
                )

            # 3 retries = 3 sleeps: 5*2^0=5, 5*2^1=10, 5*2^2=20
            assert mock_sleep.call_count == 3
            mock_sleep.assert_any_call(5.0)
            mock_sleep.assert_any_call(10.0)
            mock_sleep.assert_any_call(20.0)

    def test_no_retry_when_max_retries_zero(self, builder, tmp_path):
        """Verify no retries when max_retries=0."""
        dest = tmp_path / "artifact.tar.gz"

        with (
            patch(
                "urllib.request.urlretrieve",
                side_effect=urllib.error.URLError("fail"),
            ),
            patch("time.sleep") as mock_sleep,
        ):
            with pytest.raises(BuildError, match="after 1 attempts"):
                builder.download_file(
                    url="https://example.com/artifact.tar.gz",
                    dest=dest,
                    description="test artifact",
                    max_retries=0,
                )

            mock_sleep.assert_not_called()
