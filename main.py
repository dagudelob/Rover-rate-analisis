"""
Application entry point for Uvicorn and production ASGI servers.
Maintains full backward compatibility with Dockerfile, docker-compose.yml and dev scripts.
"""
from app.main import app, create_app

__all__ = ["app", "create_app"]
