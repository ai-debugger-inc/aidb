# Diagnostic Commands

Command playbooks for investigating AIDB issues.

## Quick Reference

**Log inspection:**

```bash
grep -r "ERROR" ~/.aidb/log/              # Find errors
tail -f ~/.aidb/log/aidb.log              # Live monitoring
cat ~/.aidb/log/adapter_traces/*/*.log.1  # Adapter traces
```

**Process debugging:**

```bash
lsof -i :5678                             # Check port usage
ps aux | grep debugpy                     # Find processes
pkill -9 debugpy                          # Kill processes
```

**Health checks:**

```bash
ls ~/.aidb/adapters/                      # Adapter installation
./dev-cli docker status                   # Docker health
```

**CLI debugging:**

```bash
./dev-cli -v <command>                    # Debug level + adapter traces
./dev-cli -vvv <command>                  # TRACE level + full DAP profiling
```

## Log Inspection

### grep - Search Logs

**Find errors:**

```bash
grep -r "ERROR" ~/.aidb/log/                          # All logs
grep "ERROR" ~/.aidb/log/aidb.log                     # Specific log
grep -i "error" ~/.aidb/log/aidb.log                  # Case-insensitive
grep -A 10 -B 10 "ERROR" ~/.aidb/log/aidb.log         # With context
```

**Common patterns:**

```bash
grep -r "Exception" ~/.aidb/log/                      # Exceptions
grep -r "Traceback" ~/.aidb/log/                      # Tracebacks
grep -r "timeout" ~/.aidb/log/                        # Timeouts
grep -r "address already in use" ~/.aidb/log/         # Port conflicts
```

**Adapter traces:**

```bash
grep -i "error" ~/.aidb/log/adapter_traces/*/*.adapter.log
grep "setBreakpoints" ~/.aidb/log/adapter_traces/*/*.adapter.log.1
grep "initialize\|attach\|launch" ~/.aidb/log/adapter_traces/*/*.adapter.log.1
```

**Test logs:**

```bash
# Docker tests
cat .cache/container-data/aidb-test-python/pytest/pytest-captured.log | grep -A 20 "FAILED"

# Local tests
cat pytest-logs/*/pytest-captured.log | grep -A 20 "AssertionError"
```

**Useful options:**

```bash
grep -c "ERROR" file.log                  # Count matches
grep "ERROR" file.log | sort -u           # Unique errors
tail -100 file.log | grep "ERROR"         # Recent errors
```

### tail - Monitor Logs

**Live monitoring:**

```bash
tail -f ~/.aidb/log/aidb.log                          # Main log
tail -f ~/.aidb/log/adapter_traces/python/*.log.1     # Adapter
tail -f ~/.aidb/log/aidb.log ~/.aidb/log/mcp.log      # Multiple
```

**Last N lines:**

```bash
tail -50 ~/.aidb/log/aidb.log                         # Last 50
tail -100 ~/.aidb/log/aidb.log | grep "ERROR"         # Last 100 errors
```

**Follow with filter:**

```bash
tail -f ~/.aidb/log/aidb.log | grep "ERROR"           # Errors only
tail -f ~/.aidb/log/aidb.log | grep "session_id.*abc" # Specific session
```

### cat - View Full Logs

**View entire log:**

```bash
cat ~/.aidb/log/aidb.log                              # Main log
cat ~/.aidb/log/adapter_traces/python/*.log.1         # Adapter trace
cat .cache/container-data/*/pytest/pytest-captured.log # Test output
```

**Pipe to commands:**

```bash
cat file.log | wc -l                      # Count lines
cat file.log | grep "ERROR"               # Find pattern
cat file.log | cut -d'"' -f4              # Extract field
```

### less - Page Through Logs

```bash
less ~/.aidb/log/aidb.log                 # Interactive paging
less +G ~/.aidb/log/aidb.log              # Start at end
less +F ~/.aidb/log/aidb.log              # Follow mode
```

**In less:** `/ERROR` to search, `n` next match, `N` previous, `q` quit

## Process Debugging

### lsof - List Open Files/Ports

**Check port usage:**

```bash
lsof -i :5678                             # Specific port
lsof -i :5678-5688                        # Port range
lsof -t -i :5678                          # PID only
kill -9 $(lsof -t -i :5678)               # Kill process on port
```

**Example output:**

```
COMMAND   PID USER   FD   TYPE DEVICE SIZE/OFF NODE NAME
debugpy  1234 user    3u  IPv4  12345      0t0  TCP *:5678 (LISTEN)
```

**Check files:**

```bash
lsof -c debugpy                           # Files opened by debugpy
lsof +D ~/.aidb/log/                      # Files in directory
```

### ps - Process Status

**Find processes:**

```bash
ps aux | grep debugpy                     # All debugpy processes
ps aux | grep "node.*inspect"             # Node debug
ps aux | grep java-debug                  # Java debug
ps aux | grep [d]ebugpy                   # Avoid matching grep
```

**Kill processes:**

```bash
pkill debugpy                             # Kill by name
pkill -9 debugpy                          # Force kill
kill -9 1234                              # Kill specific PID
```

### netstat - Network Statistics

**Check ports:**

```bash
netstat -an | grep LISTEN                 # All listening
netstat -an | grep 5678                   # Specific port
sudo netstat -tulpn | grep 5678           # With process info
netstat -an | grep ESTABLISHED            # Active connections
```

## Environment Verification

### echo - Display Variables

**Check variables:**

```bash
echo $AIDB_LOG_LEVEL                      # Specific variable
echo $AIDB_ADAPTER_TRACE                  # Check if set
env | grep AIDB_                          # All AIDB vars
```

### which - Locate Executables

```bash
which python                              # Find Python
which node                                # Find Node
which java                                # Find Java
python --version                          # Verify version
```

### env - Environment Variables

```bash
env                                       # All variables
env | grep AIDB_                          # AIDB-specific
env | grep AIDB_ | sort                   # Sorted
```

## Health Checks

### AIDB Commands

```bash
# Adapters
aidb adapter list                         # Installed adapters
aidb adapter download python              # Download
aidb adapter download python --force      # Force reinstall

# Sessions
aidb session list                         # Active sessions
aidb session info <id>                    # Details
aidb session stop <id>                    # Stop session
```

### dev-cli Commands

```bash
# Docker
./dev-cli docker status                   # Docker status
docker ps                                 # Containers
docker logs aidb-test-python              # Container logs

# Testing
./dev-cli test list                       # List tests
./dev-cli test run -t path/to/test.py     # Run test
./dev-cli test clean                      # Clean environment

# Adapters
./dev-cli adapters build --language python
./dev-cli adapters build --all
./dev-cli adapters status
```

### Docker Commands

```bash
# Status
docker ps                                 # Running containers
docker ps -a                              # All containers
docker ps | grep aidb                     # AIDB containers

# Logs
docker logs aidb-test-python              # View logs
docker logs -f aidb-test-python           # Follow
docker logs --tail 100 aidb-test-python   # Last 100 lines

# Interaction
docker exec aidb-test-python ls ~/.aidb/log/
docker exec -it aidb-test-python /bin/bash

# Cleanup
docker stop aidb-test-python
docker rm aidb-test-python
docker container prune                    # Remove stopped
```

## File Permissions

### ls - List with Permissions

```bash
ls -l file.py                             # File permissions
ls -ld directory/                         # Directory permissions
ls -la ~/.aidb/                           # Hidden files
ls -lt ~/.aidb/log/                       # Sort by time
```

**Permission format:**

```
-rw-r--r--  1 user group 1234 Jan 01 12:00 file.py
│││││││││
│││││││││── Other: read
││││││││─── Other: write (-)
│││││││──── Other: execute (-)
││││││───── Group: read
│││││────── Group: write (-)
││││─────── Group: execute (-)
│││──────── User: read
││───────── User: write
│────────── User: execute (-)
```

**Common values:**

- `644` - rw-r--r-- (normal file)
- `755` - rwxr-xr-x (executable/directory)
- `600` - rw------- (private file)
- `700` - rwx------ (private directory)

### chmod - Change Permissions

```bash
chmod 644 file.py                         # Normal file
chmod 755 directory/                      # Directory
chmod +x script.sh                        # Add execute
chmod -R 755 ~/.aidb/                     # Recursive
```

### chown - Change Ownership

```bash
chown $USER file.py                       # Change owner
chown user:group file.py                  # Owner and group
chown -R $USER ~/.aidb/                   # Recursive
sudo chown -R $USER .cache/container-data/  # Docker cache
```

## Investigation Examples

### Session Won't Start

```bash
# 1. Check logs
tail -50 ~/.aidb/log/aidb.log | grep ERROR

# 2. Check adapter
ls ~/.aidb/adapters/python/

# 3. Check ports
lsof -i :5678

# 4. Enable debug
export AIDB_LOG_LEVEL=DEBUG AIDB_ADAPTER_TRACE=1
# Retry operation

# 5. Check traces
cat ~/.aidb/log/adapter_traces/python/python.adapter.log.1
```

### Test Failure

```bash
# 1. Test summary
cat .cache/container-data/aidb-test-python/pytest/test-results.log | grep FAILED

# 2. Full traceback
cat .cache/container-data/aidb-test-python/pytest/pytest-captured.log | grep -A 50 "AssertionError"

# 3. AIDB logs
grep ERROR .cache/container-data/aidb-test-python/log/aidb.log

# 4. Adapter traces
cat .cache/container-data/aidb-test-python/log/adapter_traces/python/python.adapter.log.1

# 5. Reproduce locally
export AIDB_LOG_LEVEL=DEBUG AIDB_ADAPTER_TRACE=1
pytest path/to/test.py -v
```

### Port Conflict

```bash
# 1. Find process
lsof -i :5678

# 2. Get details
ps aux | grep $(lsof -t -i :5678)

# 3. Kill process
kill -9 $(lsof -t -i :5678)

# 4. Verify free
lsof -i :5678  # Should return nothing

# 5. Retry
```

### Permission Issues

```bash
# 1. Check permissions
ls -l file.py

# 2. Check directory
ls -ld directory/

# 3. Check owner
ls -l file.py | awk '{print $3, $4}'

# 4. Fix permissions
chmod 644 file.py
chmod 755 directory/

# 5. Fix ownership
chown $USER file.py
```

## Related Resources

- [Investigation Workflow](investigation-workflow.md) - When to use commands
- [Log Locations Reference](log-locations-reference.md) - What to check
- [Common Failure Modes](common-failure-modes.md) - Pattern-specific commands
- [Environment Variables](environment-variables.md) - Variables to verify
