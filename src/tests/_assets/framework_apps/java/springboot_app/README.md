# Spring Boot Test Application

Minimal Spring Boot application for testing debugging capabilities.

## Structure

- `src/main/java/com/example/demo/` - Application source code
  - `DemoApplication.java` - Main Spring Boot application
  - `HelloController.java` - REST controller with test endpoints
- `pom.xml` - Maven configuration
- `.vscode/launch.json` - VS Code debug configurations

## Endpoints

- `GET /` - Simple home endpoint with basic variables
- `GET /calculate/{a}/{b}` - Endpoint with calculation and variable inspection
- `GET /variables` - Endpoint with various variable types for inspection testing

## Running

```bash
mvn spring-boot:run
```

Or run the compiled JAR:

```bash
mvn clean package
java -jar target/springboot-demo-1.0.0.jar
```

## Debugging

Use the provided VS Code launch configurations:
- "Spring Boot: Debug Server" - Port 8080
- "Spring Boot: Debug Controller" - Port 8081
