# Checksum Service Implementations

**Purpose:** Detailed documentation for concrete checksum service implementations in AIDB.

**See also:** [checksum-services.md](checksum-services.md) for architecture patterns and creating new services.

______________________________________________________________________

## DockerImageChecksumService

**Location:** `src/aidb_cli/services/docker/docker_image_checksum_service.py`

**Purpose:** Track when Docker images need rebuilding based on dependency file changes.

### Tracked Images

- `base` - Base test image (Python + core dependencies)
- `python` - Python-specific test image
- `javascript` - JavaScript/Node.js test image
- `java` - Java test image

### Tracked Files per Image

```python
IMAGE_DEPENDENCIES = {
    "base": [
        versions.json,
        pyproject.toml,
        Dockerfile.test.base,
        entrypoint.sh,
        install-framework-deps.sh,
    ],
    "python": [
        versions.json,
        pyproject.toml,
        Dockerfile.test.base,
        Dockerfile.test.python,
    ],
    "javascript": [
        versions.json,
        pyproject.toml,
        Dockerfile.test.base,
        Dockerfile.test.javascript,
    ],
    "java": [
        versions.json,
        pyproject.toml,
        Dockerfile.test.base,
        Dockerfile.test.java,
    ],
}
```

### Cache Location

`.cache/docker-build/{image_type}-image-hash`

### Usage Example

```python
from pathlib import Path
from aidb_cli.services.docker import DockerImageChecksumService

service = DockerImageChecksumService(Path("/repo"), command_executor)

# Check if Python image needs rebuilding
needs_rebuild, reason = service.needs_rebuild("python")
if needs_rebuild:
    print(f"Rebuilding Python image: {reason}")
    # docker build...
    service.mark_built("python")
else:
    print(f"Python image is up-to-date: {reason}")

# Check all images
status = service.check_all_images()
for image_type, (rebuild, reason) in status.items():
    print(f"{image_type}: rebuild={rebuild}, reason={reason}")
```

### Public API

- `needs_rebuild(image_type: str) -> tuple[bool, str]` - Alias for `needs_update()`
- `mark_built(image_type: str)` - Alias for `mark_updated()`
- `check_all_images() -> dict[str, tuple[bool, str]]` - Check all image types

### Artifact Existence Check

```python
def _exists(self, image_type: str) -> bool:
    image_name = f"aidb-test-{image_type}:latest"
    result = self.command_executor.execute(
        ["docker", "image", "inspect", image_name],
        check=False,
        capture_output=True,
    )
    return result.returncode == 0
```

______________________________________________________________________

## FrameworkDepsChecksumService

**Location:** `src/aidb_cli/services/docker/framework_deps_checksum_service.py`

**Purpose:** Track when framework app dependencies need reinstallation based on dependency file changes.

### Why This Service Exists

**Problem:** After container restart...

- Hash cache files persist on host (via bind mount)
- Installed packages are GONE (ephemeral container filesystem)
- Without container tracking, service reports "up-to-date" incorrectly

**Solution:** Track container ID in context metadata

### Tracked Dependency Files per Language

```python
DEPENDENCY_PATTERNS = {
    "javascript": ["package.json", "package-lock.json", "yarn.lock"],
    "python": ["requirements.txt", "pyproject.toml", "setup.py"],
    "java": ["pom.xml", "build.gradle", "build.gradle.kts"],
}
```

### Cache Location

`src/tests/_assets/framework_apps/.cache/.deps-hash-{lang}-{app}`

### Container Lifecycle Tracking

Reads container ID from marker file created at startup:

```python
def _get_artifact_context(self, identifier: str) -> dict[str, str]:
    if DockerConstants.CONTAINER_MARKER_FILE.exists():
        container_id = DockerConstants.CONTAINER_MARKER_FILE.read_text().strip()
        return {"container_id": container_id}
    return {}
```

**What is CONTAINER_MARKER_FILE?**

Located at `/tmp/.container-id` in containers, created by entrypoint script:

```bash
# entrypoint.sh
echo "${HOSTNAME}" > /tmp/.container-id
```

When container restarts, hostname changes → context changes → cache invalidated.

### Artifact Existence

```python
def _exists(self, identifier: str) -> bool:
    # Always return True for dependencies
    # We check hash changes, not artifact existence
    return True
```

**Why always True?** Unlike Docker images (which either exist or don't), dependencies are files that might be partially installed. We rely on hash+context to determine reinstallation, not existence.

### Usage Example

```python
from pathlib import Path
from aidb_cli.services.docker import FrameworkDepsChecksumService

framework_root = Path("/repo/src/tests/_assets/framework_apps")
service = FrameworkDepsChecksumService(framework_root)

# Check if express_app dependencies need installation
needs_install, reason = service.needs_install("javascript", "express_app")
if needs_install:
    print(f"Installing express_app: {reason}")
    # npm install...
    service.mark_installed("javascript", "express_app")
else:
    print(f"express_app is up-to-date: {reason}")

# Check all JavaScript apps
status = service.check_all_apps("javascript")
for app_name, (install, reason) in status.items():
    print(f"{app_name}: install={install}, reason={reason}")
```

### Public API

- `needs_install(language: str, app_name: str) -> tuple[bool, str]` - Alias for `needs_update()`
- `mark_installed(language: str, app_name: str)` - Alias for `mark_updated()`
- `check_all_apps(language: str) -> dict[str, tuple[bool, str]]` - Check all apps for language

### Integration with install-framework-deps.sh

The bash script calls Python service to check/mark:

```bash
check_needs_install() {
    python3 <<EOF
from aidb_cli.services.docker.framework_deps_checksum_service import FrameworkDepsChecksumService
service = FrameworkDepsChecksumService(Path("${FRAMEWORK_ROOT}"))
needs_install, reason = service.needs_install("${language}", "${app_name}")
sys.exit(0 if needs_install else 1)
EOF
}

mark_installed() {
    python3 <<EOF
service = FrameworkDepsChecksumService(Path("${FRAMEWORK_ROOT}"))
service.mark_installed("${language}", "${app_name}")
EOF
}
```

______________________________________________________________________

## Integration Examples

### DockerBuildService Integration

```python
class DockerBuildService:
    def __init__(self, repo_root: Path, executor: CommandExecutor):
        self.checksum_service = DockerImageChecksumService(repo_root, executor)

    def build_images(self, image_types: list[str], no_cache: bool = False):
        for image_type in image_types:
            needs_rebuild, reason = self.checksum_service.needs_rebuild(image_type)

            if needs_rebuild or no_cache:
                logger.info("Building %s image: %s", image_type, reason)
                # docker build...
                self.checksum_service.mark_built(image_type)
            else:
                logger.info("Skipping %s image: %s", image_type, reason)
```

### Test Infrastructure Integration

```bash
# install-framework-deps.sh
for dir in "${language_dir}/"*/; do
    app_name=$(basename "${dir}")

    # Use Python checksum service
    if check_needs_install "${language}" "${app_name}"; then
        # Install dependencies
        npm install --prefix "${dir}"
        # Mark as installed
        mark_installed "${language}" "${app_name}"
    else
        echo "✓ ${app_name} (up-to-date)"
    fi
done
```

______________________________________________________________________

## Cache Locations

Summary of all checksum cache locations:

| Service                      | Cache Directory                            | File Pattern              | Example                                                                     |
| ---------------------------- | ------------------------------------------ | ------------------------- | --------------------------------------------------------------------------- |
| ComposeGeneratorService      | `.cache/`                                  | `compose-generation-hash` | `.cache/compose-generation-hash`                                            |
| DockerImageChecksumService   | `.cache/docker-build/`                     | `{type}-image-hash`       | `.cache/docker-build/python-image-hash`                                     |
| FrameworkDepsChecksumService | `src/tests/_assets/framework_apps/.cache/` | `.deps-hash-{lang}-{app}` | `src/tests/_assets/framework_apps/.cache/.deps-hash-javascript-express_app` |

**Why different locations?**

- Compose cache: Build-related, repo root
- Docker image cache: Build-related, repo root
- Framework deps cache: Test-related, persists in bind mount to container

______________________________________________________________________

## Implementation-Specific Troubleshooting

### Issue: Service reports "up-to-date" but artifact is missing

**Cause:** Artifact was deleted but cache file still exists

**Solutions:**

1. Delete cache file: `rm .cache/docker-build/{type}-image-hash`
1. Force rebuild: Pass `force=True` or `no_cache=True` flag
1. Check `_exists()` implementation is correct

### Issue: Constant rebuilds even when nothing changed

**Cause:** Hash computation is non-deterministic or volatile data included

**Solutions:**

1. Check tracked files are sorted (glob order matters)
1. Don't include timestamps or random data in hash
1. Verify file paths are absolute and correct
1. Check for symlinks (hash content, not link target)

### Issue: Container restart not invalidating deps cache

**Cause:** Container lifecycle tracking not working

**Solutions:**

1. Check container marker file exists: `/tmp/.container-id`
1. Verify entrypoint.sh creates marker: `echo "$(hostname)" > /tmp/.container-id`
1. Check `_get_artifact_context()` reads marker correctly
1. Verify cache file has context on line 2

### Issue: "No module named 'aidb_cli'" in bash script

**Cause:** PYTHONPATH not set correctly in container

**Solutions:**

1. Ensure `PYTHONPATH=/workspace/src:/workspace` in environment
1. Verify `sys.path.insert(0, "/workspace/src")` in bash heredoc
1. Check editable install: `pip install -e .`

______________________________________________________________________

## Related Files

**Implementations:**

- `src/aidb_cli/services/docker/docker_image_checksum_service.py`
- `src/aidb_cli/services/docker/framework_deps_checksum_service.py`
- `src/aidb_cli/services/docker/compose_generator_service.py` (uses pattern directly)

**Integration:**

- `src/aidb_cli/services/docker/docker_build_service.py` - Uses DockerImageChecksumService
- `src/tests/_docker/scripts/install-framework-deps.sh` - Uses FrameworkDepsChecksumService

**Container Setup:**

- `src/tests/_docker/scripts/entrypoint.sh` - Creates container marker
- `src/aidb_cli/core/paths.py` - DockerConstants.CONTAINER_MARKER_FILE

**Architecture:**

- See [checksum-services.md](checksum-services.md) for base pattern and creating new services
- See [docker-compose-generation.md](docker-compose-generation.md) for compose generation system
- See [service-patterns.md](service-patterns.md) for service architecture patterns
