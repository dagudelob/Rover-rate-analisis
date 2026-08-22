"""
Data Access Layer — Repository pattern for all database CRUD operations.

Relational architecture with exact session scoping:
1. search_sessions  (audit log & session statistical summaries)
2. sitters          (master unique sitter profiles + real postal code & coordinates)
3. session_sitters  (exact session-to-sitter many-to-many relationship)
4. sitter_services  (1-to-many rate matrix per sitter)
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.db.connection import get_db

logger = logging.getLogger("rover.db.repository")


# ── Sessions ───────────────────────────────────────────────────────────────────

def get_all_sessions() -> List[Dict[str, Any]]:
    """Returns all past search sessions ordered by newest first."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM search_sessions ORDER BY id DESC")
        return [dict(row) for row in cursor.fetchall()]


def get_session_by_id(session_id: int) -> Optional[Dict[str, Any]]:
    """
    Returns a specific search session along with the exact sitters and their services
    captured during that search session.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM search_sessions WHERE id = ?", (session_id,))
        session = cursor.fetchone()
        if not session:
            return None
        
        result = dict(session)
        cursor.execute(
            """
            SELECT s.*
            FROM sitters s
            JOIN session_sitters ss ON s.id = ss.sitter_id
            WHERE ss.session_id = ?
            ORDER BY s.rating DESC, s.reviews_count DESC
            """,
            (session_id,)
        )
        sitters = [dict(s) for s in cursor.fetchall()]
        for s in sitters:
            cursor.execute(
                """
                SELECT service_type, service_name, price_numeric, rate_unit, last_verified_at
                FROM sitter_services
                WHERE sitter_id = ? AND is_active = 1
                ORDER BY price_numeric ASC
                """,
                (s["id"],)
            )
            s["services"] = [dict(srv) for srv in cursor.fetchall()]
            if s.get("price_numeric") is None and s["services"]:
                matched = next(
                    (srv for srv in s["services"] if srv["service_type"] == result["service_type"]),
                    s["services"][0]
                )
                s["price_numeric"] = matched["price_numeric"]
                s["rate_unit"] = matched["rate_unit"]
        
        result["sitters"] = sitters
        return result


def get_sessions_sitters_combined(session_ids: List[int]) -> Dict[str, Any]:
    """
    Returns combined details and all unique sitters across multiple user-selected sessions.
    """
    if not session_ids:
        return {"sessions": [], "sitters": [], "total_sitters": 0}

    placeholders = ",".join("?" for _ in session_ids)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT * FROM search_sessions WHERE id IN ({placeholders}) ORDER BY id DESC",
            tuple(session_ids)
        )
        sessions = [dict(r) for r in cursor.fetchall()]
        if not sessions:
            return {"sessions": [], "sitters": [], "total_sitters": 0}

        cursor.execute(
            f"""
            SELECT DISTINCT s.*
            FROM sitters s
            JOIN session_sitters ss ON s.id = ss.sitter_id
            WHERE ss.session_id IN ({placeholders})
            ORDER BY s.rating DESC, s.reviews_count DESC
            """,
            tuple(session_ids)
        )
        sitters = [dict(s) for s in cursor.fetchall()]
        for s in sitters:
            cursor.execute(
                """
                SELECT service_type, service_name, price_numeric, rate_unit, last_verified_at
                FROM sitter_services
                WHERE sitter_id = ? AND is_active = 1
                ORDER BY price_numeric ASC
                """,
                (s["id"],)
            )
            s["services"] = [dict(srv) for srv in cursor.fetchall()]
            if s.get("price_numeric") is None and s["services"]:
                s["price_numeric"] = s["services"][0]["price_numeric"]
                s["rate_unit"] = s["services"][0]["rate_unit"]

        first_session = sessions[0]
        locations = sorted(list(set(s["location"] for s in sessions if s.get("location"))))
        service_types = set(s["service_type"] for s in sessions if s.get("service_type"))

        return {
            "sessions": sessions,
            "session_ids": session_ids,
            "location": ", ".join(locations) if locations else "Multiple Locations",
            "service_type": list(service_types)[0] if len(service_types) == 1 else "all-services",
            "center_lat": first_session.get("center_lat") or 43.6532,
            "center_lng": first_session.get("center_lng") or -79.3832,
            "sitters": sitters,
            "total_sitters": len(sitters)
        }


def save_scrape_results(
    location: str,
    service_type: str,
    radius_km: Optional[float],
    center_lat: Optional[float],
    center_lng: Optional[float],
    pages_requested: int,
    pages_completed: int,
    stats: Dict[str, Any],
    records: List[Dict[str, Any]],
) -> int:
    """
    Saves search session aggregates and automatically links the exact sitters + services (ETL).
    Returns the newly created session_id.
    """
    now = datetime.now().isoformat()

    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO search_sessions (
                timestamp, location, service_type, radius_km, center_lat, center_lng,
                pages_requested, pages_completed, total_sitters,
                min_price, avg_price, median_price, p25_price, p75_price, max_price
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now, location, service_type, radius_km, center_lat, center_lng,
                pages_requested, pages_completed, len(records),
                stats.get("min_price"),
                stats.get("avg_price"),
                stats.get("median_price"),
                stats.get("p25_price"),
                stats.get("p75_price"),
                stats.get("max_price"),
            ),
        )
        session_id = cursor.lastrowid or 0

    # Bulk upsert records into sitters and sitter_services tables AND link to session_id
    upsert_sitters_and_services_bulk(records, location, "rover", session_id=session_id)

    logger.info("Saved search session %d with %d sitters.", session_id, len(records))
    return session_id


def delete_session(session_id: int) -> bool:
    """
    Deletes a single search session and cleans up orphan sitters without references.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM session_sitters WHERE session_id = ?", (session_id,))
        cursor.execute("DELETE FROM search_sessions WHERE id = ?", (session_id,))
        affected = cursor.rowcount
        # Clean orphan sitters
        cursor.execute("DELETE FROM sitters WHERE id NOT IN (SELECT DISTINCT sitter_id FROM session_sitters)")
        return affected > 0


def delete_sessions(session_ids: List[int]) -> int:
    """
    Batch-deletes multiple search sessions and cleans up orphan sitters.
    """
    if not session_ids:
        return 0
    placeholders = ",".join("?" for _ in session_ids)
    ids_tuple = tuple(session_ids)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"DELETE FROM session_sitters WHERE session_id IN ({placeholders})", ids_tuple
        )
        cursor.execute(
            f"DELETE FROM search_sessions WHERE id IN ({placeholders})", ids_tuple
        )
        deleted_count = cursor.rowcount
        # Clean orphan sitters
        cursor.execute("DELETE FROM sitters WHERE id NOT IN (SELECT DISTINCT sitter_id FROM session_sitters)")
        return deleted_count


def clear_entire_database() -> Dict[str, Any]:
    """
    Purges all records from all database tables and resets SQLite auto-increment counters.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM session_sitters;")
        cursor.execute("DELETE FROM sitter_services;")
        cursor.execute("DELETE FROM sitters;")
        cursor.execute("DELETE FROM search_sessions;")
        try:
            cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('search_sessions', 'sitters', 'sitter_services');")
        except Exception:
            pass
        logger.info("Entire database purged and counters reset.")
        return {"status": "success", "message": "Database completely wiped"}


# ── Analytics Queries ──────────────────────────────────────────────────────────

def get_temporal_trends_data() -> List[Dict[str, Any]]:
    """Returns time-series grouped metrics by session for temporal trend charts."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, timestamp, location, service_type,
                   total_sitters, min_price, avg_price, median_price, max_price
            FROM search_sessions
            ORDER BY timestamp ASC
            """
        )
        return [dict(row) for row in cursor.fetchall()]


def get_master_historical_data() -> List[Dict[str, Any]]:
    """
    Returns all sitters joined with their multi-service rates for master CSV export.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                s.id             AS sitter_id,
                s.member_id,
                s.name           AS sitter_name,
                s.rating,
                s.reviews_count,
                s.location,
                s.neighborhood,
                s.postal_code,
                s.lat,
                s.lng,
                s.profile_url,
                s.first_scraped_at,
                s.last_updated_at,
                srv.service_type,
                srv.service_name,
                srv.price_numeric,
                srv.rate_unit
            FROM sitters s
            LEFT JOIN sitter_services srv ON s.id = srv.sitter_id
            ORDER BY s.last_updated_at DESC, s.name ASC
            """
        )
        return [dict(row) for row in cursor.fetchall()]


# ── Normalized Multi-Service Store Operations ──────────────────────────────────

def upsert_sitters_and_services_bulk(
    sitter_profiles: List[Dict[str, Any]],
    location: str,
    platform: str = "rover",
    session_id: Optional[int] = None
) -> Dict[str, int]:
    """
    Executes a batch upsert into sitters, sitter_services, and links to session_sitters.
    """
    now = datetime.now().isoformat()
    sitters_count = 0
    services_count = 0

    with get_db() as conn:
        cursor = conn.cursor()

        for s in sitter_profiles:
            profile_url = s.get("profile_url", "")
            member_id = s.get("member_id") or profile_url.split("/members/")[-1].strip("/")
            if not member_id or not profile_url:
                continue

            # Upsert Sitter Profile
            cursor.execute(
                """
                INSERT INTO sitters (
                    member_id, name, profile_url, headline, photo_url,
                    rating, reviews_count, location, neighborhood, postal_code, lat, lng,
                    platform, first_scraped_at, last_updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(member_id) DO UPDATE SET
                    name = excluded.name,
                    headline = excluded.headline,
                    photo_url = coalesce(excluded.photo_url, sitters.photo_url),
                    rating = excluded.rating,
                    reviews_count = excluded.reviews_count,
                    location = excluded.location,
                    neighborhood = coalesce(excluded.neighborhood, sitters.neighborhood),
                    postal_code = coalesce(excluded.postal_code, sitters.postal_code),
                    lat = coalesce(excluded.lat, sitters.lat),
                    lng = coalesce(excluded.lng, sitters.lng),
                    last_updated_at = excluded.last_updated_at
                """,
                (
                    member_id,
                    s.get("name", "Rover Sitter"),
                    profile_url,
                    s.get("headline"),
                    s.get("photo_url"),
                    s.get("rating_numeric") or 5.0,
                    s.get("reviews_count") or 0,
                    location,
                    s.get("neighborhood") or location,
                    s.get("postal_code"),
                    s.get("lat"),
                    s.get("lng"),
                    platform,
                    now,
                    now
                )
            )
            sitters_count += 1

            # Fetch the sitter DB ID
            cursor.execute("SELECT id FROM sitters WHERE member_id = ?", (member_id,))
            row = cursor.fetchone()
            if not row:
                continue
            sitter_db_id = row["id"]

            # Link Sitter to Session
            if session_id:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO session_sitters (session_id, sitter_id)
                    VALUES (?, ?)
                    """,
                    (session_id, sitter_db_id)
                )

            # Upsert each real service rate offered by this sitter
            services = s.get("services", [])
            for srv in services:
                srv_type = srv.get("service_type")
                srv_price = srv.get("price_numeric")
                if not srv_type or srv_price is None:
                    continue

                cursor.execute(
                    """
                    INSERT INTO sitter_services (
                        sitter_id, service_type, service_name, price_numeric,
                        rate_unit, is_active, last_verified_at
                    ) VALUES (?, ?, ?, ?, ?, 1, ?)
                    ON CONFLICT(sitter_id, service_type) DO UPDATE SET
                        price_numeric = excluded.price_numeric,
                        rate_unit = excluded.rate_unit,
                        service_name = excluded.service_name,
                        is_active = 1,
                        last_verified_at = excluded.last_verified_at
                    """,
                    (
                        sitter_db_id,
                        srv_type,
                        srv.get("service_name", srv_type.replace("-", " ").title()),
                        float(srv_price),
                        srv.get("rate_unit", "per service"),
                        now
                    )
                )
                services_count += 1

    logger.info("Bulk Upsert: %d sitters, %d service prices (Session %s).", sitters_count, services_count, session_id)
    return {"sitters_upserted": sitters_count, "services_upserted": services_count}


def get_all_normalized_sitters_with_services() -> List[Dict[str, Any]]:
    """
    Returns all master sitters joined with their full catalog of service pricing.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, member_id, name, profile_url, headline, photo_url,
                   rating, reviews_count, location, neighborhood, postal_code, lat, lng, platform, last_updated_at
            FROM sitters
            ORDER BY rating DESC, reviews_count DESC
        """)
        sitters = [dict(r) for r in cursor.fetchall()]

        for s in sitters:
            cursor.execute("""
                SELECT service_type, service_name, price_numeric, rate_unit, last_verified_at
                FROM sitter_services
                WHERE sitter_id = ? AND is_active = 1
                ORDER BY price_numeric ASC
            """, (s["id"],))
            s["services"] = [dict(r) for r in cursor.fetchall()]

        return sitters
