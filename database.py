import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rover_market.db")

def get_db_connection():
    """Returns a SQLite database connection with row factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database schema if tables do not exist."""
    conn = get_db_connection()
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

    # Individual sitter listings table with geospatial fields
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
        FOREIGN KEY (session_id) REFERENCES search_sessions(id) ON DELETE CASCADE
    )
    """)
    conn.commit()
    conn.close()

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
    conn = get_db_connection()
    cursor = conn.cursor()
    
    now = datetime.now().isoformat()
    
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
            location_query, radius_km, lat, lng, service_radius_km, neighborhood, page
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            r.get("page")
        ))
        
    conn.commit()
    conn.close()
    return session_id

def get_all_sessions() -> List[Dict[str, Any]]:
    """Retrieves all past search sessions ordered by newest first."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM search_sessions ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_session_by_id(session_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves a specific search session along with all its sitter listings."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM search_sessions WHERE id = ?", (session_id,))
    session = cursor.fetchone()
    if not session:
        conn.close()
        return None
    
    cursor.execute("SELECT * FROM sitter_listings WHERE session_id = ? ORDER BY id ASC", (session_id,))
    sitters = cursor.fetchall()
    conn.close()
    
    result = dict(session)
    result["sitters"] = [dict(s) for s in sitters]
    return result

def get_master_historical_data() -> List[Dict[str, Any]]:
    """
    Retrieves all records joined with session timestamps and location metadata
    for temporal tracking across the year.
    """
    conn = get_db_connection()
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
            l.profile_url
        FROM sitter_listings l
        JOIN search_sessions s ON l.session_id = s.id
        ORDER BY s.timestamp ASC, l.id ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_temporal_trends_data() -> List[Dict[str, Any]]:
    """
    Returns time-series grouped metrics of average and median prices by search session date.
    """
    conn = get_db_connection()
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
    conn.close()
    return [dict(r) for r in rows]

init_db()
