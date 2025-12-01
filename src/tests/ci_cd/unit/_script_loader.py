"""Utility for loading scripts from .github/scripts/ directory."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def load_script_module(script_name: str) -> ModuleType:
    """Load a script from .github/scripts/ as a module.

    Parameters
    ----------
    script_name : str
        Name of the script file (without .py extension)

    Returns
    -------
    ModuleType
        The loaded module

    Raises
    ------
    FileNotFoundError
        If the script doesn't exist
    ImportError
        If the script can't be imported
    """
    # Get scripts directory
    repo_root = Path(__file__).parent.parent.parent.parent.parent
    scripts_dir = repo_root / ".github" / "scripts"
    script_path = scripts_dir / f"{script_name}.py"

    if not script_path.exists():
        msg = f"Script not found: {script_path}"
        raise FileNotFoundError(msg)

    # Load spec from file
    spec = importlib.util.spec_from_file_location(script_name, script_path)
    if spec is None or spec.loader is None:
        msg = f"Could not load spec for {script_path}"
        raise ImportError(msg)

    # Create module from spec
    module = importlib.util.module_from_spec(spec)

    # Add to sys.modules to support relative imports within the script
    sys.modules[script_name] = module

    # Execute the module
    spec.loader.exec_module(module)

    return module
