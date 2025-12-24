---
myst:
  html_meta:
    description lang=en: Java debugging with AI Debugger MCP - framework support, Maven/Gradle projects, and best practices.
---

# Java Debugging Guide

This guide covers Java-specific debugging features, framework support, and common patterns when using AI Debugger MCP.

```{include} /_snippets/about-examples-disclaimer.md
```

## Requirements

- **Java**: JDK 17+ (21 LTS recommended)
- **Debug Adapter**: java-debug 0.53.1
- **Language Server**: Eclipse JDT LS 1.55.0

The adapters are installed automatically when you first debug Java code.

## Overview

The Java adapter uses Eclipse JDT Language Server (JDT LS) with the java-debug plugin to provide rich debugging capabilities including:

- Launch and attach debugging modes
- Single-file and project debugging
- Maven and Gradle project support
- JUnit test framework debugging
- Spring Boot application debugging
- Conditional breakpoints and logpoints
- Expression evaluation with full project context
- Remote JVM debugging via JDWP

## Framework Support

### JUnit Testing

Debug JUnit tests with full breakpoint and inspection capabilities. The adapter supports both JUnit 4 and JUnit 5.

**Basic JUnit Test Debugging**

```python
# Start debugging a specific test method
session_start(
    language="java",
    target="mvn",
    args=["test", "-Dtest=UserServiceTest#testCreateUser"],
    cwd="/path/to/project",
    breakpoints=[
        {
            "file": "/path/to/project/src/main/java/com/example/service/UserService.java",
            "line": 42
        },
        {
            "file": "/path/to/project/src/test/java/com/example/service/UserServiceTest.java",
            "line": 25
        }
    ]
)
```

**Debug All Tests in a Class**

```python
# Run all tests in a test class
session_start(
    language="java",
    target="mvn",
    args=["test", "-Dtest=UserServiceTest"],
    cwd="/path/to/project"
)
```

**Common JUnit Debugging Patterns**

- Set breakpoints in test methods (annotated with `@Test`)
- Set breakpoints in the code under test
- Use conditional breakpoints to catch specific test scenarios
- Inspect test fixtures and mock objects
- Debug test setup and teardown methods (`@Before`, `@After`, `@BeforeEach`, `@AfterEach`)

### Spring Boot Applications

Debug Spring Boot applications with full support for dependency injection, configuration, and web endpoints.

**Launch Spring Boot Application**

```python
# Debug Spring Boot application from JAR
session_start(
    language="java",
    target="java",
    args=["-jar", "target/myapp-0.0.1-SNAPSHOT.jar"],
    env={"SPRING_PROFILES_ACTIVE": "debug"},
    cwd="/path/to/project",
    breakpoints=[
        {
            "file": "/path/to/project/src/main/java/com/example/controller/UserController.java",
            "line": 35
        },
        {
            "file": "/path/to/project/src/main/java/com/example/service/UserService.java",
            "line": 89
        }
    ]
)
```

**Debug Spring Boot with Maven**

```python
# Use Spring Boot Maven plugin
session_start(
    language="java",
    target="mvn",
    args=["spring-boot:run"],
    cwd="/path/to/project",
    breakpoints=[
        # Application startup
        {
            "file": "/path/to/project/src/main/java/com/example/Application.java",
            "line": 15
        }
    ]
)
```

**Remote Debug Spring Boot in Docker**

```python
# Start container with JDWP enabled:
# docker run -p 8080:8080 -p 5005:5005 \
#   -e JAVA_TOOL_OPTIONS="-agentlib:jdwp=transport=dt_socket,server=y,suspend=n,address=*:5005" \
#   myapp:latest

# Attach to the running container
session_start(
    language="java",
    mode="remote_attach",
    host="localhost",
    port=5005
)
```

**Common Spring Debugging Patterns**

- Set breakpoints in `@RestController` and `@Controller` methods
- Debug `@Service` and `@Component` beans
- Inspect `@Autowired` dependencies
- Debug Spring configuration classes (`@Configuration`)
- Set conditional breakpoints based on request parameters
- Debug Spring Security filters and authentication

## Maven/Gradle Projects

### Maven Projects

**Project Structure Detection**

The adapter automatically detects Maven projects by looking for `pom.xml`. When debugging Maven projects, the adapter:

- Uses the Maven classpath from the compiled project
- Respects Maven's standard directory layout (`src/main/java`, `src/test/java`)
- Loads dependencies from `~/.m2/repository`

**Debug Maven Project Main Class**

```python
# After building with: mvn clean package
session_start(
    language="java",
    target="java",
    args=["-cp", "target/classes:target/dependency/*", "com.example.Main"],
    cwd="/path/to/project"
)
```

**Debug Maven Tests**

```python
# Debug specific test
session_start(
    language="java",
    target="mvn",
    args=["test", "-Dtest=MyTest"],
    cwd="/path/to/project"
)

# Debug with Maven Surefire debug mode (automatic port 5005)
session_start(
    language="java",
    target="mvn",
    args=["test", "-Dmaven.surefire.debug"],
    cwd="/path/to/project"
)
```

**Multi-Module Maven Projects**

```python
# Debug specific module
session_start(
    language="java",
    target="mvn",
    args=["-pl", "module-name", "exec:java"],
    cwd="/path/to/parent-project"
)
```

### Gradle Projects

**Project Structure Detection**

The adapter automatically detects Gradle projects by looking for `build.gradle` or `build.gradle.kts`. When debugging Gradle projects, the adapter:

- Uses the Gradle classpath from the compiled project
- Respects Gradle's standard directory layout
- Loads dependencies from the Gradle cache

**Debug Gradle Project Main Class**

```python
# After building with: ./gradlew build
session_start(
    language="java",
    target="java",
    args=["-cp", "build/classes/java/main:build/libs/*", "com.example.Main"],
    cwd="/path/to/project"
)
```

**Debug Gradle Application**

```python
# Using Gradle application plugin
session_start(
    language="java",
    target="./gradlew",
    args=["run"],
    cwd="/path/to/project"
)
```

**Debug Gradle Tests**

```python
# Debug specific test
session_start(
    language="java",
    target="./gradlew",
    args=["test", "--tests", "MyTest.testMethod"],
    cwd="/path/to/project"
)
```

### Build Tool Integration

**Pre-Compilation Requirements**

For Maven and Gradle projects, compile your code before debugging:

```bash
# Maven
mvn clean compile test-compile

# Gradle
./gradlew build
```

The adapter automatically compiles single `.java` files when `auto_compile=True` (default), but does not build full Maven/Gradle projects.

**VS Code Integration**

The adapter can use your existing VS Code `launch.json` configurations:

```python
# Reference a launch.json configuration
session_start(
    language="java",
    launch_config_name="Debug Spring Boot",
    workspace_root="/path/to/project"
)
```

Example `launch.json` for Maven project:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "type": "java",
      "name": "Debug Spring Boot",
      "request": "launch",
      "mainClass": "com.example.Application",
      "projectName": "myapp",
      "cwd": "${workspaceFolder}",
      "env": {
        "SPRING_PROFILES_ACTIVE": "dev"
      }
    }
  ]
}
```

## Common Patterns

### Single File Debugging

**Simple Java Program**

```python
# Debug a single .java file (auto-compiles if needed)
session_start(
    language="java",
    target="/path/to/Main.java",
    breakpoints=[
        {"file": "/path/to/Main.java", "line": 10}
    ]
)
```

**Pre-compiled Class Files**

```python
# Debug a pre-compiled .class file
session_start(
    language="java",
    target="/path/to/Main.class",
    breakpoints=[
        {"file": "/path/to/Main.java", "line": 10}
    ]
)
```

**Note**: The Java adapter automatically handles compilation for single `.java` files.

### Remote Debugging

**Attach to Running JVM**

```python
# Start your application with JDWP:
# java -agentlib:jdwp=transport=dt_socket,server=y,suspend=n,address=*:5005 -jar myapp.jar

# Attach to it
session_start(
    language="java",
    mode="remote_attach",
    host="localhost",
    port=5005
)
```

**Attach to Remote Server**

```python
# Attach to JVM on remote host
session_start(
    language="java",
    mode="remote_attach",
    host="192.168.1.100",
    port=5005
)
```

**Note**: For better expression evaluation in multi-project workspaces, configure a VS Code launch.json with the `projectName` property.

**Automatic Source Path Detection**

When debugging remote JVMs, the debugger returns JAR-internal paths like `trino-main.jar!/io/trino/Foo.java`. To resolve these to local source files, you can either:

1. **Automatic detection** (recommended): Provide `workspace_root` pointing to a Maven/Gradle project. Source paths are auto-detected from the project structure.

```python
# Clone the matching source version locally, then:
session_start(
    language="java",
    mode="remote_attach",
    host="localhost",
    port=5005,
    workspace_root="/path/to/trino-source"  # Auto-detects all src/main/java etc.
)
```

2. **Manual configuration**: Explicitly provide `source_paths` if auto-detection doesn't cover your needs.

```python
session_start(
    language="java",
    mode="remote_attach",
    host="localhost",
    port=5005,
    source_paths=[
        "/path/to/trino-source/core/trino-main/src/main/java",
        "/path/to/trino-source/plugin/trino-hive/src/main/java"
    ]
)
```

The auto-detection recursively scans for Maven (`pom.xml`) and Gradle (`build.gradle`, `build.gradle.kts`) modules, collecting standard source directories (`src/main/java`, `src/test/java`, `src/main/kotlin`, etc.).

### Conditional Breakpoints

**Simple Condition**

```python
breakpoint(
    action="set",
    location="/path/to/User.java:42",
    condition="age > 18"
)
```

**Complex Condition**

```python
breakpoint(
    action="set",
    location="/path/to/OrderService.java:156",
    condition='order.getStatus().equals("PENDING") && order.getTotal() > 1000.0'
)
```

**Hit Count Breakpoints**

```python
# Break only on 5th hit (exact count only)
breakpoint(
    action="set",
    location="/path/to/Loop.java:23",
    hit_condition="5"
)
```

**Logpoints**

```python
# Log without stopping execution
breakpoint(
    action="set",
    location="/path/to/Service.java:78",
    log_message="User ID: {userId}, Action: {action}"
)
```

### Variable Inspection

**Evaluate Expressions**

```python
# Get variable value
variable(
    action="get",
    expression="user.getName()"
)

# Get complex expression
variable(
    action="get",
    expression="orders.stream().filter(o -> o.getTotal() > 100).count()"
)
```

**Modify Variables**

```python
# Set variable value
variable(
    action="set",
    name="debugMode",
    value="true"
)

# Set object field
variable(
    action="set",
    name="user.email",
    value="\"new@example.com\""
)
```

### Exception Debugging

**Break on Exception**

When running a Java debug session, unhandled exceptions will automatically pause execution. You can then inspect the exception and stack trace:

```python
# Start session
session_start(
    language="java",
    target="/path/to/Main.java"
)

# When exception occurs, inspect it
inspect(
    target="locals"
)

# Check exception details in the stack frame
inspect(
    target="stack"
)
```

### Multi-threaded Debugging

**Inspect All Threads**

```python
# View all running threads
inspect(
    target="threads"
)
```

**Thread-specific Stack Inspection**

```python
# Inspect stack for current thread
inspect(
    target="stack"
)

# Get detailed stack information
inspect(
    target="stack",
    detailed=True
)
```

### Working with Classpath and JVM Arguments

For Maven and Gradle projects, the adapter automatically resolves classpath from your build configuration. For custom classpath, module path, or JVM arguments, use a VS Code launch.json configuration:

```json
{
  "type": "java",
  "request": "launch",
  "name": "Debug with Custom Config",
  "mainClass": "com.example.Main",
  "classPaths": [
    "${workspaceFolder}/lib/commons-lang3-3.12.0.jar",
    "${workspaceFolder}/lib/gson-2.8.9.jar"
  ],
  "modulePaths": [
    "${workspaceFolder}/modules"
  ],
  "vmArgs": "-Xms256m -Xmx1g -Dapp.environment=debug"
}
```

Then reference it:

```python
session_start(
    language="java",
    launch_config_name="Debug with Custom Config"
)
```

**Note**: The `classpath`, `module_path`, and `vmargs` parameters are configured through launch.json, not as direct MCP parameters.

### IDE Integration

**Using Eclipse JDT LS Features**

The Java adapter uses Eclipse JDT LS behind the scenes, providing:

- Automatic source file discovery
- Smart expression evaluation with project context
- Classpath resolution from Maven/Gradle
- Source attachment for libraries

**Note**: JDT LS is required for Java debugging. The Java adapter always uses Eclipse JDT LS for Maven/Gradle project support and classpath resolution. The adapter manages JDT LS workspace configuration automatically.

## Best Practices

### Project Setup

1. **Compile before debugging**: Always compile Maven/Gradle projects before starting a debug session
2. **Use launch.json for complex projects**: Configure `projectName` in launch.json for better expression evaluation in multi-project workspaces
3. **Leverage launch.json**: Create reusable configurations in VS Code's `launch.json` for advanced settings

### Breakpoints

1. **Set breakpoints before starting**: Include initial breakpoints in `session_start()` to ensure they're active from the beginning
1. **Use conditional breakpoints**: Filter breakpoint hits with conditions to reduce noise
1. **Prefer logpoints for monitoring**: Use logpoints instead of breakpoints when you don't need to pause execution

### Performance

1. **Reuse sessions**: The adapter uses a pooled JDT LS instance for better performance
1. **Limit watch expressions**: Too many watch expressions can slow down debugging
1. **Use targeted breakpoints**: Avoid setting breakpoints in high-frequency code paths

### Troubleshooting

**"Java not found" error**

Set `JAVA_HOME` environment variable:

```bash
export JAVA_HOME=/path/to/jdk
```

**"Class not found" error**

Ensure your project is compiled and classpath is correct:

```bash
# Maven
mvn clean compile

# Gradle
./gradlew build
```

**Breakpoints not binding**

1. Ensure source file paths match compiled class files
1. Check that breakpoints are on executable lines (not comments or declarations)
1. Verify the project is compiled with debug information (`-g` flag for javac)

**Remote debugging connection refused**

1. Verify the JVM is started with JDWP agent
1. Check firewall rules allow connections on the debug port
1. Ensure the host and port are correct

**Expression evaluation fails**

1. Configure `projectName` in launch.json for better context in multi-project workspaces
2. Use fully qualified class names
3. Ensure the project is built and classes are available

## Advanced Topics

### Custom JVM Arguments and Source Paths

For advanced configuration like custom JVM arguments, workspace management, or source paths, use a VS Code launch.json configuration:

```json
{
  "type": "java",
  "request": "launch",
  "name": "Advanced Java Debug",
  "mainClass": "com.example.Main",
  "vmArgs": "-Xmx2g -XX:+UseG1GC",
  "sourcePaths": [
    "${workspaceFolder}/src/main/java",
    "${workspaceFolder}/lib-sources"
  ]
}
```

Then reference it:

```python
session_start(
    language="java",
    launch_config_name="Advanced Java Debug"
)
```

**Note**: The `vmargs`, `jdtls_workspace`, and `source_paths` parameters are configured through launch.json, not as direct MCP parameters.

## Java Debugging Limitations

:::{warning}
**Java has specific hit condition limitations:**

⚠️ **Hit Conditions**: EXACT mode only (plain integers like `"5"`)
❌ **Hit Condition Operators**: `>`, `>=`, `<`, `<=`, `%`, `==` not supported by Java debug adapter
✅ **Conditional Breakpoints**: Fully supported with boolean expressions
✅ **Logpoints**: Fully supported
✅ **Launch & Attach**: Both modes fully supported

**Examples:**
- ✅ Supported: `hit_condition="5"` (pause on exactly 5th hit)
- ❌ Not supported: `hit_condition=">5"`, `hit_condition="%10"`

**Additional limitations:**
1. **Hot code reload**: Code changes during debugging require session restart
1. **Native methods**: Cannot step into native Java methods
1. **Optimized code**: JIT-optimized code may not match source exactly

**Workaround**: Use conditional breakpoints with manual counter logic for complex hit conditions.

For general limitations across all languages, see [Known Limitations](../core-concepts.md#known-limitations).
:::

## See Also

```{include} /_snippets/see-also-language-guides.md
```
