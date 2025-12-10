"""Unit tests for Python debug adapter.

Tests Python-specific adapter functionality.

Note: Module target normalization tests have been moved to test_target_resolver.py
as part of the TargetResolver abstraction.
"""

from unittest.mock import MagicMock

import pytest


class TestPythonAdapterConfig:
    """Tests for Python adapter configuration."""

    def test_default_config(self, mock_ctx: MagicMock) -> None:
        """Test that default config is created correctly."""
        from aidb.adapters.lang.python.config import PythonAdapterConfig

        config = PythonAdapterConfig()

        assert config.language == "python"
        assert config.justMyCode is True
        assert config.subProcess is False
        assert config.showReturnValue is True
        assert config.redirectOutput is True

    def test_config_with_overrides(self, mock_ctx: MagicMock) -> None:
        """Test config with custom values."""
        from aidb.adapters.lang.python.config import PythonAdapterConfig

        config = PythonAdapterConfig(
            justMyCode=False,
            subProcess=True,
            showReturnValue=True,
            django=True,
        )

        assert config.justMyCode is False
        assert config.subProcess is True
        assert config.showReturnValue is True
        assert config.django is True


class TestPythonAdapterHooks:
    """Tests for Python adapter lifecycle hooks."""

    def test_extract_launch_context_hook(self, mock_ctx: MagicMock) -> None:
        """Test that _extract_launch_context extracts env and cwd."""
        from aidb.adapters.base.hooks import HookContext
        from aidb.adapters.lang.python.python import PythonAdapter

        adapter = MagicMock(spec=PythonAdapter)
        adapter.ctx = mock_ctx
        adapter._target_env = {}
        adapter._target_cwd = None

        session = MagicMock()

        # Bind the real method
        adapter._extract_launch_context = (
            lambda context: PythonAdapter._extract_launch_context(adapter, context)
        )

        # Create hook context with env and cwd
        context = HookContext(
            adapter=adapter,
            session=session,
            data={
                "target": "pytest",
                "env": {"FOO": "bar"},
                "cwd": "/some/path",
            },
        )

        adapter._extract_launch_context(context)

        assert adapter._target_env == {"FOO": "bar"}
        assert adapter._target_cwd == "/some/path"
