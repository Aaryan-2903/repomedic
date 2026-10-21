from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.api.routes.repositories import router as repositories_router
from app.api.routes.workflows import router as workflows_router
from app.config import settings

app = FastAPI(
    title=settings.app_name,
    description=settings.description,
    version=settings.version,
)

app.include_router(health_router)
app.include_router(repositories_router, prefix="/repositories", tags=["repositories"])
app.include_router(workflows_router, prefix="/workflows", tags=["workflows"])
