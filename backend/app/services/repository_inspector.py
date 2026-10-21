import fnmatch
import os
import subprocess
from pathlib import Path
from typing import Optional, Sequence
from app.schemas.repository import (
    RepositoryMetadataResponse,
    SearchMatch,
    SearchResponse,
    TrackedFilesResponse,
)


class RepositoryInspectionError(Exception):
    """Base exception for all repository inspection errors."""
    pass


class RepositoryNotFoundError(RepositoryInspectionError):
    """Raised when the target repository path does not exist."""
    pass


class RepositoryValidationError(RepositoryInspectionError):
    """Raised when repository input or format is invalid."""
    pass


class RepositorySecurityError(RepositoryInspectionError):
    """Raised when access is denied due to security or path traversal checks."""
    pass


class GitExecutionError(RepositoryInspectionError):
    """Raised when a Git subprocess fails, times out, or cannot be executed."""
    pass


IGNORED_DIRECTORY_NAMES = {
    ".git",
    ".venv",
    "venv",
    "env",
    ".env",
    "node_modules",
    "dist",
    "build",
    "out",
    "target",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".cache",
    ".tox",
    ".nox",
    ".idea",
    ".vscode",
    ".next",
    ".nuxt",
}

SENSITIVE_FILENAME_PATTERNS = [
    ".env*",
    "*.env",
    ".netrc",
    ".npmrc",
    ".pypirc",
    "*.pem",
    "*.key",
    "*.pkcs12",
    "*.pfx",
    "*.p12",
    "*.jks",
    "*.keystore",
    "id_rsa*",
    "id_dsa*",
    "id_ecdsa*",
    "id_ed25519*",
    "*credential*",
    "*client_secret*",
    "*.token",
    "*.secret",
    "secrets.*",
    "*secret*.json",
    "*secret*.yaml",
    "*secret*.yml",
    "*secret*.txt",
    "*secret*.key",
]

BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".tiff",
    ".pdf", ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar",
    ".exe", ".dll", ".so", ".dylib", ".bin",
    ".pyc", ".pyo", ".pyd", ".class",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".mp3", ".mp4", ".mov", ".avi", ".mkv", ".wav",
    ".iso", ".dmg", ".img",
    ".db", ".sqlite", ".sqlite3",
    ".wasm", ".jar", ".war",
}

REMOTE_URL_PREFIXES = (
    "http://",
    "https://",
    "git@",
    "ssh://",
    "git://",
    "ftp://",
    "ftps://",
)


def is_sensitive_or_ignored_path(rel_path: str) -> bool:
    """
    Determines whether a repository-relative path should be excluded from listings and searches
    because it resides in a generated/vendor directory or represents a sensitive secret file.
    """
    pure_path = Path(rel_path)
    parts = pure_path.parts

    # Exclude any file residing within forbidden/generated directories
    for part in parts[:-1]:
        if part.lower() in IGNORED_DIRECTORY_NAMES:
            return True

    filename = pure_path.name.lower()

    # Exclude top-level directory names if passed as file items
    if filename in IGNORED_DIRECTORY_NAMES:
        return True

    # Exclude sensitive filenames
    for pattern in SENSITIVE_FILENAME_PATTERNS:
        if fnmatch.fnmatch(filename, pattern.lower()):
            return True

    return False


def is_binary_file(path: Path) -> bool:
    """
    Checks if a file is binary using extension checks and null-byte inspection.
    """
    if path.suffix.lower() in BINARY_EXTENSIONS:
        return True

    try:
        with open(path, "rb") as f:
            chunk = f.read(1024)
            if b"\x00" in chunk:
                return True
    except (OSError, PermissionError):
        return True

    return False


class RepositoryInspector:
    """
    Engine for validating local Git repositories, querying metadata,
    listing tracked files, and executing literal source-code search.
    """

    def __init__(
        self,
        allowed_roots: Optional[Sequence[Path | str]] = None,
        git_timeout: float = 5.0,
        max_file_size_bytes: int = 1_000_000,
        max_query_length: int = 100,
    ) -> None:
        if allowed_roots is not None:
            self.allowed_roots = [Path(r).resolve() for r in allowed_roots]
        else:
            self.allowed_roots = [Path.cwd().resolve()]

        self.git_timeout = git_timeout
        self.max_file_size_bytes = max_file_size_bytes
        self.max_query_length = max_query_length

    def _run_git(self, args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        """
        Executes a Git command with argument lists, timeout, and explicit error handling.
        Never invokes shell=True or interpolates unvalidated strings.
        """
        cmd = ["git", "-c", "core.quotepath=false"] + args

        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["GIT_CONFIG_NOSYSTEM"] = "1"

        try:
            return subprocess.run(
                cmd,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.git_timeout,
                check=False,
                shell=False,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            raise GitExecutionError(
                f"Git command timed out after {self.git_timeout}s: {' '.join(cmd)}"
            ) from exc
        except FileNotFoundError as exc:
            raise GitExecutionError("Git executable not found on system PATH") from exc
        except subprocess.SubprocessError as exc:
            raise GitExecutionError(f"Subprocess execution error: {exc}") from exc

    def validate_path(self, raw_path: str) -> Path:
        """
        Validates that raw_path:
        - Is not a remote URL
        - Exists and is a directory
        - Resolves inside one of the configured allowed roots
        - Is a Git working tree

        Returns the resolved top-level repository Path.
        """
        if not raw_path or not raw_path.strip():
            raise RepositoryValidationError("Repository path must not be empty")

        trimmed = raw_path.strip()

        # Reject remote URLs
        if any(trimmed.lower().startswith(prefix) for prefix in REMOTE_URL_PREFIXES):
            raise RepositorySecurityError(
                "Remote repository URLs are not supported; local filesystem path required"
            )

        try:
            resolved = Path(trimmed).resolve()
        except (ValueError, OSError) as exc:
            raise RepositoryValidationError(f"Invalid path format: {exc}") from exc

        # Path traversal and allowed root check
        is_allowed = any(
            resolved == root or root in resolved.parents or resolved.is_relative_to(root)
            for root in self.allowed_roots
        )
        if not is_allowed:
            raise RepositorySecurityError("Access denied: path is outside allowed repository roots")

        if not resolved.exists():
            raise RepositoryNotFoundError(f"Path does not exist: {trimmed}")

        if not resolved.is_dir():
            raise RepositoryValidationError(f"Path is not a directory: {trimmed}")

        # Check Git working tree
        proc = self._run_git(["rev-parse", "--is-inside-work-tree"], cwd=resolved)
        if proc.returncode != 0 or proc.stdout.strip() != "true":
            raise RepositoryValidationError("Path is not a Git repository working tree")

        # Resolve top-level repository root
        root_proc = self._run_git(["rev-parse", "--show-toplevel"], cwd=resolved)
        if root_proc.returncode != 0:
            raise RepositoryValidationError("Unable to determine top-level Git repository root")

        repo_root = Path(root_proc.stdout.strip()).resolve()

        # Re-verify that the canonical top-level root is also within the allowed roots
        is_root_allowed = any(
            repo_root == root or root in repo_root.parents or repo_root.is_relative_to(root)
            for root in self.allowed_roots
        )
        if not is_root_allowed:
            raise RepositorySecurityError("Access denied: repository root is outside allowed roots")

        return repo_root

    def get_metadata(self, repo_root: Path) -> RepositoryMetadataResponse:
        """
        Retrieves Git repository metadata:
        - Repository root
        - Current branch or detached-HEAD representation
        - Current commit hash (or None if unborn)
        - Dirty status with tracked and untracked change flags
        """
        # Branch or detached-HEAD
        branch_proc = self._run_git(["symbolic-ref", "--short", "-q", "HEAD"], cwd=repo_root)
        if branch_proc.returncode == 0:
            branch = branch_proc.stdout.strip()
            is_detached = False
            head_description = branch
        else:
            branch = None
            is_detached = True
            short_sha_proc = self._run_git(["rev-parse", "--short", "HEAD"], cwd=repo_root)
            if short_sha_proc.returncode == 0 and short_sha_proc.stdout.strip():
                head_description = f"HEAD (detached at {short_sha_proc.stdout.strip()})"
            else:
                head_description = "HEAD (unborn)"

        # Commit hash
        commit_proc = self._run_git(["rev-parse", "HEAD"], cwd=repo_root)
        commit_hash = commit_proc.stdout.strip() if commit_proc.returncode == 0 else None

        # Working tree status
        status_proc = self._run_git(["status", "--porcelain"], cwd=repo_root)
        status_lines = [line for line in status_proc.stdout.splitlines() if line.strip()]

        has_untracked = any(line.startswith("??") for line in status_lines)
        has_tracked = any(not line.startswith("??") for line in status_lines)
        is_dirty = has_tracked or has_untracked

        return RepositoryMetadataResponse(
            repo_root=repo_root.as_posix(),
            branch=branch,
            is_detached=is_detached,
            head_description=head_description,
            commit_hash=commit_hash,
            is_dirty=is_dirty,
            has_tracked_changes=has_tracked,
            has_untracked_changes=has_untracked,
        )

    def _get_eligible_tracked_files(self, repo_root: Path) -> list[str]:
        """
        Queries git ls-files and applies security, exclusion, and symlink validation filters.
        Returns repository-relative POSIX paths.
        """
        proc = self._run_git(["ls-files", "-z"], cwd=repo_root)
        if proc.returncode != 0:
            raise GitExecutionError(f"Failed to list tracked files: {proc.stderr}")

        raw_entries = [entry for entry in proc.stdout.split("\0") if entry]
        eligible: list[str] = []

        for entry in raw_entries:
            posix_path = entry.replace("\\", "/")
            if posix_path.startswith("./"):
                posix_path = posix_path[2:]

            if is_sensitive_or_ignored_path(posix_path):
                continue

            full_path = repo_root / posix_path

            # Guard against symlinks pointing outside the repository working tree
            if full_path.is_symlink():
                try:
                    resolved_target = full_path.resolve()
                    if not resolved_target.is_relative_to(repo_root) or not resolved_target.exists():
                        continue
                except (OSError, ValueError):
                    continue

            eligible.append(posix_path)

        return eligible

    def list_tracked_files(
        self, repo_root: Path, limit: int = 100, offset: int = 0
    ) -> TrackedFilesResponse:
        """
        Returns a paginated list of eligible tracked files in the repository.
        """
        all_eligible = self._get_eligible_tracked_files(repo_root)
        total_count = len(all_eligible)

        safe_offset = max(0, offset)
        safe_limit = max(1, limit)

        paged_files = all_eligible[safe_offset : safe_offset + safe_limit]
        truncated = (safe_offset + safe_limit) < total_count

        return TrackedFilesResponse(
            repo_root=repo_root.as_posix(),
            files=paged_files,
            total_count=total_count,
            limit=safe_limit,
            offset=safe_offset,
            truncated=truncated,
        )

    def search_source_code(
        self,
        repo_root: Path,
        query: str,
        limit: int = 20,
        case_sensitive: bool = False,
    ) -> SearchResponse:
        """
        Executes literal text search across eligible tracked source files.
        Never invokes shell commands or regular expressions.
        """
        if not query or not query.strip():
            raise RepositoryValidationError("Search query must not be empty")

        if len(query) > self.max_query_length:
            raise RepositoryValidationError(
                f"Search query exceeds maximum length of {self.max_query_length} characters"
            )

        eligible_files = self._get_eligible_tracked_files(repo_root)
        matches: list[SearchMatch] = []
        truncated = False

        target_query = query if case_sensitive else query.lower()

        for rel_path in eligible_files:
            full_path = repo_root / rel_path

            try:
                if not full_path.is_file():
                    continue

                # Exclude oversized files
                if full_path.stat().st_size > self.max_file_size_bytes:
                    continue

                # Exclude binary files
                if is_binary_file(full_path):
                    continue

                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    for line_number, raw_line in enumerate(f, start=1):
                        search_line = raw_line if case_sensitive else raw_line.lower()

                        if target_query in search_line:
                            clean_excerpt = raw_line.strip("\r\n")[:200]
                            matches.append(
                                SearchMatch(
                                    path=rel_path,
                                    line_number=line_number,
                                    line_content=clean_excerpt,
                                )
                            )

                            if len(matches) >= limit:
                                truncated = True
                                return SearchResponse(
                                    repo_root=repo_root.as_posix(),
                                    query=query,
                                    matches=matches,
                                    total_matches=len(matches),
                                    limit=limit,
                                    truncated=truncated,
                                )
            except (OSError, PermissionError):
                continue

        return SearchResponse(
            repo_root=repo_root.as_posix(),
            query=query,
            matches=matches,
            total_matches=len(matches),
            limit=limit,
            truncated=truncated,
        )
