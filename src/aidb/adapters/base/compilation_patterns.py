"""Compilation patterns for various programming languages.

This module contains the compilation patterns and commands for different source file
types that need compilation before debugging.
"""

import os
from pathlib import Path
from typing import Any


def get_compilation_patterns() -> dict[str, dict[str, Any]]:
    """Get compilation patterns for various source file extensions.

    Returns
    -------
    Dict[str, Dict[str, Any]]
        Mapping from file extension to compilation information including:
        - cmd: Compilation command template
        - output: Expected output file path
        - msg: User-friendly message about compilation requirement
    """
    return {
        ".java": {
            "cmd": "javac -g {file}",
            "output_func": lambda p: p.with_suffix(".class"),
            "msg": "Java source file detected. Please compile to .class first.",
        },
        ".go": {
            "cmd": "go build -gcflags=all=-N\\ -l {file}",
            "output_func": lambda p: (
                p.with_suffix("") if os.name != "nt" else p.with_suffix(".exe")
            ),
            "msg": "Go source file detected. Please build the binary first.",
        },
        ".cs": {
            "cmd": "dotnet build {file}",
            "output_func": lambda p: p.with_suffix(".dll"),
            "msg": "C# source file detected. Please build to .dll or .exe first.",
        },
        ".cpp": {
            "cmd": "g++ -g -O0 {file} -o {output}",
            "output_func": lambda p: (
                p.with_suffix("") if os.name != "nt" else p.with_suffix(".exe")
            ),
            "msg": "C++ source file detected. Please compile first.",
        },
        ".c": {
            "cmd": "gcc -g -O0 {file} -o {output}",
            "output_func": lambda p: (
                p.with_suffix("") if os.name != "nt" else p.with_suffix(".exe")
            ),
            "msg": "C source file detected. Please compile first.",
        },
        ".rs": {
            "cmd": "cargo build",
            "output_func": lambda p: p.parent / "target" / "debug" / p.stem,
            "msg": "Rust source file detected. Please run cargo build first.",
        },
        ".ts": {
            "cmd": "tsc {file}",
            "output_func": lambda p: p.with_suffix(".js"),
            "msg": (
                "TypeScript source file detected. Please compile to JavaScript first."
            ),
        },
    }


def get_compilation_info(file_path: Path) -> dict[str, Any]:
    """Get compilation information for a specific file.

    Parameters
    ----------
    file_path : Path
        Path to the source file

    Returns
    -------
    Dict[str, Any]
        Compilation information if file needs compilation, empty dict otherwise
    """
    ext = file_path.suffix.lower()
    patterns = get_compilation_patterns()

    if ext not in patterns:
        return {}

    pattern = patterns[ext]
    output_path = pattern["output_func"](file_path)
    compile_cmd = pattern["cmd"].format(file=str(file_path), output=output_path)

    return {
        "output_path": output_path,
        "compile_command": compile_cmd,
        "error_message": pattern["msg"],
    }
