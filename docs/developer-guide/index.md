---
myst:
  html_meta:
    description lang=en: Developer guide for contributing to AI Debugger - architecture, development setup, and workflows.
---

# Developer Guide

Comprehensive guide for contributing to AI Debugger.

## Documentation

```{toctree}
---
maxdepth: 2
---
getting-started
overview
cli-reference
ci-cd
adapters
cli-docs
api/index
```

## Quick Links

| Topic | Description |
|-------|-------------|
| [Getting Started](getting-started.md) | Setup, prerequisites, daily development |
| [Architecture](overview.md) | System design and data flow |
| [CLI Reference](cli-reference.md) | Developer CLI commands |
| [CI/CD](ci-cd.md) | Testing, releases, and workflows |
| [Adding Adapters](adapters.md) | Guide for implementing new language adapters |
| [CLI Docs (Auto)](cli-docs.md) | Auto-generated CLI command docs (sphinx-click) |
| [API Reference](api/index.rst) | Auto-generated Python API docs (autoapi) |

## Key Resources

- **Main README**: Project overview and quick start
- **Source Code**: `src/` directory
- **Tests**: `src/tests/` directory
- **CI/CD Workflows**: `.github/workflows/`
