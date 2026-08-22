"""
Database schema initialization.

Defines the normalized tables:
1. search_sessions  - Audit history & aggregate statistical snapshots
2. sitters          - Master unique sitter profiles (member_id, name, postal_code, neighborhood, lat, lng)
3. session_sitters  - Exact many-to-many relationship linking sitters captured in each search session
4. sitter_services  - 1-to-many normalized service rates per sitter
"""
import logging
from app.db.connection import get_db

logger = logging.getLogger("rover.db.schema")


def init_db() -> None:
    """
    Initializes the database schema, junction tables, and performance indexes.
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

        # ── 2. Master Sitter Profiles (1 Row per Unique Sitter) ─────────────────
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
            postal_code      TEXT,
            lat              REAL,
            lng              REAL,
            platform         TEXT    DEFAULT 'rover',
            first_scraped_at TEXT    NOT NULL,
            last_updated_at  TEXT    NOT NULL
        )
        """)

        # ── 3. Session-to-Sitter Bridge (Exact Session Scope) ───────────────────
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS session_sitters (
            session_id       INTEGER NOT NULL,
            sitter_id        INTEGER NOT NULL,
            PRIMARY KEY (session_id, sitter_id),
            FOREIGN KEY (session_id) REFERENCES search_sessions(id) ON DELETE CASCADE,
            FOREIGN KEY (sitter_id) REFERENCES sitters(id) ON DELETE CASCADE
        )
        """)

        # ── 4. Sitter Services & Real Prices (Multi-Service Rate Table) ────────
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

        # ── Forward-Compatible Column Migrations on sitters ─────────────────────
        cursor.execute("PRAGMA table_info(sitters)")
        columns = {row["name"] for row in cursor.fetchall()}
        if "neighborhood" not in columns:
            cursor.execute("ALTER TABLE sitters ADD COLUMN neighborhood TEXT")
        if "postal_code" not in columns:
            cursor.execute("ALTER TABLE sitters ADD COLUMN postal_code TEXT")
        if "lat" not in columns:
            cursor.execute("ALTER TABLE sitters ADD COLUMN lat REAL")
        if "lng" not in columns:
            cursor.execute("ALTER TABLE sitters ADD COLUMN lng REAL")

        # ── Performance Indexes ───────────────────────────────────────────────────
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_timestamp ON search_sessions(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sitters_member_id ON sitters(member_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sitters_postal_code ON sitters(postal_code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_sitters_session ON session_sitters(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_sitters_sitter ON session_sitters(sitter_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sitter_services_fk ON sitter_services(sitter_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sitter_services_type ON sitter_services(service_type)")

    logger.info("Database schema initialized with session_sitters relation.")
