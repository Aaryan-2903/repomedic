import tempfile
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "RepoMedic API"
    version: str = "0.1.0"
    description: str = "Agentic software debugging and verification platform"
    environment: str = "development"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Repository inspection settings
    allowed_repo_roots: List[str] = []
    git_timeout_seconds: float = 5.0
    max_file_listing_limit: int = 1000
    default_file_listing_limit: int = 100
    max_search_limit: int = 100
    default_search_limit: int = 20
    max_search_query_length: int = 100
    max_file_size_bytes: int = 1_000_000

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def get_allowed_roots(self) -> list[Path]:
        """
        Returns the resolved list of allowed repository roots.
        If allowed_repo_roots is configured, only those are permitted.
        Otherwise, defaults to the project root, cwd, and system temp directory.
        """
        if self.allowed_repo_roots:
            return [Path(p).resolve() for p in self.allowed_repo_roots]

        cwd = Path.cwd().resolve()
        temp_dir = Path(tempfile.gettempdir()).resolve()
        return [cwd, cwd.parent, temp_dir]


settings = Settings()
