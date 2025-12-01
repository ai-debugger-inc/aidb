"""Unit tests for SessionBuilder and SessionValidator.

Tests the builder pattern for session creation, parameter validation, mode detection,
and launch configuration handling.
"""

from unittest.mock import MagicMock, patch

import pytest

from aidb.api.session_builder import SessionBuilder, SessionValidator
from aidb.common.errors import AidbError, VSCodeVariableError
from aidb.models import StartRequestType


class TestSessionValidatorModeCompatibility:
    """Tests for SessionValidator.validate_mode_compatibility."""

    def test_validate_mode_launch_with_pid_raises(self):
        """Launch mode with pid parameter raises AidbError."""
        with pytest.raises(AidbError, match="Cannot use attach parameters"):
            SessionValidator.validate_mode_compatibility(
                mode=StartRequestType.LAUNCH,
                target="/path/to/script.py",
                pid=1234,
                host=None,
                port=None,
                args=None,
            )

    def test_validate_mode_launch_with_host_raises(self):
        """Launch mode with host parameter raises AidbError."""
        with pytest.raises(AidbError, match="Cannot use attach parameters"):
            SessionValidator.validate_mode_compatibility(
                mode=StartRequestType.LAUNCH,
                target="/path/to/script.py",
                pid=None,
                host="localhost",
                port=None,
                args=None,
            )

    def test_validate_mode_launch_with_port_raises(self):
        """Launch mode with port parameter raises AidbError."""
        with pytest.raises(AidbError, match="Cannot use attach parameters"):
            SessionValidator.validate_mode_compatibility(
                mode=StartRequestType.LAUNCH,
                target="/path/to/script.py",
                pid=None,
                host=None,
                port=5678,
                args=None,
            )

    def test_validate_mode_launch_without_target_raises(self):
        """Launch mode without target raises AidbError."""
        with pytest.raises(AidbError, match="Target file is required"):
            SessionValidator.validate_mode_compatibility(
                mode=StartRequestType.LAUNCH,
                target=None,
                pid=None,
                host=None,
                port=None,
                args=None,
            )

    def test_validate_mode_attach_with_args_raises(self):
        """Attach mode with args parameter raises AidbError."""
        with pytest.raises(AidbError, match="Cannot use 'args' parameter"):
            SessionValidator.validate_mode_compatibility(
                mode=StartRequestType.ATTACH,
                target=None,
                pid=1234,
                host=None,
                port=None,
                args=["--verbose"],
            )

    def test_validate_mode_attach_without_pid_or_host_port_raises(self):
        """Attach mode without pid or host+port raises AidbError."""
        with pytest.raises(AidbError, match="Must provide either 'pid'"):
            SessionValidator.validate_mode_compatibility(
                mode=StartRequestType.ATTACH,
                target=None,
                pid=None,
                host=None,
                port=None,
                args=None,
            )

    def test_validate_mode_attach_with_only_host_raises(self):
        """Attach mode with only host (no port) raises AidbError."""
        with pytest.raises(AidbError, match="Must provide either 'pid'"):
            SessionValidator.validate_mode_compatibility(
                mode=StartRequestType.ATTACH,
                target=None,
                pid=None,
                host="localhost",
                port=None,
                args=None,
            )

    def test_validate_mode_launch_valid_params(self):
        """Launch mode with valid parameters passes validation."""
        SessionValidator.validate_mode_compatibility(
            mode=StartRequestType.LAUNCH,
            target="/path/to/script.py",
            pid=None,
            host=None,
            port=None,
            args=["--verbose"],
        )

    def test_validate_mode_attach_with_pid_valid(self):
        """Attach mode with pid passes validation."""
        SessionValidator.validate_mode_compatibility(
            mode=StartRequestType.ATTACH,
            target=None,
            pid=1234,
            host=None,
            port=None,
            args=None,
        )

    def test_validate_mode_attach_with_host_port_valid(self):
        """Attach mode with host and port passes validation."""
        SessionValidator.validate_mode_compatibility(
            mode=StartRequestType.ATTACH,
            target=None,
            pid=None,
            host="localhost",
            port=5678,
            args=None,
        )


class TestSessionValidatorLaunchConfig:
    """Tests for SessionValidator.validate_launch_config."""

    def test_validate_launch_config_missing_name_raises(self, sample_launch_config):
        """Launch config without name raises AidbError."""
        sample_launch_config.name = None
        with pytest.raises(AidbError, match="must have a name"):
            SessionValidator.validate_launch_config(sample_launch_config)

    def test_validate_launch_config_empty_name_raises(self, sample_launch_config):
        """Launch config with empty name raises AidbError."""
        sample_launch_config.name = ""
        with pytest.raises(AidbError, match="must have a name"):
            SessionValidator.validate_launch_config(sample_launch_config)

    def test_validate_launch_config_invalid_request_type_raises(
        self,
        sample_launch_config,
    ):
        """Launch config with invalid request type raises AidbError."""
        sample_launch_config.request = "invalid"
        with pytest.raises(AidbError, match="Invalid launch configuration request"):
            SessionValidator.validate_launch_config(sample_launch_config)

    def test_validate_launch_config_valid_launch(self, sample_launch_config):
        """Valid launch config passes validation."""
        SessionValidator.validate_launch_config(sample_launch_config)

    def test_validate_launch_config_valid_attach(self, sample_launch_config_attach):
        """Valid attach config passes validation."""
        SessionValidator.validate_launch_config(sample_launch_config_attach)


class TestSessionValidatorDetermineMode:
    """Tests for SessionValidator.determine_mode."""

    def test_determine_mode_explicit_returns_explicit(self):
        """Explicit mode takes precedence over inferred mode."""
        mode = SessionValidator.determine_mode(
            target="/path/to/script.py",
            pid=1234,
            host="localhost",
            port=5678,
            start_request_type=StartRequestType.ATTACH,
        )
        assert mode == StartRequestType.ATTACH

    def test_determine_mode_with_target_returns_launch(self):
        """Target parameter implies launch mode."""
        mode = SessionValidator.determine_mode(
            target="/path/to/script.py",
            pid=None,
            host=None,
            port=None,
            start_request_type=None,
        )
        assert mode == StartRequestType.LAUNCH

    def test_determine_mode_with_pid_returns_attach(self):
        """Pid parameter implies attach mode."""
        mode = SessionValidator.determine_mode(
            target=None,
            pid=1234,
            host=None,
            port=None,
            start_request_type=None,
        )
        assert mode == StartRequestType.ATTACH

    def test_determine_mode_with_host_port_returns_attach(self):
        """Host and port parameters imply attach mode."""
        mode = SessionValidator.determine_mode(
            target=None,
            pid=None,
            host="localhost",
            port=5678,
            start_request_type=None,
        )
        assert mode == StartRequestType.ATTACH

    def test_determine_mode_no_params_raises(self):
        """No parameters raises AidbError."""
        with pytest.raises(AidbError, match="Must provide either 'target'"):
            SessionValidator.determine_mode(
                target=None,
                pid=None,
                host=None,
                port=None,
                start_request_type=None,
            )


class TestSessionBuilderInit:
    """Tests for SessionBuilder initialization."""

    def test_init_creates_default_state(self, mock_ctx):
        """SessionBuilder initializes with default state."""
        builder = SessionBuilder(ctx=mock_ctx)

        assert builder._target is None
        assert builder._language is None
        assert builder._adapter_host == "localhost"
        assert builder._adapter_port is None
        assert builder._host is None
        assert builder._port is None
        assert builder._pid is None
        assert builder._args is None
        assert builder._launch_config is None
        assert builder._breakpoints is None
        assert builder._project_name is None
        assert builder._timeout == 10000
        assert builder._kwargs == {}
        assert builder._start_request_type is None

    def test_reset_clears_all_state(self, mock_ctx):
        """Reset() restores builder to initial state."""
        builder = SessionBuilder(ctx=mock_ctx)

        builder._target = "/path/to/script.py"
        builder._language = "python"
        builder._adapter_port = 1234
        builder._project_name = "test"
        builder._kwargs = {"extra": "value"}

        result = builder.reset()

        assert result is builder
        assert builder._target is None
        assert builder._language is None
        assert builder._adapter_port is None
        assert builder._project_name is None
        assert builder._kwargs == {}


class TestSessionBuilderChaining:
    """Tests for SessionBuilder method chaining."""

    def test_with_target_sets_target_and_mode(self, mock_ctx):
        """with_target() sets target and start_request_type."""
        builder = SessionBuilder(ctx=mock_ctx)

        result = builder.with_target("/path/to/script.py", args=["--verbose"])

        assert result is builder
        assert builder._target == "/path/to/script.py"
        assert builder._args == ["--verbose"]
        assert builder._start_request_type == StartRequestType.LAUNCH

    def test_with_attach_sets_attach_params(self, mock_ctx):
        """with_attach() sets attach parameters and mode."""
        builder = SessionBuilder(ctx=mock_ctx)

        result = builder.with_attach(host="localhost", port=5678, pid=1234)

        assert result is builder
        assert builder._host == "localhost"
        assert builder._port == 5678
        assert builder._pid == 1234
        assert builder._start_request_type == StartRequestType.ATTACH

    def test_with_language_sets_language(self, mock_ctx):
        """with_language() sets the language."""
        builder = SessionBuilder(ctx=mock_ctx)

        result = builder.with_language("javascript")

        assert result is builder
        assert builder._language == "javascript"

    def test_with_adapter_sets_adapter_params(self, mock_ctx):
        """with_adapter() sets adapter connection parameters."""
        builder = SessionBuilder(ctx=mock_ctx)

        result = builder.with_adapter(host="192.168.1.100", port=4711)

        assert result is builder
        assert builder._adapter_host == "192.168.1.100"
        assert builder._adapter_port == 4711

    def test_with_project_sets_project_name(self, mock_ctx):
        """with_project() sets the project name."""
        builder = SessionBuilder(ctx=mock_ctx)

        result = builder.with_project("my-project")

        assert result is builder
        assert builder._project_name == "my-project"

    def test_with_timeout_sets_timeout(self, mock_ctx):
        """with_timeout() sets the connection timeout."""
        builder = SessionBuilder(ctx=mock_ctx)

        result = builder.with_timeout(30000)

        assert result is builder
        assert builder._timeout == 30000

    def test_with_kwargs_merges_kwargs(self, mock_ctx):
        """with_kwargs() merges additional parameters."""
        builder = SessionBuilder(ctx=mock_ctx)
        builder._kwargs = {"existing": "value"}

        result = builder.with_kwargs(new_param="new_value", another=123)

        assert result is builder
        assert builder._kwargs == {
            "existing": "value",
            "new_param": "new_value",
            "another": 123,
        }

    def test_with_breakpoints_converts_breakpoints(self, mock_ctx):
        """with_breakpoints() converts breakpoint specs."""
        builder = SessionBuilder(ctx=mock_ctx)
        builder._target = "/path/to/script.py"
        builder._language = "python"

        with patch(
            "aidb.api.session_builder.BreakpointConverter"
        ) as mock_converter_cls:
            mock_converter = MagicMock()
            mock_converter.convert.return_value = [MagicMock()]
            mock_converter_cls.return_value = mock_converter

            result = builder.with_breakpoints(
                [{"file": "/path/to/script.py", "line": 10}]
            )

            assert result is builder
            mock_converter.convert.assert_called_once()
            assert len(builder._breakpoints) == 1

    def test_chaining_multiple_methods(self, mock_ctx):
        """Methods can be chained together."""
        builder = SessionBuilder(ctx=mock_ctx)

        result = (
            builder.with_target("/path/to/script.py")
            .with_language("python")
            .with_adapter(port=1234)
            .with_project("test-project")
            .with_timeout(5000)
        )

        assert result is builder
        assert builder._target == "/path/to/script.py"
        assert builder._language == "python"
        assert builder._adapter_port == 1234
        assert builder._project_name == "test-project"
        assert builder._timeout == 5000


class TestSessionBuilderBuild:
    """Tests for SessionBuilder.build()."""

    def test_build_launch_mode_creates_session(self, mock_ctx):
        """Build() creates a session in launch mode."""
        with patch("aidb.api.session_builder.Session") as mock_session_cls:
            mock_session = MagicMock()
            mock_session_cls.return_value = mock_session

            with patch(
                "aidb.api.session_builder.SessionBuilder._infer_language"
            ) as mock_infer:
                mock_infer.return_value = "python"

                builder = SessionBuilder(ctx=mock_ctx)
                builder._target = "/path/to/script.py"
                builder._start_request_type = StartRequestType.LAUNCH

                session = builder.build()

                assert session == mock_session
                mock_session_cls.assert_called_once()
                call_kwargs = mock_session_cls.call_args.kwargs
                assert call_kwargs["target"] == "/path/to/script.py"
                assert call_kwargs["language"] == "python"

    def test_build_attach_mode_creates_session(self, mock_ctx):
        """Build() creates a session in attach mode."""
        with patch("aidb.api.session_builder.Session") as mock_session_cls:
            mock_session = MagicMock()
            mock_session_cls.return_value = mock_session

            builder = SessionBuilder(ctx=mock_ctx)
            builder._language = "python"
            builder._pid = 1234
            builder._start_request_type = StartRequestType.ATTACH

            session = builder.build()

            assert session == mock_session
            assert session._attach_params is not None

    def test_build_infers_language_from_target(self, mock_ctx):
        """Build() infers language from target extension."""
        with patch("aidb.api.session_builder.Session") as mock_session_cls:
            mock_session = MagicMock()
            mock_session_cls.return_value = mock_session

            with patch(
                "aidb.session.adapter_registry.AdapterRegistry"
            ) as mock_registry_cls:
                mock_registry = MagicMock()
                mock_registry.resolve_lang_for_target.return_value = "javascript"
                mock_registry_cls.return_value = mock_registry

                builder = SessionBuilder(ctx=mock_ctx)
                builder._target = "/path/to/script.js"
                builder._start_request_type = StartRequestType.LAUNCH

                builder.build()

                mock_registry.resolve_lang_for_target.assert_called_once_with(
                    "/path/to/script.js"
                )

    def test_build_unresolved_variables_raises(self, mock_ctx):
        """Build() raises VSCodeVariableError for unresolved variables."""
        builder = SessionBuilder(ctx=mock_ctx)
        builder._target = "${file}"
        builder._language = "python"
        builder._start_request_type = StartRequestType.LAUNCH

        with pytest.raises(VSCodeVariableError, match="unresolved VS Code variables"):
            builder.build()

    def test_build_unresolved_launch_config_raises(self, mock_ctx):
        """Build() raises VSCodeVariableError when launch config unresolved."""
        builder = SessionBuilder(ctx=mock_ctx)
        builder._launch_config_name = "Python: Current File"
        builder._launch_config = None
        builder._target = "/path/to/script.py"
        builder._language = "python"
        builder._start_request_type = StartRequestType.LAUNCH

        with pytest.raises(VSCodeVariableError, match="unresolvable variables"):
            builder.build()

    def test_build_stores_launch_config(self, mock_ctx, sample_launch_config):
        """Build() stores launch config on session when present."""
        with patch("aidb.api.session_builder.Session") as mock_session_cls:
            mock_session = MagicMock()
            mock_session_cls.return_value = mock_session

            builder = SessionBuilder(ctx=mock_ctx)
            builder._target = "/path/to/script.py"
            builder._language = "python"
            builder._launch_config = sample_launch_config
            builder._start_request_type = StartRequestType.LAUNCH

            with patch("dataclasses.asdict") as mock_asdict:
                mock_asdict.return_value = {"name": "test"}
                builder.build()

                mock_asdict.assert_called_once_with(sample_launch_config)


class TestSessionBuilderInferLanguage:
    """Tests for SessionBuilder._infer_language()."""

    def test_infer_language_returns_set_language(self, mock_ctx):
        """_infer_language() returns explicitly set language."""
        builder = SessionBuilder(ctx=mock_ctx)
        builder._language = "java"

        result = builder._infer_language()

        assert result == "java"

    def test_infer_language_from_target(self, mock_ctx):
        """_infer_language() infers from target extension."""
        with patch(
            "aidb.session.adapter_registry.AdapterRegistry"
        ) as mock_registry_cls:
            mock_registry = MagicMock()
            mock_registry.resolve_lang_for_target.return_value = "python"
            mock_registry_cls.return_value = mock_registry

            builder = SessionBuilder(ctx=mock_ctx)
            builder._target = "/path/to/script.py"

            result = builder._infer_language()

            assert result == "python"

    def test_infer_language_unknown_target_raises(self, mock_ctx):
        """_infer_language() raises when target language unknown."""
        with patch(
            "aidb.session.adapter_registry.AdapterRegistry"
        ) as mock_registry_cls:
            mock_registry = MagicMock()
            mock_registry.resolve_lang_for_target.return_value = None
            mock_registry_cls.return_value = mock_registry

            builder = SessionBuilder(ctx=mock_ctx)
            builder._target = "/path/to/unknown.xyz"

            with pytest.raises(AidbError, match="Could not determine language"):
                builder._infer_language()

    def test_infer_language_no_target_attach_mode_raises(self, mock_ctx):
        """_infer_language() raises for attach mode without target/language."""
        builder = SessionBuilder(ctx=mock_ctx)
        builder._target = None
        builder._language = None

        with pytest.raises(AidbError, match="Language must be specified"):
            builder._infer_language()
