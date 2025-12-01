#!/bin/bash
# Build script for AIDB VS Code Bridge extension

set -e

echo "Building AIDB VS Code Bridge extension..."

# Install dependencies if needed
if [[ ! -d "node_modules" ]]; then
    echo "Installing dependencies..."
    npm install
fi

# Compile TypeScript
echo "Compiling TypeScript..."
npm run compile

# Package the extension
echo "Packaging extension..."
npm run package

# Copy to resources directory for Python package
VSIX_FILE="aidb-vscode-bridge.vsix"
if [[ -f "${VSIX_FILE}" ]]; then
    echo "Extension packaged successfully: ${VSIX_FILE}"

    # Create resources directory if it doesn't exist
    RESOURCES_DIR="../../src/aidb/resources"
    mkdir -p "${RESOURCES_DIR}"

    # Copy VSIX to resources
    cp "${VSIX_FILE}" "${RESOURCES_DIR}/"
    echo "Copied VSIX to ${RESOURCES_DIR}/"
else
    echo "Error: VSIX file not created"
    exit 1
fi

echo "Build complete!"
