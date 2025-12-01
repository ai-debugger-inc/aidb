#!/usr/bin/env bash
set -euo pipefail

# Ensure log directory exists
LOG_DIR=".local"
LOG_FILE="${LOG_DIR}/pre-commit.log"
mkdir -p "${LOG_DIR}"

# Run quiet collection to keep console noise minimal

# Limit discovery to the tests directory to avoid scanning unrelated paths
if ! venv/bin/python -m pytest src/tests --collect-only -qq; then
  # On failure, capture detailed collection output for debugging
  {
    echo "[validate-pytest-collection] Collection failed; detailed output follows:";
    venv/bin/python -m pytest src/tests --collect-only -vvv || true;
    echo "[validate-pytest-collection] End detailed output";
  } >> "${LOG_FILE}" 2>&1
  exit 1
fi

exit 0
