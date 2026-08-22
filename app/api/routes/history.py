"""
History and Sitter management API routes.

Provides endpoints to:
- List all past search sessions
- Retrieve full session detail by ID
- Analyze one or multiple user-selected sessions
- Delete single or multiple sessions
- Purge/reset the entire database
"""
import logging
from fastapi import APIRouter, HTTPException

from app.models.schemas import DeleteSessionsRequest, AnalyzeSessionsRequest
from app.db.repository import (
    get_all_sessions,
    get_session_by_id,
    get_sessions_sitters_combined,
    delete_session,
    delete_sessions,
    clear_entire_database,
)
from app.services.analytics import calculate_market_statistics, detect_outliers_iqr

logger = logging.getLogger("rover.api.history")
router = APIRouter(prefix="/api", tags=["History"])


@router.get("/history")
async def list_history():
    """Returns all past search history sessions."""
    sessions = get_all_sessions()
    return {"sessions": sessions}


@router.post("/history/analyze")
async def analyze_selected_sessions(req: AnalyzeSessionsRequest):
    """
    Analyzes one or multiple user-selected search sessions from the database.
    Returns combined market statistics, 5-service models, CDF, and sitter records.
    """
    if not req.session_ids:
        raise HTTPException(status_code=400, detail="No session IDs provided for analysis.")

    combined = get_sessions_sitters_combined(req.session_ids)
    sitters = combined.get("sitters", [])
    if not sitters:
        raise HTTPException(status_code=404, detail="No sitters found for the selected session(s).")

    stats = calculate_market_statistics(sitters)
    outliers = detect_outliers_iqr(sitters)

    return {
        "status": "success",
        "session_ids": req.session_ids,
        "location": combined.get("location"),
        "service_type": combined.get("service_type"),
        "center_lat": combined.get("center_lat"),
        "center_lng": combined.get("center_lng"),
        "total_sitters": len(sitters),
        "records": sitters,
        "stats": stats,
        "auto_outliers": outliers,
    }


@router.delete("/history/{session_id}")
@router.post("/history/{session_id}/delete")
async def delete_history_session(session_id: int):
    """Deletes a single search session."""
    success = delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "success", "deleted_session_id": session_id}


@router.delete("/history")
@router.post("/history/delete-batch")
async def delete_history_sessions_batch(req: DeleteSessionsRequest):
    """Batch deletes multiple search sessions."""
    count = delete_sessions(req.session_ids)
    return {"status": "success", "deleted_count": count}


@router.post("/database/reset")
@router.post("/history/clear-all")
async def reset_database():
    """Completely wipes all tables in the database."""
    res = clear_entire_database()
    return res


@router.get("/history/{session_id}")
async def get_session_details(session_id: int):
    """Returns complete session details including full analytics distribution."""
    session = get_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    sitters = session.get("sitters", [])
    stats = calculate_market_statistics(sitters)
    outliers = detect_outliers_iqr(sitters)

    session["full_stats"] = stats
    session["auto_outliers"] = outliers
    return session
