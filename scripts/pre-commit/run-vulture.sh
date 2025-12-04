#!/usr/bin/env bash
# Run vulture and print results, but never fail the commit

# Excludes tests and DAP dirs to avoid vulture scanning them
find src -type f -name "*.py" \
    -not -path "src/tests/*" \
    -not -path "src/aidb/dap/_util/*" \
    -not -path "src/aidb/dap/protocol/*" \
    -not -path "src/aidb/models/*" \
    -print0 | xargs -0 venv/bin/python -m vulture || true

# Always exit with 0 so commit is allowed
exit 0
