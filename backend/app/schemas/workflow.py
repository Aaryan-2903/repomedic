from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class WorkflowState(str, Enum):
    IDLE = "idle"
    INSPECTING = "inspecting"
    INVESTIGATING = "investigating"
    REPRODUCING = "reproducing"
    PATCH_PROPOSED = "patch_proposed"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_STATES = {
    WorkflowState.COMPLETED,
    WorkflowState.FAILED,
    WorkflowState.CANCELLED,
}

VALID_TRANSITIONS: dict[WorkflowState, set[WorkflowState]] = {
    WorkflowState.IDLE: {
        WorkflowState.INSPECTING,
        WorkflowState.FAILED,
        WorkflowState.CANCELLED,
    },
    WorkflowState.INSPECTING: {
        WorkflowState.INVESTIGATING,
        WorkflowState.FAILED,
        WorkflowState.CANCELLED,
    },
    WorkflowState.INVESTIGATING: {
        WorkflowState.REPRODUCING,
        WorkflowState.PATCH_PROPOSED,
        WorkflowState.FAILED,
        WorkflowState.CANCELLED,
    },
    WorkflowState.REPRODUCING: {
        WorkflowState.INVESTIGATING,
        WorkflowState.PATCH_PROPOSED,
        WorkflowState.FAILED,
        WorkflowState.CANCELLED,
    },
    WorkflowState.PATCH_PROPOSED: {
        WorkflowState.VERIFYING,
        WorkflowState.INVESTIGATING,
        WorkflowState.FAILED,
        WorkflowState.CANCELLED,
    },
    WorkflowState.VERIFYING: {
        WorkflowState.COMPLETED,
        WorkflowState.INVESTIGATING,
        WorkflowState.REPRODUCING,
        WorkflowState.FAILED,
        WorkflowState.CANCELLED,
    },
    WorkflowState.COMPLETED: set(),
    WorkflowState.FAILED: set(),
    WorkflowState.CANCELLED: set(),
}


class WorkflowErrorDetail(BaseModel):
    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable explanation of the error")
    details: Optional[dict[str, Any]] = Field(None, description="Optional structured error metadata")


class WorkflowEvent(BaseModel):
    event_id: str = Field(..., description="Unique event identifier")
    event_type: str = Field(..., description="Category of event (e.g. created, state_changed, cancelled, failed)")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when event occurred",
    )
    from_state: Optional[WorkflowState] = Field(None, description="Workflow state prior to this event, if applicable")
    to_state: Optional[WorkflowState] = Field(None, description="Workflow state resulting from this event, if applicable")
    message: str = Field(..., description="Human-readable event summary")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Structured contextual event metadata")


class CreateWorkflowRequest(BaseModel):
    repo_path: str = Field(..., description="Local path to a valid Git repository")
    initial_step: Optional[str] = Field(None, description="Optional description of the initial workflow step")
    metadata: Optional[dict[str, Any]] = Field(None, description="Optional initial metadata")


class TransitionWorkflowRequest(BaseModel):
    target_state: WorkflowState = Field(..., description="Desired next workflow state")
    message: Optional[str] = Field(None, description="Optional human-readable transition note")
    metadata: Optional[dict[str, Any]] = Field(None, description="Optional structured transition metadata")


class CancelWorkflowRequest(BaseModel):
    reason: Optional[str] = Field(None, description="Optional reason for cancellation")


class WorkflowResponse(BaseModel):
    workflow_id: str = Field(..., description="Unique workflow identifier")
    repo_path: str = Field(..., description="Validated repository reference path")
    state: WorkflowState = Field(..., description="Current state of the workflow")
    current_step: str = Field(..., description="Current status message or active step")
    created_at: datetime = Field(..., description="Creation timestamp in UTC")
    updated_at: datetime = Field(..., description="Last update timestamp in UTC")
    events: list[WorkflowEvent] = Field(default_factory=list, description="Ordered chronological event history")
    error: Optional[WorkflowErrorDetail] = Field(None, description="Structured error information if workflow failed")


class WorkflowListResponse(BaseModel):
    workflows: list[WorkflowResponse] = Field(..., description="List of workflows")
    total: int = Field(..., description="Total count of workflows in store")
