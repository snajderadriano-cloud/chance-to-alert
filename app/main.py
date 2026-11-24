"""Main entrypoint for Chance to Alert.App FastAPI backend service."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.deps import get_app_state
from app.api.v1.router import api_v1_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan management."""
    state = get_app_state()
    # Prune expired tracks on startup
    state.tracker.prune_expired()

    # Automatically launch Telegram live ingestion in background
    tg_task = None
    try:
        from app.ingestion.telegram_live import TelegramLiveListener
        listener = TelegramLiveListener()
        tg_task = asyncio.create_task(listener.start())
    except Exception:
        pass

    yield

    if tg_task:
        tg_task.cancel()
    # Cleanup on shutdown
    state.storage.close()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(
        title="Chance to Alert.App",
        description="Air raid and drone threat probability calculation and early warning engine",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Enable Cross-Origin Resource Sharing (CORS) for web apps, shortcuts, and frontend clients
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health check endpoint
    @application.get("/health", tags=["Health"])
    async def health_check():
        return {
            "status": "ok",
            "service": "chance-to-alert",
            "version": "1.0.0",
        }

    # Mount v1 API router
    application.include_router(api_v1_router)

    # Static assets and Web App root route
    static_dir = Path(__file__).resolve().parent.parent / "static"
    if static_dir.exists():
        application.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        @application.get("/", include_in_schema=False)
        async def serve_index():
            index_path = static_dir / "index.html"
            if index_path.exists():
                return FileResponse(
                    index_path,
                    headers={"Cache-Control": "no-cache, no-store, must-revalidate, max-age=0"}
                )
            return {"status": "Chance to Alert API Running"}

        @application.get("/manifest.json", include_in_schema=False)
        async def serve_manifest():
            manifest_path = static_dir / "manifest.json"
            if manifest_path.exists():
                return FileResponse(manifest_path, media_type="application/manifest+json")
            return {"error": "manifest not found"}

        @application.get("/sw.js", include_in_schema=False)
        async def serve_sw():
            sw_path = static_dir / "sw.js"
            if sw_path.exists():
                return FileResponse(
                    sw_path,
                    media_type="application/javascript",
                    headers={"Cache-Control": "no-cache, no-store, must-revalidate, max-age=0"}
                )
            return {"error": "sw not found"}

    return application


app = create_app()
