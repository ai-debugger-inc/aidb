# DAP Client Layer

The DAP client layer (`src/aidb/dap/client/`) provides the foundation for all Debug Adapter Protocol communication in AIDB.

**Position in Architecture:**

```
Session Layer (src/aidb/session/)
    ↓
DAP Client Layer (src/aidb/dap/client/)  ← YOU ARE HERE
    ↓
Protocol Layer (src/aidb/dap/protocol/)
    ↓
Debug Adapters (debugpy, vscode-js-debug, java-debug-server)
```

**Related Skills:** `dap-protocol-guide` (DAP specification), `adapter-development` (adapter integration)

______________________________________________________________________

## Core Design Decisions

### 1. Single Request Path

**Problem:** Multiple components sending requests directly → race conditions, duplicate sequence numbers, circular dependencies.

**Solution:** ALL requests MUST go through `DAPClient.send_request()`:

```python
# ✅ CORRECT: Use single entry point
response = await client.send_request(request)

# ❌ WRONG: Never bypass DAPClient
# await client.transport.send_message(request)  # FORBIDDEN
```

**Enforcement:** Semaphore serializes requests, transport is private, components can't access sequence numbers.

### 2. No Requests in Event Handlers

**Problem:** Event handlers sending requests → deadlocks (receiver thread blocked waiting for response it can't receive).

**Solution:** Event handlers ONLY update state and signal futures. Listeners (user code) CAN send requests, internal handlers CANNOT.

```python
# ❌ WRONG: Deadlock
def handle_terminated(event):
    await client.send_request(DisconnectRequest(...))  # Blocked forever

# ✅ CORRECT: Update state only
def _handle_terminated(self, event: Event) -> None:
    self._state.terminated = True
    for future in self._terminated_listeners:
        if not future.done():
            future.set_result(event)
```

### 3. Future-Based Async

Each request creates `asyncio.Future[Response]` for clean timeout, cancellation, and cross-task correlation.

### 4. Component Composition

Each concern is a separate component (Transport, RequestHandler, EventProcessor, etc.) wired together. `DAPClient` composes these and exposes a clean facade.

______________________________________________________________________

## Components

### DAPClient - Main Orchestrator

**File:** `src/aidb/dap/client/client.py`

**Key Methods:**

- `send_request(request, timeout, retry_config)` - THE single entry point
- `send_request_no_wait(request)` - Fire-and-forget for deferred responses
- `connect()`, `disconnect()`, `reconnect()` - Connection lifecycle
- `wait_for_stopped()`, `wait_for_event(event_type)` - Event synchronization
- `events` property - Exposes PublicEventAPI for subscriptions

**Component Composition:**

```python
self._transport = DAPTransport(host, port, ctx)
self._state = SessionState()
self._event_processor = EventProcessor(self._state, ctx)
self._public_events = PublicEventAPI(self._event_processor, ctx)
self._request_handler = RequestHandler(transport=self._transport, ctx=ctx)
self._connection_manager = ConnectionManager(transport, state, ctx)
self._message_router = MessageRouter(ctx)
self._reverse_request_handler = ReverseRequestHandler(ctx)
```

### DAPTransport - TCP Communication

**File:** `src/aidb/dap/client/transport.py`

Raw TCP with Content-Length header framing. IPv4/IPv6 fallback, async-safe sending.

```
Content-Length: 119\r\n
\r\n
{"seq":1,"type":"request","command":"initialize","arguments":{...}}
```

### RequestHandler - Request/Response Lifecycle

**File:** `src/aidb/dap/client/request_handler.py`

Manages request/response correlation using Future-based async pattern.

**Request Lifecycle:**

1. Generate sequence number (thread-safe)
1. Create Future, store in `_pending_requests[seq]`
1. Send via transport
1. Wait for response (or timeout)
1. Future resolved when response arrives

**Execution-Aware Pattern:** For continue/step commands, register terminated/stopped listeners BEFORE sending to prevent race conditions.

### EventProcessor - Event Dispatching

**File:** `src/aidb/dap/client/events.py`

Route events to subscribers and update session state. **CRITICAL:** Event handlers NEVER send requests.

**Dispatch table:** Maps event types to handlers (initialized, stopped, continued, terminated, output).

### MessageRouter - Message Type Routing

**File:** `src/aidb/dap/client/message_router.py`

Routes incoming messages based on type: response → RequestHandler, event → EventProcessor, request → ReverseRequestHandler.

### ConnectionManager - Connection Lifecycle

**File:** `src/aidb/dap/client/connection_manager.py`

Manage connection lifecycle, reconnection with backoff. **CRITICAL:** Send DisconnectRequest BEFORE closing transport (essential for pooled adapters like Java JDT LS).

### PublicEventAPI - Type-Safe Subscriptions

**File:** `src/aidb/dap/client/public_events.py`

Clean public API wrapping EventProcessor. Supports subscriptions (persistent) and waits (one-time).

```python
# Persistent subscription
subscription_id = client.events.subscribe_to_event(EventType.STOPPED.value, handler)

# One-time wait
event = await client.events.wait_for_event_async(EventType.STOPPED.value)
```

______________________________________________________________________

## Integration Flows

### Request Flow

```
User Code → DAPClient.send_request() ← SINGLE ENTRY POINT
    → RequestHandler.send_request()
        → Acquire semaphore, generate seq, create Future
        → DAPTransport.send_message()
            → [TCP Socket] → Debug Adapter

[Response returns]

Debug Adapter → [TCP] → DAPTransport.receive_message()
    → MessageRouter → RequestHandler.handle_response()
        → future.set_result(response) ← Completes await
```

### Event Flow

```
Debug Adapter → [TCP] → DAPTransport.receive_message()
    → MessageRouter (type="event")
        → EventProcessor.process_event()
            → Update state, signal futures, notify listeners
            → [NO REQUEST SENT - one-way only]
```

______________________________________________________________________

## Quick Reference

### Common Tasks

**Adding a New Request Type:** Use existing protocol types, call `client.send_request(YourRequest(...))`. No changes to DAP client needed.

**Subscribing to Events:**

```python
subscription_id = client.events.subscribe_to_event(EventType.STOPPED.value, handler)
event = await client.events.wait_for_event_async(EventType.STOPPED.value)
client.events.unsubscribe_from_event(subscription_id)
```

**Debugging Connection Issues:** Check `client.get_connection_status()`, enable `AIDB_LOG_LEVEL=DEBUG`, verify adapter process running.

### Common Mistakes

| Don't                             | Do                                     |
| --------------------------------- | -------------------------------------- |
| Access transport directly         | Use `DAPClient.send_request()`         |
| Send requests from event handlers | Update state, defer requests to caller |
| Assume synchronous event order    | Use `await client.wait_for_stopped()`  |

______________________________________________________________________

## Key Takeaways

1. **Single Request Path** - All requests through `DAPClient.send_request()` prevents race conditions
1. **Event Handlers Never Send Requests** - Prevents receiver deadlocks
1. **Future-Based Async** - Provides timeout, cancellation, async integration
1. **Component Composition** - Each concern focused, testable, maintainable
