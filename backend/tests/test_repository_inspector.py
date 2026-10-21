import subprocess
import tempfile
from pathlib import Path
import pytest

from app.services.repository_inspector import (
    GitExecutionError,
    RepositoryInspector,
    RepositoryNotFoundError,
    RepositorySecurityError,
    RepositoryValidationError,
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
    """Helper to initialize a Git repository with valid author configs."""
    _run_git_cmd(["init"], cwd=directory)
    _run_git_cmd(["config", "user.name", "Test Runner"], cwd=directory)
    _run_git_cmd(["config", "user.email", "test@repomedic.local"], cwd=directory)
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


def test_validate_path_valid_repo(temp_repo_dir: Path):
    inspector = RepositoryInspector(allowed_roots=[temp_repo_dir.parent])
    validated_root = inspector.validate_path(str(temp_repo_dir))
    assert validated_root == temp_repo_dir.resolve()


def test_validate_path_nonexistent(temp_repo_dir: Path):
    inspector = RepositoryInspector(allowed_roots=[temp_repo_dir.parent])
    non_existent = temp_repo_dir / "does_not_exist"
    with pytest.raises(RepositoryNotFoundError) as exc_info:
        inspector.validate_path(str(non_existent))
    assert "does not exist" in str(exc_info.value).lower()


def test_validate_path_file_not_directory(temp_repo_dir: Path):
    file_path = temp_repo_dir / "file.txt"
    file_path.write_text("sample content")
    inspector = RepositoryInspector(allowed_roots=[temp_repo_dir.parent])
    with pytest.raises(RepositoryValidationError) as exc_info:
        inspector.validate_path(str(file_path))
    assert "not a directory" in str(exc_info.value).lower()


def test_validate_path_not_git_repo():
    with tempfile.TemporaryDirectory() as tmp_dir:
        non_git_dir = Path(tmp_dir) / "not_git"
        non_git_dir.mkdir()
        inspector = RepositoryInspector(allowed_roots=[tmp_dir])
        with pytest.raises(RepositoryValidationError) as exc_info:
            inspector.validate_path(str(non_git_dir))
        assert "not a git repository" in str(exc_info.value).lower()


def test_validate_path_remote_url_rejected():
    inspector = RepositoryInspector()
    with pytest.raises(RepositorySecurityError) as exc_info:
        inspector.validate_path("https://github.com/example/repo.git")
    assert "remote" in str(exc_info.value).lower()

    with pytest.raises(RepositorySecurityError):
        inspector.validate_path("git@github.com:example/repo.git")


def test_validate_path_outside_allowed_roots():
    with tempfile.TemporaryDirectory() as allowed_dir:
        with tempfile.TemporaryDirectory() as outside_dir:
            outside_repo = Path(outside_dir) / "secret_repo"
            outside_repo.mkdir()
            create_test_git_repo(outside_repo)

            inspector = RepositoryInspector(allowed_roots=[allowed_dir])
            with pytest.raises(RepositorySecurityError) as exc_info:
                inspector.validate_path(str(outside_repo))
            assert "outside allowed" in str(exc_info.value).lower()


def test_validate_path_traversal_attempt(temp_repo_dir: Path):
    inspector = RepositoryInspector(allowed_roots=[temp_repo_dir])
    # Attempting to traverse out of allowed root
    traversal_path = str(temp_repo_dir) + "/../../"
    with pytest.raises(RepositorySecurityError):
        inspector.validate_path(traversal_path)


def test_metadata_clean_and_dirty_working_tree(temp_repo_dir: Path):
    inspector = RepositoryInspector(allowed_roots=[temp_repo_dir.parent])

    # Initial commit
    test_file = temp_repo_dir / "main.py"
    test_file.write_text("print('hello world')\n")
    _run_git_cmd(["add", "main.py"], cwd=temp_repo_dir)
    _run_git_cmd(["commit", "-m", "Initial commit"], cwd=temp_repo_dir)

    # Clean state
    meta = inspector.get_metadata(temp_repo_dir)
    assert meta.commit_hash is not None
    assert len(meta.commit_hash) == 40
    assert not meta.is_dirty
    assert not meta.has_tracked_changes
    assert not meta.has_untracked_changes

    # Modify tracked file
    test_file.write_text("print('hello world updated')\n")
    meta_modified = inspector.get_metadata(temp_repo_dir)
    assert meta_modified.is_dirty
    assert meta_modified.has_tracked_changes
    assert not meta_modified.has_untracked_changes

    # Add untracked file
    untracked_file = temp_repo_dir / "notes.txt"
    untracked_file.write_text("secret scratchpad")
    meta_untracked = inspector.get_metadata(temp_repo_dir)
    assert meta_untracked.is_dirty
    assert meta_untracked.has_tracked_changes
    assert meta_untracked.has_untracked_changes


def test_metadata_detached_head(temp_repo_dir: Path):
    inspector = RepositoryInspector(allowed_roots=[temp_repo_dir.parent])

    # First commit
    f1 = temp_repo_dir / "f1.txt"
    f1.write_text("commit 1")
    _run_git_cmd(["add", "f1.txt"], cwd=temp_repo_dir)
    _run_git_cmd(["commit", "-m", "First"], cwd=temp_repo_dir)
    proc_first = _run_git_cmd(["rev-parse", "HEAD"], cwd=temp_repo_dir)
    first_sha = proc_first.stdout.strip()

    # Second commit
    f1.write_text("commit 2")
    _run_git_cmd(["add", "f1.txt"], cwd=temp_repo_dir)
    _run_git_cmd(["commit", "-m", "Second"], cwd=temp_repo_dir)

    # Detach HEAD to first commit
    _run_git_cmd(["checkout", first_sha], cwd=temp_repo_dir)

    meta = inspector.get_metadata(temp_repo_dir)
    assert meta.is_detached is True
    assert meta.branch is None
    assert "detached at" in meta.head_description
    assert meta.commit_hash == first_sha


def test_tracked_files_listing_and_normalization(temp_repo_dir: Path):
    inspector = RepositoryInspector(allowed_roots=[temp_repo_dir.parent])

    (temp_repo_dir / "src" / "components").mkdir(parents=True)
    (temp_repo_dir / "src" / "components" / "Button.tsx").write_text("// button")
    (temp_repo_dir / "src" / "index.ts").write_text("// index")
    (temp_repo_dir / "README.md").write_text("# Readme")

    _run_git_cmd(["add", "."], cwd=temp_repo_dir)
    _run_git_cmd(["commit", "-m", "Add source files"], cwd=temp_repo_dir)

    res = inspector.list_tracked_files(temp_repo_dir, limit=10, offset=0)
    assert res.total_count == 3
    assert not res.truncated
    assert "src/components/Button.tsx" in res.files
    assert "src/index.ts" in res.files
    assert "README.md" in res.files

    # Test pagination
    paged = inspector.list_tracked_files(temp_repo_dir, limit=2, offset=0)
    assert len(paged.files) == 2
    assert paged.total_count == 3
    assert paged.truncated is True


def test_tracked_files_sensitive_and_generated_exclusion(temp_repo_dir: Path):
    inspector = RepositoryInspector(allowed_roots=[temp_repo_dir.parent])

    # Legitimate source file
    (temp_repo_dir / "app.py").write_text("print('ok')")

    # Sensitive files
    (temp_repo_dir / ".env").write_text("DB_PASS=123")
    (temp_repo_dir / ".env.local").write_text("API_KEY=xyz")
    (temp_repo_dir / "id_rsa").write_text("PRIVATE KEY")
    (temp_repo_dir / "server.key").write_text("SERVER KEY")
    (temp_repo_dir / "credentials.json").write_text('{"token": "abc"}')

    # Generated directories
    (temp_repo_dir / "node_modules").mkdir()
    (temp_repo_dir / "node_modules" / "package.json").write_text("{}")
    (temp_repo_dir / ".venv").mkdir()
    (temp_repo_dir / ".venv" / "pyvenv.cfg").write_text("version = 3")
    (temp_repo_dir / "dist").mkdir()
    (temp_repo_dir / "dist" / "bundle.js").write_text("bundle")
    (temp_repo_dir / "__pycache__").mkdir()
    (temp_repo_dir / "__pycache__" / "app.cpython-312.pyc").write_text("cache")

    _run_git_cmd(["add", "-f", "."], cwd=temp_repo_dir)
    _run_git_cmd(["commit", "-m", "Add mixed files"], cwd=temp_repo_dir)

    res = inspector.list_tracked_files(temp_repo_dir, limit=100)
    assert res.files == ["app.py"]
    assert res.total_count == 1


def test_tracked_files_empty_repo(temp_repo_dir: Path):
    inspector = RepositoryInspector(allowed_roots=[temp_repo_dir.parent])
    res = inspector.list_tracked_files(temp_repo_dir)
    assert res.files == []
    assert res.total_count == 0
    assert res.truncated is False


def test_search_source_code_literal_matches(temp_repo_dir: Path):
    inspector = RepositoryInspector(allowed_roots=[temp_repo_dir.parent])

    f1 = temp_repo_dir / "math.py"
    f1.write_text("def add(a, b):\n    # TODO: optimize\n    return a + b\n")

    f2 = temp_repo_dir / "service.py"
    f2.write_text("def run():\n    # TODO: optimize query\n    pass\n")

    _run_git_cmd(["add", "."], cwd=temp_repo_dir)
    _run_git_cmd(["commit", "-m", "Add math and service"], cwd=temp_repo_dir)

    res = inspector.search_source_code(temp_repo_dir, query="TODO: optimize", limit=10)
    assert res.total_matches == 2
    assert not res.truncated
    paths = [m.path for m in res.matches]
    assert "math.py" in paths
    assert "service.py" in paths

    math_match = next(m for m in res.matches if m.path == "math.py")
    assert math_match.line_number == 2
    assert "TODO: optimize" in math_match.line_content


def test_search_malicious_query_treated_as_literal(temp_repo_dir: Path):
    inspector = RepositoryInspector(allowed_roots=[temp_repo_dir.parent])

    f1 = temp_repo_dir / "script.py"
    f1.write_text("line 1\n$(whoami)\nline 3\n")

    _run_git_cmd(["add", "."], cwd=temp_repo_dir)
    _run_git_cmd(["commit", "-m", "Add script"], cwd=temp_repo_dir)

    # Literal search of shell command syntax
    res = inspector.search_source_code(temp_repo_dir, query="$(whoami)")
    assert res.total_matches == 1
    assert res.matches[0].line_number == 2

    # Query with regex characters does not interpret as regex
    res_regex = inspector.search_source_code(temp_repo_dir, query=".*")
    assert res_regex.total_matches == 0


def test_search_empty_query_raises_validation_error(temp_repo_dir: Path):
    inspector = RepositoryInspector(allowed_roots=[temp_repo_dir.parent])
    with pytest.raises(RepositoryValidationError):
        inspector.search_source_code(temp_repo_dir, query="")

    with pytest.raises(RepositoryValidationError):
        inspector.search_source_code(temp_repo_dir, query="   ")


def test_search_truncation_at_limit(temp_repo_dir: Path):
    inspector = RepositoryInspector(allowed_roots=[temp_repo_dir.parent])

    f = temp_repo_dir / "lines.txt"
    f.write_text("\n".join(f"item #{i}: match me" for i in range(15)))

    _run_git_cmd(["add", "."], cwd=temp_repo_dir)
    _run_git_cmd(["commit", "-m", "Add lines"], cwd=temp_repo_dir)

    res = inspector.search_source_code(temp_repo_dir, query="match me", limit=5)
    assert len(res.matches) == 5
    assert res.truncated is True


def test_search_binary_and_oversized_files_excluded(temp_repo_dir: Path):
    inspector = RepositoryInspector(
        allowed_roots=[temp_repo_dir.parent], max_file_size_bytes=50
    )

    # Binary file
    bin_file = temp_repo_dir / "binary.dat"
    bin_file.write_bytes(b"some text with null \x00 byte")

    # Oversized text file (> 50 bytes)
    big_file = temp_repo_dir / "big.txt"
    big_file.write_text("a" * 100)

    # Normal small text file
    normal_file = temp_repo_dir / "normal.txt"
    normal_file.write_text("hello target")

    _run_git_cmd(["add", "."], cwd=temp_repo_dir)
    _run_git_cmd(["commit", "-m", "Add various files"], cwd=temp_repo_dir)

    res = inspector.search_source_code(temp_repo_dir, query="target")
    assert res.total_matches == 1
    assert res.matches[0].path == "normal.txt"

    # Search query inside binary file is not returned
    res_bin = inspector.search_source_code(temp_repo_dir, query="null")
    assert res_bin.total_matches == 0


def test_git_timeout_handling(temp_repo_dir: Path, monkeypatch):
    inspector = RepositoryInspector(allowed_roots=[temp_repo_dir.parent], git_timeout=0.0001)

    def mock_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=0.0001)

    monkeypatch.setattr(subprocess, "run", mock_run)

    with pytest.raises(GitExecutionError) as exc_info:
        inspector.validate_path(str(temp_repo_dir))
    assert "timed out" in str(exc_info.value).lower()
