# Contributing to AI Debugger

Thank you for your interest in contributing to AI Debugger! We welcome
contributions from the community.

## Quick Links

- **Full Contributing Guide**:
  [ai-debugger.com/community/contributing](https://ai-debugger.com/en/latest/community/contributing.html)
- **Code of Conduct**: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- **Security Policy**: [SECURITY.md](SECURITY.md)

## Getting Started

1. Fork the repository

1. Clone your fork and set up the development environment:

   ```bash
   bash scripts/install/src/install.sh
   ./dev-cli info
   ```

1. Create a branch for your changes

1. Make your changes and ensure tests pass:

   ```bash
   ./dev-cli test run -s shared
   ./dev-cli dev precommit
   ```

1. Submit a pull request

## Ways to Contribute

- **Bug Reports**: Found a bug? [Open an
  issue](https://github.com/ai-debugger-inc/aidb/issues/new?template=bug_report.md)
- **Feature Requests**: Have an idea? [Start a
  discussion](https://github.com/ai-debugger-inc/aidb/issues/new?template=feature_request.md)
- **Code Contributions**: Bug fixes, features, and improvements are welcome
- **Documentation**: Help improve our docs
- **Language Adapters**: Add support for new programming languages

## Need Help?

- Join our [Discord](https://discord.com/invite/UGS92b6KgR) for questions and
  discussions
- Check the [Developer
  Guide](https://ai-debugger.com/en/latest/developer-guide/) for architecture
  details

For the complete contribution guidelines, including code style, testing
requirements, and the pull request process, please see our [full contributing
guide](https://ai-debugger.com/en/latest/community/contributing.html).
