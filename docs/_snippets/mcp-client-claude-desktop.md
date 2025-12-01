Claude Code has built-in MCP support.

#### Desktop Application

1. Open Claude Code
1. Navigate to Settings → MCP Servers
1. Click "Add Server"
1. Enter the following configuration:

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

5. Restart Claude Code

#### CLI Configuration

Add to `~/.config/claude/claude_desktop_config.json`:

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
