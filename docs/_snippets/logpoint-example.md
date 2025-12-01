**Description**: Log a message without pausing execution.

**Use Case**: Non-intrusive debugging, collecting data without stopping the program.

**Example**:

```python
breakpoint(
    action="set",
    location="app.py:55",
    log_message="Request received: {request_id}, User: {user.name}"
)
```

**Behavior**: When line 55 is executed, the message is logged with variable values interpolated. Execution continues without pausing.

**Message Format**: Curly braces `{}` contain expressions to evaluate and interpolate.
