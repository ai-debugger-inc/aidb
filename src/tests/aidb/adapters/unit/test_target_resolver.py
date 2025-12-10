"""Unit tests for target resolvers.

Tests language-specific target resolution for Python, JavaScript, and Java.
"""

from unittest.mock import MagicMock

import pytest

from aidb.adapters.base.target_resolver import TargetType


@pytest.fixture
def mock_python_adapter(mock_ctx: MagicMock) -> MagicMock:
    """Create a mock Python adapter for resolver testing."""
    from aidb.adapters.lang.python.config import PythonAdapterConfig

    adapter = MagicMock()
    adapter.ctx = mock_ctx
    adapter.module = False
    adapter.config = PythonAdapterConfig()
    return adapter


@pytest.fixture
def mock_javascript_adapter(mock_ctx: MagicMock) -> MagicMock:
    """Create a mock JavaScript adapter for resolver testing."""
    from aidb.adapters.lang.javascript.config import JavaScriptAdapterConfig

    adapter = MagicMock()
    adapter.ctx = mock_ctx
    adapter.config = JavaScriptAdapterConfig()
    return adapter


@pytest.fixture
def mock_java_adapter(mock_ctx: MagicMock) -> MagicMock:
    """Create a mock Java adapter for resolver testing."""
    from aidb.adapters.lang.java.config import JavaAdapterConfig

    adapter = MagicMock()
    adapter.ctx = mock_ctx
    adapter.config = JavaAdapterConfig()
    return adapter


class TestPythonTargetResolver:
    """Tests for PythonTargetResolver.

    Target resolution auto-detects module vs file mode:
    1. '-m module' syntax → extract module, enable module mode
    2. File paths (/, \\, .py, or exists) → file mode
    3. Bare identifiers (pytest, unittest) → module mode
    """

    # --- Explicit '-m module' syntax ---

    def test_explicit_m_pytest(self, mock_python_adapter: MagicMock) -> None:
        """Test explicit '-m pytest' syntax."""
        from aidb.adapters.lang.python.target_resolver import PythonTargetResolver

        resolver = PythonTargetResolver(mock_python_adapter, mock_python_adapter.ctx)
        result = resolver.resolve("-m pytest")

        assert result.target == "pytest"
        assert result.target_type == TargetType.MODULE
        assert mock_python_adapter.module is True

    def test_explicit_m_unittest(self, mock_python_adapter: MagicMock) -> None:
        """Test explicit '-m unittest' syntax."""
        from aidb.adapters.lang.python.target_resolver import PythonTargetResolver

        resolver = PythonTargetResolver(mock_python_adapter, mock_python_adapter.ctx)
        result = resolver.resolve("-m unittest")

        assert result.target == "unittest"
        assert result.target_type == TargetType.MODULE
        assert mock_python_adapter.module is True

    def test_explicit_m_with_whitespace(self, mock_python_adapter: MagicMock) -> None:
        """Test '-m' syntax with extra whitespace."""
        from aidb.adapters.lang.python.target_resolver import PythonTargetResolver

        resolver = PythonTargetResolver(mock_python_adapter, mock_python_adapter.ctx)
        result = resolver.resolve("-m   pytest  ")

        assert result.target == "pytest"
        assert result.target_type == TargetType.MODULE

    def test_explicit_m_dotted_module(self, mock_python_adapter: MagicMock) -> None:
        """Test '-m http.server' syntax."""
        from aidb.adapters.lang.python.target_resolver import PythonTargetResolver

        resolver = PythonTargetResolver(mock_python_adapter, mock_python_adapter.ctx)
        result = resolver.resolve("-m http.server")

        assert result.target == "http.server"
        assert result.target_type == TargetType.MODULE

    def test_explicit_m_empty_unchanged(self, mock_python_adapter: MagicMock) -> None:
        """Test that '-m ' with empty module name is not modified."""
        from aidb.adapters.lang.python.target_resolver import PythonTargetResolver

        resolver = PythonTargetResolver(mock_python_adapter, mock_python_adapter.ctx)
        result = resolver.resolve("-m ")

        assert result.target == "-m "
        assert result.target_type == TargetType.FILE

    # --- File paths (should NOT trigger module mode) ---

    def test_absolute_path_with_py(self, mock_python_adapter: MagicMock) -> None:
        """Test absolute path with .py extension stays as file."""
        from aidb.adapters.lang.python.target_resolver import PythonTargetResolver

        resolver = PythonTargetResolver(mock_python_adapter, mock_python_adapter.ctx)
        result = resolver.resolve("/path/to/script.py")

        assert result.target == "/path/to/script.py"
        assert result.target_type == TargetType.FILE
        assert mock_python_adapter.module is False

    def test_relative_path_with_py(self, mock_python_adapter: MagicMock) -> None:
        """Test relative path with .py extension stays as file."""
        from aidb.adapters.lang.python.target_resolver import PythonTargetResolver

        resolver = PythonTargetResolver(mock_python_adapter, mock_python_adapter.ctx)
        result = resolver.resolve("tests/test_foo.py")

        assert result.target == "tests/test_foo.py"
        assert result.target_type == TargetType.FILE

    def test_windows_path(self, mock_python_adapter: MagicMock) -> None:
        """Test Windows-style path stays as file."""
        from aidb.adapters.lang.python.target_resolver import PythonTargetResolver

        resolver = PythonTargetResolver(mock_python_adapter, mock_python_adapter.ctx)
        result = resolver.resolve("C:\\scripts\\main.py")

        assert result.target == "C:\\scripts\\main.py"
        assert result.target_type == TargetType.FILE

    def test_py_extension_only(self, mock_python_adapter: MagicMock) -> None:
        """Test that .py extension alone triggers file mode."""
        from aidb.adapters.lang.python.target_resolver import PythonTargetResolver

        resolver = PythonTargetResolver(mock_python_adapter, mock_python_adapter.ctx)
        result = resolver.resolve("script.py")

        assert result.target == "script.py"
        assert result.target_type == TargetType.FILE

    # --- Bare identifiers (should trigger module mode) ---

    def test_bare_pytest(self, mock_python_adapter: MagicMock) -> None:
        """Test bare 'pytest' is detected as module."""
        from aidb.adapters.lang.python.target_resolver import PythonTargetResolver

        resolver = PythonTargetResolver(mock_python_adapter, mock_python_adapter.ctx)
        result = resolver.resolve("pytest")

        assert result.target == "pytest"
        assert result.target_type == TargetType.MODULE
        assert mock_python_adapter.module is True

    def test_bare_unittest(self, mock_python_adapter: MagicMock) -> None:
        """Test bare 'unittest' is detected as module."""
        from aidb.adapters.lang.python.target_resolver import PythonTargetResolver

        resolver = PythonTargetResolver(mock_python_adapter, mock_python_adapter.ctx)
        result = resolver.resolve("unittest")

        assert result.target == "unittest"
        assert result.target_type == TargetType.MODULE

    def test_bare_flask(self, mock_python_adapter: MagicMock) -> None:
        """Test bare 'flask' is detected as module."""
        from aidb.adapters.lang.python.target_resolver import PythonTargetResolver

        resolver = PythonTargetResolver(mock_python_adapter, mock_python_adapter.ctx)
        result = resolver.resolve("flask")

        assert result.target == "flask"
        assert result.target_type == TargetType.MODULE

    def test_bare_dotted_module(self, mock_python_adapter: MagicMock) -> None:
        """Test dotted module name like 'http.server' is detected as module."""
        from aidb.adapters.lang.python.target_resolver import PythonTargetResolver

        resolver = PythonTargetResolver(mock_python_adapter, mock_python_adapter.ctx)
        result = resolver.resolve("http.server")

        assert result.target == "http.server"
        assert result.target_type == TargetType.MODULE

    # --- Edge cases ---

    def test_already_module_mode(self, mock_python_adapter: MagicMock) -> None:
        """Test that if module=True already, target is unchanged."""
        from aidb.adapters.lang.python.target_resolver import PythonTargetResolver

        mock_python_adapter.module = True
        resolver = PythonTargetResolver(mock_python_adapter, mock_python_adapter.ctx)
        result = resolver.resolve("anything")

        assert result.target == "anything"
        assert result.target_type == TargetType.MODULE


class TestJavaScriptTargetResolver:
    """Tests for JavaScriptTargetResolver.

    JavaScript targets are typically file paths.
    """

    def test_js_file(self, mock_javascript_adapter: MagicMock) -> None:
        """Test .js file is detected as file."""
        from aidb.adapters.lang.javascript.target_resolver import (
            JavaScriptTargetResolver,
        )

        resolver = JavaScriptTargetResolver(
            mock_javascript_adapter,
            mock_javascript_adapter.ctx,
        )
        result = resolver.resolve("app.js")

        assert result.target == "app.js"
        assert result.target_type == TargetType.FILE

    def test_ts_file(self, mock_javascript_adapter: MagicMock) -> None:
        """Test .ts file is detected as file."""
        from aidb.adapters.lang.javascript.target_resolver import (
            JavaScriptTargetResolver,
        )

        resolver = JavaScriptTargetResolver(
            mock_javascript_adapter,
            mock_javascript_adapter.ctx,
        )
        result = resolver.resolve("src/index.ts")

        assert result.target == "src/index.ts"
        assert result.target_type == TargetType.FILE

    def test_mjs_file(self, mock_javascript_adapter: MagicMock) -> None:
        """Test .mjs file is detected as file."""
        from aidb.adapters.lang.javascript.target_resolver import (
            JavaScriptTargetResolver,
        )

        resolver = JavaScriptTargetResolver(
            mock_javascript_adapter,
            mock_javascript_adapter.ctx,
        )
        result = resolver.resolve("module.mjs")

        assert result.target == "module.mjs"
        assert result.target_type == TargetType.FILE

    def test_absolute_path(self, mock_javascript_adapter: MagicMock) -> None:
        """Test absolute path is detected as file."""
        from aidb.adapters.lang.javascript.target_resolver import (
            JavaScriptTargetResolver,
        )

        resolver = JavaScriptTargetResolver(
            mock_javascript_adapter,
            mock_javascript_adapter.ctx,
        )
        result = resolver.resolve("/home/user/project/server.js")

        assert result.target == "/home/user/project/server.js"
        assert result.target_type == TargetType.FILE


class TestJavaTargetResolver:
    """Tests for JavaTargetResolver.

    Java targets can be .java (source), .class (compiled), .jar, or class names.
    """

    def test_java_source_file(self, mock_java_adapter: MagicMock) -> None:
        """Test .java file is detected as file needing compilation."""
        from aidb.adapters.lang.java.target_resolver import JavaTargetResolver

        resolver = JavaTargetResolver(mock_java_adapter, mock_java_adapter.ctx)
        result = resolver.resolve("Main.java")

        assert result.target == "Main.java"
        assert result.target_type == TargetType.FILE
        assert result.metadata.get("needs_compilation") is True

    def test_class_file(self, mock_java_adapter: MagicMock) -> None:
        """Test .class file is detected as class."""
        from aidb.adapters.lang.java.target_resolver import JavaTargetResolver

        resolver = JavaTargetResolver(mock_java_adapter, mock_java_adapter.ctx)
        result = resolver.resolve("Main.class")

        assert result.target == "Main.class"
        assert result.target_type == TargetType.CLASS

    def test_jar_file(self, mock_java_adapter: MagicMock) -> None:
        """Test .jar file is detected as executable."""
        from aidb.adapters.lang.java.target_resolver import JavaTargetResolver

        resolver = JavaTargetResolver(mock_java_adapter, mock_java_adapter.ctx)
        result = resolver.resolve("app.jar")

        assert result.target == "app.jar"
        assert result.target_type == TargetType.EXECUTABLE

    def test_qualified_class_name(self, mock_java_adapter: MagicMock) -> None:
        """Test qualified class name is detected as class."""
        from aidb.adapters.lang.java.target_resolver import JavaTargetResolver

        resolver = JavaTargetResolver(mock_java_adapter, mock_java_adapter.ctx)
        result = resolver.resolve("com.example.Main")

        assert result.target == "com.example.Main"
        assert result.target_type == TargetType.CLASS
        assert result.metadata.get("qualified_class_name") is True

    def test_absolute_path(self, mock_java_adapter: MagicMock) -> None:
        """Test absolute path is detected as file."""
        from aidb.adapters.lang.java.target_resolver import JavaTargetResolver

        resolver = JavaTargetResolver(mock_java_adapter, mock_java_adapter.ctx)
        result = resolver.resolve("/home/user/project/src/Main.java")

        assert result.target == "/home/user/project/src/Main.java"
        assert result.target_type == TargetType.FILE
