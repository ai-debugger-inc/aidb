# AIDB VS Code Bridge Extension

This VS Code extension acts as a bridge between VS Code's debugging
infrastructure and aidb's Python API, enabling proper execution of preLaunchTask
and postDebugTask features.

## Features

- **Task Execution**: Execute VS Code tasks from aidb Python API
- **Launch Configuration Support**: Handle preLaunchTask and postDebugTask
- **Multi-Fork Compatibility**: Works with VS Code, Cursor, Windsurf, VSCodium,
  and Code-OSS
- **Communication Server**: Socket-based communication on port 42042

## Installation

### Automatic Installation (via aidb)

When using aidb, the extension will be automatically detected and installed when
needed:

```python
from aidb import SessionManager

manager = SessionManager()
# Use launch configuration (extension installation will be prompted if needed)
session = manager.create_session(launch_config_name="Debug Python")
```

### Manual Installation

1. Build the extension:

   ```bash
   cd extensions/aidb-vscode-bridge
   npm install
   npm run package
   ```

1. Install the VSIX:

   ```bash
   code --install-extension aidb-vscode-bridge.vsix
   ```

## Commands

- `aidb.executeTask`: Execute a VS Code task
- `aidb.getTaskList`: Get list of available tasks
- `aidb.executeLaunchConfig`: Execute a launch configuration

## Communication Protocol

The extension runs a socket server on port 42042 that accepts JSON commands:

```json
{
  "command": "executeTask",
  "taskName": "build"
}
```

Response format:

```json
{
  "success": true,
  "taskName": "build",
  "exitCode": 0
}
```

## Development

1. Clone the repository
1. Install dependencies: `npm install`
1. Compile TypeScript: `npm run compile`
1. Test in VS Code: Press F5 to launch extension development host

## License

Apache-2.0
