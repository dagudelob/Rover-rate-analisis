"""
Database connection management.

Provides a context manager that:
- Opens a SQLite connection with row_factory for dict-like access
- Enables WAL journal mode for safe concurrent reads
- Enforces foreign key constraints (required for ON DELETE CASCADE)
- Auto-commits on success and rolls back on exception
- Guarantees connection closure via finally block
"""
import sqlite3
import logging
from contextlib import contextmanager
from typing import Generator

from app.config import settings

logger = logging.getLogger("rover.db.connection")


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """
    Yields an open SQLite connection with WAL mode and FK constraints enabled.
    Automatically commits on success and rolls back on any exception.
    """
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row

    # Enable WAL mode: allows concurrent reads while a write is in progress
    conn.execute("PRAGMA journal_mode=WAL;")
    # Enforce foreign key constraints (OFF by default in SQLite)
    conn.execute("PRAGMA foreign_keys=ON;")

    try:
        yield conn
        conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.error("Database transaction rolled back: %s", exc)
        raise
    finally:
        conn.close()
