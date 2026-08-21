"""
Data Access Layer — Repository pattern for all database CRUD operations.

Rules:
- All raw SQL lives here and only here
- Functions accept typed Python arguments and return typed Python dicts/lists
- No FastAPI, no HTTP, no business logic — pure data access
- Routes and services call these functions; they never write SQL directly
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
    """Returns a specific search session along with all its sitter listings."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM search_sessions WHERE id = ?", (session_id,))
        session = cursor.fetchone()
        if not session:
            return None
        cursor.execute(
            "SELECT * FROM sitter_listings WHERE session_id = ? ORDER BY id ASC",
            (session_id,)
        )
        result = dict(session)
        result["sitters"] = [dict(s) for s in cursor.fetchall()]
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
    Saves a complete scrape session: metadata, aggregate stats, and all sitter listings.
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

        for r in records:
            cursor.execute(
                """
                INSERT INTO sitter_listings (
                    session_id, name, raw_price, price_numeric, rating, rating_numeric,
                    reviews, reviews_count, headline, profile_url, photo_url, service_type,
                    location_query, radius_km, lat, lng, service_radius_km, neighborhood, page,
                    is_excluded, excluded_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
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
                    r.get("excluded_reason"),
                ),
            )

    logger.info("Saved session %d with %d sitters.", session_id, len(records))
    return session_id


def delete_session(session_id: int) -> bool:
    """Deletes a single search session and its associated sitter listings."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sitter_listings WHERE session_id = ?", (session_id,))
        cursor.execute("DELETE FROM search_sessions WHERE id = ?", (session_id,))
        return cursor.rowcount > 0


def delete_sessions(session_ids: List[int]) -> int:
    """Batch-deletes multiple search sessions and their sitter listings."""
    if not session_ids:
        return 0
    placeholders = ",".join("?" for _ in session_ids)
    ids_tuple = tuple(session_ids)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"DELETE FROM sitter_listings WHERE session_id IN ({placeholders})", ids_tuple
        )
        cursor.execute(
            f"DELETE FROM search_sessions WHERE id IN ({placeholders})", ids_tuple
        )
        return cursor.rowcount


# ── Sitter Exclusion ───────────────────────────────────────────────────────────

def update_sitter_exclusion(
    sitter_id: int, is_excluded: bool, reason: Optional[str] = None
) -> bool:
    """Persists the outlier exclusion state of a specific sitter listing."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE sitter_listings SET is_excluded = ?, excluded_reason = ? WHERE id = ?",
            (1 if is_excluded else 0, reason, sitter_id),
        )
        return cursor.rowcount > 0


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
    Returns all sitter listings joined with session metadata for master CSV export.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                s.id          AS session_id,
                s.timestamp   AS session_date,
                s.location    AS session_location,
                s.service_type AS session_service,
                s.radius_km   AS session_radius_km,
                l.id          AS sitter_id,
                l.name        AS sitter_name,
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
            """
        )
        return [dict(row) for row in cursor.fetchall()]


# ── Bulk ETL Operations (Normalized Multi-Service Store) ────────────────────────

def upsert_sitters_and_services_bulk(
    sitter_profiles: List[Dict[str, Any]],
    location: str,
    platform: str = "rover"
) -> Dict[str, int]:
    """
    Executes a high-performance transactional batch insert/update:
    1. Upserts unique sitters into the master 'sitters' table.
    2. Upserts all associated service rates into 'sitter_services'.
    Returns count of sitters and services processed.
    """
    now = datetime.now().isoformat()
    sitters_count = 0
    services_count = 0

    with get_db() as conn:
        cursor = conn.cursor()

        for s in sitter_profiles:
            member_id = s.get("member_id") or s.get("profile_url", "").split("/members/")[-1].strip("/")
            if not member_id:
                continue

            # Upsert Sitter Profile
            cursor.execute(
                """
                INSERT INTO sitters (
                    member_id, name, profile_url, headline, photo_url,
                    rating, reviews_count, location, lat, lng, service_radius_km,
                    platform, first_scraped_at, last_updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(member_id) DO UPDATE SET
                    name = excluded.name,
                    headline = excluded.headline,
                    photo_url = coalesce(excluded.photo_url, sitters.photo_url),
                    rating = excluded.rating,
                    reviews_count = excluded.reviews_count,
                    location = excluded.location,
                    lat = coalesce(excluded.lat, sitters.lat),
                    lng = coalesce(excluded.lng, sitters.lng),
                    service_radius_km = coalesce(excluded.service_radius_km, sitters.service_radius_km),
                    last_updated_at = excluded.last_updated_at
                """,
                (
                    member_id,
                    s.get("name", "Rover Sitter"),
                    s.get("profile_url", ""),
                    s.get("headline"),
                    s.get("photo_url"),
                    s.get("rating_numeric") or 5.0,
                    s.get("reviews_count") or 0,
                    location,
                    s.get("lat"),
                    s.get("lng"),
                    s.get("service_radius_km"),
                    platform,
                    now,
                    now
                )
            )
            sitters_count += 1

            # Fetch the sitter ID
            cursor.execute("SELECT id FROM sitters WHERE member_id = ?", (member_id,))
            row = cursor.fetchone()
            if not row:
                continue
            sitter_db_id = row["id"]

            # Upsert each service rate offered by this sitter
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

    logger.info("ETL Bulk Upsert Complete: %d sitters, %d service prices.", sitters_count, services_count)
    return {"sitters_upserted": sitters_count, "services_upserted": services_count}


def get_all_normalized_sitters_with_services() -> List[Dict[str, Any]]:
    """
    Returns all master sitters joined with their full catalog of service pricing.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, member_id, name, profile_url, headline, photo_url,
                   rating, reviews_count, location, lat, lng, platform, last_updated_at
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

