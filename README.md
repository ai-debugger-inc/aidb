# AI Debugger

[![PyPI
version](https://badge.fury.io/py/ai-debugger-inc.svg)](https://badge.fury.io/py/ai-debugger-inc)
[![Python
versions](https://img.shields.io/pypi/pyversions/ai-debugger-inc.svg)](https://pypi.org/project/ai-debugger-inc/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/ai-debugger-inc/aidb/blob/main/LICENSE)
[![Downloads](https://static.pepy.tech/badge/ai-debugger-inc)](https://pepy.tech/project/ai-debugger-inc)
[![GitHub
stars](https://img.shields.io/github/stars/ai-debugger-inc/aidb?style=social)](https://github.com/ai-debugger-inc/aidb)

**AI-Powered Debugging for Every Language**

AI Debugger (AIDB) brings the proven Debug Adapter Protocol (DAP) ecosystem to
AI agents through a standardized Model Context Protocol (MCP) interface. Debug
Python, JavaScript, TypeScript, and Java programs using the same battle-tested
adapters that power VS Code—no IDE required, no heavyweight dependencies, just
powerful debugging at your AI assistant's fingertips.

**[Read the Docs](https://ai-debugger.com)** | **[Join
Discord](https://discord.com/invite/UGS92b6KgR)** | **[Star on
GitHub](https://github.com/ai-debugger-inc/aidb)**

______________________________________________________________________

## Quick Install

Get started with Python debugging in under 60 seconds:

```bash
pip install ai-debugger-inc
```

Add to your MCP client settings (Claude Code, Cline, Cursor, etc.):

```json
{
  "mcpServers": {
    "ai-debugger": {
      "command": "python",
      "args": ["-m", "aidb_mcp"]
    }
  }
}
```

Ask your AI assistant:

> "Initialize debugging for Python. Debug `app.py` with a breakpoint at line
> 25."

**JavaScript/Java?** [Visit the
docs](https://ai-debugger.com/en/latest/user-guide/mcp/quickstart.html) for
multi-language setup.

______________________________________________________________________

## Why AI Debugger?

### Standalone & Zero Heavy Dependencies

No VS Code required. No heavyweight IDEs. Just install with pip and you're
debugging––works on macOS, Linux, and Windows (WSL supported).

The core Python dependencies are lightweight and minimal:

```toml
dependencies = [
  "aiofiles",
  "mcp",
  "psutil"
]
```

Debug adapters are built during the release pipeline and are published as
release artifacts. Once the `ai-debugger-inc` package is installed, your agent
will use the `download` tool to fetch the appropriate adapter binaries
automatically on first run.

### Multi-Language from Day One

Debug Python, JavaScript, TypeScript, and Java with a single MCP server. AIDB is
designed to support **all** DAP-compatible adapters, with more languages coming.

### Built on the DAP Standard

AIDB uses the same Debug Adapter Protocol that powers VS Code debugging. We
integrate with proven, open-source debug adapters:

- **Python**: [debugpy](https://github.com/microsoft/debugpy) (Microsoft)
- **JavaScript/TypeScript**:
  [vscode-js-debug](https://github.com/microsoft/vscode-js-debug) (Microsoft)
- **Java**: [java-debug](https://github.com/microsoft/java-debug) (Microsoft)

This means you get reliable, well-maintained debugging that "just works" with
established patterns developers already trust.

### VS Code Integration (Without VS Code)

Already have complex debug configurations in `launch.json`? AIDB can use them
directly—making sophisticated debugging setups portable and shareable across
teams without requiring VS Code installations.

### Advanced Debugging Features

- **Framework detection**: Auto-detects pytest, jest, django, spring, flask, and
  more
- **Conditional breakpoints**: Break on `user.role == "admin"` or after N hits
- **Logpoints**: Log values without pausing execution
- **Live code patching**: Modify functions at runtime during debugging

### Future-Ready Architecture

AIDB is built for where AI-assisted development is heading:

- **CI/CD Debugging**: Imagine test failures in your pipeline automatically
  triggering debug sessions for deeper RCA
- **Agent Tooling**: Native debugging capabilities for autonomous AI agents
- **Cross-Platform Consistency**: Same debugging API across all environments

______________________________________________________________________

## How It Works

```
┌──────────────────────────────────────────────────────────────────┐
│                        Your AI Assistant                         │
│                    (Claude, GPT, Local LLMs)                     │
└────────────────────────────────┬─────────────────────────────────┘
                                 │
                                 ▼
                            MCP Protocol
┌──────────────────────────────────────────────────────────────────┐
│                      AI Debugger MCP Server                      │
│         Agent-Optimized Tools (init, step, inspect, etc.)        │
└────────────────────────────────┬─────────────────────────────────┘
                                 │
                                 ▼
                            AIDB Core API
┌──────────────────────────────────────────────────────────────────┐
│                     Debug Adapter Protocol                       │
│              Language-Agnostic Debugging Interface               │
└───────────┬────────────────────┼────────────────────┬────────────┘
            │                    │                    │
            ▼                    ▼                    ▼
    ┌───────────────┐   ┌─────────────────┐   ┌───────────────┐
    │    debugpy    │   │ vscode-js-debug │   │   java-debug  │
    │    (Python)   │   │     (JS/TS)     │   │     (Java)    │
    └───────┬───────┘   └────────┬────────┘   └───────┬───────┘
            │                    │                    │
            ▼                    ▼                    ▼
       Your Python          Your Node.js          Your Java
         Program              Program              Program
```

**The Bridge Between AI and Proven Tools**

AI Debugger acts as a translation layer, exposing the mature Debug Adapter
Protocol ecosystem to AI agents through a clean, agent-optimized MCP interface.
Your AI assistant gets powerful debugging capabilities, and you get the
reliability of debug adapters used by millions of developers worldwide.

**[Learn more about the architecture
→](https://ai-debugger.com/en/latest/developer-guide/overview.html)**

______________________________________________________________________

## Supported Languages

| Language          | Python      | JavaScript/TypeScript | Java        |
| ----------------- | ----------- | --------------------- | ----------- |
| **Status**        | ✔ Available | ✔ Available           | ✔ Available |
| **Versions**      | 3.10+       | Node 18+              | JDK 17+     |
| **Platforms**     | All         | All                   | All         |
| **Debug Adapter** | debugpy     | vscode-js-debug       | java-debug  |

**Platforms**: macOS, Linux, Windows (WSL recommended; native support in progress)

**Coming Soon**: Built to support all DAP-compatible adapters––AIDB is designed
to become the debugging standard for AI systems across every popular language
and framework.

______________________________________________________________________

## Documentation

### Getting Started

- **[Quickstart
  Guide](https://ai-debugger.com/en/latest/user-guide/mcp/quickstart.html)**
  - Install and debug in 5 minutes
- **[Core
  Concepts](https://ai-debugger.com/en/latest/user-guide/mcp/core-concepts.html)**
  - Sessions, breakpoints, execution flow
- **[Language
  Guides](https://ai-debugger.com/en/latest/user-guide/mcp/languages/python.html)**
  - Python, JavaScript, Java examples

### Technical Reference

- **[MCP Tools
  Reference](https://ai-debugger.com/en/latest/user-guide/mcp-usage.html#mcp-tools-reference)**
  - Complete tool documentation
- **[API
  Documentation](https://ai-debugger.com/en/latest/developer-guide/api/index.html)**
  - Python API reference
- **[Advanced
  Workflows](https://ai-debugger.com/en/latest/user-guide/mcp/advanced-workflows.html)**
  - Remote debugging, multi-session

### Architecture & Design

- **[How It
  Works](https://ai-debugger.com/en/latest/developer-guide/overview.html)**
  - System architecture deep dive
- **[DAP Protocol
  Guide](https://ai-debugger.com/en/latest/developer-guide/adapters.html)**
  - Debug Adapter Protocol reference

______________________________________________________________________

## Development Setup

**Prerequisites**: Python 3.10+, Docker

**Initial setup**:

```bash
bash scripts/install/src/install.sh -v
./dev-cli info
./dev-cli completion install --yes  # optional
```

**Common commands**:

```bash
./dev-cli test run --coverage
./dev-cli docs serve --build-first -p 8000
```

## Project Structure

- **`aidb/`**: Core debugging API, language adapters, session management
- **`aidb_mcp/`**: MCP server exposing debugging tools to AI agents
- **`aidb_cli/`**: Developer CLI for testing, Docker, adapter builds
- **`aidb_common/`**, **`aidb_logging/`**: Shared utilities and structured
  logging

For architecture details and implementation guidance, see the [Developer
Guide](https://ai-debugger.com/en/latest/developer-guide/).

______________________________________________________________________

## Robust Testing & Releases

AIDB is built with a comprehensive CI/CD pipeline:

- **Thorough E2E Testing**: Multi-language, multi-framework integration tests
- **Automated Releases**: Reliable version management and publishing
- **Continuous Quality**: The test suite is run nightly and on all release PRs

We catch issues early and ship features confidently, ensuring the debugging
experience you depend on stays reliable.

Our entire CI/CD release pipeline executes start to finish in under 15
minutes––a target we plan to maintain.

______________________________________________________________________

## Our Vision

**Becoming the debugging standard in the MCP tools space.**

As AI agents become more capable, they need debugging tools designed for their
workflows—not adapted from human-centric IDEs. AIDB provides a unified,
language-agnostic approach to debug any program with any AI agent through the
proven MCP standard.

We're building the future of AI-assisted debugging, one DAP adapter at a time.

______________________________________________________________________

## Contributing

We welcome contributions! See our [Contributing Guide](CONTRIBUTING.md) to get
started.

- **[Contributing Guide](CONTRIBUTING.md)** - How to contribute
- **[Code of Conduct](CODE_OF_CONDUCT.md)** - Community standards
- **[Security Policy](SECURITY.md)** - Reporting vulnerabilities

______________________________________________________________________

## Community & Support

- **Documentation**: [ai-debugger.com](https://ai-debugger.com)
- **Discord Community**: [Join the
  conversation](https://discord.com/invite/UGS92b6KgR)
- **Issues & Features**: [GitHub
  Issues](https://github.com/ai-debugger-inc/aidb/issues)

______________________________________________________________________

## License

AI Debugger is licensed under the Apache 2.0 License. See [LICENSE](LICENSE) for
details.

______________________________________________________________________

<div align="center">

**Ready to bring debugging to your AI assistant?**

[Get Started](https://ai-debugger.com/en/latest/user-guide/mcp/quickstart.html)
| [Read the Docs](https://ai-debugger.com) | [Join
Discord](https://discord.com/invite/UGS92b6KgR)

</div>
