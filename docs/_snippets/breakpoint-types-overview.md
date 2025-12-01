**Breakpoint Types:**

- **Conditional breakpoints**: Pause only when a condition is true (`condition='status_code >= 400'`)
- **Hit count breakpoints**: Pause after N hits or every Nth hit (`hit_condition='>5'` or `hit_condition='%10'`)
- **Logpoints**: Log variable values without pausing execution (`log_message='User: {user.name}'`)
- **Column breakpoints**: Debug minified code with precise column positions
