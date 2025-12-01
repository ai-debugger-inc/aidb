# Flask Test Application

Minimal Flask application for testing debugging capabilities.

## Structure

- `app.py` - Main Flask application with test routes
- `.vscode/launch.json` - VS Code debug configurations

## Routes

- `/` - Simple home route with basic variables
- `/calculate/<a>/<b>` - Route with calculation and variable inspection
- `/variables` - Route with various variable types for inspection testing

## Running

```bash
python app.py
```

Or via flask CLI:

```bash
FLASK_APP=app.py flask run --no-debugger --no-reload --port 5000
```

## Debugging

Use the provided VS Code launch configurations:
- "Flask: Debug Server" - Port 5000
- "Flask: Debug View" - Port 5001
