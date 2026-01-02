Claude Desktop has built-in MCP support.

#### Desktop Application

1. Open Claude Desktop
1. Navigate to Settings → MCP Servers
1. Click "Add Server"
1. Enter the following configuration:

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

5. Restart Claude Desktop

#### CLI Configuration

Add to `~/.config/claude/claude_desktop_config.json`:

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
