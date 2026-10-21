import subprocess
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings

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
    _run_git_cmd(["config", "user.email", "api-test@repomedic.local"], cwd=directory)
    _run_git_cmd(["config", "commit.gpgsign", "false"], cwd=directory)
    _run_git_cmd(["config", "core.autocrlf", "false"], cwd=directory)
    return directory


@pytest.fixture
def test_repo():
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_dir = Path(tmp_dir) / "api_test_repo"
        repo_dir.mkdir()
        create_test_git_repo(repo_dir)

        # Ensure settings allows this temp root
        orig_roots = settings.allowed_repo_roots
        settings.allowed_repo_roots = [tmp_dir]

        try:
            yield repo_dir
        finally:
            settings.allowed_repo_roots = orig_roots


def test_api_validate_post_and_get(test_repo: Path):
    # Test POST /repositories/validate with body
    res_post = client.post("/repositories/validate", json={"path": str(test_repo)})
    assert res_post.status_code == 200
    data = res_post.json()
    assert data["valid"] is True
    assert data["repo_root"] == test_repo.resolve().as_posix()

    # Test GET /repositories/validate with query param
    res_get = client.get("/repositories/validate", params={"path": str(test_repo)})
    assert res_get.status_code == 200
    assert res_get.json()["valid"] is True


def test_api_validate_nonexistent():
    fake_path = Path(tempfile.gettempdir()) / "nonexistent_repo_12345"
    res = client.post("/repositories/validate", json={"path": str(fake_path)})
    assert res.status_code == 404
    assert "does not exist" in res.json()["detail"].lower()


def test_api_validate_not_git_repo():
    with tempfile.TemporaryDirectory() as tmp_dir:
        non_git = Path(tmp_dir) / "not_git"
        non_git.mkdir()
        orig_roots = settings.allowed_repo_roots
        settings.allowed_repo_roots = [tmp_dir]
        try:
            res = client.post("/repositories/validate", json={"path": str(non_git)})
            assert res.status_code == 400
            assert "not a git repository" in res.json()["detail"].lower()
        finally:
            settings.allowed_repo_roots = orig_roots


def test_api_validate_remote_url():
    res = client.post("/repositories/validate", json={"path": "https://github.com/org/repo.git"})
    assert res.status_code == 403
    assert "remote" in res.json()["detail"].lower()


def test_api_validate_path_traversal():
    res = client.post("/repositories/validate", json={"path": "../../../../../etc"})
    assert res.status_code in (400, 403, 404)


def test_api_metadata(test_repo: Path):
    f = test_repo / "hello.py"
    f.write_text("print('hello')\n")
    _run_git_cmd(["add", "hello.py"], cwd=test_repo)
    _run_git_cmd(["commit", "-m", "first commit"], cwd=test_repo)

    res = client.get("/repositories/metadata", params={"path": str(test_repo)})
    assert res.status_code == 200
    data = res.json()
    assert data["repo_root"] == test_repo.resolve().as_posix()
    assert data["commit_hash"] is not None
    assert len(data["commit_hash"]) == 40
    assert data["is_dirty"] is False
    assert data["has_tracked_changes"] is False
    assert data["has_untracked_changes"] is False


def test_api_files_listing_and_pagination(test_repo: Path):
    # Add files
    (test_repo / "src").mkdir()
    (test_repo / "src" / "a.py").write_text("a")
    (test_repo / "src" / "b.py").write_text("b")
    (test_repo / "src" / "c.py").write_text("c")

    _run_git_cmd(["add", "."], cwd=test_repo)
    _run_git_cmd(["commit", "-m", "add files"], cwd=test_repo)

    # Page 1
    res1 = client.get("/repositories/files", params={"path": str(test_repo), "limit": 2, "offset": 0})
    assert res1.status_code == 200
    data1 = res1.json()
    assert len(data1["files"]) == 2
    assert data1["total_count"] == 3
    assert data1["truncated"] is True

    # Page 2
    res2 = client.get("/repositories/files", params={"path": str(test_repo), "limit": 2, "offset": 2})
    assert res2.status_code == 200
    data2 = res2.json()
    assert len(data2["files"]) == 1
    assert data2["total_count"] == 3
    assert data2["truncated"] is False


def test_api_search_endpoint(test_repo: Path):
    (test_repo / "handler.py").write_text(
        "import sys\n\ndef process_event(event):\n    # CRITICAL: validate payload\n    return True\n"
    )
    _run_git_cmd(["add", "."], cwd=test_repo)
    _run_git_cmd(["commit", "-m", "add handler"], cwd=test_repo)

    res = client.get(
        "/repositories/search",
        params={"path": str(test_repo), "q": "CRITICAL: validate", "limit": 10},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total_matches"] == 1
    assert data["matches"][0]["path"] == "handler.py"
    assert data["matches"][0]["line_number"] == 4
    assert "CRITICAL: validate payload" in data["matches"][0]["line_content"]


def test_api_search_empty_query_rejected(test_repo: Path):
    res = client.get(
        "/repositories/search",
        params={"path": str(test_repo), "q": "", "limit": 10},
    )
    assert res.status_code in (400, 422)


def test_api_search_invalid_limit(test_repo: Path):
    res = client.get(
        "/repositories/search",
        params={"path": str(test_repo), "q": "test", "limit": 0},
    )
    assert res.status_code == 422


def test_api_openapi_documentation():
    res = client.get("/openapi.json")
    assert res.status_code == 200
    schema = res.json()
    paths = schema.get("paths", {})
    assert "/health" in paths
    assert "/repositories/validate" in paths
    assert "/repositories/metadata" in paths
    assert "/repositories/files" in paths
    assert "/repositories/search" in paths
