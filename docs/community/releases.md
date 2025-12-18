---
myst:
  html_meta:
    description lang=en: AI Debugger release strategy, versioning, and roadmap.
---

# Releases & Versioning

AI Debugger follows a phased release approach to ensure quality while moving quickly. Our versioning strategy balances rapid iteration with production-ready stability.

## Version Strategy

### 0.0.x - 0.9.x: Active Development

**Current Phase** - Free and open source under Apache 2.0

All features are available to everyone at no cost:

- **Full feature access** - All debugging capabilities, multi-language support, and MCP integration
- **Community-driven** - Help shape the product roadmap with your feedback and contributions
- **Open development** - All code, issues, and discussions are public
- **Active iteration** - Regular updates and improvements based on community needs

**What to expect:**

- Rapid iteration based on community feedback
- Breaking changes may occur between minor versions (e.g., 0.1.x → 0.2.0)
- Active development of new language adapters and frameworks
- Regular updates and improvements

### 1.0.0: General Availability (GA)

**Future Milestone** - Stable API and production-ready release

GA release criteria:

- ≥80% test coverage for core packages
- Production-ready stability and performance
- At least 2 frameworks per language:
  - **Python**: `pytest` + `django`/`flask`
  - **JavaScript**: `express` + React/Next.js
  - **Java**: `junit` + `spring`
- Complete user documentation and API reference
- Comprehensive integration tests
- Performance benchmarks for typical workflows

### 1.x.x+: Stable Releases

**Standard Semantic Versioning:**

- **MAJOR** (1.x.x → 2.0.0): Breaking API changes
- **MINOR** (1.0.x → 1.1.0): New features, backward compatible
- **PATCH** (1.0.0 → 1.0.1): Bug fixes, backward compatible

## Debug Adapter Distribution

AI Debugger uses language-specific debug adapters to enable debugging across Python, JavaScript, Java, and more.

### How Adapters Are Distributed

**1. GitHub Releases**

Pre-built adapter binaries are published with each release:

- **Location**: [github.com/ai-debugger-inc/aidb/releases](https://github.com/ai-debugger-inc/aidb/releases)
- **Platforms**: macOS (Intel/ARM) and Linux (x86_64)
- **Format**: Compiled binaries ready to use
- **Manifest**: Each release includes a manifest file listing all adapters with checksums

**2. Agent-Driven Download via MCP**

When an AI agent attempts to start a debugging session without the required adapter, the system raises an error with installation instructions. The agent then uses MCP tools to download the adapter.

**Download workflow:**
1. System checks if adapter exists in `~/.aidb/adapters/`
2. If missing, raises error with installation instructions
3. AI agent calls MCP `adapter` tool with `download` action
4. System fetches from GitHub releases and verifies metadata
5. Adapter cached locally for future sessions

### Supported Adapters

- **Python**: `debugpy` (agent-installed via MCP)
- **JavaScript/TypeScript**: `vscode-js-debug` (agent-installed via MCP)
- **Java**: `java-debug` (agent-installed via MCP)

**Coming in 1.0.0:**

- Additional framework-specific configurations
- Extended language support
- Performance optimizations

## Current Status

**Version**: 0.0.9

### What's Working ✓

- Python debugging with `debugpy`
- JavaScript/TypeScript debugging (Node.js, Express)
- Java debugging with JUnit
- MCP integration for AI assistants (Claude, Cline, etc.)
- Cross-platform support (macOS, Linux)
- Breakpoints (line, conditional, hit count, logpoints)
- Step execution (into, over, out)
- Variable inspection and evaluation
- Multi-session debugging
- DAP protocol compatibility

### Known Limitations

- Windows support pending (WSL works)
- Limited framework-specific features
- Documentation still evolving

## Roadmap to 1.0.0

### Phase 1: Early Access Feedback (Weeks 1-6)

**Focus**: Learn from real users

- Gather feedback from early adopters
- Refine core debugging workflows
- Improve documentation based on actual usage patterns
- Add `pytest` framework support (Python)
- Add React/Next.js support (JavaScript)
- Performance profiling and optimization

### Phase 2: Stabilization (Weeks 7-9)

**Focus**: Production readiness

- Feature freeze for core API
- Comprehensive testing across all adapters
- Performance benchmarking
- Bug bash and stability improvements
- Documentation review and polish

### Phase 3: GA Preparation (Weeks 10-13)

**Focus**: Launch readiness

- Release candidate testing (1.0.0-rc.1, rc.2, etc.)
- Community testing period (minimum 1 week per RC)
- Final documentation updates
- Production deployment validation
- 1.0.0 launch preparation
- Announcement and marketing materials

## Getting Started

AI Debugger is free and open source. Get started in minutes:

1. Install AI Debugger: `pip install ai-debugger-inc`
2. Set up MCP integration with your AI assistant
3. Join our [Discord community](https://discord.com/invite/UGS92b6KgR)

### Community & Support

- **Discord**: [discord.com/invite/UGS92b6KgR](https://discord.com/invite/UGS92b6KgR) - Get help and discuss features
- **GitHub**: [github.com/ai-debugger-inc/aidb](https://github.com/ai-debugger-inc/aidb) - Report bugs and contribute
- **Documentation**: See the [User Guide](../user-guide/index)

## Release Notes

For detailed release notes and changelogs, see:

- **Latest releases**: [GitHub Releases](https://github.com/ai-debugger-inc/aidb/releases)
- **Version history**: [Release Notes](../release-notes/index)

## Frequently Asked Questions

### When will 1.0.0 be released?

We're targeting a 1.0.0 stable release in 2026. The timeline depends on community feedback and completion of stability milestones.

### Can I use AI Debugger in production?

AI Debugger has comprehensive test coverage and is actively used in development workflows. However, as a pre-1.0 project, expect potential breaking changes between minor versions. Breaking changes will be clearly communicated in release notes.

### How stable is the current release?

Very stable for core features. We have comprehensive test coverage, CI/CD automation, and active development. All features (Python, JavaScript, Java) are production-ready, but the API may evolve before 1.0.0.

### What languages are supported?

Python, JavaScript/TypeScript, and Java are fully supported. Additional languages and frameworks are planned for future releases based on community needs.

---

**Ready to join?** Start with our [Quick Start Guide](../user-guide/mcp/quickstart) or explore the [full documentation](../user-guide/index).
