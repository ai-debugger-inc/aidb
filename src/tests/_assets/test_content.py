"""Test content provider for generated test programs.

This module provides access to generated test program content for different
languages and scenarios.
"""

from pathlib import Path

from aidb_common.constants import Language


def get_test_content(language: str | Language, scenario: str) -> str:
    """Get test program content for a given language and scenario.

    Parameters
    ----------
    language : str | Language
        Programming language (python, javascript, java)
    scenario : str
        Scenario name (e.g., 'basic_variables', 'basic_for_loop')

    Returns
    -------
    str
        Test program source code

    Raises
    ------
    FileNotFoundError
        If the test program file doesn't exist for the given language/scenario
    ValueError
        If the language is not supported
    """
    lang_str = language.value if isinstance(language, Language) else language
    lang_str = lang_str.lower()

    test_programs_dir = Path(__file__).parent / "test_programs" / "generated"
    scenario_dir = test_programs_dir / scenario

    if not scenario_dir.exists():
        msg = f"Scenario '{scenario}' not found in {test_programs_dir}"
        raise FileNotFoundError(msg)

    file_map = {
        "python": "test_program.py",
        "javascript": "test_program.js",
        "java": "TestProgram.java",
    }

    if lang_str not in file_map:
        msg = f"Language '{lang_str}' not supported. Use: {list(file_map.keys())}"
        raise ValueError(msg)

    test_file = scenario_dir / file_map[lang_str]

    if not test_file.exists():
        msg = f"Test program not found: {test_file}"
        raise FileNotFoundError(msg)

    return test_file.read_text()
