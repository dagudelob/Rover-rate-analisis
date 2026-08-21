"""
Database schema initialization.

Handles:
- Table creation (CREATE TABLE IF NOT EXISTS)
- Index creation for query performance
- Forward-compatible schema migrations via PRAGMA table_info
"""
import logging

from app.db.connection import get_db

logger = logging.getLogger("rover.db.schema")


def init_db() -> None:
    """
    Initializes the database schema and performance indexes.
    Safe to call on every startup — all statements use IF NOT EXISTS.
    Also applies forward-compatible column migrations for older databases.
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # ── Search Sessions ────────────────────────────────────────────────────
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

        # ── Sitter Listings (Search Session Snapshot) ──────────────────────────
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sitter_listings (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id       INTEGER NOT NULL,
            name             TEXT,
            raw_price        TEXT,
            price_numeric    REAL,
            rating           TEXT,
            rating_numeric   REAL,
            reviews          TEXT,
            reviews_count    INTEGER,
            headline         TEXT,
            profile_url      TEXT,
            photo_url        TEXT,
            service_type     TEXT,
            location_query   TEXT,
            radius_km        REAL,
            lat              REAL,
            lng              REAL,
            service_radius_km REAL,
            neighborhood     TEXT,
            page             INTEGER,
            is_excluded      INTEGER DEFAULT 0,
            excluded_reason  TEXT,
            FOREIGN KEY (session_id) REFERENCES search_sessions(id) ON DELETE CASCADE
        )
        """)

        # ── Normalized Master Sitter Profiles (1 Row per Unique Sitter) ─────────
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
            lat              REAL,
            lng              REAL,
            service_radius_km REAL,
            platform         TEXT    DEFAULT 'rover',
            first_scraped_at TEXT    NOT NULL,
            last_updated_at  TEXT    NOT NULL
        )
        """)

        # ── Normalized Sitter Services & Prices (Multi-Service Rate Table) ──────
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

        # ── Batch ETL Audit Runs ───────────────────────────────────────────────
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS etl_runs (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at       TEXT    NOT NULL,
            completed_at     TEXT,
            location         TEXT    NOT NULL,
            platforms        TEXT    NOT NULL,
            total_sitters_processed INTEGER DEFAULT 0,
            total_services_extracted INTEGER DEFAULT 0,
            status           TEXT    DEFAULT 'running',
            error_message    TEXT
        )
        """)

        # ── Indexes ────────────────────────────────────────────────────────────
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sitter_session   ON sitter_listings(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sitter_price     ON sitter_listings(price_numeric)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_timestamp ON search_sessions(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sitters_member_id ON sitters(member_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sitter_services_fk ON sitter_services(sitter_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sitter_services_type ON sitter_services(service_type)")

        # ── Forward-Compatible Migrations ──────────────────────────────────────
        cursor.execute("PRAGMA table_info(sitter_listings)")
        columns = {row["name"] for row in cursor.fetchall()}

        if "is_excluded" not in columns:
            cursor.execute("ALTER TABLE sitter_listings ADD COLUMN is_excluded INTEGER DEFAULT 0")
            logger.info("Migration applied: added is_excluded column")

        if "excluded_reason" not in columns:
            cursor.execute("ALTER TABLE sitter_listings ADD COLUMN excluded_reason TEXT")
            logger.info("Migration applied: added excluded_reason column")

    logger.info("Database schema, normalized tables, and indexes initialized successfully.")
