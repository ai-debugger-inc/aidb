# Adding a New Debug Adapter to AIDB

This guide covers all the steps and touchpoints required to add a new language adapter to the AIDB codebase. Use this as a comprehensive checklist when implementing support for a new programming language.

## Overview

Adding a new adapter involves updates across multiple packages:

- **Core implementation** (`src/aidb/`): Adapter logic and configuration
- **Constants** (`src/aidb_common/`, `src/aidb_mcp/`): Shared enums and types
- **CLI** (`src/aidb_cli/`): Test program generator
- **CI/CD** (`.github/`): Build scripts and workflows
- **Configuration** (`versions.json`): Adapter metadata and build configuration
- **Testing** (`src/tests/`): Test infrastructure

## Prerequisites

Before starting, ensure you:

1. Understand the Debug Adapter Protocol (DAP)
1. Have identified the debug adapter you'll integrate (e.g., delve for Go, codelldb for Rust)
1. Know the adapter's build/installation requirements
1. Understand the language's debugging model (compilation requirements, runtime behavior, etc.)

## Step 1: Core Implementation

### 1.1 Create Adapter Package

Create a new package: `src/aidb/adapters/lang/<language>/`

**Required files:**

```
src/aidb/adapters/lang/<language>/
├── __init__.py          # Package initialization
├── <language>.py        # Main adapter implementation
├── config.py           # Configuration and launch config
└── syntax_validator.py # (Optional) Syntax validation
```

### 1.2 Implement Adapter Class

**File**: `src/aidb/adapters/lang/<language>/<language>.py`

**Pattern**: Inherit from `DebugAdapter` (see `src/aidb/adapters/base/adapter.py:60`)

**Required abstract methods:**

```python
from aidb.adapters.base import DebugAdapter
from .config import <Language>AdapterConfig

class <Language>Adapter(DebugAdapter):
    """<Language> debug adapter implementation."""

    async def _build_launch_command(
        self,
        target: str,
        adapter_host: str,
        adapter_port: int,
        args: list[str] | None = None,
    ) -> list[str]:
        """Build the command to launch the debug adapter.

        Example from Python (src/aidb/adapters/lang/python/python.py:288):
            return [python_executable, "-m", "debugpy", "--listen",
                    f"{adapter_host}:{adapter_port}", "--wait-for-client", target]
        """
        # Return command array for launching the adapter
        pass

    def _add_adapter_specific_vars(self, env: dict[str, str]) -> dict[str, str]:
        """Add language-specific environment variables.

        Example from Python (src/aidb/adapters/lang/python/python.py:421):
            env["DEBUGPY_LOG_DIR"] = str(trace_dir)
            env["PYTHONDONTWRITEBYTECODE"] = "1"
        """
        # Add any required environment variables
        return env

    def _get_process_name_pattern(self) -> str:
        """Get the process name pattern for cleanup operations.

        Example from Python (src/aidb/adapters/lang/python/python.py:463):
            return "debugpy"
        """
        # Return a string pattern to match adapter processes
        pass
```

**Optional methods to override:**

- `_validate_target_hook()`: Custom target validation
- `check_compilation_status()`: For compiled languages
- `get_launch_configuration()`: DAP launch request configuration
- Lifecycle hooks (see `src/aidb/adapters/base/hooks.py`)

**Reference implementations:**

- **Python**: `src/aidb/adapters/lang/python/python.py` (interpreted language)
- **Java**: `src/aidb/adapters/lang/java/java.py` (compiled language with LSP)
- **JavaScript**: `src/aidb/adapters/lang/javascript/javascript.py` (child session handling)

### 1.3 Implement Config Class

**File**: `src/aidb/adapters/lang/<language>/config.py`

**Pattern**: Inherit from `AdapterConfig` (see `src/aidb/adapters/base/config.py`)

```python
from dataclasses import dataclass, field
from aidb.adapters.base.config import AdapterConfig
from aidb.adapters.base.launch import BaseLaunchConfig

@dataclass
class <Language>AdapterConfig(AdapterConfig):
    """Configuration for <Language> debug adapter."""

    # Required: Basic identification
    language: str = "<language>"
    adapter_id: str = "<language>"

    # Required: File extensions this adapter handles
    file_extensions: list[str] = field(
        default_factory=lambda: [".ext1", ".ext2"]
    )

    # Required: Binary identifier (file/directory name in adapter package)
    binary_identifier: str = "path/to/adapter/binary"

    # Optional: Framework support
    supported_frameworks: list[str] = field(
        default_factory=lambda: ["framework1", "framework2"]
    )
    framework_examples: list[str] = field(
        default_factory=lambda: ["framework1"]  # 2-3 popular ones
    )

    # Optional: Port configuration
    default_dap_port: int = 9999
    fallback_port_ranges: list[int] = field(default_factory=lambda: [10000, 10100])

    # Optional: Adapter-specific settings
    # Add any language-specific configuration here
```

**Optional: VS Code launch.json Support**

If your language has VS Code launch configurations:

```python
@dataclass
class <Language>LaunchConfig(BaseLaunchConfig):
    """VS Code launch configuration for <Language>."""

    # Define any launch.json specific fields
    # See JavaScriptLaunchConfig (src/aidb/adapters/lang/javascript/config.py:115)

    LAUNCH_TYPE_ALIASES = ["<language>", "type1", "type2"]  # VS Code request types
```

**Reference implementations:**

- **Python**: `src/aidb/adapters/lang/python/config.py`
- **JavaScript**: `src/aidb/adapters/lang/javascript/config.py` (extensive launch config)
- **Java**: `src/aidb/adapters/lang/java/config.py` (compilation support)

### 1.4 Optional: Syntax Validator

**File**: `src/aidb/adapters/lang/<language>/syntax_validator.py`

If your language can validate syntax without execution:

```python
from aidb.adapters.base.syntax_validator import LanguageSyntaxValidator

class <Language>SyntaxValidator(LanguageSyntaxValidator):
    """Syntax validator for <Language>."""

    @property
    def language(self) -> str:
        return "<language>"

    def validate(self, file_path: str) -> tuple[bool, str | None]:
        """Validate syntax of the target file."""
        # Implement validation logic
        pass
```

**Registration**: Update `src/aidb/adapters/base/syntax_validator.py` in the `for_language()` method (around line 87-96) to register your validator:

```python
@classmethod
def for_language(cls, language: str) -> Optional["LanguageSyntaxValidator"]:
    """Get syntax validator for a language."""
    if language == "python":
        from ..lang.python.syntax_validator import PythonSyntaxValidator
        return PythonSyntaxValidator()
    if language in ["javascript", "js", "node"]:
        from ..lang.javascript.syntax_validator import JavaScriptSyntaxValidator
        return JavaScriptSyntaxValidator()
    if language == "java":
        from ..lang.java.syntax_validator import JavaSyntaxValidator
        return JavaSyntaxValidator()
    # Add your language here:
    if language == "<language>":
        from ..lang.<language>.syntax_validator import <Language>SyntaxValidator
        return <Language>SyntaxValidator()
    return None
```

### 1.5 Adapter Discovery

**No action required!** The `AdapterRegistry` automatically discovers adapters in `src/aidb/adapters/lang/` (see `src/aidb/session/adapter_registry.py:340`).

The registry uses reflection to find:

- Config classes inheriting from `AdapterConfig`
- Adapter classes inheriting from `DebugAdapter`
- Launch config classes (if present)

## Step 2: Constants and Enums

### 2.1 Add to Language Enum

**File**: `src/aidb_common/constants.py:10`

```python
class Language(str, Enum):
    """Supported programming languages for debugging."""

    PYTHON = "python"
    JAVASCRIPT = "javascript"
    JAVA = "java"
    <LANGUAGE> = "<language>"  # Add your language here

    @property
    def file_extension(self) -> str:
        ext_map = {
            Language.PYTHON: ".py",
            Language.JAVASCRIPT: ".js",
            Language.JAVA: ".java",
            Language.<LANGUAGE>: ".ext",  # Add mapping
        }
        return ext_map.get(self, ".txt")

    @property
    def comment_prefix(self) -> str:
        comment_map = {
            Language.PYTHON: "#",
            Language.JAVASCRIPT: "//",
            Language.JAVA: "//",
            Language.<LANGUAGE>: "//",  # Add mapping
        }
        return comment_map.get(self, "#")
```

### 2.2 Update MCP Constants (If Needed)

**File**: `src/aidb_mcp/core/constants.py:13`

Only update if the adapter type differs from the language name:

```python
class DebugAdapter(Enum):
    """Debug adapter types."""

    DEBUGPY = "debugpy"
    NODE = "node"
    JAVA = "java"
    <ADAPTER_TYPE> = "<adapter_type>"  # If needed
```

## Step 3: CLI Integration

### 3.1 Implement Test Program Generator

**File**: `src/aidb_cli/generators/plugins/<language>_generator.py`

**Pattern**: Inherit from `LanguageGenerator` (see `src/aidb_cli/generators/plugins/base.py:21`)

```python
from aidb_cli.generators.plugins.base import LanguageGenerator
from aidb_cli.generators.core.types import (
    VariableConstruct, LoopConstruct, FunctionConstruct,
    ConditionalConstruct, ExceptionConstruct, PrintConstruct,
    ReturnConstruct, ArrayConstruct, Scenario, ValidationResult
)

class <Language>Generator(LanguageGenerator):
    """Test program generator for <Language>."""

    @property
    def language_name(self) -> str:
        return "<language>"

    @property
    def file_extension(self) -> str:
        return ".ext"

    @property
    def comment_prefix(self) -> str:
        return "//"  # or "#" for your language

    # Implement all abstract methods:
    def generate_variable(self, construct: VariableConstruct) -> str:
        """Generate variable declaration."""
        pass

    def generate_loop(self, construct: LoopConstruct) -> str:
        """Generate loop code."""
        pass

    def generate_function(self, construct: FunctionConstruct) -> str:
        """Generate function definition or call."""
        pass

    def generate_conditional(self, construct: ConditionalConstruct) -> str:
        """Generate if/else code."""
        pass

    def generate_exception(self, construct: ExceptionConstruct) -> str:
        """Generate exception handling."""
        pass

    def generate_print(self, construct: PrintConstruct) -> str:
        """Generate print statement."""
        pass

    def generate_return(self, construct: ReturnConstruct) -> str:
        """Generate return statement."""
        pass

    def generate_array(self, construct: ArrayConstruct) -> str:
        """Generate array/list creation."""
        pass

    def format_program(self, code_blocks: list[str], scenario: Scenario) -> str:
        """Format code blocks into a complete program."""
        pass

    def validate_syntax(self, code: str) -> ValidationResult:
        """Validate generated code syntax."""
        pass
```

**Reference implementations:**

- **Python**: `src/aidb_cli/generators/plugins/python_generator.py`
- **JavaScript**: `src/aidb_cli/generators/plugins/javascript_generator.py`
- **Java**: `src/aidb_cli/generators/plugins/java_generator.py`

### 3.2 Register Generator

**File**: `src/aidb_cli/generators/plugins/__init__.py`

The `__init__.py` file should automatically export your generator if it follows the naming convention. Verify the file imports your generator class.

## Step 4: CI/CD Build System

### 4.1 Create Builder Script

**File**: `.github/scripts/adapters/builders/<language>.py`

**Pattern**: Inherit from `AdapterBuilder` (see `.github/scripts/adapters/base.py:16`)

```python
from pathlib import Path
from ..base import AdapterBuilder, BuildError
from ..metadata import create_and_write_metadata

class <Language>AdapterBuilder(AdapterBuilder):
    """Builder for <Language> debug adapter."""

    @property
    def adapter_name(self) -> str:
        return "<language>"

    def get_adapter_config(self) -> dict:
        """Get adapter config from versions.json."""
        return self.versions["adapters"]["<language>"]

    def clone_repository(self) -> Path:
        """Clone the adapter repository."""
        config = self.get_adapter_config()
        repo_url = config["repository"]  # or config["repo"] if using shorthand
        ref = config.get("ref", config.get("version"))

        # Clone logic here
        # See PythonAdapterBuilder for example
        pass

    def build(self) -> Path:
        """Build the adapter from source."""
        repo_dir = self.clone_repository()

        # Build logic specific to your adapter
        # May involve: npm install, mvn build, cargo build, etc.
        # See existing builders for patterns
        pass

    def package(self) -> Path:
        """Package the adapter for distribution."""
        # Create tarball with metadata
        # See existing builders for patterns
        pass
```

**Reference implementations:**

- **Python**: `.github/scripts/adapters/builders/python.py`
- **JavaScript**: `.github/scripts/adapters/builders/javascript.py`
- **Java**: `.github/scripts/adapters/builders/java.py`

### 4.2 Register Builder

**File**: `.github/scripts/adapters/registry.py:15`

```python
from .builders import (
    JavaScriptAdapterBuilder,
    JavaAdapterBuilder,
    PythonAdapterBuilder,
    <Language>AdapterBuilder,  # Add import
)

ADAPTER_BUILDERS: Dict[str, Type[AdapterBuilder]] = {
    "javascript": JavaScriptAdapterBuilder,
    "java": JavaAdapterBuilder,
    "python": PythonAdapterBuilder,
    "<language>": <Language>AdapterBuilder,  # Add entry
}
```

### 4.3 Update versions.json

**File**: `versions.json`

Add your adapter configuration:

```yaml
adapters:
  <language>:
    version: "x.y.z"
    repo: "org/repo-name"
    repository: "https://github.com/org/repo-name.git"  # Full URL
    ref: "vx.y.z"  # Git tag/branch to build from
    description: "Description of the adapter"
    universal: false  # true if platform-independent (like Java)
    build_deps:
      # Language-specific build dependencies
      # Examples:
      node_version: "18"  # For JavaScript/TypeScript
      java_version: "21"  # For Java
      java_distribution: "temurin"  # For Java
      python_version: "3.12"  # For Python

      # Build configuration
      build_command: "npm ci && npm run compile"  # How to build
      output_path: "dist"  # Where build outputs go
      package_files:  # Files to include in package
        - "dist/**"
        - "package.json"
        - "README.md"
        - "LICENSE"
```

**Platform Configuration**:

- For **universal** adapters (like Java): Set `universal: true`, no platform list needed
- For **platform-specific** adapters: The workflow uses the global `platforms` list from `versions.json:109`

**Version Management:**

- **Infrastructure versions** (`infrastructure` section in versions.json): Used by testing workflows for runtime environment
  - Python, Node, Java versions for testing
  - Loaded dynamically via `load-versions.json` reusable workflow
- **Adapter build_deps**: Used for building the adapter itself
  - May differ from infrastructure versions (e.g., JavaScript adapter uses Node 18 per vscode-js-debug requirements, while infrastructure uses Node 22)
  - Python versions should match between infrastructure and build_deps (validated by load-versions workflow)
- **Validation**: The `load-versions.json` workflow validates that Python versions match between infrastructure and adapter build_deps

**Example scenario**: If you're adding a JavaScript adapter:

- Set `build_deps.node_version` to what the adapter requires (e.g., "18" if that's in the adapter's .nvmrc)
- Don't worry if this differs from `infrastructure.node.version` (e.g., "22") - they serve different purposes

### 4.4 Update GitHub Workflow (If Needed)

**File**: `.github/workflows/adapter-build.yaml`

The workflow is **generic** and should work for most adapters. You may need to add language-specific setup steps:

```yaml
# Add around line 105-116 if your adapter needs special setup
- name: Setup <Language> (for <Language> adapter)
  if: matrix.adapter == '<language>'
  uses: actions/setup-<language>@v4
  with:
    <language>-version: ${{ steps.adapter-config.outputs.<language>_version }}
```

Also update the adapter config extraction logic (lines 70-103) if your adapter has unique build dependencies.

### 4.5 Update Build Environment Validator

**File**: `.github/scripts/validation/build_env.py`

Add validation logic for your adapter's build dependencies (around lines 116-143):

```python
def validate_adapter_dependencies(self, adapter: str) -> List[str]:
    """Validate dependencies for a specific adapter."""
    issues = []

    if adapter not in self.versions.get("adapters", {}):
        issues.append(f"Unknown adapter: {adapter}")
        return issues

    adapter_config = self.versions["adapters"][adapter]
    build_deps = adapter_config.get("build_deps", {})

    # Add validation for your language
    elif adapter == "<language>":
        # Check for required tools
        if not self._check_command_exists("<build-tool>"):
            issues.append("<Build tool> not found (required for <Language> adapter)")
        else:
            tool_version = self._check_command_version("<build-tool>", "--version")
            required_version = build_deps.get("<tool>_version", "default")
            print(f"[OK] <Build tool> found: {tool_version} (required: {required_version})")

    return issues
```

**Note**: This validation is used in CI/CD and local builds to ensure all build dependencies are present.

## Step 5: Testing Infrastructure

### 5.1 Test Constants

**File**: `src/tests/_helpers/constants.py`

Add language-specific test constants if needed (check existing patterns).

### 5.2 Test Fixtures and Hardcoded Mappings

Several test files contain hardcoded language mappings that need updates:

#### 5.2.1 Test Content Provider

**File**: `src/tests/_assets/test_content.py:44`

Add your language to the file mapping:

```python
file_map = {
    "python": "test_program.py",
    "javascript": "test_program.js",
    "java": "TestProgram.java",
    "<language>": "test_program.<ext>",  # Add your mapping
}
```

#### 5.2.2 Test Scenarios Fixtures

**File**: `src/tests/_fixtures/scenarios.py`

Update hardcoded mappings in helper functions:

```python
def _get_file_extension(language: str) -> str:
    """Get file extension for language."""
    extensions = {
        "python": ".py",
        "javascript": ".js",
        "java": ".java",
        "<language>": ".<ext>",  # Add your extension
    }
    return extensions.get(language, ".txt")

def _inject_errors(content: str, language: str) -> str:
    """Inject intentional errors for testing."""
    error_injections = {
        "python": ("return", "return"),
        "javascript": ("const", "cnst"),
        "java": ("public", "publik"),
        "<language>": ("<keyword>", "<typo>"),  # Add error injection
    }
    # ... rest of function
```

#### 5.2.3 Test Helpers

**File**: `src/tests/_helpers/mocks.py` (if needed)

Update mock configurations if your tests use the mock DAP client with adapter-specific capabilities.

**Other fixture locations:**

- `src/tests/_fixtures/base.py`: Base test classes
- `src/tests/_fixtures/generated_programs.py`: Test program fixtures

### 5.3 Docker Test Infrastructure (Optional)

**Files**: `src/tests/_docker/dockerfiles/Dockerfile.test.base` and `src/tests/_docker/dockerfiles/Dockerfile.test.<language>`

If you plan to run tests in Docker containers, you may need to:

1. **Add language runtime to base image** (if it's a common dependency):

   - Edit `dockerfiles/Dockerfile.test.base` to include the runtime
   - This affects all test images, so only do this if the runtime is needed by multiple languages

1. **Create language-specific test image**:

   - Create `dockerfiles/Dockerfile.test.<language>` inheriting from `aidb-test-base:latest`
   - Install language-specific runtime and tools
   - Install framework dependencies using `/scripts/install-framework-deps.sh`

**Note**: The Docker build arguments should align with `versions.json` infrastructure section. This is only necessary if you're running integration/E2E tests in containerized environments.

### 5.4 Framework Tests

Consider adding framework-specific tests in `src/tests/frameworks/<language>/` following the patterns used for JavaScript (Express, Jest) and Python (pytest, Django).

## Step 6: Validation & Testing

### 6.1 Pre-Implementation Checklist

Before you start implementing, verify:

- [ ] Debug adapter is available and documented
- [ ] You understand the adapter's launch mechanism
- [ ] You know how to build/package the adapter
- [ ] You've identified any language-specific quirks (compilation, child processes, etc.)

### 6.2 Implementation Checklist

Core Implementation:

- [ ] Created adapter package in `src/aidb/adapters/lang/<language>/`
- [ ] Implemented `<Language>Adapter` class with all abstract methods
- [ ] Implemented `<Language>AdapterConfig` class
- [ ] (Optional) Implemented `<Language>LaunchConfig` for VS Code support
- [ ] (Optional) Implemented syntax validator
- [ ] (Optional) Registered syntax validator in `src/aidb/adapters/base/syntax_validator.py`

Constants & Enums:

- [ ] Added to `Language` enum in `src/aidb_common/constants.py`
- [ ] Updated file extension and comment prefix mappings
- [ ] (If needed) Updated `DebugAdapter` enum in `src/aidb_mcp/core/constants.py`

CLI Integration:

- [ ] Implemented `<Language>Generator` in `src/aidb_cli/generators/plugins/`
- [ ] Verified generator is exported in `__init__.py`

CI/CD:

- [ ] Implemented `<Language>AdapterBuilder` in `.github/scripts/adapters/builders/`
- [ ] Registered builder in `.github/scripts/adapters/registry.py`
- [ ] Added adapter configuration to `versions.json`
- [ ] (If needed) Updated workflow in `.github/workflows/adapter-build.yaml`
- [ ] Added build validation in `.github/scripts/validation/build_env.py`

Testing:

- [ ] Added test constants if needed
- [ ] Updated `src/tests/_assets/test_content.py` file mapping
- [ ] Updated `src/tests/_fixtures/scenarios.py` extension and error mappings
- [ ] (Optional) Updated test mocks in `src/tests/_helpers/mocks.py`
- [ ] (Optional) Updated Docker test infrastructure in `src/tests/_docker/`
- [ ] Considered framework-specific tests in `src/tests/frameworks/<language>/`

### 6.3 Testing Steps

1. **Test Adapter Discovery**:

   ```python
   from aidb.session.adapter_registry import AdapterRegistry

   registry = AdapterRegistry()
   assert registry.is_language_supported("<language>")
   config = registry.get_adapter_config("<language>")
   adapter_class = registry.get_adapter_class("<language>")
   ```

1. **Test Generator**:

   ```bash
   ./dev-cli generate --language <language> --scenario basic_variables
   ```

1. **Test Builder** (local):

   ```bash
   ./dev-cli adapters build --language <language>
   ```

1. **Test Adapter Binary**:

   ```bash
   ./dev-cli adapters download --language <language> --install
   # Or after building:
   ./dev-cli adapters build --language <language> --install
   ```

1. **Test Basic Debugging**:

   ```python
   import aidb

   session = aidb.create(
       target="path/to/test/file.ext",
       language="<language>",
       breakpoints=[{"file": "path/to/test/file.ext", "line": 5}]
   )
   session.execute(action="continue")
   ```

1. **Test CI/CD** (if you have access):

   - Push to a test branch
   - Trigger the adapter build workflow
   - Verify artifacts are created correctly

### 6.4 Documentation Updates

After implementation:

- [ ] Update user-facing docs with new language support
- [ ] Add language to README if applicable
- [ ] Create language-specific examples if needed

## Common Patterns & Best Practices

### Adapter Implementation Patterns

1. **Use Hooks for Lifecycle Events**

   ```python
   def _register_language_hooks(self):
       self.register_hook(
           LifecycleHook.PRE_LAUNCH,
           self._validate_setup,
           priority=90
       )
   ```

1. **Lazy-Initialize Heavy Components**

   ```python
   @property
   def heavy_component(self):
       if self._heavy_component is None:
           self._heavy_component = HeavyComponent(ctx=self.ctx)
       return self._heavy_component
   ```

1. **Use Config Mapper for Launch Settings**

   ```python
   from aidb.adapters.base.config_mapper import ConfigurationMapper

   config_mappings = {
       "frameworkFlag": "framework_flag",
       "customSetting": "custom_setting",
   }
   ConfigurationMapper.apply_kwargs(config, kwargs, config_mappings)
   ```

### Build Script Patterns

1. **Use Subprocess Safely**

   ```python
   self.run_command(
       ["npm", "install"],
       cwd=repo_dir,
       capture_output=True
   )
   ```

1. **Generate Metadata**

   ```python
   from ..metadata import create_and_write_metadata

   create_and_write_metadata(
       adapter_name=self.adapter_name,
       adapter_version=config["version"],
       output_dir=dist_dir
   )
   ```

1. **Create Checksums**

   ```python
   checksum = self.create_checksum(tarball_path)
   checksum_path = tarball_path.with_suffix(tarball_path.suffix + ".sha256")
   checksum_path.write_text(f"{checksum}  {tarball_path.name}\n")
   ```

## Troubleshooting

### Adapter Not Discovered

- Check package structure matches `src/aidb/adapters/lang/<language>/`
- Ensure `__init__.py` exists in the package
- Verify class names follow pattern: `<Language>Adapter`, `<Language>AdapterConfig`
- Check that classes inherit from correct base classes

### Build Fails

- Verify `versions.json` configuration is correct
- Check build dependencies are available
- Review build command in builder script
- Check platform-specific issues (path separators, executable permissions, etc.)

### Generator Issues

- Verify all abstract methods are implemented
- Check syntax of generated code manually
- Test with simple scenarios first

### Runtime Issues

- Check adapter binary is installed correctly (`~/.aidb/adapters/<language>/`)
- Verify adapter command is constructed correctly (add logging to `_build_launch_command`)
- Check environment variables are set properly (`_add_adapter_specific_vars`)
- Review adapter process logs (enable with `AIDB_LOG_LEVEL=DEBUG AIDB_ADAPTER_TRACE=1`)

## Reference Implementations

Use these as templates:

- **Simple interpreted language**: Python adapter

  - `src/aidb/adapters/lang/python/`
  - `.github/scripts/adapters/builders/python.py`

- **Compiled language with LSP**: Java adapter

  - `src/aidb/adapters/lang/java/`
  - `.github/scripts/adapters/builders/java.py`

- **Complex with child sessions**: JavaScript adapter

  - `src/aidb/adapters/lang/javascript/`
  - `.github/scripts/adapters/builders/javascript.py`

## File Locations Quick Reference

Use this as a quick checklist of all files that require updates:

### Required Updates

**Core Implementation:**

- `src/aidb/adapters/lang/<language>/` - New package directory
  - `__init__.py`
  - `<language>.py` - Adapter class
  - `config.py` - Config and launch config classes

**Constants & Enums:**

- `src/aidb_common/constants.py` - Add to Language enum (line ~10)
- `src/aidb_mcp/core/constants.py` - (If needed) Add to DebugAdapter enum (line ~13)

**CLI Integration:**

- `src/aidb_cli/generators/plugins/<language>_generator.py` - New generator class
- `src/aidb_cli/generators/plugins/__init__.py` - Verify export

**CI/CD:**

- `.github/scripts/adapters/builders/<language>.py` - New builder script
- `.github/scripts/adapters/registry.py` - Register builder (line ~15)
- `versions.json` - Add adapter configuration
- `.github/scripts/validation/build_env.py` - Add validation (line ~116)

**Testing:**

- `src/tests/_assets/test_content.py` - Add file mapping (line ~44)
- `src/tests/_fixtures/scenarios.py` - Add extension and error mappings (line ~30, ~53)

### Optional Updates

**Core Implementation:**

- `src/aidb/adapters/lang/<language>/syntax_validator.py` - Syntax validator
- `src/aidb/adapters/base/syntax_validator.py` - Register validator (line ~87)

**CI/CD:**

- `.github/workflows/adapter-build.yaml` - Add setup steps (line ~105)

**Testing:**

- `src/tests/_helpers/constants.py` - Language-specific constants
- `src/tests/_helpers/mocks.py` - Mock configurations (if needed)
- `src/tests/_docker/Dockerfile.runtime` - Runtime installation (for Docker tests)
- `src/tests/frameworks/<language>/` - Framework-specific tests

**Documentation:**

- User-facing docs - Announce new language support
- README - Update supported languages list
- Examples - Language-specific usage examples

### Files That Auto-Update

**No manual changes needed:**

- `src/aidb/session/adapter_registry.py` - Auto-discovers adapters
- `.github/scripts/utils/matrix_generator.py` - Reads from versions.json
- Most MCP and CLI validation code - Uses Language enum

## Summary

Adding a new adapter requires updates in **6 main areas**:

1. **Core** (4-5 files): Adapter class, config class, optional validators
1. **Constants** (1-2 files): Language enum, adapter type enum
1. **CLI** (2 files): Test program generator and registration
1. **CI/CD** (4-5 files): Builder script, registry, versions.json, validation
1. **Testing** (3+ files): Test content provider, fixtures, optional Docker
1. **Docs** (optional): User-facing documentation

**Total files to update**: 15-20 files minimum, more if adding comprehensive testing.

Follow the checklists in Section 6.2 to ensure you don't miss any touchpoints. Reference existing adapters (Python, JavaScript, Java) for concrete implementation patterns.
