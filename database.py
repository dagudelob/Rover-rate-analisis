import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional, Generator
from contextlib import contextmanager
import os
import logging

logger = logging.getLogger("rover.database")

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rover_market.db")

@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager providing safe SQLite database connection handling.
    Automatically commits transactions and guarantees connection closure.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database transaction rollback due to error: {e}")
        raise
    finally:
        conn.close()

def init_db():
    """Initializes the database schema and indexes if tables do not exist."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Search sessions table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS search_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            location TEXT NOT NULL,
            service_type TEXT NOT NULL,
            radius_km REAL,
            center_lat REAL,
            center_lng REAL,
            pages_requested INTEGER NOT NULL,
            pages_completed INTEGER NOT NULL,
            total_sitters INTEGER NOT NULL,
            min_price REAL,
            avg_price REAL,
            median_price REAL,
            p25_price REAL,
            p75_price REAL,
            max_price REAL
        )
        """)

        # Individual sitter listings table with geospatial fields and exclusion state
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sitter_listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            name TEXT,
            raw_price TEXT,
            price_numeric REAL,
            rating TEXT,
            rating_numeric REAL,
            reviews TEXT,
            reviews_count INTEGER,
            headline TEXT,
            profile_url TEXT,
            photo_url TEXT,
            service_type TEXT,
            location_query TEXT,
            radius_km REAL,
            lat REAL,
            lng REAL,
            service_radius_km REAL,
            neighborhood TEXT,
            page INTEGER,
            is_excluded INTEGER DEFAULT 0,
            excluded_reason TEXT,
            FOREIGN KEY (session_id) REFERENCES search_sessions(id) ON DELETE CASCADE
        )
        """)

        # Performance Indexes to prevent table scans on high-cardinality queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sitter_session ON sitter_listings(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sitter_price ON sitter_listings(price_numeric)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_timestamp ON search_sessions(timestamp)")

        # Schema evolution safety: check if is_excluded exists in sitter_listings
        cursor.execute("PRAGMA table_info(sitter_listings)")
        columns = [row["name"] for row in cursor.fetchall()]
        if "is_excluded" not in columns:
            cursor.execute("ALTER TABLE sitter_listings ADD COLUMN is_excluded INTEGER DEFAULT 0")
        if "excluded_reason" not in columns:
            cursor.execute("ALTER TABLE sitter_listings ADD COLUMN excluded_reason TEXT")

    logger.info("Database schema and indexes initialized successfully.")

def save_scrape_results(
    location: str,
    service_type: str,
    radius_km: Optional[float],
    center_lat: Optional[float],
    center_lng: Optional[float],
    pages_requested: int,
    pages_completed: int,
    stats: Dict[str, Any],
    records: List[Dict[str, Any]]
) -> int:
    """Saves search metadata, center location, statistics, and individual sitter listings into SQLite."""
    now = datetime.now().isoformat()
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO search_sessions (
            timestamp, location, service_type, radius_km, center_lat, center_lng,
            pages_requested, pages_completed, total_sitters, min_price, avg_price,
            median_price, p25_price, p75_price, max_price
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            now, location, service_type, radius_km, center_lat, center_lng,
            pages_requested, pages_completed, len(records),
            stats.get("min_price"),
            stats.get("avg_price"),
            stats.get("median_price"),
            stats.get("p25_price"),
            stats.get("p75_price"),
            stats.get("max_price")
        ))
        
        session_id = cursor.lastrowid or 0
        
        for r in records:
            cursor.execute("""
            INSERT INTO sitter_listings (
                session_id, name, raw_price, price_numeric, rating, rating_numeric,
                reviews, reviews_count, headline, profile_url, photo_url, service_type,
                location_query, radius_km, lat, lng, service_radius_km, neighborhood, page,
                is_excluded, excluded_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                r.get("name"),
                r.get("raw_price"),
                r.get("price_numeric"),
                r.get("rating"),
                r.get("rating_numeric"),
                r.get("reviews"),
                r.get("reviews_count"),
                r.get("headline"),
                r.get("profile_url"),
                r.get("photo_url"),
                r.get("service_type"),
                r.get("location_query"),
                r.get("radius_km"),
                r.get("lat"),
                r.get("lng"),
                r.get("service_radius_km"),
                r.get("neighborhood"),
                r.get("page"),
                1 if r.get("is_excluded") else 0,
                r.get("excluded_reason")
            ))
            
    return session_id

def update_sitter_exclusion(sitter_id: int, is_excluded: bool, reason: Optional[str] = None) -> bool:
    """Updates the exclusion status of a specific sitter listing."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE sitter_listings
            SET is_excluded = ?, excluded_reason = ?
            WHERE id = ?
        """, (1 if is_excluded else 0, reason, sitter_id))
        return cursor.rowcount > 0

def get_all_sessions() -> List[Dict[str, Any]]:
    """Retrieves all past search sessions ordered by newest first."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM search_sessions ORDER BY id DESC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def get_session_by_id(session_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves a specific search session along with all its sitter listings."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM search_sessions WHERE id = ?", (session_id,))
        session = cursor.fetchone()
        if not session:
            return None
        
        cursor.execute("SELECT * FROM sitter_listings WHERE session_id = ? ORDER BY id ASC", (session_id,))
        sitters = cursor.fetchall()
        
        result = dict(session)
        result["sitters"] = [dict(s) for s in sitters]
        return result

def delete_session(session_id: int) -> bool:
    """Deletes a single search session and its associated sitter listings."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sitter_listings WHERE session_id = ?", (session_id,))
        cursor.execute("DELETE FROM search_sessions WHERE id = ?", (session_id,))
        return cursor.rowcount > 0

def delete_sessions(session_ids: List[int]) -> int:
    """Batch deletes multiple search sessions and associated sitter listings."""
    if not session_ids:
        return 0
    placeholders = ",".join("?" for _ in session_ids)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM sitter_listings WHERE session_id IN ({placeholders})", session_ids)
        cursor.execute(f"DELETE FROM search_sessions WHERE id IN ({placeholders})", session_ids)
        return cursor.rowcount

def get_master_historical_data() -> List[Dict[str, Any]]:
    """
    Retrieves all records joined with session timestamps and location metadata
    for temporal tracking across the year.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                s.id as session_id,
                s.timestamp as session_date,
                s.location as session_location,
                s.service_type as session_service,
                s.radius_km as session_radius_km,
                l.id as sitter_id,
                l.name as sitter_name,
                l.raw_price,
                l.price_numeric,
                l.rating,
                l.reviews_count,
                l.neighborhood,
                l.lat,
                l.lng,
                l.service_radius_km,
                l.profile_url,
                l.is_excluded,
                l.excluded_reason
            FROM sitter_listings l
            JOIN search_sessions s ON l.session_id = s.id
            ORDER BY s.timestamp ASC, l.id ASC
        """)
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

def get_temporal_trends_data() -> List[Dict[str, Any]]:
    """
    Returns time-series grouped metrics of average and median prices by search session date.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                id,
                timestamp,
                location,
                service_type,
                total_sitters,
                min_price,
                avg_price,
                median_price,
                max_price
            FROM search_sessions
            ORDER BY timestamp ASC
        """)
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
