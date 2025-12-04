**Problem:** The debug adapter for your language is not installed.

**Solution:** Download the adapter using the `adapter` tool.

Ask your AI assistant:

> "Download the Python debug adapter."

The AI assistant will call `adapter`:

```python
action='download'
language='python'
```

To download all available adapters:

```python
action='download_all'
```

**Offline/Manual Installation:**

If automatic download fails or you're in an air-gapped environment:

1. Download the appropriate adapter from [GitHub Releases](https://github.com/ai-debugger-inc/aidb/releases)
2. Extract to `~/.aidb/adapters/{language}/`

```bash
# Example for Python (replace {platform} with your OS/arch, e.g., linux-x64, darwin-arm64)
mkdir -p ~/.aidb/adapters/python
tar -xzf debugpy-1.8.16-{platform}.tar.gz -C ~/.aidb/adapters/python/
```

Or set a custom adapter path:

```bash
export AIDB_PYTHON_ADAPTER_PATH=/path/to/your/debugpy
```

See the Configuration Tools documentation for detailed offline installation instructions.
