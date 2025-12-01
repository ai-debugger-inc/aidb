# Advanced Breakpoint Types

Complete reference for function, exception, data, and instruction breakpoints in DAP.

## Function Breakpoints

Break when entering a specific function by name.

### Setting Function Breakpoints

```python
from aidb.dap.protocol import SetFunctionBreakpointsRequest
from aidb.dap.protocol.types import FunctionBreakpoint
from aidb.dap.protocol.bodies import SetFunctionBreakpointsArguments

seq = await client.get_next_seq()
response = await client.send_request(
    SetFunctionBreakpointsRequest(
        seq=seq,
        arguments=SetFunctionBreakpointsArguments(
            breakpoints=[
                FunctionBreakpoint(name="main"),
                FunctionBreakpoint(name="process_data", condition="len(data) > 0"),
            ]
        )
    )
)
```

### Language-Specific Function Names

```python
# Python
FunctionBreakpoint(name="my_function")
FunctionBreakpoint(name="MyClass.my_method")
FunctionBreakpoint(name="module.submodule.function")

# JavaScript
FunctionBreakpoint(name="myFunction")
FunctionBreakpoint(name="MyClass.myMethod")
FunctionBreakpoint(name="myModule.myFunction")

# Java
FunctionBreakpoint(name="com.example.MyClass.myMethod")
FunctionBreakpoint(name="main")  # Main method
```

### Function Breakpoint Support

Check adapter capabilities:

```python
init_response = await client.send_request(initialize_request)
capabilities = init_response.body

if capabilities.supportsFunctionBreakpoints:
    # Can use function breakpoints
    pass
else:
    ctx.warning("Adapter does not support function breakpoints")
```

## Exception Breakpoints

Break when exceptions are thrown or left unhandled.

### Setting Exception Breakpoints

```python
from aidb.dap.protocol import SetExceptionBreakpointsRequest
from aidb.dap.protocol.bodies import SetExceptionBreakpointsArguments

seq = await client.get_next_seq()
response = await client.send_request(
    SetExceptionBreakpointsRequest(
        seq=seq,
        arguments=SetExceptionBreakpointsArguments(
            filters=["raised", "uncaught"]  # Adapter-specific filter IDs
        )
    )
)
```

### Language-Specific Exception Filters

#### Python (debugpy)

```python
# Available filters
filters = [
    "raised",    # Break on all raised exceptions
    "uncaught",  # Break on uncaught exceptions
]

# With conditions
from aidb.dap.protocol.types import ExceptionFilterOptions

SetExceptionBreakpointsArguments(
    filters=["raised"],
    filterOptions=[
        ExceptionFilterOptions(
            filterId="raised",
            condition="isinstance(exception, ValueError)"
        )
    ]
)
```

#### JavaScript (vscode-js-debug)

```python
# Available filters
filters = [
    "all",        # All exceptions
    "uncaught",   # Uncaught exceptions
]
```

#### Java (java-debug-server)

```python
# Available filters
filters = [
    "caught",      # Caught exceptions
    "uncaught",    # Uncaught exceptions
]

# With specific exception types
from aidb.dap.protocol.types import ExceptionOptions, ExceptionPathSegment

SetExceptionBreakpointsArguments(
    exceptionOptions=[
        ExceptionOptions(
            path=[
                ExceptionPathSegment(names=["java.lang.NullPointerException"])
            ],
            breakMode="always"
        )
    ]
)
```

### Exception Breakpoint Capabilities

```python
init_response = await client.send_request(initialize_request)
capabilities = init_response.body

if capabilities.exceptionBreakpointFilters:
    # List of available filters
    for filter in capabilities.exceptionBreakpointFilters:
        ctx.debug(f"Filter: {filter.filter}, Label: {filter.label}")

if capabilities.supportsExceptionFilterOptions:
    # Can use ExceptionFilterOptions with conditions
    pass

if capabilities.supportsExceptionOptions:
    # Can use ExceptionOptions for fine-grained control
    pass
```

## Data Breakpoints

Break when memory location or variable changes (limited adapter support).

### Data Breakpoint Info Request

First, query if a variable supports data breakpoints:

```python
from aidb.dap.protocol import DataBreakpointInfoRequest
from aidb.dap.protocol.bodies import DataBreakpointInfoArguments

seq = await client.get_next_seq()
response = await client.send_request(
    DataBreakpointInfoRequest(
        seq=seq,
        arguments=DataBreakpointInfoArguments(
            variablesReference=vars_ref,
            name="my_variable"
        )
    )
)

if response.body.dataId:
    # Variable supports data breakpoint
    data_id = response.body.dataId
    ctx.debug(f"Can set data breakpoint: {data_id}")
else:
    ctx.warning("Variable does not support data breakpoints")
```

### Setting Data Breakpoints

```python
from aidb.dap.protocol import SetDataBreakpointsRequest
from aidb.dap.protocol.types import DataBreakpoint, DataBreakpointAccessType
from aidb.dap.protocol.bodies import SetDataBreakpointsArguments

seq = await client.get_next_seq()
response = await client.send_request(
    SetDataBreakpointsRequest(
        seq=seq,
        arguments=SetDataBreakpointsArguments(
            breakpoints=[
                DataBreakpoint(
                    dataId=data_id,
                    accessType=DataBreakpointAccessType.WRITE,
                    condition="newValue > 100"
                )
            ]
        )
    )
)
```

### Data Breakpoint Support

Most adapters have limited or no data breakpoint support:

```python
init_response = await client.send_request(initialize_request)
capabilities = init_response.body

if capabilities.supportsDataBreakpoints:
    # Adapter supports data breakpoints
    pass
else:
    ctx.info("Data breakpoints not supported")
```

## Instruction Breakpoints

Assembly-level breakpoints at specific instruction addresses.

```python
from aidb.dap.protocol import SetInstructionBreakpointsRequest
from aidb.dap.protocol.types import InstructionBreakpoint
from aidb.dap.protocol.bodies import SetInstructionBreakpointsArguments

seq = await client.get_next_seq()
response = await client.send_request(
    SetInstructionBreakpointsRequest(
        seq=seq,
        arguments=SetInstructionBreakpointsArguments(
            breakpoints=[
                InstructionBreakpoint(
                    instructionReference="0x00007fff8b2a1234",
                    offset=0,
                    condition="rax > 0"
                )
            ]
        )
    )
)
```

**Note**: Instruction breakpoints are rarely used and not well supported by most adapters.

## Usage Recommendations

### When to Use Each Type

**Source Breakpoints** (most common):

- Debugging specific lines of code
- Setting conditional breaks on logic paths
- Hit count breakpoints for loops

**Function Breakpoints**:

- Breaking at function entry without knowing exact line
- Debugging callbacks or dynamically loaded code
- Setting breakpoints in libraries when you don't have source

**Exception Breakpoints**:

- Finding where exceptions originate
- Catching uncaught exceptions
- Debugging error handling paths

**Data Breakpoints** (rarely supported):

- Finding when/where a variable changes
- Debugging state corruption
- Memory debugging

**Instruction Breakpoints** (advanced):

- Assembly-level debugging
- Reverse engineering
- Low-level system debugging

### Capability Detection Pattern

Always check capabilities before using advanced breakpoint types:

```python
async def setup_breakpoints(client: DAPClient, capabilities: Capabilities):
    """Set up breakpoints based on adapter capabilities"""

    # Source breakpoints always supported
    await set_source_breakpoints(...)

    # Function breakpoints
    if capabilities.supportsFunctionBreakpoints:
        await set_function_breakpoints(...)

    # Exception breakpoints
    if capabilities.exceptionBreakpointFilters:
        await set_exception_breakpoints(...)

    # Data breakpoints
    if capabilities.supportsDataBreakpoints:
        await set_data_breakpoints(...)

    # Instruction breakpoints
    if capabilities.supportsInstructionBreakpoints:
        await set_instruction_breakpoints(...)
```
