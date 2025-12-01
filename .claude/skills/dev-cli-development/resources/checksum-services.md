# Checksum Services Architecture

## Overview

AIDB uses checksum-based cache invalidation to intelligently avoid unnecessary rebuilds and reinstallations. The checksum service pattern provides a shared foundation for services that track file changes and determine when cached artifacts need regeneration.

**Key Benefits:**

- Avoid unnecessary Docker image rebuilds (saves minutes per build)
- Skip redundant dependency installations (especially important in containers)
- Container lifecycle tracking (detect when containers restart)
- Consistent hash-based decision making across all services

**For implementation examples:** See [checksum-service-implementations.md](checksum-service-implementations.md)

## ChecksumServiceBase Pattern

### Abstract Base Class

**Location:** `src/aidb_common/io/checksum_service_base.py`

Provides common functionality for tracking file checksums and managing cache files. All checksum services inherit from this base class.

**Core Responsibilities:**

- Compute and cache file hashes
- Compare current vs cached hashes
- Track artifact context (e.g., container lifecycle)
- Determine when updates are needed
- Manage cache file I/O

### Abstract Methods (Must Implement)

Subclasses must implement these three methods:

#### 1. `_get_hash_cache_file(identifier: str) -> Path`

Return the cache file path for a given identifier.

**Purpose:** Define where to store hash cache for each artifact

**Example:**

```python
def _get_hash_cache_file(self, identifier: str) -> Path:
    return self.cache_dir / f"{identifier}-image-hash"
```

#### 2. `_compute_hash(identifier: str) -> str`

Compute the current hash for a given identifier.

**Purpose:** Define what files/content to track for changes

**Example:**

```python
def _compute_hash(self, identifier: str) -> str:
    files_to_track = [Path("pyproject.toml"), Path("Dockerfile")]
    return compute_files_hash(files_to_track)
```

#### 3. `_exists(identifier: str) -> bool`

Check if the cached artifact exists.

**Purpose:** Determine if artifact needs creation vs update

**Example:**

```python
def _exists(self, identifier: str) -> bool:
    image_name = f"aidb-test-{identifier}:latest"
    result = docker_inspect(image_name)
    return result.returncode == 0
```

### Optional Override

#### `_get_artifact_context(identifier: str) -> dict[str, str]`

Return context metadata that invalidates cache when changed.

**Purpose:** Track environment-specific state (e.g., container ID)

**Default:** Returns empty dict (no context tracking)

**Example:**

```python
def _get_artifact_context(self, identifier: str) -> dict[str, str]:
    if container_marker_file.exists():
        container_id = container_marker_file.read_text().strip()
        return {"container_id": container_id}
    return {}
```

### Public API

#### `needs_update(identifier: str) -> tuple[bool, str]`

Check if cached artifact needs updating.

**Returns:** `(needs_update: bool, reason: str)`

**Possible Reasons:**

- `"Artifact '{identifier}' not found"` - Artifact doesn't exist
- `"Artifact context changed (e.g., container restart)"` - Context mismatch
- `"No cached hash found (first run)"` - No cached hash file
- `"Source files changed (hash mismatch)"` - Files changed
- `"Up-to-date"` - No update needed

**Decision Logic:**

1. Check if artifact exists → if not, return `(True, "not found")`
1. Compare artifact context → if changed, return `(True, "context changed")`
1. Compare file hashes → if different, return `(True, "hash mismatch")`
1. Otherwise → return `(False, "up-to-date")`

**Example:**

```python
service = DockerImageChecksumService(repo_root)
needs_rebuild, reason = service.needs_update("python")
if needs_rebuild:
    print(f"Rebuild required: {reason}")
    # Build image...
    service.mark_updated("python")
```

#### `mark_updated(identifier: str) -> None`

Mark artifact as updated by saving current hash.

**Purpose:** Update cache after successful artifact generation

**What it does:**

1. Compute current hash
1. Get current artifact context
1. Save both to cache file

**Example:**

```python
# After successfully building Docker image
service.mark_updated("python")
```

## Cache File Format

### Two-Line Format

```
<sha256_hash>
{"container_id": "abc123", "other_context": "value"}
```

**Line 1:** SHA256 hash of tracked files (hex digest)
**Line 2:** JSON object with context metadata (optional)

### Examples

**Without context:**

```
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

**With container context:**

```
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
{"container_id": "aidb-test-python-abc123"}
```

### File I/O

**Reading:**

```python
def _get_cached_hash(self, identifier: str) -> str | None:
    content = read_cache_file(cache_file)
    if not content:
        return None
    lines = content.strip().split("\n")
    return lines[0] if lines else None
```

**Writing:**

```python
def _save_hash(self, identifier: str, hash_value: str) -> None:
    content = hash_value + "\n"
    context = self._get_artifact_context(identifier)
    if context:
        content += json.dumps(context) + "\n"
    write_cache_file(cache_file, content.strip())
```

## Concrete Implementations

AIDB includes two concrete checksum service implementations:

1. **DockerImageChecksumService** - Tracks Docker test image rebuilds
1. **FrameworkDepsChecksumService** - Tracks framework dependency installations with container lifecycle awareness

**See:** [checksum-service-implementations.md](checksum-service-implementations.md) for detailed documentation, usage examples, and integration patterns

## Creating a New Checksum Service

### Step-by-Step Guide

1. **Identify what to track:**

   - What files affect the artifact?
   - Does the artifact actually exist (image) or is it ephemeral (dependencies)?
   - Does environment context matter (container ID, runtime version)?

1. **Create service class:**

```python
from pathlib import Path
from aidb_common.io import ChecksumServiceBase, compute_files_hash

class MyChecksumService(ChecksumServiceBase):
    def __init__(self, repo_root: Path):
        cache_dir = repo_root / ".cache" / "my-service"
        super().__init__(cache_dir)
        self.repo_root = repo_root

    def _get_hash_cache_file(self, identifier: str) -> Path:
        return self.cache_dir / f"{identifier}-hash"

    def _compute_hash(self, identifier: str) -> str:
        files_to_track = [
            self.repo_root / "relevant-file.txt",
            self.repo_root / "another-file.yaml",
        ]
        return compute_files_hash(files_to_track)

    def _exists(self, identifier: str) -> bool:
        # Check if artifact exists
        artifact_path = self.repo_root / "artifacts" / identifier
        return artifact_path.exists()

    # Optional: Track context
    def _get_artifact_context(self, identifier: str) -> dict[str, str]:
        # Example: Track Python version
        import sys
        return {"python_version": f"{sys.version_info.major}.{sys.version_info.minor}"}
```

3. **Add public convenience methods:**

```python
    def needs_regeneration(self, identifier: str) -> tuple[bool, str]:
        """Alias for needs_update with domain-specific name."""
        return self.needs_update(identifier)

    def mark_generated(self, identifier: str) -> None:
        """Alias for mark_updated with domain-specific name."""
        self.mark_updated(identifier)
```

4. **Use the service:**

```python
service = MyChecksumService(Path("/repo"))
needs_regen, reason = service.needs_regeneration("my-artifact")
if needs_regen:
    # Generate artifact...
    service.mark_generated("my-artifact")
```

### Best Practices

**✅ DO:**

- Use descriptive identifier names (e.g., "python-image" not "py")
- Log hash values (first 8-12 chars) for debugging
- Handle missing files gracefully in `_compute_hash()`
- Validate cache directory exists (base class handles this)
- Use `compute_files_hash()` for consistent hashing

**❌ DON'T:**

- Include volatile data in hash computation (timestamps, random values)
- Track files that change frequently without affecting artifact (logs, temp files)
- Forget to call `mark_updated()` after successful artifact creation
- Assume cache files exist (base class handles missing files)
- Mix artifact types in same service (create separate services)

## Performance Considerations

### Hash Computation Cost

- **Small files (\<1MB)**: ~1-5ms per file
- **Large files (>10MB)**: ~50-100ms per file
- **Many files (>100)**: Consider caching or sampling

**Optimization tips:**

- Cache hash computation results within same process
- Only track files that actually affect artifact
- Use glob patterns efficiently (avoid recursive scans)
- Consider file modification time as quick pre-check

### Cache File I/O

- **Read cost**: ~0.1-1ms per cache file
- **Write cost**: ~1-5ms per cache file (includes ensure_dir)
- **Negligible** compared to artifact generation (seconds to minutes)

### When to Use Checksums

**✅ Good use cases:**

- Docker image builds (minutes saved)
- Dependency installations (10s-100s saved)
- Code generation (seconds saved)
- File transformations (compilation, transpilation)

**❌ Poor use cases:**

- Operations already \<100ms (overhead not worth it)
- Volatile inputs (constant cache misses)
- Write-once artifacts (no benefit from caching)

## Related Files

**Base Pattern:**

- `src/aidb_common/io/checksum_service_base.py` - Abstract base class
- `src/aidb_common/io/hashing.py` - `compute_files_hash()` utility
- `src/aidb_common/io/files.py` - Cache file I/O utilities (`read_cache_file()`, `write_cache_file()`, `ensure_dir()`)

**Implementations:** See [checksum-service-implementations.md](checksum-service-implementations.md)

**Further Reading:**

- [checksum-service-implementations.md](checksum-service-implementations.md) - DockerImageChecksumService and FrameworkDepsChecksumService details
- [docker-compose-generation.md](docker-compose-generation.md) - Compose generation system
- [service-patterns.md](service-patterns.md) - Service architecture patterns
