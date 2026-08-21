"""
Database schema initialization.

Defines the 3 core normalized tables:
1. search_sessions  - Audit history & aggregate statistical snapshots
2. sitters          - Master unique sitter profiles (member_id, name, neighborhood, rating, etc.)
3. sitter_services  - 1-to-many normalized service rates per sitter
"""
import logging
from app.db.connection import get_db

logger = logging.getLogger("rover.db.schema")


def init_db() -> None:
    """
    Initializes the simplified 3-table database schema and performance indexes.
    Safe to call on every startup — all statements use IF NOT EXISTS.
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # ── 1. Search Sessions (Audit History & Aggregates) ──────────────────────
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS search_sessions (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp        TEXT    NOT NULL,
            location         TEXT    NOT NULL,
            service_type     TEXT    NOT NULL,
            radius_km        REAL,
            center_lat       REAL,
            center_lng       REAL,
            pages_requested  INTEGER NOT NULL,
            pages_completed  INTEGER NOT NULL,
            total_sitters    INTEGER NOT NULL,
            min_price        REAL,
            avg_price        REAL,
            median_price     REAL,
            p25_price        REAL,
            p75_price        REAL,
            max_price        REAL
        )
        """)

        # ── 2. Normalized Master Sitter Profiles (1 Row per Unique Sitter) ───────
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sitters (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id        TEXT    UNIQUE NOT NULL,
            name             TEXT    NOT NULL,
            profile_url      TEXT    UNIQUE NOT NULL,
            headline         TEXT,
            photo_url        TEXT,
            rating           REAL    DEFAULT 5.0,
            reviews_count    INTEGER DEFAULT 0,
            location         TEXT,
            neighborhood     TEXT,
            platform         TEXT    DEFAULT 'rover',
            first_scraped_at TEXT    NOT NULL,
            last_updated_at  TEXT    NOT NULL
        )
        """)

        # ── 3. Normalized Sitter Services & Real Prices (Multi-Service Rate Table) ─
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sitter_services (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            sitter_id        INTEGER NOT NULL,
            service_type     TEXT    NOT NULL,
            service_name     TEXT    NOT NULL,
            price_numeric    REAL    NOT NULL,
            rate_unit        TEXT    NOT NULL,
            is_active        INTEGER DEFAULT 1,
            last_verified_at TEXT    NOT NULL,
            FOREIGN KEY (sitter_id) REFERENCES sitters(id) ON DELETE CASCADE,
            UNIQUE(sitter_id, service_type)
        )
        """)

        # ── Forward-Compatible Column Migrations on sitters before index creation ─
        cursor.execute("PRAGMA table_info(sitters)")
        columns = {row["name"] for row in cursor.fetchall()}
        if "neighborhood" not in columns:
            cursor.execute("ALTER TABLE sitters ADD COLUMN neighborhood TEXT")
            logger.info("Migration applied: added neighborhood column to sitters table")

        # ── Performance Indexes ───────────────────────────────────────────────────
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_timestamp ON search_sessions(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sitters_member_id ON sitters(member_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sitters_neighborhood ON sitters(neighborhood)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sitter_services_fk ON sitter_services(sitter_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sitter_services_type ON sitter_services(service_type)")

    logger.info("Database schema initialized with 3 clean tables: search_sessions, sitters, sitter_services.")
