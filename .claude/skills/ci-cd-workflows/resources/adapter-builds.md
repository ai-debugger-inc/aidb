# Adapter Builds

Debug adapter build workflows, artifact management, and platform matrix.

**Workflow:** `.github/workflows/adapter-build.yaml`

## Adapters

| Adapter             | Upstream                  | Languages              |
| ------------------- | ------------------------- | ---------------------- |
| **debugpy**         | microsoft/debugpy         | Python                 |
| **vscode-js-debug** | microsoft/vscode-js-debug | JavaScript, TypeScript |
| **java-debug**      | microsoft/java-debug      | Java                   |

**Platforms:** linux (x64, arm64), darwin (x64, arm64), windows (x64)

## Triggers

1. `release:published` - Automatically builds when release creates a release
1. `workflow_dispatch` - Manual dispatch

**Note:** This workflow does NOT create releases. It attaches adapters to releases created by the main release workflow.

## Execution Flow

```
Release published (0.1.0)
    ↓
Generate matrix from versions.json
    ↓
Build adapters in parallel (per adapter × platform × arch)
    ↓
Upload artifacts per matrix job
    ↓
Consolidate artifacts + generate manifest.json
    ↓
Upload to existing release
```

## Matrix Generation

Script `.github/scripts/utils/matrix_generator.py` reads `versions.json` and generates adapter × platform × arch combinations. Java uses universal build (platform-independent).

## Build Scripts

- **Orchestrator:** `.github/scripts/build-adapter.py`
- **Modular builders:** `.github/scripts/adapters/builders/{python,javascript,java}.py`

Each builder: fetches sources → runs build → packages tarball → generates SHA256 checksum.

## Artifact Retention

| Type                                   | Retention | Purpose           |
| -------------------------------------- | --------- | ----------------- |
| `debug-adapters`, `docker-test-images` | 1 day     | CI testing        |
| Per-matrix artifacts                   | 30 days   | Build validation  |
| `adapter-artifacts-all`                | 7 days    | Release debugging |
| GitHub Release assets                  | Permanent | User downloads    |

## Local Builds with act

**Workflow:** `.github/workflows/adapter-build-act.yaml`

```bash
# Build for container platform (linux)
./dev-cli adapters build --local

# Build for host platform (e.g., macOS arm64)
./dev-cli adapters build --local --use-host-platform
```

Host platform override sets: `AIDB_USE_HOST_PLATFORM=1`, `AIDB_BUILD_PLATFORM`, `AIDB_BUILD_ARCH`

## Configuration (versions.json)

```json
{
  "adapters": {
    "javascript": {
      "version": "v1.104.0",
      "repo": "microsoft/vscode-js-debug",
      "build_deps": {
        "node_version": "18"
      }
    },
    "java": {
      "version": "0.53.1",
      "repo": "microsoft/java-debug",
      "build_deps": {
        "java_version": "21"
      }
    },
    "python": {
      "version": "1.8.0",
      "repo": "microsoft/debugpy"
    }
  },
  "platforms": [
    {
      "os": "ubuntu-latest",
      "platform": "linux",
      "arch": "x64"
    }
  ]
}
```

## Troubleshooting

**Build failures:**

- Verify `versions.json` adapter versions
- Check upstream repository accessibility
- Match build dependencies (Node 18 for JS, JDK 21 for Java)

**Local build issues:**

- Use `--use-host-platform` for platform mismatch
- Verify `.github/actrc` configuration
- Check container is running (`--reuse` flag for extraction)

**Artifact issues:**

- Check workflow logs for upload errors
- Verify storage limits (2GB/file, 10GB total)

## Performance

- npm cache: ~5-10 min saved per JS build
- Maven cache: ~3-5 min saved per Java build
- Total time = longest single build (~10-15 min with parallelization)

## References

- `.github/workflows/adapter-build.yaml` - Production builds
- `.github/workflows/adapter-build-act.yaml` - Local builds
- `.github/scripts/build-adapter.py` - Build orchestrator
- `versions.json` - Adapter versions and platforms
- `docs/developer-guide/ci-cd.md` - Complete CI/CD reference
