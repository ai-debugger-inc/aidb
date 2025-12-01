# Common Failure Modes

Known failure patterns across AIDB components with diagnosis and solutions.

Each includes: **Symptoms** → **Diagnosis** → **Solution** → **Routing**

## 1. Port Conflicts

**Symptoms:**

- "Address already in use"
- Adapter fails to start
- Session initialization fails

**Diagnosis:**

```bash
lsof -i :5678                             # Check port
grep -i "address already in use" ~/.aidb/log/adapter_traces/*/*.adapter.log
```

**Solution:**

```bash
kill -9 $(lsof -t -i :5678)               # Kill process
pkill -9 debugpy                          # Kill all debugpy
./dev-cli test clean                      # Docker cleanup
```

**Configure different port:**

```bash
export AIDB_PORT_RANGE_START=6000
export AIDB_PORT_RANGE_END=6100
```

**Routing:** Adapter port configuration → **adapter-development**

## 2. Timeout Issues

**Symptoms:**

- "Timed out waiting for..."
- Session hangs
- Operations never complete

**Diagnosis:**

```bash
export AIDB_LOG_LEVEL=DEBUG
ps aux | grep -E "(debugpy|vscode-js-debug|java-debug)"
tail -f ~/.aidb/log/adapter_traces/{language}/*.adapter.log.1
grep -i "timeout" ~/.aidb/log/aidb.log
```

**Solution:**

Increase timeouts:

```python
session = aidb.create_session(
    language="python",
    target="slow_program.py",
    timeout=60.0  # Increase from default 30s
)
```

Check adapter health:

```bash
./dev-cli adapter test {language}
cat ~/.aidb/log/adapter_traces/{language}/*.adapter.log.1 | grep -i error
```

**For fast-executing programs:** Set breakpoints BEFORE starting session.

**Routing:**

- General timeout → covered here
- Adapter-specific → **adapter-development**
- Test timeout → **testing-strategy**
- CI timeout → **ci-cd-workflows**

## 3. DAP Protocol Errors

**Symptoms:**

- "Invalid response from adapter"
- "Unexpected message type"
- Breakpoints not verified
- Variables show incorrect values

**Diagnosis:**

```bash
# CRITICAL: Set BEFORE starting session
export AIDB_ADAPTER_TRACE=1

# Run operation, then check
cat ~/.aidb/log/adapter_traces/{language}/*.adapter.log.1
grep -i "dap.*error" ~/.aidb/log/adapter_traces/*/*.adapter.log
grep "initialize\|attach\|launch" ~/.aidb/log/adapter_traces/*/*.adapter.log.1
```

**Solution:**

Verify adapter version:

```bash
ls -la ~/.aidb/adapters/
cat ~/.aidb/adapters/*/VERSION
```

Reinstall adapter:

```bash
aidb adapter download {language} --force
```

**Routing:**

- Protocol overview → here
- Adapter DAP issues → **adapter-development**
- Protocol reference → **dap-protocol-guide**

## 4. Session Initialization Failures

**Symptoms:**

- "Failed to initialize session"
- "Target not found"
- "Invalid target path"
- Immediate failure after launch

**Diagnosis:**

```bash
# Check target file
ls -la /path/to/target.py
cat /path/to/target.py > /dev/null

# Check logs
grep "initialize.*failed" ~/.aidb/log/aidb.log
grep "target.*not found" ~/.aidb/log/aidb.log
grep "launch.*failed" ~/.aidb/log/adapter_traces/*/*.adapter.log
```

**Solution:**

Use absolute paths:

```python
import os
target = os.path.abspath("my_program.py")
session = aidb.create_session(language="python", target=target)
```

Fix permissions:

```bash
chmod 644 /path/to/file.py
chmod 755 /path/to/directory/
```

Java classpath:

```bash
export CLASSPATH=/path/to/classes:/path/to/libs/*
```

**Routing:**

- General path/permission → here
- Java classpath → **adapter-development**
- JavaScript modules → **adapter-development**
- Test targets → **testing-strategy**

## 5. Adapter Not Found

**Symptoms:**

- "Adapter binary not found at..."
- "No adapter installed for \{language}"
- Session fails immediately

**Diagnosis:**

```bash
ls ~/.aidb/adapters/                      # List installed
ls ~/.aidb/adapters/{language}/           # Check specific
grep "adapter.*not found" ~/.aidb/log/aidb.log
```

**Solution:**

```bash
aidb adapter download {language}          # Download
aidb adapter download python --force      # Force reinstall

# Verify
aidb adapter list
ls -la ~/.aidb/adapters/{language}/
```

**Dev environment:**

```bash
./dev-cli adapters build --language python
./dev-cli adapters build --all
```

**Routing:**

- Installation → here
- Development/building → **adapter-development**
- CI/CD setup → **ci-cd-workflows**

## 6. Permission Errors

**Symptoms:**

- "Permission denied"
- "Cannot write to..."
- "Cannot read file"

**Diagnosis:**

```bash
ls -l /path/to/file.py                    # File permissions
ls -ld /path/to/directory/                # Directory
ls -ld ~/.aidb/                           # AIDB directory
grep -i "permission denied" ~/.aidb/log/aidb.log
```

**Solution:**

Fix file permissions:

```bash
chmod 644 /path/to/file.py                # File readable/writable
chmod 755 /path/to/directory/             # Directory accessible
chmod +x /path/to/script.sh               # Executable
```

Fix ownership:

```bash
chown $USER /path/to/file.py              # Change owner
chown -R $USER /path/to/directory/        # Recursive
```

Fix AIDB directories:

```bash
chmod -R 755 ~/.aidb/
chown -R $USER ~/.aidb/
```

Docker:

```bash
sudo chown -R $USER .cache/container-data/
```

**Routing:**

- General permissions → here
- Test environment → **testing-strategy**
- Docker → **dev-cli-development**
- CI/CD → **ci-cd-workflows**

## Quick Lookup Table

| Symptom                    | Failure Mode          | Quick Check            |
| -------------------------- | --------------------- | ---------------------- |
| "Address already in use"   | Port conflict         | `lsof -i :5678`        |
| "Timed out waiting for..." | Timeout               | Check adapter logs     |
| "Invalid response"         | DAP protocol error    | `AIDB_ADAPTER_TRACE=1` |
| "Target not found"         | Session init failure  | Verify file exists     |
| "Adapter binary not found" | Adapter not installed | `ls ~/.aidb/adapters/` |
| "Permission denied"        | Permission error      | `ls -l file.py`        |

## Investigation Strategy

For any failure:

1. **Reproduce** - Consistent reproduction
1. **Check logs** - Find error evidence
1. **Match pattern** - Identify from symptoms
1. **Run diagnostic** - Execute suggested commands
1. **Apply solution** - Fix based on diagnosis
1. **Route if needed** - Use component skill for details

See [Investigation Workflow](investigation-workflow.md) for complete playbook.

## Related Resources

- [Investigation Workflow](investigation-workflow.md) - Step-by-step debugging
- [Log Locations Reference](log-locations-reference.md) - Where to find logs
- [Environment Variables](environment-variables.md) - Debug configuration
- [Diagnostic Commands](diagnostic-commands.md) - Command playbooks

### Component Skills

- **adapter-development** - Adapter-specific debugging
- **testing-strategy** - Test-specific debugging
- **ci-cd-workflows** - CI/CD debugging
