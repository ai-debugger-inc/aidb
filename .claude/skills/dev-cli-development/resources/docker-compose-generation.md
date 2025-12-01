# Docker Compose Generation System

## Overview

AIDB uses a template-based system to programmatically generate the `docker-compose.yaml` file from declarative language configurations and Jinja2 templates. This system provides consistency across language-specific test runners while maintaining DRY principles.

**Key Benefits:**

- Single source of truth for language configurations (languages.yaml)
- Automatic regeneration when source files change (hash-based cache invalidation)
- Consistent service structure across all languages
- Easy addition of new languages or frameworks

## Architecture

### Core Service

**ComposeGeneratorService** (`src/aidb_cli/services/docker/compose_generator_service.py`)

Responsible for:

- Loading language configurations from `languages.yaml`
- Rendering Jinja2 templates for each language
- Merging generated services with static base configuration
- Hash-based cache invalidation
- Writing final `docker-compose.yaml`

### Source Files

The generation system uses these source files:

1. **docker-compose.base.yaml** - Static services (utilities, network configuration)
1. **languages.yaml** - Language-specific metadata (healthchecks, dockerfiles, test paths)
1. **templates/\*.j2** - Jinja2 service templates
   - `framework-test-runner.yaml.j2` - Framework testing services
   - `mcp-test-runner.yaml.j2` - MCP testing services
1. **versions.json** - Version dependencies (Python, Node, Java versions)

### Output File

**docker-compose.yaml** (`src/tests/_docker/docker-compose.yaml`)

- AUTO-GENERATED - never edit manually
- Contains header with generation instructions
- Merges base configuration + generated language services

## Template System

### Jinja2 Environment

The service configures Jinja2 with:

```python
Environment(
    loader=FileSystemLoader(templates_dir),
    autoescape=select_autoescape(),
    trim_blocks=True,      # Remove first newline after template tag
    lstrip_blocks=True,    # Strip leading whitespace before blocks
)
```

### Available Templates

#### framework-test-runner.yaml.j2

Generates language-specific framework test runners (e.g., `test-runner-python`, `test-runner-javascript`, `test-runner-java`).

**Template Variables:**

- `lang` - Language identifier (python, javascript, java)
- `config` - Configuration from languages.yaml for this language
- `config.dockerfile` - Path to Dockerfile
- `config.healthcheck` - Health check command
- `config.pip_flags` - Pip installation flags
- `config.test_path` - Default test path

**Generated Service Name:** `test-runner-{lang}`

**Example Output:**

```yaml
test-runner-python:
  profiles: ["python", "frameworks", "launch"]
  build:
    context: ${REPO_ROOT:-../../..}
    dockerfile: src/tests/_docker/dockerfiles/Dockerfile.test.python
    args: *build-args
  image: aidb-test-python:${IMAGE_TAG:-latest}
  ...
```

#### mcp-test-runner.yaml.j2

Generates language-specific MCP test runners (e.g., `mcp-python`, `mcp-javascript`, `mcp-java`).

**Template Variables:** Same as framework template

**Generated Service Name:** `mcp-{lang}`

## languages.yaml Structure

Each language entry specifies:

```yaml
languages:
  python:
    dockerfile: dockerfiles/Dockerfile.test.python
    version_key: PYTHON_VERSION
    adapter_env_vars:
      AIDB_PYTHON_PATH: /root/.aidb/adapters/python/debugpy/__init__.py
    healthcheck: "python --version && test -d /root/.aidb/adapters/python"
    pip_flags: "--root-user-action=ignore"
    test_path: "src/tests/frameworks/python/"
    mcp_test_filter: "python"
```

**Field Definitions:**

- `dockerfile` - Relative path to language-specific Dockerfile
- `version_key` - Environment variable name for version (used with versions.json)
- `adapter_env_vars` - Language-specific environment variables for adapter paths
- `healthcheck` - Shell command to verify language and adapter availability
- `pip_flags` - Additional flags for pip install (e.g., `--break-system-packages` for system Python)
- `test_path` - Default pytest path for framework tests
- `mcp_test_filter` - pytest `-k` filter for MCP tests

## Generation Process

### Step-by-Step Flow

1. **Load Configurations**

   - Load `languages.yaml` configuration
   - Load `versions.json` for build args
   - Initialize Jinja2 environment with templates directory

1. **Generate Language Services**

   - For each language in `languages.yaml`:
     - Render `framework-test-runner.yaml.j2` with lang + config
     - Render `mcp-test-runner.yaml.j2` with lang + config
   - Sort languages alphabetically for deterministic output

1. **Merge with Base**

   - Read `docker-compose.base.yaml` content
   - Find `services:` section
   - Insert generated services just before end of services section
   - Preserve networks and volumes sections

1. **Write Output**

   - Add generation header with instructions
   - Write merged content to `docker-compose.yaml`
   - Save hash for cache validation

### Code Flow

```python
def generate(self, force: bool = False) -> tuple[bool, str]:
    # Check if regeneration needed (unless forced)
    if not force and not self.needs_regeneration():
        return False, str(self.output_file)

    # Load language configurations
    languages = self._load_languages_config()

    # Generate language-specific services from templates
    language_services = self._generate_language_services(languages)

    # Merge with base compose file
    merged_content = self._merge_compose_files(language_services)

    # Write output and save hash
    self.output_file.write_text(merged_content)
    current_hash = self._compute_source_hash()
    self._save_hash(current_hash)

    return True, str(self.output_file)
```

## Hash-Based Cache Invalidation

### Tracked Source Files

ComposeGeneratorService tracks checksums of:

- `languages.yaml` - Language configuration changes
- `versions.json` - Version dependency changes
- `docker-compose.base.yaml` - Base configuration changes
- All `*.j2` templates - Template logic changes

Hash computed via `compute_files_hash(source_files)` which creates a SHA256 digest.

### Cache File Location

`.cache/compose-generation-hash`

**Format:**

```
<sha256_hash_of_source_files>
```

### Regeneration Triggers

Regeneration happens when:

1. **Output file doesn't exist** - First run or file deleted
1. **Source files changed** - Hash mismatch detected
1. **Force flag passed** - `generate(force=True)`

**Regeneration is SKIPPED when:**

- Output file exists
- Current hash == cached hash
- Force flag not set

### When Regeneration Occurs

Automatic regeneration happens before:

- `./dev-cli test run` - Any test suite execution
- `./dev-cli docker build` - Docker image build operations

## Modifying the System

### Adding a New Language

**Steps:**

1. **Create Dockerfile** - `src/tests/_docker/dockerfiles/Dockerfile.test.{language}`
1. **Add to languages.yaml:**
   ```yaml
   {language}:
     dockerfile: dockerfiles/Dockerfile.test.{language}
     version_key: {LANGUAGE}_VERSION
     adapter_env_vars:
       AIDB_{LANGUAGE}_PATH: /root/.aidb/adapters/{language}/...
     healthcheck: "{language} --version && test -f /path/to/adapter"
     pip_flags: ""
     test_path: "src/tests/frameworks/{language}/"
     mcp_test_filter: "{language}"
   ```
1. **Run regeneration:**
   ```bash
   ./dev-cli test run --regenerate-compose
   ```

### Modifying Service Configuration

**Static Services (utilities, network):**

- Edit `docker-compose.base.yaml` directly
- Run `./dev-cli test run` to regenerate

**Language-Specific Metadata:**

- Edit `languages.yaml`
- Changes apply to all services for that language

**Service Structure/Layout:**

- Edit templates (`framework-test-runner.yaml.j2`, `mcp-test-runner.yaml.j2`)
- Changes apply to all language services
- Be careful with indentation in Jinja2 templates

**Version Dependencies:**

- Edit `versions.json` (infrastructure section)
- Used in build args for Dockerfiles

### Template Development Tips

**Indentation:**

- Jinja2 has `trim_blocks=True` and `lstrip_blocks=True`
- First newline after `{% %}` is removed
- Leading whitespace before blocks is stripped
- Test with actual generation to verify YAML validity

**Variable Access:**

```jinja
{{ lang }}                    # Language name (python, javascript, java)
{{ config.dockerfile }}       # From languages.yaml
{{ config.healthcheck }}      # From languages.yaml
{{ config.pip_flags }}        # From languages.yaml (may be empty string)
{{ config.test_path }}        # From languages.yaml
```

**Conditional Logic:**

```jinja
{% if config.pip_flags %}
python -m pip install {{ config.pip_flags }} -e .[test,dev] -q
{% else %}
python -m pip install -e .[test,dev] -q
{% endif %}
```

**String Formatting:**

```jinja
{{ lang.title() }}            # "Python", "Javascript", "Java"
{{ lang|upper }}              # "PYTHON", "JAVASCRIPT", "JAVA"
```

## Validation

### Automatic Validation

After generation, the service validates the output:

```python
def validate_generated_file(self) -> tuple[bool, list[str]]:
    # Check file exists
    if not self.output_file.exists():
        return False, ["Generated file does not exist"]

    # Validate YAML syntax
    try:
        safe_read_yaml(self.output_file)
    except FileOperationError as e:
        return False, [str(e)]

    return True, []
```

### Manual Testing

Validate generated compose file:

```bash
# Check YAML syntax
docker compose -f src/tests/_docker/docker-compose.yaml config --quiet

# Validate services can be built
docker compose -f src/tests/_docker/docker-compose.yaml build --dry-run

# Test specific profile
docker compose -f src/tests/_docker/docker-compose.yaml --profile python config
```

## Troubleshooting

### Issue: Generated file has wrong indentation

**Cause:** Jinja2 template indentation incorrect

**Solution:**

- Check that template YAML matches expected indentation (2 spaces)
- Remember `lstrip_blocks=True` strips leading whitespace before blocks
- Use `{% ... %}` for logic, `{{ ... }}` for variables

### Issue: Regeneration not happening when it should

**Cause:** Hash cache not invalidated

**Solution:**

```bash
# Force regeneration
./dev-cli test run --regenerate-compose

# Or delete cache
rm .cache/compose-generation-hash
```

### Issue: New language not appearing

**Cause:** Language not added to languages.yaml or template error

**Solution:**

1. Verify language added to `languages.yaml`
1. Check template rendering doesn't fail:
   ```python
   from pathlib import Path
   from aidb_cli.services.docker.compose_generator_service import ComposeGeneratorService

   service = ComposeGeneratorService(Path.cwd())
   was_generated, path = service.generate(force=True)
   print(f"Generated: {was_generated}, Path: {path}")
   ```
1. Check for template syntax errors in logs

### Issue: Invalid YAML generated

**Cause:** Template produces invalid YAML structure

**Solution:**

1. Run validation: `docker compose -f docker-compose.yaml config`
1. Check YAML syntax of generated file
1. Fix template indentation or structure
1. Regenerate with `--regenerate-compose`

## Related Files

**Source Files:**

- `src/aidb_cli/services/docker/compose_generator_service.py` - Main service
- `src/tests/_docker/docker-compose.base.yaml` - Static configuration
- `src/tests/_docker/languages.yaml` - Language metadata
- `src/tests/_docker/templates/*.j2` - Jinja2 templates
- `versions.json` - Version dependencies

**Generated Output:**

- `src/tests/_docker/docker-compose.yaml` - Final generated file (DO NOT EDIT)

**Cache:**

- `.cache/compose-generation-hash` - Generation hash cache

**CLI Integration:**

- `src/aidb_cli/services/docker/docker_build_service.py` - Calls generator before builds
- `src/aidb_cli/services/test/test_execution_service.py` - Calls generator before test runs
