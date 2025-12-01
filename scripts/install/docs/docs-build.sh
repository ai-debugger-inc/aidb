#!/usr/bin/env bash
set -euo pipefail

cd /docs

# Copy source to writable location
# The /workspace mount is read-only, but pip needs to write .egg-info during install
echo "Setting up source for documentation generation..."
cp -r /workspace /tmp/aidb-src

# Install the package and its dependencies
# This includes aidb_cli for sphinx-click to generate CLI docs
pip install --quiet /tmp/aidb-src[docs]

# Set autoapi source root for sphinx-autoapi extension
export AUTOAPI_SOURCE_ROOT="/tmp/aidb-src/src"

# Build HTML and capture warnings
mkdir -p _build

# Don't fail on warnings (Sphinx returns exit code 1 for warnings with nitpicky=True)
# The build succeeds even with warnings, we just capture them for reference
sphinx-build -b html -w _build/warnings.txt . _build/html || true

# Only check links if SKIP_LINKCHECK is not set
# Linkcheck is slow (~10s) and not needed for every local build
if [[ "${SKIP_LINKCHECK:-0}" != "1" ]]; then
    sphinx-build -b linkcheck -w _build/linkcheck_warnings.txt . _build/linkcheck || true
fi
