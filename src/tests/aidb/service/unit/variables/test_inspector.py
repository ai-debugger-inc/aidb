"""Unit tests for VariableService."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from aidb.models import (
    AidbVariablesResponse,
    EvaluationResult,
    SessionStatus,
    VariableType,
)
from aidb.service.variables.inspector import VariableService


@pytest.fixture
def mock_service_session(mock_ctx: MagicMock) -> MagicMock:
    """Create a mock session for service tests.

    Returns
    -------
    MagicMock
        Mock session with DAP client and required attributes
    """
    session = MagicMock()
    session.id = "test-session-id"
    session.language = "python"
    session.is_child = False
    session.started = True
    session.ctx = mock_ctx
    session.child_session_ids = []
    session.status = SessionStatus.PAUSED
    session._frame_cache = {"thread_id": 1, "frame_id": 0}

    # Mock DAP client
    session.dap = MagicMock()
    session.dap.send_request = AsyncMock()
    session.dap.get_next_seq = AsyncMock(return_value=1)

    # Mock capabilities
    session.has_capability = MagicMock(return_value=True)

    # Mock registry
    session.registry = MagicMock()
    session.registry.get_session = MagicMock(return_value=None)

    return session


class TestVariableServiceInit:
    """Test VariableService initialization."""

    def test_init_with_session(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test that VariableService can be initialized with a session."""
        service = VariableService(mock_service_session, mock_ctx)

        assert service._session is mock_service_session
        assert service.ctx is mock_ctx


class TestVariableServiceEvaluate:
    """Test VariableService.evaluate method."""

    @pytest.mark.asyncio
    async def test_evaluate_expression(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test evaluating an expression."""
        mock_response = MagicMock()
        mock_response.ensure_success = MagicMock()
        mock_response.body = MagicMock()
        mock_response.body.result = "42"
        mock_response.body.type = "int"
        mock_response.body.variablesReference = 0
        mock_service_session.dap.send_request = AsyncMock(return_value=mock_response)

        service = VariableService(mock_service_session, mock_ctx)

        result = await service.evaluate("2 + 40", frame_id=0)

        assert isinstance(result, EvaluationResult)
        assert result.expression == "2 + 40"
        assert result.result == "42"
        assert result.type_name == "int"
        mock_service_session.dap.send_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_evaluate_with_children(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test evaluating an expression that has child variables."""
        mock_response = MagicMock()
        mock_response.ensure_success = MagicMock()
        mock_response.body = MagicMock()
        mock_response.body.result = "{'a': 1}"
        mock_response.body.type = "dict"
        mock_response.body.variablesReference = 5
        mock_service_session.dap.send_request = AsyncMock(return_value=mock_response)

        service = VariableService(mock_service_session, mock_ctx)

        result = await service.evaluate("my_dict", frame_id=0)

        assert result.has_children is True


class TestVariableServiceLocals:
    """Test VariableService.locals method."""

    @pytest.mark.asyncio
    async def test_locals_returns_variables(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test getting local variables."""
        # Mock scopes response
        mock_scopes_response = MagicMock()
        mock_scopes_response.ensure_success = MagicMock()
        mock_scopes_response.body = MagicMock()
        mock_scope = MagicMock()
        mock_scope.name = "Locals"
        mock_scope.variablesReference = 1
        mock_scopes_response.body.scopes = [mock_scope]

        # Mock variables response
        mock_vars_response = MagicMock()
        mock_vars_response.ensure_success = MagicMock()
        mock_vars_response.body = MagicMock()
        mock_var = MagicMock()
        mock_var.name = "x"
        mock_var.value = "10"
        mock_var.type = "int"
        mock_var.variablesReference = 0
        mock_vars_response.body.variables = [mock_var]

        mock_service_session.dap.send_request = AsyncMock(
            side_effect=[mock_scopes_response, mock_vars_response],
        )

        service = VariableService(mock_service_session, mock_ctx)

        result = await service.locals(frame_id=0)

        assert isinstance(result, AidbVariablesResponse)
        assert "x" in result.variables
        assert result.variables["x"].value == "10"


class TestVariableServiceGlobals:
    """Test VariableService.globals method."""

    @pytest.mark.asyncio
    async def test_globals_returns_variables(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test getting global variables."""
        # Mock scopes response
        mock_scopes_response = MagicMock()
        mock_scopes_response.ensure_success = MagicMock()
        mock_scopes_response.body = MagicMock()
        mock_scope = MagicMock()
        mock_scope.name = "Globals"
        mock_scope.variablesReference = 2
        mock_scopes_response.body.scopes = [mock_scope]

        # Mock variables response
        mock_vars_response = MagicMock()
        mock_vars_response.ensure_success = MagicMock()
        mock_vars_response.body = MagicMock()
        mock_var = MagicMock()
        mock_var.name = "CONSTANT"
        mock_var.value = "100"
        mock_var.type = "int"
        mock_var.variablesReference = 0
        mock_vars_response.body.variables = [mock_var]

        mock_service_session.dap.send_request = AsyncMock(
            side_effect=[mock_scopes_response, mock_vars_response],
        )

        service = VariableService(mock_service_session, mock_ctx)

        result = await service.globals(frame_id=0)

        assert isinstance(result, AidbVariablesResponse)
        assert "CONSTANT" in result.variables


class TestVariableServiceWatch:
    """Test VariableService.watch method."""

    @pytest.mark.asyncio
    async def test_watch_expression(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test watching an expression."""
        mock_response = MagicMock()
        mock_response.ensure_success = MagicMock()
        mock_response.body = MagicMock()
        mock_response.body.result = "hello"
        mock_response.body.type = "str"
        mock_response.body.variablesReference = 0
        mock_service_session.dap.send_request = AsyncMock(return_value=mock_response)

        service = VariableService(mock_service_session, mock_ctx)

        result = await service.watch("my_var", frame_id=0)

        assert isinstance(result, EvaluationResult)
        assert result.expression == "my_var"
        assert result.result == "hello"


class TestVariableServiceSetVariable:
    """Test VariableService.set_variable method."""

    @pytest.mark.asyncio
    async def test_set_variable(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test setting a variable value."""
        mock_response = MagicMock()
        mock_response.ensure_success = MagicMock()
        mock_response.body = MagicMock()
        mock_response.body.value = "99"
        mock_response.body.type = "int"
        mock_response.body.variablesReference = 0
        mock_service_session.dap.send_request = AsyncMock(return_value=mock_response)

        service = VariableService(mock_service_session, mock_ctx)

        result = await service.set_variable(
            variable_ref=1,
            name="x",
            value="99",
        )

        assert result.name == "x"
        assert result.value == "99"
        mock_service_session.dap.send_request.assert_called_once()


class TestVariableServiceSetExpression:
    """Test VariableService.set_expression method."""

    @pytest.mark.asyncio
    async def test_set_expression(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test setting an expression value."""
        mock_response = MagicMock()
        mock_response.ensure_success = MagicMock()
        mock_response.body = MagicMock()
        mock_response.body.value = "[1, 2, 3]"
        mock_response.body.type = "list"
        mock_response.body.variablesReference = 10
        mock_response.body.indexedVariables = 3
        mock_service_session.dap.send_request = AsyncMock(return_value=mock_response)

        service = VariableService(mock_service_session, mock_ctx)

        result = await service.set_expression(
            expression="my_list",
            value="[1, 2, 3]",
            frame_id=0,
        )

        assert result.name == "my_list"
        assert result.value == "[1, 2, 3]"
        assert result.var_type == VariableType.ARRAY


class TestVariableServiceGetVariables:
    """Test VariableService.get_variables method."""

    @pytest.mark.asyncio
    async def test_get_variables(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test getting variables by reference."""
        mock_response = MagicMock()
        mock_response.ensure_success = MagicMock()
        mock_response.body = MagicMock()
        mock_var1 = MagicMock()
        mock_var1.name = "key1"
        mock_var1.value = "value1"
        mock_var1.type = "str"
        mock_var1.variablesReference = 0
        mock_var2 = MagicMock()
        mock_var2.name = "key2"
        mock_var2.value = "value2"
        mock_var2.type = "str"
        mock_var2.variablesReference = 0
        mock_response.body.variables = [mock_var1, mock_var2]
        mock_service_session.dap.send_request = AsyncMock(return_value=mock_response)

        service = VariableService(mock_service_session, mock_ctx)

        result = await service.get_variables(variables_reference=5)

        assert "key1" in result
        assert "key2" in result
        assert result["key1"].value == "value1"


class TestDetermineVariableType:
    """Test _determine_variable_type helper method."""

    def test_primitive_types(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test detection of primitive types."""
        service = VariableService(mock_service_session, mock_ctx)

        assert service._determine_variable_type("int") == VariableType.PRIMITIVE
        assert service._determine_variable_type("float") == VariableType.PRIMITIVE
        assert service._determine_variable_type("str") == VariableType.PRIMITIVE
        assert service._determine_variable_type("bool") == VariableType.PRIMITIVE
        assert service._determine_variable_type("string") == VariableType.PRIMITIVE
        assert service._determine_variable_type("number") == VariableType.PRIMITIVE
        assert service._determine_variable_type("boolean") == VariableType.PRIMITIVE

    def test_array_types(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test detection of array types."""
        service = VariableService(mock_service_session, mock_ctx)

        assert service._determine_variable_type("list") == VariableType.ARRAY
        assert service._determine_variable_type("array") == VariableType.ARRAY
        assert service._determine_variable_type("int[]") == VariableType.ARRAY

    def test_function_types(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test detection of function types."""
        service = VariableService(mock_service_session, mock_ctx)

        assert service._determine_variable_type("function") == VariableType.FUNCTION
        assert service._determine_variable_type("method") == VariableType.FUNCTION
        assert service._determine_variable_type("callable") == VariableType.FUNCTION

    def test_class_types(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test detection of class types."""
        service = VariableService(mock_service_session, mock_ctx)

        assert service._determine_variable_type("class") == VariableType.CLASS
        assert service._determine_variable_type("type") == VariableType.CLASS

    def test_module_types(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test detection of module types."""
        service = VariableService(mock_service_session, mock_ctx)

        assert service._determine_variable_type("module") == VariableType.MODULE

    def test_object_fallback(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test that unknown types fall back to OBJECT."""
        service = VariableService(mock_service_session, mock_ctx)

        assert service._determine_variable_type("Person") == VariableType.OBJECT
        assert service._determine_variable_type("dict") == VariableType.OBJECT
        assert service._determine_variable_type("object") == VariableType.OBJECT

    def test_empty_type(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test that empty type returns UNKNOWN."""
        service = VariableService(mock_service_session, mock_ctx)

        assert service._determine_variable_type("") == VariableType.UNKNOWN
