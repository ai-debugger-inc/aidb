# JUnit Test Suite

Sample JUnit 5 test suite for testing debugging capabilities with Java test frameworks.

## Structure

- `src/test/java/com/example/test/SampleTest.java` - Sample JUnit tests
- `pom.xml` - Maven configuration
- `.vscode/launch.json` - VS Code debug configurations

## Tests

- `testSimpleAssertion` - Basic test with simple variables
- `testCalculation` - Test with calculations and variable inspection
- `testVariableTypes` - Test with various variable types
- `testException` - Test with exception handling
- `testClassMethod` - Class-based test method

## Running

```bash
mvn test
```

Or run a specific test:

```bash
mvn test -Dtest=SampleTest
```

## Debugging

Use the provided VS Code launch configurations:
- "JUnit: Debug Tests" - Run all tests in package
- "JUnit: Debug Single Test" - Run specific test class
