"""Script run to update the kitchen sink from https://sphinx-themes.org."""

from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen


def _validate_url_scheme(url: str) -> None:
    """Validate that URL uses a safe scheme."""
    parsed = urlparse(url)
    allowed_schemes = {"http", "https"}

    if parsed.scheme.lower() not in allowed_schemes:
        msg = (
            f"URL scheme '{parsed.scheme}' not allowed. Only http/https are permitted."
        )
        raise ValueError(msg)


EXTRA_MESSAGE = """\
.. note::

   The Kitchen Sink was generated from the
   `Sphinx Themes website <https://sphinx-themes.org/>`_, a community-supported showcase
   of themes for `Sphinx <https://www.sphinx-doc.org/>`_.
   Check it out to see other great themes.

   .. button-link:: https://sphinx-themes.org
      :color: primary

      Go to Sphinx Themes
"""

kitchen_sink_files = [
    "admonitions.rst",
    "api.rst",
    "blocks.rst",
    "generic.rst",
    "images.rst",
    "index.rst",
    "lists.rst",
    "really-long.rst",
    "structure.rst",
    "tables.rst",
    "typography.rst",
]
path_sink = Path(__file__).resolve().parents[1] / "examples" / "kitchen-sink"
if not path_sink.exists():
    msg = f"Kitchen sink directory not found: {path_sink}"
    raise FileNotFoundError(msg)
for ifile in kitchen_sink_files:
    print(f"Reading {ifile}...")
    url = f"https://github.com/sphinx-themes/sphinx-themes.org/raw/master/sample-docs/kitchen-sink/{ifile}"
    _validate_url_scheme(url)  # Validate URL scheme for security
    text = urlopen(url).read().decode()  # noqa: S310
    # The sphinx-themes docs expect Furo to be installed, so we overwrite w/ PST
    text = text.replace("src/furo", "src/pydata_sphinx_theme")
    text = text.replace(":any:`sphinx.ext.autodoc`", "``sphinx.ext.autodoc``")
    # Add introductory message directing people to Sphinx Themes
    if "index" in ifile:
        text = text.replace("============", "============\n\n" + EXTRA_MESSAGE)
    (path_sink / f"{ifile}").write_text(text)

print(f"Finished updating {len(kitchen_sink_files)} files...")
