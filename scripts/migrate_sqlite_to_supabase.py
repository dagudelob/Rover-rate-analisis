"""
Data Migration script: SQLite (rover_market.db) -> Supabase PostgreSQL.

Reads all normalized entities from local SQLite and loads them into Supabase tables:
1. search_sessions
2. sitters
3. session_sitters
4. sitter_services
"""
import os
import sys
import sqlite3
import logging
from typing import Dict, Any, List

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import settings
from app.db.supabase_client import get_supabase_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("rover.migration")


def migrate():
    supabase = get_supabase_client()
    if not supabase:
        logger.error("Supabase client is not available. Please verify SUPABASE_URL and SUPABASE_KEY.")
        sys.exit(1)

    sqlite_path = settings.db_path
    if not os.path.exists(sqlite_path):
        logger.error("SQLite database not found at %s", sqlite_path)
        sys.exit(1)

    logger.info("Connecting to SQLite database: %s", sqlite_path)
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. Migrate sitters
    cursor.execute("SELECT * FROM sitters ORDER BY id ASC")
    sqlite_sitters = [dict(r) for r in cursor.fetchall()]
    logger.info("Found %d sitters in SQLite.", len(sqlite_sitters))

    sitter_id_map: Dict[int, int] = {}  # sqlite_id -> supabase_id
    batch_size = 50

    for i in range(0, len(sqlite_sitters), batch_size):
        chunk = sqlite_sitters[i:i + batch_size]
        payload = []
        for s in chunk:
            payload.append({
                "member_id": s["member_id"],
                "name": s["name"],
                "profile_url": s["profile_url"],
                "headline": s.get("headline"),
                "photo_url": s.get("photo_url"),
                "rating": float(s["rating"]) if s.get("rating") is not None else 5.0,
                "reviews_count": int(s["reviews_count"]) if s.get("reviews_count") is not None else 0,
                "location": s.get("location"),
                "neighborhood": s.get("neighborhood"),
                "postal_code": s.get("postal_code"),
                "lat": float(s["lat"]) if s.get("lat") is not None else None,
                "lng": float(s["lng"]) if s.get("lng") is not None else None,
                "platform": s.get("platform") or "rover",
                "first_scraped_at": s.get("first_scraped_at") or s.get("last_updated_at"),
                "last_updated_at": s.get("last_updated_at"),
            })
        
        # Upsert on member_id
        res = supabase.table("sitters").upsert(payload, on_conflict="member_id").execute()
        if res.data:
            for item in res.data:
                # Find matching original item by member_id
                orig = next((x for x in chunk if x["member_id"] == item["member_id"]), None)
                if orig:
                    sitter_id_map[orig["id"]] = item["id"]

    logger.info("Migrated/Mapped %d sitters to Supabase.", len(sitter_id_map))

    # 2. Migrate search_sessions
    cursor.execute("SELECT * FROM search_sessions ORDER BY id ASC")
    sqlite_sessions = [dict(r) for r in cursor.fetchall()]
    logger.info("Found %d search_sessions in SQLite.", len(sqlite_sessions))

    session_id_map: Dict[int, int] = {}
    for s in sqlite_sessions:
        row = {
            "timestamp": s["timestamp"],
            "location": s["location"],
            "service_type": s["service_type"],
            "radius_km": float(s["radius_km"]) if s.get("radius_km") is not None else None,
            "center_lat": float(s["center_lat"]) if s.get("center_lat") is not None else None,
            "center_lng": float(s["center_lng"]) if s.get("center_lng") is not None else None,
            "pages_requested": int(s["pages_requested"]),
            "pages_completed": int(s["pages_completed"]),
            "total_sitters": int(s["total_sitters"]),
            "min_price": float(s["min_price"]) if s.get("min_price") is not None else None,
            "avg_price": float(s["avg_price"]) if s.get("avg_price") is not None else None,
            "median_price": float(s["median_price"]) if s.get("median_price") is not None else None,
            "p25_price": float(s["p25_price"]) if s.get("p25_price") is not None else None,
            "p75_price": float(s["p75_price"]) if s.get("p75_price") is not None else None,
            "max_price": float(s["max_price"]) if s.get("max_price") is not None else None,
        }
        res = supabase.table("search_sessions").insert(row).execute()
        if res.data and len(res.data) > 0:
            session_id_map[s["id"]] = res.data[0]["id"]

    logger.info("Migrated/Mapped %d search_sessions to Supabase.", len(session_id_map))

    # 3. Migrate session_sitters
    cursor.execute("SELECT * FROM session_sitters")
    sqlite_session_sitters = [dict(r) for r in cursor.fetchall()]
    logger.info("Found %d session_sitters relations in SQLite.", len(sqlite_session_sitters))

    ss_payload = []
    for ss in sqlite_session_sitters:
        supa_sess_id = session_id_map.get(ss["session_id"])
        supa_sitter_id = sitter_id_map.get(ss["sitter_id"])
        if supa_sess_id and supa_sitter_id:
            ss_payload.append({
                "session_id": supa_sess_id,
                "sitter_id": supa_sitter_id
            })

    for i in range(0, len(ss_payload), 100):
        chunk = ss_payload[i:i + 100]
        supabase.table("session_sitters").upsert(chunk, on_conflict="session_id,sitter_id").execute()

    logger.info("Migrated %d session_sitters relations to Supabase.", len(ss_payload))

    # 4. Migrate sitter_services
    cursor.execute("SELECT * FROM sitter_services")
    sqlite_services = [dict(r) for r in cursor.fetchall()]
    logger.info("Found %d sitter_services in SQLite.", len(sqlite_services))

    srv_payload = []
    for srv in sqlite_services:
        supa_sitter_id = sitter_id_map.get(srv["sitter_id"])
        if supa_sitter_id:
            srv_payload.append({
                "sitter_id": supa_sitter_id,
                "service_type": srv["service_type"],
                "service_name": srv.get("service_name") or srv["service_type"],
                "price_numeric": float(srv["price_numeric"]),
                "rate_unit": srv.get("rate_unit") or "per service",
                "is_active": int(srv.get("is_active", 1)),
                "last_verified_at": srv.get("last_verified_at"),
            })

    for i in range(0, len(srv_payload), 100):
        chunk = srv_payload[i:i + 100]
        supabase.table("sitter_services").upsert(chunk, on_conflict="sitter_id,service_type").execute()

    logger.info("Migrated %d sitter_services to Supabase.", len(srv_payload))
    logger.info("=== Migration from SQLite to Supabase completed successfully! ===")


if __name__ == "__main__":
    migrate()
