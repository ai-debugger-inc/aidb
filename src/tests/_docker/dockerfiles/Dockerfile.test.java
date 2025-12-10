# Language-specific test image for Java
# Optimized for Java framework testing with minimal size
# NOTE: Inherits from aidb-test-base which provides Python 3.12 + common dependencies
# NOTE: Version should match versions.json infrastructure.java.version (21)

# Parametrize base image for CI flexibility (local: aidb-test-base:latest, CI: GHCR)
# hadolint ignore=DL3006
ARG AIDB_TEST_BASE_IMAGE=aidb-test-base:latest
FROM ${AIDB_TEST_BASE_IMAGE}

# AIDB Docker labels
LABEL com.aidb.language="java"

# Java version ARG - should match versions.json infrastructure.java.version
ARG JAVA_VERSION=21

# Install Java runtime and Maven with apt cache mount
RUN --mount=type=cache,target=/var/cache/apt \
    --mount=type=cache,target=/var/lib/apt \
    apt-get update && apt-get install -y --no-install-recommends \
    openjdk-${JAVA_VERSION}-jdk-headless \
    maven \
    wget

# Install Eclipse JDT Language Server
# NOTE: Version should match versions.json adapters.java.jdtls_version
ARG JDTLS_VERSION=1.55.0-202511271007
RUN mkdir -p /opt/jdtls && \
    curl -fsSL -o /tmp/jdtls.tar.gz \
        "https://download.eclipse.org/jdtls/snapshots/jdt-language-server-${JDTLS_VERSION}.tar.gz" && \
    tar -xzf /tmp/jdtls.tar.gz -C /opt/jdtls && \
    rm -f /tmp/jdtls.tar.gz

# Install Java framework dependencies with Maven and Gradle cache mounts
RUN --mount=type=cache,target=/root/.m2/repository \
    --mount=type=cache,target=/root/.gradle \
    /scripts/install-framework-deps.sh java

# Adapter environment (Java adapter mounted from .cache/adapters/)
ENV AIDB_JAVA_PATH=/root/.aidb/adapters/java/java-debug.jar
ENV JDT_LS_HOME=/opt/jdtls

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD java -version && python --version

# Default command: run Java tests
CMD ["pytest", "-m", "language_java", "-v"]
