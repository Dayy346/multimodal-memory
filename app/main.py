"""FastAPI entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import jobs, media, query, roots
from app.core.config import get_settings
from config.settings import ensure_output_dirs


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_output_dirs()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title="multimodal-memory", lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(roots.router, prefix="/api")
    application.include_router(jobs.router, prefix="/api")
    application.include_router(query.router, prefix="/api")
    application.include_router(media.router, prefix="/api")

    @application.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
