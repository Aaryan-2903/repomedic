from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.config import settings
from app.schemas.repository import (
    RepositoryMetadataResponse,
    RepositoryValidateRequest,
    RepositoryValidateResponse,
    SearchResponse,
    TrackedFilesResponse,
)
from app.services.repository_inspector import (
    GitExecutionError,
    RepositoryInspector,
    RepositoryNotFoundError,
    RepositorySecurityError,
    RepositoryValidationError,
)

router = APIRouter()


def get_repository_inspector() -> RepositoryInspector:
    return RepositoryInspector(
        allowed_roots=settings.get_allowed_roots(),
        git_timeout=settings.git_timeout_seconds,
        max_file_size_bytes=settings.max_file_size_bytes,
        max_query_length=settings.max_search_query_length,
    )


def _handle_inspector_error(exc: Exception) -> HTTPException:
    if isinstance(exc, RepositoryNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, RepositorySecurityError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, RepositoryValidationError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if isinstance(exc, GitExecutionError):
        code = (
            status.HTTP_504_GATEWAY_TIMEOUT
            if "timed out" in str(exc).lower()
            else status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        return HTTPException(status_code=code, detail=str(exc))
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Unexpected repository inspection error: {exc}",
    )


@router.post("/validate", response_model=RepositoryValidateResponse)
@router.get("/validate", response_model=RepositoryValidateResponse)
def validate_repository(
    body: Optional[RepositoryValidateRequest] = None,
    path: Optional[str] = Query(None, description="Path to the repository"),
    inspector: RepositoryInspector = Depends(get_repository_inspector),
) -> RepositoryValidateResponse:
    """
    Validates that a local filesystem path exists, is inside allowed roots,
    and resolves to a valid Git repository working tree.
    """
    target_path = body.path if body is not None else path
    if not target_path or not target_path.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository path must be provided in request body or 'path' query parameter",
        )

    try:
        repo_root = inspector.validate_path(target_path)
        resolved_input = Path(target_path).resolve().as_posix()
        return RepositoryValidateResponse(
            valid=True,
            path=resolved_input,
            repo_root=repo_root.as_posix(),
            message="Repository is a valid Git working tree",
        )
    except Exception as exc:
        raise _handle_inspector_error(exc) from exc


@router.get("/metadata", response_model=RepositoryMetadataResponse)
def get_repository_metadata(
    path: str = Query(..., description="Local path to the target repository directory"),
    inspector: RepositoryInspector = Depends(get_repository_inspector),
) -> RepositoryMetadataResponse:
    """
    Retrieves Git metadata for a valid repository:
    root path, current branch or detached-HEAD state, commit SHA, and dirty status.
    """
    try:
        repo_root = inspector.validate_path(path)
        return inspector.get_metadata(repo_root)
    except Exception as exc:
        raise _handle_inspector_error(exc) from exc


@router.get("/files", response_model=TrackedFilesResponse)
def get_tracked_files(
    path: str = Query(..., description="Local path to the target repository directory"),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of files to return"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    inspector: RepositoryInspector = Depends(get_repository_inspector),
) -> TrackedFilesResponse:
    """
    Lists tracked files in the repository using Git, excluding sensitive credentials,
    keys, .env files, caches, and generated vendor directories.
    """
    try:
        repo_root = inspector.validate_path(path)
        return inspector.list_tracked_files(repo_root, limit=limit, offset=offset)
    except Exception as exc:
        raise _handle_inspector_error(exc) from exc


@router.get("/search", response_model=SearchResponse)
def search_repository(
    path: str = Query(..., description="Local path to the target repository directory"),
    q: str = Query(..., min_length=1, max_length=100, description="Literal query string to search for"),
    limit: int = Query(default=20, ge=1, le=100, description="Maximum number of matches to return"),
    case_sensitive: bool = Query(default=False, description="Whether search matching is case-sensitive"),
    inspector: RepositoryInspector = Depends(get_repository_inspector),
) -> SearchResponse:
    """
    Executes a safe literal text search across eligible tracked source files.
    Excludes binary files, oversized files, and secrets.
    """
    try:
        repo_root = inspector.validate_path(path)
        return inspector.search_source_code(
            repo_root, query=q, limit=limit, case_sensitive=case_sensitive
        )
    except Exception as exc:
        raise _handle_inspector_error(exc) from exc
