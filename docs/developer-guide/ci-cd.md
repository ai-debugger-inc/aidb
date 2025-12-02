# CI/CD Reference

CI/CD infrastructure for AIDB: testing, releases, and adapter builds.

## Quick Reference

| Task | Command/Action |
|------|----------------|
| Run tests | Push PR to `main` (auto-triggers `test-parallel.yaml`) |
| Cut release | Create `release/X.Y.Z` branch, open PR to `main` |
| Build adapters locally | `./dev-cli adapters build` |
| Run local CI | Install `act`, then `./dev-cli adapters build` |

## Workflows Overview

All workflows in `.github/workflows/`. Configuration in `versions.json` (single source of truth).

### Testing (`test-parallel.yaml`)

- **Triggers**: PRs/pushes to `main`/`develop`
- **Duration**: ~10-15 min (parallel execution)
- **Jobs**: MCP tests, AIDB core, Infrastructure (CLI/Logging/Common), Adapter frameworks (Python/JS/Java)

### Release (`release-pr.yaml` + `release-publish.yaml`)

- **Trigger**: PR from `release/X.Y.Z` to `main`
- **Process**: Validate → Test → Build → TestPyPI → ProdPyPI → Draft Release → Adapters
- **On merge**: Draft release published automatically

### Adapter Builds (`adapter-build.yaml`)

- **Trigger**: Release published, or manual dispatch
- **Platforms**: Python/JS (linux+darwin × x64+arm64), Java (universal)
- **Local**: `./dev-cli adapters build`

## Cutting a Release

### Prerequisites

- All tests passing on `main`
- Release notes prepared

### Steps

```bash
# 1. Create release branch
git checkout main && git pull
git checkout -b release/X.Y.Z

# 2. Create release notes
cp docs/release-notes/template.md docs/release-notes/X.Y.Z.md
# Edit with features, changes, fixes

# 3. Commit and push
git add docs/release-notes/X.Y.Z.md
git commit -m "chore: prepare release X.Y.Z"
git push origin release/X.Y.Z

# 4. Open PR to main
# → CI/CD runs automatically
# → Draft release created with all artifacts

# 5. Review draft release, then merge PR
# → Release published automatically
```

### Post-Release

- Verify: `pip install --upgrade ai-debugger-inc==X.Y.Z`
- Check GitHub release page
- Announce in Discord

## Configuration Files

| File | Purpose |
|------|---------|
| `versions.json` | Adapter versions, platforms, infrastructure versions |
| `.github/testing-config.yaml` | Framework testing, suite configuration |
| `.github/config/adapter-sources.yaml` | Upstream adapter repos for watchdog |

## Required Secrets

| Secret | Purpose |
|--------|---------|
| `GITHUB_TOKEN` | Auto-provided by GitHub Actions |
| `PYPI_TOKEN` | Production PyPI upload |
| `TESTPYPI_TOKEN` | Test PyPI upload |
| `ANTHROPIC_API_KEY` | Adapter watchdog LLM analysis |

## Local CI with Act

```bash
# Install act (https://github.com/nektos/act)
brew install act  # macOS

# Build adapters locally
./dev-cli adapters build                      # All adapters
./dev-cli adapters build --use-host-platform  # Host platform only
./dev-cli adapters build -l java              # Specific adapter
```

## Troubleshooting

### Transient Network Failures (502, connection reset, etc.)

Docker image builds and adapter builds include automatic retry logic (3 attempts with 30s delays) to handle transient infrastructure failures. If a build fails after all retries:

1. Check [GitHub Status](https://www.githubstatus.com/) for outages
2. Re-run the failed job manually
3. If persistent, check GitHub Actions cache/storage quotas

### Release Notes Not Found

```bash
cp docs/release-notes/template.md docs/release-notes/X.Y.Z.md
# Edit, commit, push
```

### PyPI Upload Failed (version exists)

PyPI versions are immutable. Increment version and create new release branch.

### Tests Failing

```bash
# Run same commands locally
./dev-cli test run -s mcp --coverage
./dev-cli test run -s shared -v
```

## CD_SKIP_PYPI Testing Mode

Set repository variable `CD_SKIP_PYPI=true` to validate entire workflow without PyPI uploads. Useful for first-time release validation or testing workflow changes.
