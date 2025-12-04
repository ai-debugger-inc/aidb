"""Configuration file for the Sphinx documentation builder.

This file only contains a selection of the most common options. For a full
list see the documentation:
https://www.sphinx-doc.org/en/master/usage/configuration.html
"""

# -- Path setup --------------------------------------------------------------
import sys

# Use tomli for Python < 3.11, tomllib for Python >= 3.11
try:
    import tomllib
except ImportError:
    import tomli as tomllib

from pathlib import Path
from typing import Any

from sphinx.application import Sphinx

sys.path.append(str(Path().resolve()))

# -- Project information -----------------------------------------------------


# Read version from pyproject.toml
def _get_version():
    try:
        with Path("../pyproject.toml").resolve().open("rb") as f:
            data = tomllib.load(f)
            return data["project"]["version"]
    except Exception:
        return "unknown"


project = "AI Debugger"
copyright = "2025, AI Debugger"
author = "AI Debugger"
release = _get_version()

# -- General configuration ---------------------------------------------------

# Set the root document (master doc)
root_doc = "index"

extensions = [
    "sphinx.ext.napoleon",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx_design",
    "sphinx_copybutton",
    "myst_parser",
    "sphinx_favicon",
    "sphinx_click",  # auto-generate Click CLI documentation
    "autoapi.extension",  # auto-generate Python API documentation
    "sphinxcontrib.mermaid",  # enable Mermaid diagrams
    # custom extentions - KEEP THE GALLERY GRID
    "_extension.gallery_directive",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "**.ipynb_checkpoints"]

intersphinx_mapping = {
    "sphinx": ("https://www.sphinx-doc.org/en/master", None),
    "python": ("https://docs.python.org/3", None),
    "click": ("https://click.palletsprojects.com/en/8.1.x/", None),
}

# -- Sitemap -----------------------------------------------------------------
# Disabled for now - can be enabled later with sphinx_sitemap

# -- MyST options ------------------------------------------------------------

# This allows us to use ::: to denote directives, useful for admonitions
myst_enable_extensions = ["colon_fence", "linkify", "substitution"]
myst_fence_as_directive = ["mermaid"]  # Enable mermaid code blocks in markdown
myst_heading_anchors = 2
myst_substitutions = {"rtd": "[Read the Docs](https://readthedocs.org/)"}

# -- Internationalization ----------------------------------------------------

# specifying the natural language populates some key tags
language = "en"


# -- sphinx_ext_graphviz options ---------------------------------------------

graphviz_output_format = "svg"
inheritance_graph_attrs = dict(
    rankdir="LR",
    fontsize=14,
    ratio="compress",
)


# -- Sphinx-copybutton options ---------------------------------------------
# Exclude copy button from appearing over notebook cell numbers by using :not()
# The default copybutton selector is `div.highlight pre`
# https://github.com/executablebooks/sphinx-copybutton/blob/master/sphinx_copybutton/__init__.py#L82
copybutton_exclude = ".linenos, .gp"
copybutton_selector = ":not(.prompt) > div.highlight pre"

# -- Options for HTML output -------------------------------------------------

html_theme = "pydata_sphinx_theme"
html_logo = "_static/aidb-logo-transparent.svg"
html_favicon = "_static/favicon.ico"
html_sourcelink_suffix = ""
html_last_updated_fmt = ""  # to reveal the build date in the pages meta

# Favicon configuration (using sphinx_favicon extension)
favicons = [
    "favicon.ico",
    "favicon-16x16.png",
    "favicon-32x32.png",
    "favicon-48x48.png",
    "aidb-favicon-black.png",
]

# Define the json_url for our version switcher.
json_url = "_static/switcher.json"
version_match = release

html_theme_options = {
    "external_links": [
        {
            "url": "https://github.com/ai-debugger-inc/aidb",
            "name": "GitHub",
        },
    ],
    "header_links_before_dropdown": 4,
    "icon_links": [
        {
            "name": "GitHub",
            "url": "https://github.com/ai-debugger-inc/aidb",
            "icon": "fa-brands fa-github",
        },
        {
            "name": "PyPI",
            "url": "https://pypi.org/project/ai-debugger-inc",
            "icon": "fa-solid fa-box",
        },
    ],
    # alternative way to set twitter and github header icons
    # "github_url": "https://github.com/pydata/pydata-sphinx-theme",
    # "twitter_url": "https://twitter.com/PyData",
    "logo": {
        "text": "AI Debugger",
    },
    "use_edit_page_button": True,
    "show_toc_level": 1,
    # [left, content, right] For testing that the navbar items align properly
    "navbar_align": "left",
    # "show_nav_level": 2,
    "announcement": None,
    "show_version_warning_banner": True,
    "navbar_center": ["version-switcher", "navbar-nav"],
    # "navbar_start": ["navbar-logo"],
    # "navbar_end": ["theme-switcher", "navbar-icon-links"],
    # "navbar_persistent": ["search-button"],
    # "primary_sidebar_end": ["custom-template", "sidebar-ethical-ads"],
    # "article_footer_items": ["test", "test"],
    # "content_footer_items": ["test", "test"],
    "footer_start": ["copyright"],
    "footer_center": ["sphinx-version"],
    "secondary_sidebar_items": {
        "**/*": ["page-toc", "edit-this-page", "sourcelink"],
        "examples/no-sidebar": [],
    },
    "switcher": {
        "json_url": json_url,
        "version_match": version_match,
    },
    # "back_to_top_button": False,
}

html_sidebars = {}

html_context = {
    "github_user": "ai-debugger",
    "github_repo": "aidb",
    "github_version": "main",
    "doc_path": "docs",
}


# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]
html_css_files = ["custom.css", "support.css"]
html_js_files = [
    ("custom-icons.js", {"defer": "defer"}),
    ("support.js", {"defer": "defer"}),
]
todo_include_todos = True

# -- Options for autosummary/autodoc output ------------------------------------
# Disabled for faster builds
# autosummary_generate = True
# autodoc_typehints = "description"
# autodoc_member_order = "groupwise"

# -- Options for autoapi -------------------------------------------------------
autoapi_type = "python"
# Use environment variable to support both local and Docker builds
# Docker: copies source to /tmp/aidb-src, sets AUTOAPI_SOURCE_ROOT
# Local: defaults to ../src relative to docs/
import os

_autoapi_root = os.environ.get("AUTOAPI_SOURCE_ROOT", "../src")
autoapi_dirs = [
    f"{_autoapi_root}/aidb",
    f"{_autoapi_root}/aidb_cli",
    f"{_autoapi_root}/aidb_mcp",
    f"{_autoapi_root}/aidb_logging",
    f"{_autoapi_root}/aidb_common",
]
autoapi_root = "developer-guide/api"
autoapi_keep_files = True
autoapi_add_toctree_entry = True
autoapi_member_order = "alphabetical"
autoapi_options = [
    "members",
    "show-inheritance",
    "show-module-summary",
]
autoapi_ignore = [
    "**/test*",
    "**/conftest.py",
    "**/__pycache__/*",
    "**/_[!_]*.py",  # Ignore _private.py but not __init__.py or __dunder__.py
]
autoapi_template_dir = "_templates/autoapi"
suppress_warnings = [
    "autoapi.python_import_resolution",
    "ref.python",  # Suppress "more than one target found" for duplicate class names
]


# -- Warnings / Nitpicky -------------------------------------------------------

nitpicky = True
bad_classes = (
    r".*abc def.*",  # urllib.parse.unquote_to_bytes
    r"api_sample\.RandomNumberGenerator",
    r"bs4\.BeautifulSoup",
    r"docutils\.nodes\.Node",
    r"matplotlib\.artist\.Artist",  # matplotlib xrefs are in the class diagram demo
    r"matplotlib\.figure\.Figure",
    r"matplotlib\.figure\.FigureBase",
    r"pygments\.formatters\.HtmlFormatter",
    # Common type aliases that don't resolve in autoapi
    r"optional",
    r"any",
    r"callable",
    r"T",
    r"F",
    r"S",
    r"Obj",
    r"Handler",
    r"Enum",
    r"Ellipsis",
    r"Dictionary",
    # Standard library types without full module path
    r"Path",
    r"CompletedProcess",
    r"Resource",
    r"Process",
    # Blanket ignore docstring fragments parsed as types
    # Matches anything with spaces (real types don't have spaces)
    r".* .*",
    # Common single-word fragments and return value names
    r"default=.*",
    r"e\.g\.",
    r"\".*\"",  # Quoted strings
    # Common variable/parameter names parsed as types
    r"name",
    r"is_valid",
    r"is_running",
    r"error_messages",
    r"status_message",
    r"url_if_running",
    r"volumes",
    r"networks",
    r"port",
    r"var",
    r"Name",
    r"images",
    r"identifier",
    r"func",
    r"flow",
    r"eval",
    r"datetime",
    r"containers",
    r"category",
    r"bp",
    r"action",
    r"Icon",
    r"Tool",
    # Third-party types
    r"psutil\..*",
    r"mcp\..*",
    # Internal types
    r"CommandExecutor",
    r"ProfileType",
    r"LoggingContext",
    r"MCPResponse",
    r"TestOrchestrator",
    r"TestManager",
    r"SetVariableResponseModel",
    r"ResourceContents",
    r"EvaluateResponseModel",
    r"DAPStopReason",
    r"BaseConfigManager",
    r"APIOrchestrationOperations",
    r"APIIntrospectionOperations",
    # Internal types that may not cross-reference properly
    r"aidb\..*",
    r"aidb_cli\..*",
    r"aidb_mcp\..*",
    r"aidb_common\..*",
    r"aidb_logging\..*",
)
nitpick_ignore_regex = [
    *[("py:class", target) for target in bad_classes],
    *[("py:obj", target) for target in bad_classes],
    # we demo some `urllib` docs on our site; don't care that its xrefs fail to resolve
    ("py:obj", r"urllib\.parse\.(Defrag|Parse|Split)Result(Bytes)?\.(count|index)"),
    # the kitchen sink pages include some intentional errors
    ("token", r"(suite|expression|target)"),
    # RST reference warnings from docstrings containing underscores
    ("ref", r"aidb"),
    ("ref", r"aidb_cli"),
    ("ref", r"secret"),
]

# -- application setup -------------------------------------------------------


def setup_to_main(
    _app: Sphinx,
    _pagename: str,
    _templatename: str,
    context,
    _doctree,
) -> None:
    """
    Add a function that jinja can access for returning an "edit this page" link
    pointing to `main`.
    """

    def to_main(link: str) -> str:
        """
        Transform "edit on github" links and make sure they always point to the
        main branch.

        Args:
            link: the link to the github edit interface

        Returns:
            the link to the tip of the main branch for the same file
        """
        links = link.split("/")
        idx = links.index("edit")
        return "/".join(links[: idx + 1]) + "/main/" + "/".join(links[idx + 2 :])

    context["to_main"] = to_main


def setup(app: Sphinx) -> dict[str, Any]:
    """Add custom configuration to sphinx app.

    Args:
        app: the Sphinx application
    Returns:
        the 2 parallel parameters set to ``True``.
    """
    app.connect("html-page-context", setup_to_main)

    return {
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }


# -- linkcheck options ---------------------------------------------------------

linkcheck_anchors_ignore = [
    # match any anchor that starts with a '/' since this is an invalid HTML anchor
    r"\/.*",
]

linkcheck_ignore = [
    # The crawler gets "Anchor not found" for various anchors
    r"https://github.com.+?#.*",
    r"https://www.sphinx-doc.org/en/master/*/.+?#.+?",
    # sample urls
    "http://someurl/release-0.1.0.tar-gz",
    "http://python.py",
    # get a 403 on CI
    "https://canvas.workday.com/styles/tokens/type",
    "https://unsplash.com/",
    r"https?://www.gnu.org/software/gettext/.*",
]

linkcheck_allowed_redirects = {
    r"http://www.python.org": "https://www.python.org/",
    # :source:`something` linking files in the repository
    r"https://github.com/pydata/pydata-sphinx-theme/tree/.*": r"https://github.com/pydata/pydata-sphinx-theme/blob/.*",
    r"https://github.com/sphinx-themes/sphinx-themes.org/raw/.*": r"https://github.com/sphinx-themes/sphinx-themes.org/tree/.*",
    # project redirects
    r"https://pypi.org/project/[A-Za-z\d_\-\.]+/": r"https://pypi.org/project/[a-z\d\-\.]+/",
    r"https://virtualenv.pypa.io/": "https://virtualenv.pypa.io/en/latest/",
    # catching redirects in rtd
    r"https://[A-Za-z\d_\-\.]+.readthedocs.io/": r"https://[A-Za-z\d_\-\.]+\.readthedocs\.io(/en)?/(stable|latest)/",
    r"https://readthedocs.org/": r"https://about.readthedocs.com/\?ref=app.readthedocs.org",
    r"https://app.readthedocs.org/dashboard/": r"https://app.readthedocs.org/accounts/login/\?next=/dashboard/",
    # miscellanenous urls
    r"https://python.arviz.org/": "https://python.arviz.org/en/stable/",
    r"https://www.sphinx-doc.org/": "https://www.sphinx-doc.org/en/master/",
    r"https://idtracker.ai/": "https://idtracker.ai/latest/",
    r"https://gitlab.com": "https://about.gitlab.com/",
    r"http://www.yahoo.com": "https://www.yahoo.com/",
    r"https://feature-engine.readthedocs.io/": "https://feature-engine.trainindata.com/en/latest/",
    r"https://picsum.photos/": r"https://fastly.picsum.photos/",
}

# we have had issues with linkcheck timing and retries on www.gnu.org
linkcheck_retries = 1
linkcheck_timeout = 5
linkcheck_report_timeouts_as_broken = True
