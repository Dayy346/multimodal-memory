"""FastAPI entrypoint."""

from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import jobs, media, query, roots
from app.api import settings as settings_api
from app.core.config import get_settings
from config.settings import ensure_output_dirs

logger = logging.getLogger(__name__)


def _warmup_embeddings() -> None:
    try:
        from multimodal_memory.embed import ensure_model_loaded

        ensure_model_loaded()
    except Exception:
        logger.exception("Embedding model warmup failed")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_output_dirs()
    threading.Thread(
        target=_warmup_embeddings,
        daemon=True,
        name="embed-warmup",
    ).start()
    yield


def create_app() -> FastAPI:
    app_settings = get_settings()
    application = FastAPI(title="multimodal-memory", lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(roots.router, prefix="/api")
    application.include_router(jobs.router, prefix="/api")
    application.include_router(query.router, prefix="/api")
    application.include_router(media.router, prefix="/api")
    application.include_router(settings_api.router, prefix="/api")

    @application.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
