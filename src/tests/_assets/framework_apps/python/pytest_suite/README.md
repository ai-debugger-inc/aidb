# pytest Test Suite

Sample pytest test suite for testing debugging capabilities with test frameworks.

## Structure

- `test_sample.py` - Sample tests with various patterns
- `.vscode/launch.json` - VS Code debug configurations

## Tests

- `test_simple_assertion` - Basic test with simple variables
- `test_calculation` - Test with calculations and variable inspection
- `test_variable_types` - Test with various variable types
- `test_with_fixture` - Test using pytest fixtures
- `TestClass.test_class_method` - Class-based test

## Running

```bash
pytest test_sample.py -v
```

Or run a specific test:

```bash
pytest test_sample.py::test_simple_assertion -v
```

## Debugging

Use the provided VS Code launch configurations:
- "pytest: Debug Tests" - Run all tests
- "pytest: Debug Single Test" - Run specific test
