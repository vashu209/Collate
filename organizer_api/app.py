"""FastAPI application factory."""

from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from organizer_api.routes import operations, proposals, status, tasks


def create_app() -> FastAPI:
    app = FastAPI(
        title="Autonomous File Organizer API",
        description="Local HTTP API for Autonomous File Organizer review and operations",
        version="0.1.0",
    )

    # Restrict to local origins only
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:8000",
            "http://localhost:8000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(status.router)
    app.include_router(proposals.router)
    app.include_router(operations.router)
    app.include_router(tasks.router)

    # Serve built frontend if dist exists
    dist_dir = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    if dist_dir.exists() and dist_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(dist_dir), html=True), name="frontend")

    return app


app = create_app()
