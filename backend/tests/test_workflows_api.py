import subprocess
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services.workflow_orchestrator import default_workflow_store

client = TestClient(app)


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
    _run_git_cmd(["config", "user.name", "API Test Runner"], cwd=directory)
    _run_git_cmd(["config", "user.email", "api@repomedic.local"], cwd=directory)
    _run_git_cmd(["config", "commit.gpgsign", "false"], cwd=directory)
    _run_git_cmd(["config", "core.autocrlf", "false"], cwd=directory)
    return directory


@pytest.fixture
def test_repo():
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_dir = Path(tmp_dir) / "wf_api_repo"
        repo_dir.mkdir()
        create_test_git_repo(repo_dir)

        orig_roots = settings.allowed_repo_roots
        settings.allowed_repo_roots = [tmp_dir]
        default_workflow_store.clear()

        try:
            yield repo_dir
        finally:
            settings.allowed_repo_roots = orig_roots
            default_workflow_store.clear()


def test_api_create_and_get_workflow(test_repo: Path):
    res_create = client.post(
        "/workflows",
        json={"repo_path": str(test_repo), "initial_step": "Diagnosing issue"},
    )
    assert res_create.status_code == 201
    data = res_create.json()
    assert data["workflow_id"].startswith("wf_")
    assert data["state"] == "idle"
    assert data["current_step"] == "Diagnosing issue"
    assert len(data["events"]) == 1

    wf_id = data["workflow_id"]
    res_get = client.get(f"/workflows/{wf_id}")
    assert res_get.status_code == 200
    get_data = res_get.json()
    assert get_data["workflow_id"] == wf_id
    assert get_data["state"] == "idle"


def test_api_create_workflow_invalid_path():
    res = client.post("/workflows", json={"repo_path": "c:/nonexistent_repo_dir_xyz"})
    assert res.status_code in (400, 403, 404)


def test_api_get_workflow_not_found():
    res = client.get("/workflows/wf_doesnotexist")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_api_list_workflows(test_repo: Path):
    client.post("/workflows", json={"repo_path": str(test_repo)})
    client.post("/workflows", json={"repo_path": str(test_repo)})

    res = client.get("/workflows")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 2
    assert len(data["workflows"]) == 2


def test_api_cancel_workflow(test_repo: Path):
    res_create = client.post("/workflows", json={"repo_path": str(test_repo)})
    wf_id = res_create.json()["workflow_id"]

    res_cancel = client.post(
        f"/workflows/{wf_id}/cancel",
        json={"reason": "User abort"},
    )
    assert res_cancel.status_code == 200
    data = res_cancel.json()
    assert data["state"] == "cancelled"
    assert data["current_step"] == "User abort"

    # Cancelling already cancelled workflow returns 400
    res_cancel_again = client.post(f"/workflows/{wf_id}/cancel")
    assert res_cancel_again.status_code == 400


def test_api_transition_workflow(test_repo: Path):
    res_create = client.post("/workflows", json={"repo_path": str(test_repo)})
    wf_id = res_create.json()["workflow_id"]

    # Valid transition: idle -> inspecting
    res_trans = client.post(
        f"/workflows/{wf_id}/transition",
        json={"target_state": "inspecting", "message": "Analyzing repository"},
    )
    assert res_trans.status_code == 200
    assert res_trans.json()["state"] == "inspecting"
    assert res_trans.json()["current_step"] == "Analyzing repository"

    # Invalid transition: inspecting -> completed
    res_invalid = client.post(
        f"/workflows/{wf_id}/transition",
        json={"target_state": "completed"},
    )
    assert res_invalid.status_code == 400
    assert "invalid state transition" in res_invalid.json()["detail"].lower()


def test_api_openapi_schema_contains_workflows():
    res = client.get("/openapi.json")
    assert res.status_code == 200
    schema = res.json()
    paths = schema.get("paths", {})
    assert "/workflows" in paths
    assert "/workflows/{workflow_id}" in paths
    assert "/workflows/{workflow_id}/cancel" in paths
    assert "/workflows/{workflow_id}/transition" in paths
