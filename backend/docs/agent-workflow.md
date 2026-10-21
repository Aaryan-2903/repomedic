# RepoMedic Agent Orchestration Engine

## 1. Overview
The Agent Orchestration Engine provides deterministic workflow and state management for RepoMedic debugging sessions. In this milestone, the engine tracks the lifecycle of an inspection and repair run through a formal finite state machine (FSM) without executing code or calling autonomous LLMs.

---

## 2. Workflow States & Transitions

### 2.1 States
The orchestration engine defines 9 explicit states:

| State | Type | Description |
| :--- | :--- | :--- |
| `idle` | Active (Initial) | Workflow created and initialized; awaiting initial task dispatch. |
| `inspecting` | Active | Repository files, structure, and Git working tree are being analyzed. |
| `investigating` | Active | Fault localization in progress (identifying candidate failure locations). |
| `reproducing` | Active | Executing and capturing deterministic reproduction test commands. |
| `patch_proposed` | Active | Candidate patch diff has been generated. |
| `verifying` | Active | Validating candidate patch against test suites in an isolated sandbox. |
| `completed` | Terminal | Bug successfully localized, patched, and verified. |
| `failed` | Terminal | Workflow encountered an unrecoverable error. |
| `cancelled` | Terminal | Workflow aborted by user request. |

### 2.2 State Transition Matrix
Transitions are strictly validated. Any transition not listed below is rejected with an `InvalidStateTransitionError` (HTTP 400). Terminal states cannot transition to any state.

```
       ┌───────────────────────────────┐
       │             idle              │
       └──────────────┬────────────────┘
                      │
                      ▼
       ┌───────────────────────────────┐
       │          inspecting           │
       └──────────────┬────────────────┘
                      │
                      ▼
       ┌───────────────────────────────┐◄────────┐
       │         investigating         │         │
       └──────────────┬────────────────┘         │
                      │                          │
              ┌───────┴───────┐                  │
              ▼               ▼                  │
       ┌─────────────┐ ┌──────────────┐          │
       │ reproducing │ │patch_proposed│          │
       └──────┬──────┘ └──────┬───────┘          │
              │               │                  │
              │               ▼                  │
              │        ┌──────────────┐          │
              └───────►│  verifying   ├──────────┘
                       └──────┬───────┘
                              │
                              ▼
                       ┌──────────────┐
                       │  completed   │ (Terminal)
                       └──────────────┘

* Any active state can transition to `failed` or `cancelled`.
* `completed`, `failed`, and `cancelled` are terminal and cannot be changed.
```

---

## 3. API Endpoints

All endpoints are served under `/workflows`:

| Method | Path | Description | Status Codes |
| :--- | :--- | :--- | :--- |
| `POST` | `/workflows` | Create a new workflow for a validated local repository (starts in `idle`). | 201, 400, 403, 404 |
| `GET` | `/workflows` | List all workflows in the store. | 200 |
| `GET` | `/workflows/{id}` | Retrieve workflow status, current step, error detail, and event history. | 200, 404 |
| `POST` | `/workflows/{id}/cancel` | Cancel an active workflow. Rejects cancellation of terminal workflows. | 200, 400, 404 |
| `POST` | `/workflows/{id}/transition` | Manually advance workflow state along valid transition paths. | 200, 400, 404 |

---

## 4. In-Memory Persistence & Concurrency

### 4.1 In-Memory Storage Limitations
- **Ephemeral State**: Workflows are stored exclusively in memory in an encapsulated `InMemoryWorkflowStore`.
- **Server Restarts**: All workflow records and event histories will disappear when the FastAPI server process restarts.
- **Multi-Process Limitation**: Multiple worker processes (e.g. `uvicorn --workers 4`) do not share memory and will not see workflows created on other workers. Use a single worker during local development until a persistent backing store (e.g., PostgreSQL or Redis) is introduced.

### 4.2 Concurrency Protection
- All read, write, transition, failure-recording, and cancellation operations are synchronized using a reentrant lock (`threading.RLock`).
- Deep copies (`model_copy(deep=True)`) are returned to prevent external caller mutation of store entries.

---

## 5. Non-Goals for Milestone 3
- **Autonomous Fixes**: The engine does not synthesize patches or run LLM completions.
- **Code Execution**: The engine does not invoke compilers, test suites, or Docker sandboxes in this milestone.
- **Durable Persistence**: No database, Celery, or external message queues are utilized yet.
