---
myst:
  html_meta:
    description lang=en: |
      AI Debugger MCP - A lightweight Python API for AI-assisted debugging workflows.
html_theme.sidebar_secondary.remove: true
---

# AI Debugger MCP

A lightweight, language-agnostic Python API that enables AI systems to
programmatically control and introspect live debugging sessions through the
Debug Adapter Protocol (DAP).

```{gallery-grid}
---
grid-columns: 1 2 2 3
---
- header: "{fas}`bug;pst-color-primary` Debug Adapter Protocol"
  content: "Leverage the standardized DAP for consistent debugging across languages and IDEs."
- header: "{fab}`python;pst-color-primary` Multi-Language Support"
  content: "Debug Python, JavaScript, Java and more with language-specific adapters."
- header: "{fas}`robot;pst-color-primary` AI-Powered Debugging"
  content: "Enable AI systems to programmatically control and introspect debugging sessions."
- header: "{fas}`bolt;pst-color-primary` MCP Integration"
  content: "Built as a Model Context Protocol (MCP) tool for seamless AI integration."
- header: "{fas}`code;pst-color-primary` Lightweight API"
  content: "Simple Python API that works at human debugging cadence with proper session management."
- header: "{fab}`github;pst-color-primary` Open Source"
  content: "Open source project with [community support](https://github.com/ai-debugger-inc/aidb)."
```

## Quick Install

Get started with Python debugging in under 60 seconds:

```bash
pip install ai-debugger-inc
```

Add to your MCP client settings (Claude Code, Cline, Cursor, etc.):

```json
{
  "mcpServers": {
    "aidb-debug": {
      "command": "python",
      "args": ["-m", "aidb_mcp"]
    }
  }
}
```

Ask your AI assistant:

> "Initialize debugging for Python. Debug `app.py` with a breakpoint at line 25."

**JavaScript/Java?** See [Multi-Language Setup](user-guide/mcp/quickstart) for additional language configuration.

## Open Source

AI Debugger is free and open source under the Apache 2.0 license. All features are available to everyone at no cost.

```{button-ref} user-guide/mcp-usage
---
color: primary
---
Get Started
```

```{button-link} https://github.com/ai-debugger-inc/aidb
---
color: secondary
outline:
---
View on GitHub
```

## Key Features

AI Debugger provides a comprehensive debugging platform designed for AI-assisted workflows with enterprise-grade reliability.

### Core Debugging Capabilities

**Comprehensive Core DAP Coverage**
- Fully DAP compliant for core debugging operations with industry-standard adapters
- Multi-language support: Python, JavaScript/TypeScript, Java (expanding to all major languages)
- Essential debugging operations: execution control, stepping, introspection, variable manipulation, breakpoint management

**Advanced Breakpoint Features**
- Sophisticated hit conditions with 7 modes (`>`, `>=`, `=`, `<`, `<=`, `%`, `exact`) - pause on "5th hit" or "every 10th iteration"
- Non-intrusive logpoints with template syntax (e.g., `"User: {user.name}, Status: {status}"`) for production debugging
- Column-level breakpoints for debugging minified JavaScript/TypeScript
- Real-time verification and state tracking (PENDING, VERIFIED, UNVERIFIED, ERROR)

### AI-Optimized Design

**Intelligent MCP Server**
- Context-aware next steps with 14 scenario-specific guides showing AI agents what to do next
- Responses are size-optimized to be as compact as possible, reserving context usage for your core work
- Variable change tracking with 50-entry history answering "what changed?"
- Error recovery with actionable guidance for autonomous agent recovery

**Developer Experience**
- Remote & attach mode debugging (PID, host:port, Docker containers) without restarts
- Streamlined adapter installation with one-command setup (manual and offline install supported)
- Framework-aware configuration for popular test runners and web frameworks

### IDE & Workflow Integration

**VS Code Ecosystem**
- Full `launch.json` support with variable substitution (`${workspaceFolder}`, `${file}`, etc.)
- Language-specific configuration translation for all supported languages
- Zero duplicate configuration - leverage existing workspace settings

**Framework Support**
- Python: `pytest`, `django`, `flask`, `fastapi`, `pyramid`, `asyncio`, `behave`
- JavaScript/TypeScript: `jest`, `mocha`, `node`, `express`, `typescript`
- Java: JUnit, Spring, Maven, Gradle
- Browser frameworks (React, Angular, Vue, Next.js): via `pwa-chrome` adapter - examples coming soon

### Production Features

**Quality & Reliability**
- Comprehensive E2E test coverage
- Shared cross-language test framework validating identical operations across all supported languages
- Health monitoring and automatic session recovery for long-running debugging

**Compliance & Security**
- Enterprise audit logging with configurable data masking for sensitive information
- Retention policies and log rotation (default: 30 days)
- DAP protocol logging for compliance requirements
- No external telemetry - all data stays local
- See [Security & Audit Logging](#security-audit-logging) for configuration details

(security-audit-logging)=

### Security & Audit Logging

AI Debugger provides enterprise-grade audit logging and security features for compliance-sensitive environments.

**Audit Logging Features:**
- **Comprehensive event tracking** - All debugging operations, breakpoints, variable access, and session lifecycle events
- **Configurable data masking** - Automatically mask sensitive data in audit logs (credentials, API keys, PII)
- **Retention policies** - Automatic log rotation with configurable retention periods
- **No external telemetry** - All audit data stays local; no data sent to external servers
- **DAP protocol logging** - Optional detailed DAP message logging for deep debugging and compliance audits

**Configuration (Environment Variables):**

```bash
# Enable audit logging (default: disabled)
export AIDB_AUDIT_ENABLED=true

# Set log retention period in days (default: 30)
export AIDB_AUDIT_RETENTION_DAYS=90

# Enable sensitive data masking (default: true)
export AIDB_AUDIT_MASK_SENSITIVE=true

# Enable DAP protocol trace logging (default: false)
export AIDB_ADAPTER_TRACE=1

# Set general log level (default: INFO)
export AIDB_LOG_LEVEL=DEBUG
```

**Audit Log Location:**

Audit logs are stored in `~/.aidb/logs/audit/` with automatic rotation when size limits are reached.

**Privacy & Data Handling:**

- ✅ All debugging data stays on your local machine
- ✅ No telemetry or usage data sent to external servers
- ✅ Sensitive data masking prevents credential leakage in logs
- ✅ Full control over log retention and rotation

---

## User Guide

Learn how to use AI Debugger MCP for AI-assisted debugging workflows.

```{toctree}
---
maxdepth: 2
---
user-guide/index
```

## Developer Guide

Architecture, development setup, and implementation details for contributors.

```{toctree}
---
maxdepth: 2
---
developer-guide/index
```

## Community and contribution guide

Information about the community behind this project and how you can contribute.

```{toctree}
---
maxdepth: 2
---
community/index
```

## Support

Get help with AI Debugger.

```{toctree}
---
maxdepth: 2
---
support/index
```

```{toctree}
---
maxdepth: 2
---
Release Notes <release-notes/index>
```
