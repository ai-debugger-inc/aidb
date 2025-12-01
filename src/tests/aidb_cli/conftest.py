"""Fixtures for CLI test suite."""

import pytest


@pytest.fixture(autouse=True, scope="session")
def suppress_cli_test_session_logs():
    """Suppress session-specific log directories for programmatic CLI test runs.

    CLI integration tests programmatically invoke other test suites (logging, mcp) using
    CliRunner. These meta-tests should not create timestamped log directories in pytest-
    logs/, as this fills up the 10-slot log retention buffer.

    This fixture patches CliRunner.__init__ to automatically inject
    AIDB_SKIP_SESSION_LOGS=1 into the isolated environment that CliRunner creates. This
    ensures programmatic test invocations use the base pytest-logs/ directory instead of
    creating session-specific subdirectories like pytest-logs/logging-20251029-021636/.
    """
    from click.testing import CliRunner

    original_init = CliRunner.__init__

    def patched_init(
        self,
        charset: str = "utf-8",
        env=None,
        echo_stdin: bool = False,
        catch_exceptions: bool = True,
    ):
        """Patched CliRunner.__init__ that injects AIDB_SKIP_SESSION_LOGS."""
        env = env or {}
        env = {"AIDB_SKIP_SESSION_LOGS": "1", **env}
        original_init(
            self,
            charset=charset,
            env=env,
            echo_stdin=echo_stdin,
            catch_exceptions=catch_exceptions,
        )

    CliRunner.__init__ = patched_init  # type: ignore[method-assign]
    yield
    CliRunner.__init__ = original_init  # type: ignore[method-assign]
