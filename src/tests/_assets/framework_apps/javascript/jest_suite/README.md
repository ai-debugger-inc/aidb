# Jest Test Suite

Sample Jest test suite for testing debugging capabilities with JavaScript test frameworks.

## Structure

- `sample.test.js` - Sample tests with various patterns
- `.vscode/launch.json` - VS Code debug configurations
- `jest.config.js` - Jest configuration

## Tests

- `Basic Tests` - Simple tests with variables and calculations
- `Async Tests` - Async/await testing
- `Test Class` - Grouped tests

## Running

Install dependencies first:
```bash
npm install
```

Then run tests:
```bash
npm test
```

Or with Jest directly:
```bash
npx jest
```

## Debugging

Use the provided VS Code launch configurations:
- "Jest: Debug Tests" - Run all tests
- "Jest: Debug Single Test" - Run specific test file
