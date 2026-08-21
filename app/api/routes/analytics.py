"""
Analytics API routes.

Provides endpoints to:
- Dynamically recalculate statistics for active vs excluded records
- Retrieve longitudinal temporal trend data across sessions
"""
import logging
from fastapi import APIRouter

from app.models.schemas import RecalculateRequest
from app.db.repository import get_session_by_id, get_temporal_trends_data
from app.services.analytics import calculate_market_statistics, detect_outliers_iqr

logger = logging.getLogger("rover.api.analytics")
router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.post("/recalculate")
async def recalculate_stats(req: RecalculateRequest):
    """
    Recalculates advanced market statistics dynamically given active vs excluded record indices.
    Can resolve sitters directly by session_id or from client records payload.
    """
    records_to_process = []

    if req.session_id:
        session = get_session_by_id(req.session_id)
        if session:
            records_to_process = session.get("sitters", [])

    if not records_to_process and req.records is not None:
        records_to_process = req.records

    excluded_set = set(req.excluded_indices)
    stats = calculate_market_statistics(records_to_process, excluded_indices=excluded_set)
    auto_outliers = detect_outliers_iqr(records_to_process)

    return {
        "stats": stats,
        "auto_outliers": auto_outliers,
    }


@router.get("/temporal-trends")
async def temporal_trends():
    """Returns consolidated historical session data for temporal trend visualization."""
    trends = get_temporal_trends_data()
    return {"trends": trends}
