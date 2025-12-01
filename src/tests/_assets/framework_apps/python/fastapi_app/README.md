# FastAPI Test Application

Minimal FastAPI application for testing debugging capabilities with async routes.

## Structure

- `app.py` - Main FastAPI application with async test routes
- `.vscode/launch.json` - VS Code debug configurations

## Routes

- `/` - Simple home route with basic variables
- `/calculate/{a}/{b}` - Route with calculation and variable inspection
- `/variables` - Route with various variable types for inspection testing

## Running

```bash
python app.py
```

Or via uvicorn:

```bash
uvicorn app:app --host 127.0.0.1 --port 8000
```

## Debugging

Use the provided VS Code launch configurations:
- "FastAPI: Debug Server" - Port 8000
- "FastAPI: Debug View" - Port 8001
