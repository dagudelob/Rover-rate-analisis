"""
Data Access Layer — Repository pattern for all database CRUD operations.

Clean 3-table relational architecture:
1. search_sessions  (audit log & session statistical summaries)
2. sitters          (master unique sitter profiles + real postal code & coordinates)
3. sitter_services  (1-to-many rate matrix per sitter)
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
    """Returns a specific search session along with all sitters and their services."""
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
            WHERE s.location = ?
            ORDER BY s.rating DESC, s.reviews_count DESC
            """,
            (result["location"],)
        )
        sitters = [dict(s) for s in cursor.fetchall()]
        for s in sitters:
            cursor.execute(
                "SELECT service_type, service_name, price_numeric, rate_unit, last_verified_at FROM sitter_services WHERE sitter_id = ? AND is_active = 1",
                (s["id"],)
            )
            s["services"] = [dict(srv) for srv in cursor.fetchall()]
        
        result["sitters"] = sitters
        return result


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
    Saves search session aggregates and automatically upserts sitters + services (ETL).
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

    # Bulk upsert records into sitters and sitter_services tables
    upsert_sitters_and_services_bulk(records, location, "rover")

    logger.info("Saved search session %d with %d sitters.", session_id, len(records))
    return session_id


def delete_session(session_id: int) -> bool:
    """Deletes a single search session from the audit table."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM search_sessions WHERE id = ?", (session_id,))
        return cursor.rowcount > 0


def delete_sessions(session_ids: List[int]) -> int:
    """Batch-deletes multiple search sessions."""
    if not session_ids:
        return 0
    placeholders = ",".join("?" for _ in session_ids)
    ids_tuple = tuple(session_ids)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"DELETE FROM search_sessions WHERE id IN ({placeholders})", ids_tuple
        )
        return cursor.rowcount


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
    platform: str = "rover"
) -> Dict[str, int]:
    """
    Executes a high-performance batch upsert into the 2 core normalized tables:
    1. Upserts unique sitters into 'sitters'.
    2. Upserts each service rate into 'sitter_services'.
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

    logger.info("Bulk Upsert: %d sitters, %d service prices.", sitters_count, services_count)
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
