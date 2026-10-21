import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from app.schemas.workflow import (
    TERMINAL_STATES,
    VALID_TRANSITIONS,
    WorkflowErrorDetail,
    WorkflowEvent,
    WorkflowResponse,
    WorkflowState,
)
from app.services.repository_inspector import RepositoryInspector


class WorkflowOrchestratorError(Exception):
    """Base exception for all workflow orchestration errors."""
    pass


class WorkflowNotFoundError(WorkflowOrchestratorError):
    """Raised when a requested workflow ID does not exist in the store."""
    pass


class InvalidStateTransitionError(WorkflowOrchestratorError):
    """Raised when an invalid or forbidden workflow state transition is attempted."""
    def __init__(self, message: str, from_state: Optional[WorkflowState] = None, to_state: Optional[WorkflowState] = None) -> None:
        super().__init__(message)
        self.from_state = from_state
        self.to_state = to_state


class WorkflowNotCancellableError(WorkflowOrchestratorError):
    """Raised when cancellation is requested on a workflow in a terminal state."""
    pass


class InMemoryWorkflowStore:
    """
    Lightweight, thread-safe, in-memory repository of workflow instances.
    Workflows are ephemeral and exist only for the lifetime of the process.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._workflows: dict[str, WorkflowResponse] = {}

    def save(self, workflow: WorkflowResponse) -> None:
        with self._lock:
            # Store a model copy to prevent accidental in-place mutation without locking
            self._workflows[workflow.workflow_id] = workflow.model_copy(deep=True)

    def get(self, workflow_id: str) -> Optional[WorkflowResponse]:
        with self._lock:
            wf = self._workflows.get(workflow_id)
            return wf.model_copy(deep=True) if wf else None

    def list_all(self) -> list[WorkflowResponse]:
        with self._lock:
            # Return ordered by creation timestamp ascending
            return [wf.model_copy(deep=True) for wf in sorted(self._workflows.values(), key=lambda w: w.created_at)]

    def delete(self, workflow_id: str) -> bool:
        with self._lock:
            return self._workflows.pop(workflow_id, None) is not None

    def clear(self) -> None:
        with self._lock:
            self._workflows.clear()


# Default process-level store instance
default_workflow_store = InMemoryWorkflowStore()


class WorkflowOrchestrator:
    """
    Deterministic agent workflow orchestrator.
    Manages workflow lifecycle, explicit state transitions, event auditing,
    failure capture, and safe cancellation.
    """

    def __init__(
        self,
        store: Optional[InMemoryWorkflowStore] = None,
        inspector: Optional[RepositoryInspector] = None,
    ) -> None:
        self.store = store or default_workflow_store
        self.inspector = inspector or RepositoryInspector()

    def create_workflow(
        self,
        repo_path: str,
        initial_step: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> WorkflowResponse:
        """
        Validates the target repository and initializes a new workflow in IDLE state.
        Raises RepositoryValidationError / RepositoryNotFoundError / RepositorySecurityError if invalid.
        """
        validated_root = self.inspector.validate_path(repo_path)
        normalized_repo_path = validated_root.as_posix()

        workflow_id = f"wf_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        step_message = initial_step.strip() if initial_step and initial_step.strip() else "Workflow initialized in idle state"

        initial_event = WorkflowEvent(
            event_id=f"evt_{uuid.uuid4().hex[:10]}",
            event_type="created",
            timestamp=now,
            from_state=None,
            to_state=WorkflowState.IDLE,
            message=step_message,
            metadata=metadata or {},
        )

        workflow = WorkflowResponse(
            workflow_id=workflow_id,
            repo_path=normalized_repo_path,
            state=WorkflowState.IDLE,
            current_step=step_message,
            created_at=now,
            updated_at=now,
            events=[initial_event],
            error=None,
        )

        self.store.save(workflow)
        return workflow

    def get_workflow(self, workflow_id: str) -> WorkflowResponse:
        """
        Retrieves a workflow by its unique ID.
        Raises WorkflowNotFoundError if the workflow does not exist.
        """
        workflow = self.store.get(workflow_id)
        if not workflow:
            raise WorkflowNotFoundError(f"Workflow not found: {workflow_id}")
        return workflow

    def list_workflows(self) -> list[WorkflowResponse]:
        """Lists all workflows currently held in the in-memory store."""
        return self.store.list_all()

    def transition_state(
        self,
        workflow_id: str,
        to_state: WorkflowState,
        message: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> WorkflowResponse:
        """
        Performs a validated state transition on the specified workflow.
        Guarantees thread-safe validation and event recording.
        """
        with self.store._lock:
            workflow = self.get_workflow(workflow_id)
            current_state = workflow.state

            # Reject transitions from terminal states
            if current_state in TERMINAL_STATES:
                raise InvalidStateTransitionError(
                    f"Cannot transition workflow from terminal state '{current_state.value}' to '{to_state.value}'",
                    from_state=current_state,
                    to_state=to_state,
                )

            # Check if transition is explicitly defined in the state graph
            allowed_next_states = VALID_TRANSITIONS.get(current_state, set())
            if to_state not in allowed_next_states:
                raise InvalidStateTransitionError(
                    f"Invalid state transition from '{current_state.value}' to '{to_state.value}'",
                    from_state=current_state,
                    to_state=to_state,
                )

            now = datetime.now(timezone.utc)
            step_message = message.strip() if message and message.strip() else f"Transitioned from {current_state.value} to {to_state.value}"

            event = WorkflowEvent(
                event_id=f"evt_{uuid.uuid4().hex[:10]}",
                event_type="state_changed",
                timestamp=now,
                from_state=current_state,
                to_state=to_state,
                message=step_message,
                metadata=metadata or {},
            )

            workflow.state = to_state
            workflow.current_step = step_message
            workflow.updated_at = now
            workflow.events.append(event)

            self.store.save(workflow)
            return workflow

    def record_event(
        self,
        workflow_id: str,
        event_type: str,
        message: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> WorkflowResponse:
        """
        Appends an informational event to the workflow history without changing state.
        """
        with self.store._lock:
            workflow = self.get_workflow(workflow_id)
            now = datetime.now(timezone.utc)

            event = WorkflowEvent(
                event_id=f"evt_{uuid.uuid4().hex[:10]}",
                event_type=event_type,
                timestamp=now,
                from_state=workflow.state,
                to_state=workflow.state,
                message=message,
                metadata=metadata or {},
            )

            workflow.updated_at = now
            workflow.events.append(event)
            self.store.save(workflow)
            return workflow

    def record_failure(
        self,
        workflow_id: str,
        error_code: str,
        error_message: str,
        details: Optional[dict[str, Any]] = None,
    ) -> WorkflowResponse:
        """
        Transitions the workflow to FAILED and records structured error information.
        Cannot be called on already terminal workflows.
        """
        with self.store._lock:
            workflow = self.get_workflow(workflow_id)
            current_state = workflow.state

            if current_state in TERMINAL_STATES:
                raise InvalidStateTransitionError(
                    f"Cannot record failure on workflow in terminal state '{current_state.value}'",
                    from_state=current_state,
                    to_state=WorkflowState.FAILED,
                )

            now = datetime.now(timezone.utc)
            error_obj = WorkflowErrorDetail(
                code=error_code,
                message=error_message,
                details=details,
            )

            event = WorkflowEvent(
                event_id=f"evt_{uuid.uuid4().hex[:10]}",
                event_type="failed",
                timestamp=now,
                from_state=current_state,
                to_state=WorkflowState.FAILED,
                message=f"Workflow failed: {error_message}",
                metadata={"error_code": error_code, "details": details or {}},
            )

            workflow.state = WorkflowState.FAILED
            workflow.current_step = f"Failed: {error_message}"
            workflow.error = error_obj
            workflow.updated_at = now
            workflow.events.append(event)

            self.store.save(workflow)
            return workflow

    def cancel_workflow(
        self,
        workflow_id: str,
        reason: Optional[str] = None,
    ) -> WorkflowResponse:
        """
        Cancels an active workflow, transitioning it to CANCELLED state.
        Rejects cancellation if the workflow is already terminal.
        """
        with self.store._lock:
            workflow = self.get_workflow(workflow_id)
            current_state = workflow.state

            if current_state in TERMINAL_STATES:
                raise WorkflowNotCancellableError(
                    f"Cannot cancel workflow in terminal state '{current_state.value}'"
                )

            now = datetime.now(timezone.utc)
            cancel_message = reason.strip() if reason and reason.strip() else "Workflow cancelled by user"

            event = WorkflowEvent(
                event_id=f"evt_{uuid.uuid4().hex[:10]}",
                event_type="cancelled",
                timestamp=now,
                from_state=current_state,
                to_state=WorkflowState.CANCELLED,
                message=cancel_message,
                metadata={"reason": reason} if reason else {},
            )

            workflow.state = WorkflowState.CANCELLED
            workflow.current_step = cancel_message
            workflow.updated_at = now
            workflow.events.append(event)

            self.store.save(workflow)
            return workflow
