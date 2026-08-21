"""
FastAPI Application Factory.

Configures:
- Application lifecycle (lifespan)
- Middleware (CORS)
- Static files mounting
- Route inclusion from modular routers
"""
import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.schema import init_db
from app.api.routes.scraping import router as scraping_router
from app.api.routes.history import router as history_router
from app.api.routes.analytics import router as analytics_router
from app.api.routes.export import router as export_router

logger = logging.getLogger("rover.app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager: initializes database schema and WAL mode on startup."""
    logger.info("Initializing Rover Market Intelligence database schema and indexes...")
    init_db()
    logger.info("Application startup complete.")
    yield
    logger.info("Application shutting down.")


def create_app() -> FastAPI:
    """Factory creating and configuring the FastAPI application instance."""
    app = FastAPI(
        title="Rover.com Market Intelligence Platform",
        description="Modular anti-detection multi-page scraper, outlier studio, historical data archive & analytics for Rover.com",
        version="3.0.0",
        lifespan=lifespan,
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Static assets mounting
    if not os.path.exists(settings.static_dir):
        os.makedirs(settings.static_dir, exist_ok=True)

    app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")

    # Serve index HTML at root
    @app.get("/", response_class=HTMLResponse)
    async def serve_index():
        index_path = os.path.join(settings.static_dir, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return HTMLResponse("<h1>Rover Market Intelligence API is running.</h1>")

    # Include modular routers
    app.include_router(scraping_router)
    app.include_router(history_router)
    app.include_router(analytics_router)
    app.include_router(export_router)

    return app


app = create_app()
