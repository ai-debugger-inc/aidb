#!/usr/bin/env bash
# Run vulture and print results, but never fail the commit

# Build explicit file list excluding tests and DAP dirs to avoid vulture scanning them
readarray -d '' -t FILES < <(
  find src -type f -name "*.py" \
    -not -path "src/tests/*" \
    -not -path "src/aidb/dap/_util/*" \
    -not -path "src/aidb/dap/protocol/*" \
    -not -path "src/aidb/models/*" \
    -print0
) || true

# Run vulture on the explicit list (informational only)
venv/bin/python -m vulture "${FILES[@]}" || true

# Always exit with 0 so commit is allowed
exit 0
