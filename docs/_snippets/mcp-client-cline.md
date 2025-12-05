1. Install the Cline extension from the VS Code marketplace
1. Open Command Palette (`Cmd+Shift+P` on macOS, `Ctrl+Shift+P` on Windows/Linux)
1. Type "Cline: Open Settings"
1. Add the following MCP server configuration:

```json
{
  "cline.mcpServers": {
    "ai-debugger": {
      "command": "python",
      "args": ["-m", "aidb_mcp"]
    }
  }
}
```

5. Reload VS Code
