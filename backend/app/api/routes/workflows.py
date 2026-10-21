from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.routes.repositories import get_repository_inspector
from app.schemas.workflow import (
    CancelWorkflowRequest,
    CreateWorkflowRequest,
    TransitionWorkflowRequest,
    WorkflowListResponse,
    WorkflowResponse,
)
from app.services.repository_inspector import (
    RepositoryInspector,
    RepositoryNotFoundError,
    RepositorySecurityError,
    RepositoryValidationError,
)
from app.services.workflow_orchestrator import (
    InvalidStateTransitionError,
    WorkflowNotCancellableError,
    WorkflowNotFoundError,
    WorkflowOrchestrator,
    default_workflow_store,
)

router = APIRouter()


def get_workflow_orchestrator(
    inspector: RepositoryInspector = Depends(get_repository_inspector),
) -> WorkflowOrchestrator:
    return WorkflowOrchestrator(store=default_workflow_store, inspector=inspector)


def _handle_workflow_error(exc: Exception) -> HTTPException:
    if isinstance(exc, WorkflowNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, (InvalidStateTransitionError, WorkflowNotCancellableError, RepositoryValidationError)):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if isinstance(exc, RepositoryNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, RepositorySecurityError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Internal workflow error: {exc}",
    )


@router.post("", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
def create_workflow(
    request: CreateWorkflowRequest,
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
) -> WorkflowResponse:
    """
    Creates and initializes a new debugging workflow for a validated local repository.
    The workflow begins in the 'idle' state.
    """
    try:
        return orchestrator.create_workflow(
            repo_path=request.repo_path,
            initial_step=request.initial_step,
            metadata=request.metadata,
        )
    except Exception as exc:
        raise _handle_workflow_error(exc) from exc


@router.get("", response_model=WorkflowListResponse)
@router.get("/", response_model=WorkflowListResponse)
def list_workflows(
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
) -> WorkflowListResponse:
    """
    Lists all workflows currently stored in the in-memory orchestrator store.
    """
    workflows = orchestrator.list_workflows()
    return WorkflowListResponse(workflows=workflows, total=len(workflows))


@router.get("/{workflow_id}", response_model=WorkflowResponse)
def get_workflow(
    workflow_id: str,
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
) -> WorkflowResponse:
    """
    Retrieves full workflow status, including current state, timestamps,
    current step message, structured error (if failed), and chronological event history.
    """
    try:
        return orchestrator.get_workflow(workflow_id)
    except Exception as exc:
        raise _handle_workflow_error(exc) from exc


@router.post("/{workflow_id}/cancel", response_model=WorkflowResponse)
def cancel_workflow(
    workflow_id: str,
    request: Optional[CancelWorkflowRequest] = None,
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
) -> WorkflowResponse:
    """
    Cancels an active workflow.
    Fails with HTTP 400 if the workflow is already in a terminal state (completed, failed, cancelled).
    """
    reason = request.reason if request else None
    try:
        return orchestrator.cancel_workflow(workflow_id, reason=reason)
    except Exception as exc:
        raise _handle_workflow_error(exc) from exc


@router.post("/{workflow_id}/transition", response_model=WorkflowResponse)
def transition_workflow(
    workflow_id: str,
    request: TransitionWorkflowRequest,
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
) -> WorkflowResponse:
    """
    Executes an explicit state transition on an active workflow.
    Fails with HTTP 400 if the transition is invalid or the workflow is in a terminal state.
    """
    try:
        return orchestrator.transition_state(
            workflow_id=workflow_id,
            to_state=request.target_state,
            message=request.message,
            metadata=request.metadata,
        )
    except Exception as exc:
        raise _handle_workflow_error(exc) from exc
