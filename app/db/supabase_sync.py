"""
Supabase repository and cloud synchronization layer.

Handles real-time dual persistence and Supabase synchronization:
- Synchronously/asynchronously upserts scraped search sessions, sitters, and service rates to Supabase.
- Resiliently catches network errors so that scrapers and frontend requests never fail if remote connection suffers jitter.
- Uses bulk batching for maximum throughput.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.config import settings
from app.db.supabase_client import get_supabase_client

logger = logging.getLogger("rover.db.supabase_sync")


def sync_scrape_session_to_supabase(
    location: str,
    service_type: str,
    radius_km: Optional[float],
    center_lat: Optional[float],
    center_lng: Optional[float],
    pages_requested: int,
    pages_completed: int,
    stats: Dict[str, Any],
    records: List[Dict[str, Any]],
    platform: str = "rover",
) -> Optional[int]:
    """
    Synchronizes a completed scrape session and all extracted sitter profiles and
    service rates to Supabase PostgreSQL.

    Returns the Supabase search_session ID if successful, or None if Supabase is disabled / unavailable.
    Never raises an uncaught exception (guarantees zero downtime/failure in local workflows).
    """
    if not settings.is_supabase_enabled:
        return None

    supabase = get_supabase_client()
    if not supabase:
        logger.warning("Supabase sync skipped: client unavailable.")
        return None

    try:
        now = datetime.now().isoformat()

        # 1. Insert Search Session Record
        # Safe numeric parsing helper
        def _to_float(val: Any) -> Optional[float]:
            if val is None or val == "":
                return None
            try:
                return float(val)
            except (ValueError, TypeError):
                return None

        # 1. Insert Search Session Record
        session_row: Dict[str, Any] = {
            "timestamp": now,
            "location": location,
            "service_type": service_type,
            "radius_km": _to_float(radius_km),
            "center_lat": _to_float(center_lat),
            "center_lng": _to_float(center_lng),
            "pages_requested": int(pages_requested),
            "pages_completed": int(pages_completed),
            "total_sitters": len(records),
            "min_price": _to_float(stats.get("min_price")),
            "avg_price": _to_float(stats.get("avg_price")),
            "median_price": _to_float(stats.get("median_price")),
            "p25_price": _to_float(stats.get("p25_price")),
            "p75_price": _to_float(stats.get("p75_price")),
            "max_price": _to_float(stats.get("max_price")),
        }

        sess_res = supabase.table("search_sessions").insert(session_row).execute()
        sess_data = getattr(sess_res, "data", None)
        if not sess_data or not isinstance(sess_data, list):
            logger.error("Failed to insert search session into Supabase.")
            return None

        supa_session_id = int(sess_data[0]["id"])
        logger.info("Supabase Sync: Created search_session id=%s", supa_session_id)

        if not records:
            return supa_session_id

        # 2. Batch Upsert Sitter Profiles
        # Deduplicate sitters by member_id in current batch
        unique_sitters: Dict[str, Dict[str, Any]] = {}
        for s in records:
            profile_url = str(s.get("profile_url") or "")
            member_id = str(s.get("member_id") or profile_url.split("/members/")[-1].strip("/"))
            if not member_id:
                continue

            unique_sitters[member_id] = {
                "member_id": member_id,
                "name": str(s.get("name") or "Rover Sitter"),
                "profile_url": profile_url or f"https://www.rover.com/members/{member_id}/",
                "headline": s.get("headline"),
                "photo_url": s.get("photo_url"),
                "rating": _to_float(s.get("rating_numeric")) or 5.0,
                "reviews_count": int(s.get("reviews_count") or 0),
                "location": str(s.get("location") or location),
                "neighborhood": str(s.get("neighborhood") or location),
                "postal_code": s.get("postal_code"),
                "lat": _to_float(s.get("lat")),
                "lng": _to_float(s.get("lng")),
                "platform": str(s.get("platform") or platform),
                "first_scraped_at": now,
                "last_updated_at": now,
            }

        sitter_id_map: Dict[str, int] = {}  # member_id -> Supabase sitter_id
        sitters_list = list(unique_sitters.values())

        batch_size = 50
        for i in range(0, len(sitters_list), batch_size):
            chunk = sitters_list[i:i + batch_size]
            upsert_res = supabase.table("sitters").upsert(chunk, on_conflict="member_id").execute()
            upsert_data = getattr(upsert_res, "data", None)
            if upsert_data and isinstance(upsert_data, list):
                for item in upsert_data:
                    if isinstance(item, dict) and "member_id" in item and "id" in item:
                        sitter_id_map[str(item["member_id"])] = int(item["id"])

        logger.info("Supabase Sync: Upserted %d master sitters.", len(sitter_id_map))

        # 3. Link Sitters to Session in session_sitters
        session_sitters_payload = []
        for supa_sitter_id in sitter_id_map.values():
            session_sitters_payload.append({
                "session_id": supa_session_id,
                "sitter_id": supa_sitter_id,
            })

        for i in range(0, len(session_sitters_payload), 100):
            chunk = session_sitters_payload[i:i + 100]
            supabase.table("session_sitters").upsert(chunk, on_conflict="session_id,sitter_id").execute()

        # 4. Upsert Sitter Services Matrix
        services_payload = []
        for s in records:
            profile_url = str(s.get("profile_url") or "")
            member_id = str(s.get("member_id") or profile_url.split("/members/")[-1].strip("/"))
            supa_sitter_id = sitter_id_map.get(member_id)
            if not supa_sitter_id:
                continue

            for srv in s.get("services", []):
                srv_type = str(srv.get("service_type") or "")
                srv_price = _to_float(srv.get("price_numeric"))
                if not srv_type or srv_price is None:
                    continue

                services_payload.append({
                    "sitter_id": supa_sitter_id,
                    "service_type": srv_type,
                    "service_name": str(srv.get("service_name") or srv_type.replace("-", " ").title()),
                    "price_numeric": srv_price,
                    "rate_unit": str(srv.get("rate_unit") or "per service"),
                    "is_active": 1,
                    "last_verified_at": now,
                })

        # Deduplicate services by (sitter_id, service_type) before upsert
        unique_services: Dict[str, Dict[str, Any]] = {}
        for sp in services_payload:
            key = f"{sp['sitter_id']}_{sp['service_type']}"
            unique_services[key] = sp

        srv_list = list(unique_services.values())
        for i in range(0, len(srv_list), 100):
            chunk = srv_list[i:i + 100]
            supabase.table("sitter_services").upsert(chunk, on_conflict="sitter_id,service_type").execute()

        logger.info("Supabase Sync: Upserted %d service rate records for session %s.", len(srv_list), supa_session_id)
        return supa_session_id

    except Exception as exc:
        logger.error("Failed to synchronize scrape session to Supabase: %s", exc, exc_info=True)
        return None
