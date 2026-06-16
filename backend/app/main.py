from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.demo import router as demo_router
from backend.app.api.health import router as health_router
from backend.app.api.memory import router as memory_router
from backend.app.api.observability import router as observability_router
from backend.app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.app_version)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.demo_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(demo_router)
    app.include_router(memory_router)
    app.include_router(observability_router)
    return app


app = create_app()
