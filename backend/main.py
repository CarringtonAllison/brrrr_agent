"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import Database
from backend.routers.markets import create_markets_router
from backend.routers.scans import create_scans_router


def create_app(db_path: str | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        db_path: Override database path (used in tests).
    """
    from backend.config import DB_PATH

    app = FastAPI(title="BRRRR Deal Finder", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    db = Database(db_path or DB_PATH)
    app.state.db = db

    app.include_router(create_markets_router(db))
    app.include_router(create_scans_router(db))

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
