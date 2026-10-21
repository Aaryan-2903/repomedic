import concurrent.futures
import subprocess
import tempfile
from pathlib import Path
import pytest

from app.schemas.workflow import WorkflowState
from app.services.repository_inspector import (
    RepositoryInspector,
    RepositoryNotFoundError,
    RepositorySecurityError,
    RepositoryValidationError,
)
from app.services.workflow_orchestrator import (
    InMemoryWorkflowStore,
    InvalidStateTransitionError,
    WorkflowNotCancellableError,
    WorkflowNotFoundError,
    WorkflowOrchestrator,
)


def _run_git_cmd(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git"] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=True,
        shell=False,
    )


def create_test_git_repo(directory: Path) -> Path:
    _run_git_cmd(["init"], cwd=directory)
    _run_git_cmd(["config", "user.name", "Workflow Test Runner"], cwd=directory)
    _run_git_cmd(["config", "user.email", "workflow@repomedic.local"], cwd=directory)
    _run_git_cmd(["config", "commit.gpgsign", "false"], cwd=directory)
    _run_git_cmd(["config", "core.autocrlf", "false"], cwd=directory)
    return directory


@pytest.fixture
def temp_repo_dir():
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_path = Path(tmp_dir) / "test_repo"
        repo_path.mkdir()
        create_test_git_repo(repo_path)
        yield repo_path


@pytest.fixture
def orchestrator(temp_repo_dir: Path):
    store = InMemoryWorkflowStore()
    inspector = RepositoryInspector(allowed_roots=[temp_repo_dir.parent])
    return WorkflowOrchestrator(store=store, inspector=inspector)


def test_workflow_creation_and_retrieval(orchestrator: WorkflowOrchestrator, temp_repo_dir: Path):
    wf = orchestrator.create_workflow(
        repo_path=str(temp_repo_dir),
        initial_step="Analyzing syntax tree",
        metadata={"priority": "high"},
    )

    assert wf.workflow_id.startswith("wf_")
    assert wf.state == WorkflowState.IDLE
    assert wf.repo_path == temp_repo_dir.resolve().as_posix()
    assert wf.current_step == "Analyzing syntax tree"
    assert len(wf.events) == 1
    assert wf.events[0].event_type == "created"
    assert wf.events[0].to_state == WorkflowState.IDLE
    assert wf.events[0].metadata == {"priority": "high"}
    assert wf.error is None

    retrieved = orchestrator.get_workflow(wf.workflow_id)
    assert retrieved.workflow_id == wf.workflow_id
    assert retrieved.state == WorkflowState.IDLE


def test_workflow_creation_invalid_repository_references(orchestrator: WorkflowOrchestrator, temp_repo_dir: Path):
    # Nonexistent path
    with pytest.raises(RepositoryNotFoundError):
        orchestrator.create_workflow(repo_path=str(temp_repo_dir / "nonexistent"))

    # Remote URL
    with pytest.raises(RepositorySecurityError):
        orchestrator.create_workflow(repo_path="https://github.com/org/repo.git")

    # Non-git directory
    with tempfile.TemporaryDirectory() as tmp:
        non_git = Path(tmp) / "plain_dir"
        non_git.mkdir()
        insp = RepositoryInspector(allowed_roots=[tmp])
        orch = WorkflowOrchestrator(store=InMemoryWorkflowStore(), inspector=insp)
        with pytest.raises(RepositoryValidationError):
            orch.create_workflow(repo_path=str(non_git))


def test_workflow_not_found(orchestrator: WorkflowOrchestrator):
    with pytest.raises(WorkflowNotFoundError):
        orchestrator.get_workflow("wf_nonexistent_123")


def test_valid_state_transitions_full_cycle(orchestrator: WorkflowOrchestrator, temp_repo_dir: Path):
    wf = orchestrator.create_workflow(repo_path=str(temp_repo_dir))
    wf_id = wf.workflow_id

    # idle -> inspecting
    wf = orchestrator.transition_state(wf_id, WorkflowState.INSPECTING, "Examining AST")
    assert wf.state == WorkflowState.INSPECTING
    assert wf.current_step == "Examining AST"

    # inspecting -> investigating
    wf = orchestrator.transition_state(wf_id, WorkflowState.INVESTIGATING, "Tracing stack trace")
    assert wf.state == WorkflowState.INVESTIGATING

    # investigating -> reproducing
    wf = orchestrator.transition_state(wf_id, WorkflowState.REPRODUCING, "Running reproduction test")
    assert wf.state == WorkflowState.REPRODUCING

    # reproducing -> patch_proposed
    wf = orchestrator.transition_state(wf_id, WorkflowState.PATCH_PROPOSED, "Synthesized fix")
    assert wf.state == WorkflowState.PATCH_PROPOSED

    # patch_proposed -> verifying
    wf = orchestrator.transition_state(wf_id, WorkflowState.VERIFYING, "Running sandbox suite")
    assert wf.state == WorkflowState.VERIFYING

    # verifying -> completed
    wf = orchestrator.transition_state(wf_id, WorkflowState.COMPLETED, "Patch fully verified")
    assert wf.state == WorkflowState.COMPLETED

    # Total events: 1 (created) + 6 (transitions) = 7
    assert len(wf.events) == 7
    assert wf.events[-1].to_state == WorkflowState.COMPLETED
    assert wf.events[-1].from_state == WorkflowState.VERIFYING


def test_invalid_state_transitions(orchestrator: WorkflowOrchestrator, temp_repo_dir: Path):
    wf = orchestrator.create_workflow(repo_path=str(temp_repo_dir))
    wf_id = wf.workflow_id

    # idle -> completed is invalid
    with pytest.raises(InvalidStateTransitionError) as exc_info:
        orchestrator.transition_state(wf_id, WorkflowState.COMPLETED)
    assert "invalid state transition" in str(exc_info.value).lower()

    # idle -> verifying is invalid
    with pytest.raises(InvalidStateTransitionError):
        orchestrator.transition_state(wf_id, WorkflowState.VERIFYING)


def test_terminal_state_cannot_transition(orchestrator: WorkflowOrchestrator, temp_repo_dir: Path):
    wf = orchestrator.create_workflow(repo_path=str(temp_repo_dir))
    wf_id = wf.workflow_id

    orchestrator.transition_state(wf_id, WorkflowState.INSPECTING)
    orchestrator.transition_state(wf_id, WorkflowState.INVESTIGATING)
    orchestrator.transition_state(wf_id, WorkflowState.PATCH_PROPOSED)
    orchestrator.transition_state(wf_id, WorkflowState.VERIFYING)
    orchestrator.transition_state(wf_id, WorkflowState.COMPLETED)

    # Completed cannot transition back to idle
    with pytest.raises(InvalidStateTransitionError) as exc_info:
        orchestrator.transition_state(wf_id, WorkflowState.IDLE)
    assert "terminal state" in str(exc_info.value).lower()

    # Completed cannot transition to failed
    with pytest.raises(InvalidStateTransitionError):
        orchestrator.transition_state(wf_id, WorkflowState.FAILED)


def test_cancellation_active_and_terminal(orchestrator: WorkflowOrchestrator, temp_repo_dir: Path):
    wf = orchestrator.create_workflow(repo_path=str(temp_repo_dir))
    wf_id = wf.workflow_id

    orchestrator.transition_state(wf_id, WorkflowState.INSPECTING)

    # Cancel active workflow
    cancelled_wf = orchestrator.cancel_workflow(wf_id, reason="User triggered stop")
    assert cancelled_wf.state == WorkflowState.CANCELLED
    assert cancelled_wf.current_step == "User triggered stop"
    assert cancelled_wf.events[-1].event_type == "cancelled"

    # Cancelling already cancelled workflow is rejected
    with pytest.raises(WorkflowNotCancellableError):
        orchestrator.cancel_workflow(wf_id)


def test_failure_recording(orchestrator: WorkflowOrchestrator, temp_repo_dir: Path):
    wf = orchestrator.create_workflow(repo_path=str(temp_repo_dir))
    wf_id = wf.workflow_id

    orchestrator.transition_state(wf_id, WorkflowState.INSPECTING)

    failed_wf = orchestrator.record_failure(
        wf_id,
        error_code="SYNTAX_ERROR",
        error_message="Cannot parse AST in main.py",
        details={"file": "main.py", "line": 42},
    )

    assert failed_wf.state == WorkflowState.FAILED
    assert failed_wf.error is not None
    assert failed_wf.error.code == "SYNTAX_ERROR"
    assert failed_wf.error.message == "Cannot parse AST in main.py"
    assert failed_wf.error.details == {"file": "main.py", "line": 42}
    assert failed_wf.events[-1].event_type == "failed"

    # Recording failure on already failed workflow is rejected
    with pytest.raises(InvalidStateTransitionError):
        orchestrator.record_failure(wf_id, "ANOTHER_ERR", "message")


def test_event_ordering_and_custom_events(orchestrator: WorkflowOrchestrator, temp_repo_dir: Path):
    wf = orchestrator.create_workflow(repo_path=str(temp_repo_dir))
    wf_id = wf.workflow_id

    orchestrator.record_event(wf_id, event_type="log", message="Scanning files")
    orchestrator.transition_state(wf_id, WorkflowState.INSPECTING)
    orchestrator.record_event(wf_id, event_type="log", message="Found 10 source files")

    wf = orchestrator.get_workflow(wf_id)
    assert len(wf.events) == 4
    event_types = [e.event_type for e in wf.events]
    assert event_types == ["created", "log", "state_changed", "log"]

    # Verify timestamps are non-decreasing
    for i in range(len(wf.events) - 1):
        assert wf.events[i].timestamp <= wf.events[i + 1].timestamp


def test_concurrent_workflow_operations(orchestrator: WorkflowOrchestrator, temp_repo_dir: Path):
    """Verifies thread-safety when multiple threads concurrently record events on workflows."""
    wf = orchestrator.create_workflow(repo_path=str(temp_repo_dir))
    wf_id = wf.workflow_id

    def record_dummy_event(idx: int):
        orchestrator.record_event(wf_id, event_type="worker_ping", message=f"Ping #{idx}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(record_dummy_event, i) for i in range(25)]
        for f in concurrent.futures.as_completed(futures):
            f.result()

    wf_final = orchestrator.get_workflow(wf_id)
    # 1 created + 25 worker pings = 26
    assert len(wf_final.events) == 26
