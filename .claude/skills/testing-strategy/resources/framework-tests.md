# Framework Tests

**Philosophy:** We're testing that AIDB works WITH frameworks, not testing the frameworks themselves.

______________________________________________________________________

## The Golden Rule

**Do test:**

- AIDB can launch the framework
- AIDB can debug the framework code
- Both API and VS Code launch work

**Don't test:**

- Framework internals (routing, middleware, ORM)
- Framework-specific features
- Framework configuration

______________________________________________________________________

## Required Pattern: Dual-Launch

All framework tests MUST inherit from `FrameworkDebugTestBase` and implement:

```python
from tests._helpers.framework_base import FrameworkDebugTestBase

class TestMyFramework(FrameworkDebugTestBase):
    framework_name = "MyFramework"  # REQUIRED

    @abstractmethod
    async def test_launch_via_api(self, debug_interface, *args):
        """Test direct API launch."""

    @abstractmethod
    async def test_launch_via_vscode_config(self, debug_interface, *args):
        """Test VS Code launch.json."""

    @abstractmethod
    async def test_dual_launch_equivalence(self, *args):
        """Verify both methods work identically."""
```

**Why?** Ensures we never ship a framework integration that only works through one entry point.

______________________________________________________________________

## Flask Example (Python)

**See:** `src/tests/frameworks/python/flask/e2e/test_flask_debugging.py`

```python
class TestFlaskDebugging(FrameworkDebugTestBase):
    framework_name = "Flask"

    @pytest.fixture
    def flask_app(self) -> Path:
        return get_framework_app_path("python", "flask")

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_launch_via_api(self, debug_interface, flask_app: Path):
        session_info = await debug_interface.start_session(
            program=str(flask_app / "app.py"),
            env={"FLASK_ENV": "development"},
            cwd=str(flask_app),
        )
        self.assert_framework_debuggable(session_info)

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_launch_via_vscode_config(self, debug_interface, flask_app: Path):
        manager = LaunchConfigurationManager(workspace_root=flask_app)
        config = manager.get_configuration(name="Flask: Debug")
        session_info = await self.launch_from_config(
            debug_interface, config, workspace_root=flask_app
        )
        self.assert_framework_debuggable(session_info)
```

______________________________________________________________________

## Express Example (JavaScript)

**See:** `src/tests/frameworks/javascript/express/e2e/test_express_debugging.py`

```python
class TestExpressDebugging(FrameworkDebugTestBase):
    framework_name = "Express"

    @pytest.fixture
    def express_app(self) -> Path:
        return get_framework_app_path("javascript", "express")

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_launch_via_api(self, debug_interface, express_app: Path):
        session_info = await debug_interface.start_session(
            program=str(express_app / "server.js"),
            env={"PORT": "3000"},
            cwd=str(express_app),
        )
        self.assert_framework_debuggable(session_info)
```

______________________________________________________________________

## Framework App Structure

**Location:** `src/tests/_assets/framework_apps/{language}/{framework}_app/`

```
{framework}_app/
├── .vscode/
│   └── launch.json      # VS Code launch configs
├── README.md
├── {main_file}          # Entry point
└── {source_files}       # Source with markers
```

______________________________________________________________________

## Marker Conventions

Use markers for breakpoint locations in framework code:

```python
# Python
x = 10  # MARKER: api.handler.entry

# JavaScript
const x = 10; // MARKER: api.handler.entry

# Java
int x = 10; // MARKER: api.handler.entry
```

______________________________________________________________________

## Dependency Management

Framework apps auto-manage dependencies via checksum services:

- npm install (JavaScript)
- pip install (Python)
- mvn install (Java)

**See:** dev-cli-development skill for infrastructure details.
