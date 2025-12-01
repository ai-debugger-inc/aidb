ARG PYTHON_TAG
ARG PIP_VERSION=25.3
ARG SETUPTOOLS_VERSION=80.9.0
ARG WHEEL_VERSION=0.45.1

FROM ${PYTHON_TAG}

# Re-declare build args for use after FROM (Docker requirement)
ARG PIP_VERSION=25.3
ARG SETUPTOOLS_VERSION=80.9.0
ARG WHEEL_VERSION=0.45.1

# AIDB Docker labels for resource management
LABEL com.aidb.project="aidb"
LABEL com.aidb.component="docs"
LABEL com.aidb.managed="true"
LABEL com.aidb.type="image"

WORKDIR /docs

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pandoc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY docs/requirements.txt /tmp/docs-requirements.txt

# Install all dependencies in one layer
RUN pip install --upgrade --no-cache-dir \
    "pip==${PIP_VERSION}" \
    "setuptools==${SETUPTOOLS_VERSION}" \
    "wheel==${WHEEL_VERSION}" && \
    pip install --no-cache-dir \
    -r /tmp/docs-requirements.txt

ENTRYPOINT ["bash"]
