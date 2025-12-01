# Express Test App

Minimal Express.js application for AIDB framework debugging tests.

## Purpose

This application serves as a test fixture for validating AIDB's JavaScript/Node.js debugging capabilities with the Express framework. It demonstrates the dual-launch pattern where the same application can be debugged both programmatically via the AIDB API and through VS Code launch configurations.

## Structure

```
express_app/
├── server.js              # Main Express app with middleware
├── routes/
│   ├── index.js          # Main routes with breakpoint markers
│   └── api.js            # API endpoints with breakpoint markers
├── .vscode/
│   └── launch.json       # VS Code debug configurations
├── package.json          # Dependencies
└── README.md            # This file
```

## Breakpoint Markers

All route handlers and middleware contain breakpoint markers in the format `:bp.{context}.{marker}:`.

These markers are used by tests to set breakpoints at specific lines without hardcoding line numbers.

### Available Markers

**Server (server.js):**
- `:bp.middleware.timestamp:` - Logging middleware timestamp
- `:bp.middleware.log:` - Middleware console.log
- `:bp.error.message:` - Error handler message
- `:bp.error.response:` - Error response
- `:bp.server.start:` - Server startup

**Index Routes (routes/index.js):**
- `:bp.home.message:` - Home route message
- `:bp.home.status:` - Home route status
- `:bp.home.response:` - Home route response
- `:bp.hello.name:` - Hello route name parameter
- `:bp.hello.greeting:` - Hello route greeting construction
- `:bp.hello.response:` - Hello route response
- `:bp.echo.data:` - Echo route data
- `:bp.echo.response:` - Echo route response
- `:bp.calc.x:` - Calculate route x parameter
- `:bp.calc.y:` - Calculate route y parameter
- `:bp.calc.sum:` - Calculate route sum
- `:bp.calc.product:` - Calculate route product
- `:bp.calc.response:` - Calculate route response

**API Routes (routes/api.js):**
- `:bp.api.status.uptime:` - Status endpoint uptime
- `:bp.api.status.memory:` - Status endpoint memory
- `:bp.api.status.response:` - Status endpoint response
- `:bp.api.data.input:` - Data endpoint input
- `:bp.api.data.processed:` - Data endpoint processed
- `:bp.api.data.response:` - Data endpoint response
- `:bp.api.users.id:` - Users endpoint ID
- `:bp.api.users.user:` - Users endpoint user object
- `:bp.api.users.response:` - Users endpoint response
- `:bp.api.update.input:` - Update endpoint input
- `:bp.api.update.result:` - Update endpoint result

## Launch Configurations

The `.vscode/launch.json` file contains three debug configurations:

1. **Express: Debug Server** - Launch server on port 3000
2. **Express: Debug Routes** - Launch server on port 3001
3. **Express: Attach** - Attach to running Node.js process on port 9229

## Usage

### Manual Testing

```bash
# Install dependencies
npm install

# Run normally
npm start

# Run with debugger
npm run dev
```

### In Tests

Tests use this app through the `FrameworkDebugTestBase` class:

```python
@pytest.fixture
def express_app(self) -> Path:
    return Path(__file__).parents[4] / "_assets" / "framework_apps" / "express_app"

async def test_launch_via_api(self, debug_interface, express_app: Path):
    server_js = express_app / "server.js"
    await debug_interface.start_session(
        program=str(server_js),
        env={"PORT": "3000"},
        cwd=str(express_app),
    )
```

## Routes

- `GET /` - Home route returning JSON status
- `GET /hello/:name` - Parameterized greeting
- `POST /echo` - Echo request body
- `GET /calculate?x=1&y=2` - Calculate sum and product
- `GET /api/status` - Server status and metrics
- `POST /api/data` - Process data
- `GET /api/users/:id` - Get user by ID
- `PUT /api/update` - Update data
