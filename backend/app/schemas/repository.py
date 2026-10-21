from typing import Optional
from pydantic import BaseModel, Field


class RepositoryValidateRequest(BaseModel):
    path: str = Field(..., description="Local filesystem path to the target repository directory")


class RepositoryValidateResponse(BaseModel):
    valid: bool = Field(True, description="Whether the path points to a valid Git repository")
    path: str = Field(..., description="Canonical resolved repository path")
    repo_root: str = Field(..., description="Top-level Git repository working tree root")
    message: str = Field("Repository is a valid Git working tree", description="Validation status message")


class RepositoryMetadataResponse(BaseModel):
    repo_root: str = Field(..., description="Top-level repository directory")
    branch: Optional[str] = Field(None, description="Current branch name, or None if in detached-HEAD state")
    is_detached: bool = Field(False, description="Whether the repository is currently in a detached-HEAD state")
    head_description: str = Field(..., description="Human-readable description of current HEAD (e.g. branch name or detached commit)")
    commit_hash: Optional[str] = Field(None, description="Full commit SHA-1 of HEAD, or None if unborn/no commits")
    is_dirty: bool = Field(False, description="True if the working tree has any tracked or untracked changes")
    has_tracked_changes: bool = Field(False, description="True if there are staged or unstaged modifications to tracked files")
    has_untracked_changes: bool = Field(False, description="True if there are untracked files present in the repository")


class TrackedFilesResponse(BaseModel):
    repo_root: str = Field(..., description="Top-level repository directory")
    files: list[str] = Field(..., description="List of repository-relative POSIX paths of tracked files")
    total_count: int = Field(..., description="Total number of eligible tracked files after filtering")
    limit: int = Field(..., description="Maximum number of files returned in this page")
    offset: int = Field(..., description="Pagination offset applied")
    truncated: bool = Field(..., description="True if more files exist beyond the current offset + limit")


class SearchMatch(BaseModel):
    path: str = Field(..., description="Repository-relative POSIX path of the matching file")
    line_number: int = Field(..., description="1-based line number of the match")
    line_content: str = Field(..., description="Trimmed content of the matching line")


class SearchResponse(BaseModel):
    repo_root: str = Field(..., description="Top-level repository directory")
    query: str = Field(..., description="Literal search query executed")
    matches: list[SearchMatch] = Field(..., description="List of matching lines")
    total_matches: int = Field(..., description="Total matches found in this search batch")
    limit: int = Field(..., description="Maximum number of matches requested")
    truncated: bool = Field(..., description="True if more matches were found and truncated at the limit")
