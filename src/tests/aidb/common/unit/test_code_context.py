"""Unit tests for code context extraction with source path resolution."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from aidb.adapters.lang.java.source_path_resolver import JavaSourcePathResolver
from aidb.adapters.lang.javascript.source_path_resolver import (
    JavaScriptSourcePathResolver,
)
from aidb.adapters.lang.python.source_path_resolver import PythonSourcePathResolver
from aidb.common.code_context import CodeContext


class TestJavaSourcePathResolver:
    """Tests for JavaSourcePathResolver.extract_relative_path."""

    @pytest.fixture
    def resolver(self) -> JavaSourcePathResolver:
        """Create a JavaSourcePathResolver with mocked adapter."""
        adapter = MagicMock()
        adapter.ctx = MagicMock()
        adapter.ctx.logger = MagicMock()
        return JavaSourcePathResolver(adapter=adapter, ctx=adapter.ctx)

    def test_jar_notation_simple(self, resolver: JavaSourcePathResolver) -> None:
        """Test extraction from simple JAR notation."""
        result = resolver.extract_relative_path(
            "trino-main.jar!/io/trino/execution/QueryStateMachine.java"
        )
        assert result == "io/trino/execution/QueryStateMachine.java"

    def test_jar_notation_with_path(self, resolver: JavaSourcePathResolver) -> None:
        """Test extraction from JAR notation with leading path."""
        result = resolver.extract_relative_path(
            "/opt/trino/lib/trino-main-476.jar!/io/trino/Foo.java"
        )
        assert result == "io/trino/Foo.java"

    def test_jar_notation_nested(self, resolver: JavaSourcePathResolver) -> None:
        """Test extraction from nested JAR path."""
        result = resolver.extract_relative_path(
            "file:/home/user/app.jar!/com/example/service/Handler.java"
        )
        assert result == "com/example/service/Handler.java"

    def test_src_main_java_pattern(self, resolver: JavaSourcePathResolver) -> None:
        """Test extraction from Maven source layout."""
        result = resolver.extract_relative_path(
            "/opt/app/src/main/java/io/trino/execution/QueryStateMachine.java"
        )
        assert result == "io/trino/execution/QueryStateMachine.java"

    def test_src_test_java_pattern(self, resolver: JavaSourcePathResolver) -> None:
        """Test extraction from Maven test layout."""
        result = resolver.extract_relative_path(
            "/workspace/project/src/test/java/com/example/MyTest.java"
        )
        assert result == "com/example/MyTest.java"

    def test_common_package_io(self, resolver: JavaSourcePathResolver) -> None:
        """Test extraction using io package marker."""
        result = resolver.extract_relative_path(
            "/opt/app/classes/io/trino/execution/QueryStateMachine.java"
        )
        assert result == "io/trino/execution/QueryStateMachine.java"

    def test_common_package_com(self, resolver: JavaSourcePathResolver) -> None:
        """Test extraction using com package marker."""
        result = resolver.extract_relative_path(
            "/var/lib/app/com/example/service/Handler.java"
        )
        assert result == "com/example/service/Handler.java"

    def test_common_package_org(self, resolver: JavaSourcePathResolver) -> None:
        """Test extraction using org package marker."""
        result = resolver.extract_relative_path(
            "/deploy/org/apache/commons/StringUtils.java"
        )
        assert result == "org/apache/commons/StringUtils.java"

    def test_no_recognizable_pattern(self, resolver: JavaSourcePathResolver) -> None:
        """Test that unrecognizable patterns return None."""
        result = resolver.extract_relative_path("/some/random/path/file.java")
        assert result is None

    def test_regular_local_path(self, resolver: JavaSourcePathResolver) -> None:
        """Test that regular local paths without package markers return None."""
        result = resolver.extract_relative_path(
            "/Users/dev/projects/myapp/MyClass.java"
        )
        assert result is None


class TestPythonSourcePathResolver:
    """Tests for PythonSourcePathResolver.extract_relative_path."""

    @pytest.fixture
    def resolver(self) -> PythonSourcePathResolver:
        """Create a PythonSourcePathResolver with mocked adapter."""
        adapter = MagicMock()
        adapter.ctx = MagicMock()
        adapter.ctx.logger = MagicMock()
        return PythonSourcePathResolver(adapter=adapter, ctx=adapter.ctx)

    def test_site_packages(self, resolver: PythonSourcePathResolver) -> None:
        """Test extraction from site-packages path."""
        result = resolver.extract_relative_path(
            "/usr/lib/python3.11/site-packages/requests/api.py"
        )
        assert result == "requests/api.py"

    def test_dist_packages(self, resolver: PythonSourcePathResolver) -> None:
        """Test extraction from dist-packages path."""
        result = resolver.extract_relative_path(
            "/usr/lib/python3/dist-packages/flask/app.py"
        )
        assert result == "flask/app.py"

    def test_venv_path(self, resolver: PythonSourcePathResolver) -> None:
        """Test extraction from virtual environment path."""
        result = resolver.extract_relative_path(
            "/app/.venv/lib/python3.11/site-packages/pkg/mod.py"
        )
        assert result == "pkg/mod.py"

    def test_egg_path(self, resolver: PythonSourcePathResolver) -> None:
        """Test extraction from egg path."""
        result = resolver.extract_relative_path(
            "/app/mypackage.egg/mypackage/module.py"
        )
        assert result == "mypackage/module.py"

    def test_src_layout(self, resolver: PythonSourcePathResolver) -> None:
        """Test extraction from src layout."""
        result = resolver.extract_relative_path("/app/src/mypackage/module.py")
        assert result == "mypackage/module.py"

    def test_no_recognizable_pattern(self, resolver: PythonSourcePathResolver) -> None:
        """Test that unrecognizable patterns return None."""
        result = resolver.extract_relative_path("/home/user/script.py")
        assert result is None


class TestJavaScriptSourcePathResolver:
    """Tests for JavaScriptSourcePathResolver.extract_relative_path."""

    @pytest.fixture
    def resolver(self) -> JavaScriptSourcePathResolver:
        """Create a JavaScriptSourcePathResolver with mocked adapter."""
        adapter = MagicMock()
        adapter.ctx = MagicMock()
        adapter.ctx.logger = MagicMock()
        return JavaScriptSourcePathResolver(adapter=adapter, ctx=adapter.ctx)

    def test_webpack_path(self, resolver: JavaScriptSourcePathResolver) -> None:
        """Test extraction from webpack source map path."""
        result = resolver.extract_relative_path("webpack://./src/components/App.tsx")
        assert result == "src/components/App.tsx"

    def test_webpack_path_triple_slash(
        self, resolver: JavaScriptSourcePathResolver
    ) -> None:
        """Test extraction from webpack path with triple slash."""
        result = resolver.extract_relative_path("webpack:///./src/index.js")
        assert result == "src/index.js"

    def test_node_modules(self, resolver: JavaScriptSourcePathResolver) -> None:
        """Test extraction from node_modules path."""
        result = resolver.extract_relative_path("/app/node_modules/lodash/lodash.js")
        assert result == "lodash/lodash.js"

    def test_dist_path(self, resolver: JavaScriptSourcePathResolver) -> None:
        """Test extraction from dist directory path."""
        result = resolver.extract_relative_path("/app/dist/bundle.js")
        assert result == "bundle.js"

    def test_build_path(self, resolver: JavaScriptSourcePathResolver) -> None:
        """Test extraction from build directory path."""
        result = resolver.extract_relative_path("/app/build/main.js")
        assert result == "main.js"

    def test_src_path(self, resolver: JavaScriptSourcePathResolver) -> None:
        """Test extraction from src directory path."""
        result = resolver.extract_relative_path("/app/src/utils/helper.ts")
        assert result == "utils/helper.ts"

    def test_no_recognizable_pattern(
        self, resolver: JavaScriptSourcePathResolver
    ) -> None:
        """Test that unrecognizable patterns return None."""
        result = resolver.extract_relative_path("/home/user/script.js")
        assert result is None


class TestSourcePathResolution:
    """Tests for SourcePathResolver.resolve method."""

    @pytest.fixture
    def temp_source_tree(self, tmp_path: Path) -> Path:
        """Create a temporary source tree for testing."""
        # Create a mock Trino source structure
        source_root = (
            tmp_path / "trino-source" / "core" / "trino-main" / "src" / "main" / "java"
        )
        io_trino = source_root / "io" / "trino" / "execution"
        io_trino.mkdir(parents=True)

        # Create a test file
        test_file = io_trino / "QueryStateMachine.java"
        test_file.write_text("public class QueryStateMachine {}\n")

        return source_root

    @pytest.fixture
    def java_resolver(self, temp_source_tree: Path) -> JavaSourcePathResolver:
        """Create a JavaSourcePathResolver with mocked adapter."""
        adapter = MagicMock()
        adapter.ctx = MagicMock()
        adapter.ctx.logger = MagicMock()
        return JavaSourcePathResolver(adapter=adapter, ctx=adapter.ctx)

    def test_resolve_jar_path(
        self, java_resolver: JavaSourcePathResolver, temp_source_tree: Path
    ) -> None:
        """Test resolving a JAR-internal path to local source."""
        result = java_resolver.resolve(
            "trino-main.jar!/io/trino/execution/QueryStateMachine.java",
            [str(temp_source_tree)],
        )
        assert result is not None
        assert result.exists()
        assert result.name == "QueryStateMachine.java"

    def test_resolve_container_path(
        self, java_resolver: JavaSourcePathResolver, temp_source_tree: Path
    ) -> None:
        """Test resolving a container absolute path to local source."""
        result = java_resolver.resolve(
            "/opt/trino/lib/io/trino/execution/QueryStateMachine.java",
            [str(temp_source_tree)],
        )
        assert result is not None
        assert result.exists()

    def test_resolve_nonexistent_file(
        self, java_resolver: JavaSourcePathResolver
    ) -> None:
        """Test that nonexistent files return None."""
        result = java_resolver.resolve(
            "trino-main.jar!/io/trino/NonExistent.java",
            ["/nonexistent/path"],
        )
        assert result is None

    def test_resolve_without_source_paths(
        self, java_resolver: JavaSourcePathResolver
    ) -> None:
        """Test that resolution fails gracefully without source paths."""
        result = java_resolver.resolve(
            "trino-main.jar!/io/trino/execution/QueryStateMachine.java",
            [],
        )
        assert result is None

    def test_resolve_multiple_source_paths(self, tmp_path: Path) -> None:
        """Test resolution with multiple source paths."""
        # Create two source trees
        source1 = tmp_path / "source1" / "io" / "trino"
        source1.mkdir(parents=True)
        (source1 / "Foo.java").write_text("class Foo {}")

        source2 = tmp_path / "source2" / "io" / "trino"
        source2.mkdir(parents=True)
        (source2 / "Bar.java").write_text("class Bar {}")

        adapter = MagicMock()
        adapter.ctx = MagicMock()
        adapter.ctx.logger = MagicMock()
        java_resolver = JavaSourcePathResolver(adapter=adapter, ctx=adapter.ctx)

        # File in first source path
        result1 = java_resolver.resolve(
            "app.jar!/io/trino/Foo.java",
            [str(tmp_path / "source1"), str(tmp_path / "source2")],
        )
        assert result1 is not None
        assert "source1" in str(result1)

        # File in second source path
        result2 = java_resolver.resolve(
            "app.jar!/io/trino/Bar.java",
            [str(tmp_path / "source1"), str(tmp_path / "source2")],
        )
        assert result2 is not None
        assert "source2" in str(result2)


class TestExtractContextWithSourcePaths:
    """Integration tests for CodeContext.extract_context with source path resolution."""

    @pytest.fixture
    def temp_source_file(self, tmp_path: Path) -> tuple[Path, Path]:
        """Create a temporary source file for testing."""
        source_root = tmp_path / "src" / "main" / "java"
        package_dir = source_root / "io" / "trino" / "execution"
        package_dir.mkdir(parents=True)

        test_file = package_dir / "QueryStateMachine.java"
        test_file.write_text(
            "package io.trino.execution;\n"
            "\n"
            "public class QueryStateMachine {\n"
            "    private String state;\n"
            "\n"
            "    public void setState(String state) {\n"
            "        this.state = state;\n"
            "    }\n"
            "}\n"
        )
        return source_root, test_file

    def test_extract_context_resolves_jar_path(
        self, temp_source_file: tuple[Path, Path]
    ) -> None:
        """Test that extract_context resolves JAR paths using source_paths."""
        source_root, _ = temp_source_file

        # Create a Java source path resolver
        adapter = MagicMock()
        adapter.ctx = MagicMock()
        adapter.ctx.logger = MagicMock()
        java_resolver = JavaSourcePathResolver(adapter=adapter, ctx=adapter.ctx)

        code_context = CodeContext(
            ctx=None,
            source_paths=[str(source_root)],
            source_path_resolver=java_resolver,
        )

        result = code_context.extract_context(
            file_path="trino-main.jar!/io/trino/execution/QueryStateMachine.java",
            line=6,
            breadth=2,
        )

        assert result["current_line"] == 6
        assert len(result["lines"]) > 0
        assert "setState" in result["formatted"]

    def test_extract_context_direct_path_still_works(
        self, temp_source_file: tuple[Path, Path]
    ) -> None:
        """Test that direct file paths still work without source paths."""
        _, test_file = temp_source_file

        code_context = CodeContext(ctx=None)

        result = code_context.extract_context(
            file_path=str(test_file),
            line=3,
            breadth=2,
        )

        assert result["current_line"] == 3
        assert len(result["lines"]) > 0
        assert "class QueryStateMachine" in result["formatted"]

    def test_extract_context_file_not_found_with_source_paths(self) -> None:
        """Test graceful handling when file not found even with source paths."""
        code_context = CodeContext(ctx=None, source_paths=["/nonexistent/path"])

        result = code_context.extract_context(
            file_path="app.jar!/io/trino/Missing.java",
            line=1,
        )

        assert "File not found" in result["formatted"]
        assert result["lines"] == []
