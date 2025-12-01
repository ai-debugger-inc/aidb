"""Fixtures for generator integration tests."""

from pathlib import Path

import pytest

from aidb_cli.generators.core.generator import Generator


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Path:
    """Provide temporary directory for generated output."""
    output_dir = tmp_path / "test_programs" / "generated"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


@pytest.fixture
def generator_with_output(temp_output_dir: Path) -> tuple[Generator, Path]:
    """Return generator and output directory for integration tests."""
    generator = Generator()
    return generator, temp_output_dir


@pytest.fixture
def all_languages() -> list[str]:
    """Return list of all supported languages."""
    return ["python", "javascript", "java"]


@pytest.fixture
def basic_scenarios() -> list[str]:
    """Return list of basic scenario IDs."""
    return [
        "basic_variables",
        "basic_for_loop",
        "basic_while_loop",
        "simple_function",
        "conditionals",
        "basic_exception",
    ]
