# Django Test App

Minimal Django application for testing framework debugging capabilities.

## Structure

```
django_app/
├── manage.py               # Django management script
├── test_project/          # Django project
│   ├── __init__.py
│   ├── settings.py        # Minimal Django settings
│   ├── urls.py           # URL routing
│   └── views.py          # Test views with breakpoint markers
└── .vscode/
    └── launch.json        # VS Code debug configuration
```

## Views

All views contain special markers (e.g., `#:bp.home.message:`) for setting breakpoints in tests.

### 1. `home_view` - `/`
Simple view demonstrating basic variable inspection.

### 2. `calculate_view` - `/calculate/<a>/<b>/`
View with multiple variables for testing stepping and arithmetic.

### 3. `variable_inspection_view` - `/variables/`
View with various data types (int, str, list, dict, nested dict) for comprehensive variable inspection testing.

## Usage in Tests

```python
from pathlib import Path
from tests._helpers.framework_base import FrameworkDebugTestBase

class TestDjangoDebugging(FrameworkDebugTestBase):
    framework_name = "Django"

    async def test_launch_via_api(self, debug_interface):
        django_app = Path(__file__).parent / "_assets" / "framework_apps" / "django_app"

        # Launch Django dev server
        session = await debug_interface.start_session(
            program=str(django_app / "manage.py"),
            args=["runserver", "8000", "--noreload"],
            cwd=str(django_app),
        )

        # Set breakpoint in view
        # Test HTTP request triggering breakpoint
        ...
```

## Breakpoint Markers

- `#:bp.home.message:` - Home view message variable
- `#:bp.home.counter:` - Home view counter
- `#:bp.calc.x:` - Calculate view x variable
- `#:bp.calc.total:` - Calculate view total
- `#:bp.vars.integer:` - Variable inspection integer
- `#:bp.vars.nested:` - Variable inspection nested dict

Extract line numbers using marker parsing utilities from test helpers.
