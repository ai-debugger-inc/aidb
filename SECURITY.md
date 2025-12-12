# Security Policy

## Supported Versions

We release patches for security vulnerabilities in the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 0.0.x   | :white_check_mark: |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report them via email to **security@ai-debugger.com**.

You should receive a response within 48 hours. If for some reason you do not,
please follow up via email to ensure we received your original message.

Please include the following information in your report:

- Type of issue (e.g., buffer overflow, command injection, etc.)
- Full paths of source file(s) related to the issue
- Location of the affected source code (tag/branch/commit or direct URL)
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the issue, including how an attacker might exploit it

## Disclosure Policy

When we receive a security bug report, we will:

1. Confirm the problem and determine the affected versions
1. Audit code to find any similar problems
1. Prepare fixes for all supported versions
1. Release new versions and publish the advisory

## Security Best Practices

When using AI Debugger:

- **Never debug untrusted code** - Debug adapters execute code; only debug code
  you trust
- **Secure your MCP server** - If exposing the MCP server over a network, ensure
  proper authentication and encryption
- **Review breakpoint conditions** - Conditional breakpoints execute expressions
  in the debugged process
- **Limit adapter permissions** - Run debug sessions with minimal necessary
  privileges

## Comments on this Policy

If you have suggestions on how this process could be improved, please submit a
pull request.
