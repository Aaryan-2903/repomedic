from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
import json
from pathlib import Path
from .config import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="Repomedic Agentic Debugging & Verification Platform API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {
        "name": settings.app_name,
        "version": settings.version,
        "docs_url": "/docs",
        "status": "online"
    }

@app.get("/health")
@app.get("/api/v1/health")
def health_check():
    return {
        "status": "healthy",
        "version": settings.version,
        "environment": settings.environment,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sandbox_ready": False,  # Pending Step 4 sandbox integration
    }

@app.get("/api/v1/fixtures")
def list_fixtures():
    """List available reproducible bug fixtures."""
    fixtures_dir = Path(__file__).resolve().parent.parent.parent / "fixtures" / "bugs"
    fixtures = []
    
    if fixtures_dir.exists():
        for fixture_folder in fixtures_dir.iterdir():
            desc_file = fixture_folder / "fixture.json"
            if desc_file.is_file():
                try:
                    with open(desc_file, "r", encoding="utf-8") as f:
                        fixtures.append(json.load(f))
                except Exception:
                    pass
                    
    return {"fixtures": fixtures, "total": len(fixtures)}
