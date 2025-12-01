#!/bin/bash
set -e

# This entrypoint wraps commands to ensure framework dependencies are installed
# AFTER volumes are mounted (which happens before CMD execution in docker-compose)

# If we're running bash -lc '...' (the typical test runner pattern),
# inject dependency installation at the start of the script
if [[ "${1}" == "bash" && "${2}" == "-lc" ]]; then
    # Extract the original script
    original_script="${3}"

    # Create new script with dependency installation prepended
    new_script="
# Create container lifecycle marker for cache invalidation
echo \"\${HOSTNAME}\" > /tmp/.container-id

# Install framework dependencies if needed (after volumes are mounted)
# Skip if SKIP_FRAMEWORK_DEPS_CHECK is set to 'true'
if [[ -f /scripts/install-framework-deps.sh ]]; then
    echo '=== Checking framework dependencies ==='
    # Use TEST_LANGUAGE from docker-compose, fallback to AIDB_LANGUAGE, default to 'all'
    LANG_FILTER=\"\${TEST_LANGUAGE:-\${AIDB_LANGUAGE:-all}}\"
    # Pass through SKIP_FRAMEWORK_DEPS_CHECK environment variable
    SKIP_FRAMEWORK_DEPS_CHECK=\"\${SKIP_FRAMEWORK_DEPS_CHECK:-false}\" /scripts/install-framework-deps.sh \"\${LANG_FILTER}\" || echo 'Warning: dependency installation had issues'
    echo '=== Framework dependencies ready ==='
fi

# Run original command
${original_script}
"

    # Execute with the modified script
    exec bash -lc "${new_script}"
else
    # For other commands, just execute as-is
    exec "${@}"
fi
