# Repomedic API Contract & Specification

**Version**: `1.0.0-draft`  
**Base URL**: `/api/v1`  
**Default Port**: `8000`

---

## 1. REST Endpoints

### 1.1 Health & Diagnostics

#### `GET /api/v1/health`
Returns the operational status of the Repomedic backend and connected subsystems.

**Response** (`200 OK`):
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "sandbox_available": true,
  "supported_runtimes": ["python", "node"],
  "timestamp": "2026-10-21T08:45:00Z"
}
```

---

### 1.2 Bug Fixtures

#### `GET /api/v1/fixtures`
Lists all available reproducible bug benchmarks registered in `fixtures/bugs/`.

**Response** (`200 OK`):
```json
{
  "fixtures": [
    {
      "id": "sample-calculator-bug",
      "name": "Calculator Off-By-One Division",
      "language": "python",
      "difficulty": "beginner",
      "description": "Division by zero handling and off-by-one roundoff in calculator module.",
      "reproduce_cmd": "pytest tests/test_calc.py"
    }
  ]
}
```

#### `GET /api/v1/fixtures/{fixture_id}`
Retrieves detailed metadata for a specific fixture.

---

### 1.3 Diagnosis Sessions

#### `POST /api/v1/sessions`
Initializes a new autonomous diagnosis and repair session.

**Request Body**:
```json
{
  "source_type": "fixture",
  "fixture_id": "sample-calculator-bug",
  "repo_url": null,
  "branch": "main",
  "issue_description": "test_division fails when divisor is negative",
  "reproduce_cmd": "pytest tests/test_calc.py",
  "max_iterations": 10,
  "model": "claude-3-7-sonnet"
}
```

**Response** (`201 Created`):
```json
{
  "session_id": "sess_01j9x7k8p9q42m",
  "status": "queued",
  "created_at": "2026-10-21T08:46:12Z",
  "websocket_url": "ws://localhost:8000/api/v1/sessions/sess_01j9x7k8p9q42m/ws"
}
```

#### `GET /api/v1/sessions/{session_id}`
Retrieves current snapshot of the session state, thoughts, patch candidates, and test outputs.

**Response** (`200 OK`):
```json
{
  "session_id": "sess_01j9x7k8p9q42m",
  "status": "completed",
  "verdict": "verified",
  "iterations": 3,
  "elapsed_seconds": 18.4,
  "patch": "diff --git a/calc.py b/calc.py\nindex 8b9..4c2 100644\n--- a/calc.py\n+++ b/calc.py\n...",
  "verification": {
    "passed": true,
    "tests_run": 8,
    "tests_failed": 0,
    "output": "8 passed in 0.12s"
  }
}
```

#### `POST /api/v1/sessions/{session_id}/cancel`
Aborts an in-flight diagnosis session.

---

## 2. WebSocket Real-Time Event Stream

### `WS /api/v1/sessions/{session_id}/ws`
Bi-directional channel streaming live telemetry during diagnosis runs.

### Event Format

Every WebSocket message is a JSON object conforming to:

```typescript
interface RepomedicEvent {
  id: string;
  session_id: string;
  timestamp: string;
  type: "status" | "thought" | "tool_call" | "tool_result" | "patch" | "verification" | "error";
  payload: Record<string, unknown>;
}
```

### Event Types

| Type | Description | Sample Payload |
| :--- | :--- | :--- |
| `status` | State transition notification | `{"from": "diagnosing", "to": "verifying"}` |
| `thought` | Agent internal reasoning step | `{"thought": "Inspecting calc.py line 24 for division logic"}` |
| `tool_call` | Tool invocation dispatched | `{"tool": "grep_search", "args": {"query": "def divide"}}` |
| `tool_result` | Result from tool execution | `{"output": "calc.py:24:def divide(a, b):"}` |
| `patch` | Proposed code patch generated | `{"diff": "--- a/calc.py\n+++ b/calc.py\n..."}` |
| `verification`| Sandbox execution outcome | `{"exit_code": 0, "passed": true, "logs": "..."}` |
| `error` | Failure or unrecoverable error | `{"code": "SANDBOX_TIMEOUT", "message": "Timed out after 60s"}` |
