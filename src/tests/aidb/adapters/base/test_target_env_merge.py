"""Tests for target environment variable merging in base adapter.

These tests verify that user-provided environment variables (via the `env`
parameter in session_start) are properly merged into the subprocess environment
for all language adapters.

This addresses the issue where custom PYTHONPATH, JAVA_HOME, NODE_PATH, etc.
were not being applied to debug subprocesses.
"""

from unittest.mock import MagicMock

import pytest


class TestTargetEnvMerge:
    """Tests for _merge_target_env functionality in base adapter."""

    @pytest.fixture
    def mock_base_adapter(self, mock_ctx: MagicMock) -> MagicMock:
        """Create a mock adapter with _merge_target_env behavior.

        This imports the real base adapter to test actual merge behavior.
        """
        from aidb.adapters.base.adapter import DebugAdapter

        # Create a concrete subclass for testing (can't instantiate ABC directly)
        class TestAdapter(DebugAdapter):
            def _add_adapter_specific_vars(self, env):
                return env

            def _get_process_name_pattern(self):
                return "test"

            async def _build_launch_command(
                self, target, adapter_host, adapter_port, args=None
            ):
                return ["test"]

            def _create_target_resolver(self):
                return None

            def _create_source_path_resolver(self):
                return None

        # Mock the session and required components
        mock_session = MagicMock()
        mock_session.id = "test-session"
        mock_session.resource = MagicMock()

        return TestAdapter(session=mock_session, ctx=mock_ctx)

    def test_merge_target_env_with_empty_target_env(
        self, mock_base_adapter: MagicMock
    ) -> None:
        """Test that empty _target_env doesn't modify base env."""
        base_env = {"PATH": "/usr/bin", "HOME": "/home/user"}
        mock_base_adapter._target_env = {}

        result = mock_base_adapter._merge_target_env(base_env.copy())

        assert result == base_env

    def test_merge_target_env_adds_user_vars(
        self, mock_base_adapter: MagicMock
    ) -> None:
        """Test that user env vars are added to base env."""
        base_env = {"PATH": "/usr/bin"}
        mock_base_adapter._target_env = {"CUSTOM_VAR": "custom_value"}

        result = mock_base_adapter._merge_target_env(base_env.copy())

        assert result["PATH"] == "/usr/bin"
        assert result["CUSTOM_VAR"] == "custom_value"

    def test_merge_target_env_user_vars_override_base(
        self, mock_base_adapter: MagicMock
    ) -> None:
        """Test that user env vars override existing base vars."""
        base_env = {"PATH": "/usr/bin", "DEBUG": "false"}
        mock_base_adapter._target_env = {"DEBUG": "true"}

        result = mock_base_adapter._merge_target_env(base_env.copy())

        assert result["DEBUG"] == "true"

    def test_merge_target_env_logs_merge_count(
        self, mock_base_adapter: MagicMock, mock_ctx: MagicMock
    ) -> None:
        """Test that merge logs the number of variables merged."""
        base_env = {"PATH": "/usr/bin"}
        mock_base_adapter._target_env = {"VAR1": "val1", "VAR2": "val2"}

        mock_base_adapter._merge_target_env(base_env.copy())

        mock_ctx.debug.assert_called()
        # Verify the log message mentions the count
        call_args = str(mock_ctx.debug.call_args)
        assert "2" in call_args


class TestPythonPathMerge:
    """Tests for PYTHONPATH handling in Python adapter.

    Verifies that user-provided PYTHONPATH is preserved and adapter path is prepended
    correctly.
    """

    @pytest.fixture
    def python_adapter(self, mock_ctx: MagicMock) -> MagicMock:
        """Create a Python adapter for testing."""
        from aidb.adapters.lang.python.python import PythonAdapter

        mock_session = MagicMock()
        mock_session.id = "test-session"
        mock_session.resource = MagicMock()

        return PythonAdapter(session=mock_session, ctx=mock_ctx)

    def test_user_pythonpath_preserved_after_merge(
        self, python_adapter: MagicMock
    ) -> None:
        """Test that user's PYTHONPATH is in final environment."""
        user_pythonpath = "/custom/src:/another/path"
        python_adapter._target_env = {"PYTHONPATH": user_pythonpath}

        # Simulate the environment preparation pipeline
        env = python_adapter._load_base_environment()
        env = python_adapter._merge_target_env(env)

        assert "PYTHONPATH" in env
        assert user_pythonpath in env["PYTHONPATH"]

    def test_adapter_path_prepended_to_user_pythonpath(
        self, python_adapter: MagicMock
    ) -> None:
        """Test that adapter path is prepended to user's PYTHONPATH."""
        user_pythonpath = "/custom/src"
        python_adapter._target_env = {"PYTHONPATH": user_pythonpath}

        # Get adapter path
        adapter_path = python_adapter._get_adapter_pythonpath()
        if not adapter_path:
            pytest.skip("Adapter path not available (adapter not installed)")

        # Run the full environment preparation
        env = python_adapter._prepare_environment()

        # Verify order: adapter_path comes first, then user path
        pythonpath = env.get("PYTHONPATH", "")
        assert pythonpath.startswith(adapter_path)
        assert user_pythonpath in pythonpath


class TestJavaEnvMerge:
    """Tests for environment handling in Java adapter."""

    @pytest.fixture
    def java_adapter(self, mock_ctx: MagicMock) -> MagicMock:
        """Create a Java adapter for testing."""
        from aidb.adapters.lang.java.java import JavaAdapter

        mock_session = MagicMock()
        mock_session.id = "test-session"
        mock_session.resource = MagicMock()

        return JavaAdapter(session=mock_session, ctx=mock_ctx)

    def test_user_java_home_preserved(self, java_adapter: MagicMock) -> None:
        """Test that user's JAVA_HOME is preserved in environment."""
        custom_java_home = "/custom/jdk"
        java_adapter._target_env = {"JAVA_HOME": custom_java_home}

        env = java_adapter._load_base_environment()
        env = java_adapter._merge_target_env(env)

        assert env["JAVA_HOME"] == custom_java_home

    def test_user_classpath_preserved(self, java_adapter: MagicMock) -> None:
        """Test that user's CLASSPATH is preserved in environment."""
        custom_classpath = "/custom/lib/classes.jar"
        java_adapter._target_env = {"CLASSPATH": custom_classpath}

        env = java_adapter._load_base_environment()
        env = java_adapter._merge_target_env(env)

        assert env["CLASSPATH"] == custom_classpath


class TestJavaScriptEnvMerge:
    """Tests for environment handling in JavaScript adapter."""

    @pytest.fixture
    def javascript_adapter(self, mock_ctx: MagicMock) -> MagicMock:
        """Create a JavaScript adapter for testing."""
        from aidb.adapters.lang.javascript.javascript import JavaScriptAdapter

        mock_session = MagicMock()
        mock_session.id = "test-session"
        mock_session.resource = MagicMock()

        return JavaScriptAdapter(session=mock_session, ctx=mock_ctx)

    def test_user_node_path_preserved(self, javascript_adapter: MagicMock) -> None:
        """Test that user's NODE_PATH is preserved in environment."""
        custom_node_path = "/custom/node_modules"
        javascript_adapter._target_env = {"NODE_PATH": custom_node_path}

        env = javascript_adapter._load_base_environment()
        env = javascript_adapter._merge_target_env(env)

        assert env["NODE_PATH"] == custom_node_path

    def test_user_node_env_preserved(self, javascript_adapter: MagicMock) -> None:
        """Test that user's NODE_ENV is preserved in environment."""
        javascript_adapter._target_env = {"NODE_ENV": "production"}

        env = javascript_adapter._load_base_environment()
        env = javascript_adapter._merge_target_env(env)

        assert env["NODE_ENV"] == "production"


class TestPrepareEnvironmentPipeline:
    """Tests for the full _prepare_environment pipeline.

    Verifies that _merge_target_env is called in the correct order within the pipeline.
    """

    @pytest.fixture
    def mock_adapter_with_spies(self, mock_ctx: MagicMock) -> MagicMock:
        """Create an adapter with spied methods to verify call order."""
        from aidb.adapters.base.adapter import DebugAdapter

        class SpyAdapter(DebugAdapter):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.call_order = []

            def _load_base_environment(self):
                self.call_order.append("load_base")
                return {"BASE": "env"}

            def _merge_target_env(self, env):
                self.call_order.append("merge_target")
                return super()._merge_target_env(env)

            def _add_trace_configuration(self, env):
                self.call_order.append("add_trace")
                return env

            def _add_adapter_specific_vars(self, env):
                self.call_order.append("add_specific")
                return env

            def _get_process_name_pattern(self):
                return "test"

            async def _build_launch_command(
                self, target, adapter_host, adapter_port, args=None
            ):
                return ["test"]

            def _create_target_resolver(self):
                return None

            def _create_source_path_resolver(self):
                return None

        mock_session = MagicMock()
        mock_session.id = "test-session"
        mock_session.resource = MagicMock()

        return SpyAdapter(session=mock_session, ctx=mock_ctx)

    def test_pipeline_order(self, mock_adapter_with_spies: MagicMock) -> None:
        """Test that environment preparation follows correct order."""
        mock_adapter_with_spies._prepare_environment()

        expected_order = ["load_base", "merge_target", "add_trace", "add_specific"]
        assert mock_adapter_with_spies.call_order == expected_order

    def test_user_env_available_to_adapter_specific(
        self, mock_adapter_with_spies: MagicMock
    ) -> None:
        """Test that user env is available when adapter-specific runs."""
        mock_adapter_with_spies._target_env = {"USER_VAR": "user_value"}

        # Override adapter-specific to capture the env it receives
        captured_env = {}

        original_add_specific = mock_adapter_with_spies._add_adapter_specific_vars

        def capturing_add_specific(env):
            captured_env.update(env)
            return original_add_specific(env)

        mock_adapter_with_spies._add_adapter_specific_vars = capturing_add_specific

        mock_adapter_with_spies._prepare_environment()

        # Verify user var was available to adapter-specific
        assert captured_env.get("USER_VAR") == "user_value"
