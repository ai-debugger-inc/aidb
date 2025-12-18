"""Sphinx configuration for AIDB Developer Guide.

This configuration builds the developer documentation for the AIDB project.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

# -- Path setup --------------------------------------------------------------

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent.parent / "src"))

# -- Project information -----------------------------------------------------
project = "AIDB Developer Guide"

# -- General configuration ---------------------------------------------------
extensions = [
    "myst_parser",  # enable Markdown support
    # "sphinx.ext.autosectionlabel",  # Disabled - causes conflicts with autoapi
    "sphinx_click",  # auto-generate Click CLI documentation
    "sphinxcontrib.mermaid",  # enable Mermaid diagrams
]
# Note: autoapi extension added conditionally below based on whether we need to generate
# autosectionlabel_prefix_document = True  # Disabled with extension
# autosectionlabel_maxdepth = 2  # Disabled with extension

# -- MyST configuration ------------------------------------------------------
# Enable mermaid code blocks in markdown
myst_fence_as_directive = ["mermaid"]

# -- Autoapi configuration ---------------------------------------------------
# API docs generation can be slow - use smart change detection


def _should_generate_api_docs() -> bool:  # noqa: C901
    """Check if API docs need regeneration based on source file changes."""
    # Allow manual override to skip
    if os.getenv("SKIP_API_DOCS", "0") == "1":
        return False

    # Allow manual override to force rebuild
    if os.getenv("FORCE_API_DOCS", "0") == "1":
        return True

    # Calculate hash of all Python source files
    src_dir = ROOT.parent.parent / "src"
    packages = ["aidb", "aidb_cli", "aidb_mcp", "aidb_logging", "aidb_common"]

    hash_obj = hashlib.md5()  # noqa: S324
    file_count = 0

    for pkg in packages:
        pkg_path = src_dir / pkg
        if pkg_path.exists():
            for py_file in sorted(pkg_path.rglob("*.py")):
                # Skip test files and private modules
                if any(skip in str(py_file) for skip in ["test", "__pycache__", "/_"]):
                    continue
                try:
                    hash_obj.update(py_file.read_bytes())
                    file_count += 1
                except (OSError, PermissionError):
                    pass

    current_hash = hash_obj.hexdigest()
    cache_file = ROOT / "_build" / ".api_docs_hash"

    # Create _build dir if it doesn't exist
    cache_file.parent.mkdir(exist_ok=True)

    # Check if hash has changed
    try:
        if cache_file.exists():
            cached_data = json.loads(cache_file.read_text())
            if (
                cached_data.get("hash") == current_hash
                and cached_data.get("file_count") == file_count
            ):
                print(f"✓ API docs up to date ({file_count} source files unchanged)")
                return False
    except (json.JSONDecodeError, OSError):
        pass

    # Hash changed or cache missing - need to rebuild
    print(f"→ API docs need regeneration ({file_count} source files changed)")
    cache_file.write_text(json.dumps({"hash": current_hash, "file_count": file_count}))
    return True


GENERATE_API_DOCS = _should_generate_api_docs()

# Only load autoapi extension if we need to generate
if GENERATE_API_DOCS:
    extensions.append("autoapi.extension")

# Configure autoapi (required even when extension not loaded, for existing docs)
autoapi_dirs = [
    str(ROOT.parent.parent / "src" / "aidb"),
    str(ROOT.parent.parent / "src" / "aidb_cli"),
    str(ROOT.parent.parent / "src" / "aidb_mcp"),
    str(ROOT.parent.parent / "src" / "aidb_logging"),
    str(ROOT.parent.parent / "src" / "aidb_common"),
]
autoapi_type = "python"
autoapi_template_dir = "_autoapi_templates"
autoapi_options = [
    "members",
    "show-inheritance",
    "show-module-summary",
    # Remove "undoc-members" to reduce noise from private/incomplete modules
]
autoapi_ignore = [
    "*migrations*",
    "*tests*",
    "*test_*",
    "*/conftest.py",
    "*/__pycache__/*",
    "**/fixtures/*",  # Test fixtures may have complex imports
    "**/helpers/*",  # Test helpers may have complex imports
    "**/test/*",  # Additional test patterns causing import issues
    "**/test_*/*",  # Test subdirectories
    "**/_*.py",  # Skip private modules (massive speedup)
    "**/adapters/*/build/*",  # Skip adapter build artifacts
    "**/vendor/*",  # Skip vendored code
    "**/_assets/*",  # Skip test assets
    "**/_docker/*",  # Skip Docker configurations
]
autoapi_root = "api"
autoapi_add_toctree_entry = True  # Let autoapi generate index automatically
autoapi_keep_files = True  # Keep files for incremental builds
autoapi_python_class_content = "class"  # Skip __init__ docstrings for faster builds
autoapi_member_order = "alphabetical"  # Simpler/faster than groupwise

# Control whether to actually generate (can skip if files unchanged)
autoapi_generate_api_docs = GENERATE_API_DOCS

suppress_warnings = [
    "autoapi.python_import_resolution",
]  # Suppress import warnings - expected in Docker

# Keep it small and simple
templates_path: list[str] = []
exclude_patterns: list[str] = ["_build", "**/.ipynb_checkpoints"]

# MyST options
myst_heading_anchors = 4

# Root document
root_doc = "index"

# -- Options for HTML output -------------------------------------------------
html_theme = "sphinx_rtd_theme"
html_title = "AIDB Developer Guide"
html_theme_options = {
    "collapse_navigation": False,
    "navigation_depth": 4,
    "style_external_links": True,
    "includehidden": True,
    "sticky_navigation": True,  # Keep navigation visible when scrolling
    "titles_only": False,  # Show subsections in navigation
}

# Code highlighting style (built-in Pygments styles)
pygments_style = "sphinx"

html_static_path: list[str] = ["_static"]

# -- linkcheck options ---------------------------------------------------------
# Keep link checking reasonably fast and robust for internal docs
linkcheck_timeout = 10
linkcheck_retries = 2
linkcheck_report_timeouts_as_broken = True

# Ignore common non-external or unstable targets
linkcheck_ignore = [
    r"^http://localhost",
    r"^https?://127\.0\.0\.1",
    r"^mailto:",
    r"^file://",
    r"^about:blank",
]
