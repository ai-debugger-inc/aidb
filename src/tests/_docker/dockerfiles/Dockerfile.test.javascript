# Language-specific test image for JavaScript/Node.js
# Optimized for JavaScript framework testing with minimal size
# NOTE: Inherits from aidb-test-base which provides Python 3.12 + common dependencies
# NOTE: Versions from versions.json

# Parametrize base image for CI flexibility (local: aidb-test-base:latest, CI: GHCR)
# Must be declared in global scope (before first FROM) for multi-stage builds
# hadolint ignore=DL3006
ARG AIDB_TEST_BASE_IMAGE=aidb-test-base:latest

# Accept build args for versions
ARG NODE_VERSION=22
ARG TYPESCRIPT_VERSION=5.9.3
ARG TS_NODE_VERSION=10.9.2

# Stage 1: Get Node.js binaries from official image
FROM node:${NODE_VERSION}-slim AS node-source

# Stage 2: Build final image with Python base + Node.js
FROM ${AIDB_TEST_BASE_IMAGE}

# AIDB Docker labels
LABEL com.aidb.language="javascript"

# Set shell to bash with pipefail for better error handling
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Copy Node.js binaries and libraries from official Node.js image
COPY --from=node-source /usr/local/bin/node /usr/local/bin/
COPY --from=node-source /usr/local/lib/node_modules /usr/local/lib/node_modules

# Create symlinks for npm and npx
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm && \
    ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

# Install Node.js tooling for testing with npm cache mount (pinned versions)
# hadolint ignore=DL3059
RUN --mount=type=cache,target=/root/.npm \
    npm install -g "typescript@${TYPESCRIPT_VERSION}" "ts-node@${TS_NODE_VERSION}"

# Install JavaScript framework dependencies with npm cache mount
# hadolint ignore=DL3059
RUN --mount=type=cache,target=/root/.npm \
    /scripts/install-framework-deps.sh javascript

# Adapter environment (JavaScript adapter mounted from .cache/adapters/)
ENV AIDB_JAVASCRIPT_PATH=/root/.aidb/adapters/javascript/src/dapDebugServer.js

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD node --version && python --version

# Default command: run JavaScript tests
CMD ["pytest", "-m", "language_javascript", "-v"]
