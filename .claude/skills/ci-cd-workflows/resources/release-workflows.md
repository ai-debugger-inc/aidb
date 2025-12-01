# Release Workflows

This document provides a high-level overview of AIDB's release processes. For complete implementation details, troubleshooting, and step-by-step guides, see `docs/developer-guide/ci-cd.md`.

## Overview

AIDB uses a **PR-based release workflow** with automatic CI/CD gating. All validation happens before any uploads to PyPI.

**Key Workflows:**

1. **pr-release.yaml** - Main release orchestration (PR to main from release/\*)
1. **publish-release.yaml** - Publish draft releases on PR merge

## Quick Reference

**Release Branch Pattern:** `release/X.Y.Z`

**Tag Convention:**

- Production releases only: bare X.Y.Z format (e.g., 1.0.0, 2.1.3). No prefixes, no suffixes.

**Workflow Trigger:**

```yaml
on:
  pull_request:
    branches: [main]
    # Source branch must match release/** pattern
```

**Pipeline:**
See `docs/developer-guide/ci-cd.md` for complete job list and descriptions.

## CD_SKIP_PYPI Testing Mode

**Purpose:** Validate release workflow without uploading to PyPI

**Set via:** Repository variable `CD_SKIP_PYPI=true`

**What's Skipped:**

- TestPyPI upload (`twine` command only)
- ProdPyPI upload (`twine` command only)
- PyPI smoke tests

**What Still Runs:**

- All tests and builds
- Draft release creation
- Adapter builds and uploads

**Use Cases:**

- Initial workflow validation
- Testing workflow changes
- Training and familiarization

## Composite Actions

New reusable actions for release workflow:

- **extract-version** - Parse `release/X.Y.Z` branch names and validate versions
- **smoke-test** - Verify PyPI package functionality with retry logic

See [Quick Reference](quick-reference.md#composite-actions) for action list and `.github/actions/` for implementations.

## Version Management

**Detection Priority:**

1. Release branch name: `release/X.Y.Z` → version `X.Y.Z`
1. Validate semantic versioning: `X.Y.Z`

**Tag Generation:**

- Production releases: bare version format (e.g., 1.0.0, 2.1.3)

**Release Notes:**

- Required at: `docs/release-notes/{version}.md`
- Validation: minimum 5 lines, standard sections recommended

## Release Process (Quick Summary)

1. Create release branch: `release/X.Y.Z`
1. Create release notes: `docs/release-notes/X.Y.Z.md`
1. Open PR to `main` → triggers comprehensive release workflow
1. Review workflow results and draft release
1. Merge PR → draft becomes published release

**For detailed step-by-step guide**, see `docs/developer-guide/ci-cd.md`.

## Execution Flow

```
PR opened (release/X.Y.Z → main)
    ↓
[0] Load infrastructure versions (single load, passed to all jobs)
    ↓
[1] Validate version & release notes
    ↓
    ├──────────────────────────────────────┐
    ↓                                      ↓
[2] Run test suite (parallel)    [3] Build VS Code extension (VSIX)
    │                                      ↓
    │                            [4] Build Python wheel
    │                                      │
    └──────────────────┬───────────────────┘
                       ↓
[5] Upload to TestPyPI → Smoke test (retry logic)
    ↓
[6] Upload to ProdPyPI → Smoke test (only if TestPyPI passed)
    ↓
[7] Create draft GitHub release
    ↓
[8] Generate dynamic adapter matrix from versions.json
    ↓
[9] Build adapters (parallel: Python/JS/Java × platforms)
    ↓
[10] Consolidate adapters + verify checksums
    ↓
[11] Upload adapters to draft release
    ↓
PR merged → Draft becomes published (via publish-release.yaml)
```

## Complete Documentation

For comprehensive details, see:

**Primary:** `docs/developer-guide/ci-cd.md`

- Complete pipeline documentation with detailed job list
- Step-by-step release guide
- Troubleshooting section
- Secret configuration
- Error handling

**Related:**

- [Quick Reference](quick-reference.md#composite-actions) - Composite action list
- [Adapter Builds](adapter-builds.md) - Adapter build process and matrix generation
- [Test Orchestration](test-orchestration.md) - Test suite architecture
- [Troubleshooting](troubleshooting.md) - General CI/CD troubleshooting

## Quick Commands

```bash
# Create release branch
git checkout -b release/X.Y.Z

# Create release notes
echo "## Features\n- Feature description" > docs/release-notes/X.Y.Z.md

# Open PR to main
git add . && git commit -m "chore: prepare release X.Y.Z"
git push origin release/X.Y.Z

# Create PR in GitHub UI → Workflow runs automatically
# Review draft release → Merge PR → Release published
```

## Workflow Files

- `.github/workflows/release-pr.yaml` - Main release orchestration
- `.github/workflows/release-publish.yaml` - Publish draft on merge
- `.github/actions/extract-version/` - Version extraction action
- `.github/actions/smoke-test/` - PyPI smoke test action
