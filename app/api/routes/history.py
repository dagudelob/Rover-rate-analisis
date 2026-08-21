"""
History and Sitter management API routes.

Provides endpoints to:
- List all past search sessions
- Retrieve full session detail by ID
- Delete a single session or batch-delete sessions
- Toggle sitter outlier exclusion in the database
"""
import logging
from fastapi import APIRouter, HTTPException

from app.models.schemas import DeleteSessionsRequest, SitterExclusionRequest
from app.db.repository import (
    get_all_sessions,
    get_session_by_id,
    delete_session,
    delete_sessions,
    update_sitter_exclusion,
)
from app.services.analytics import calculate_market_statistics, detect_outliers_iqr

logger = logging.getLogger("rover.api.history")
router = APIRouter(prefix="/api", tags=["History"])


@router.get("/history")
async def list_history():
    """Returns search history sessions."""
    sessions = get_all_sessions()
    return {"sessions": sessions}


@router.delete("/api/history/{session_id}")
@router.delete("/history/{session_id}")
async def delete_history_session(session_id: int):
    """Deletes a single search session and associated sitters."""
    success = delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "success", "deleted_session_id": session_id}


@router.delete("/api/history")
@router.delete("/history")
async def delete_history_sessions_batch(req: DeleteSessionsRequest):
    """Batch deletes multiple search sessions."""
    count = delete_sessions(req.session_ids)
    return {"status": "success", "deleted_count": count}


@router.get("/history/{session_id}")
async def get_session_details(session_id: int):
    """Returns complete session details including full analytics distribution."""
    session = get_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    sitters = session.get("sitters", [])
    pre_excluded_indices = {
        idx for idx, s in enumerate(sitters)
        if s.get("is_excluded") == 1
    }

    stats = calculate_market_statistics(sitters, excluded_indices=pre_excluded_indices)
    outliers = detect_outliers_iqr(sitters)

    session["full_stats"] = stats
    session["auto_outliers"] = outliers
    session["persisted_excluded_indices"] = list(pre_excluded_indices)
    return session


@router.post("/sitters/{sitter_id}/exclude")
async def toggle_sitter_exclusion_endpoint(sitter_id: int, req: SitterExclusionRequest):
    """Persists a sitter exclusion state into the database."""
    success = update_sitter_exclusion(sitter_id, req.is_excluded, req.reason)
    if not success:
        raise HTTPException(status_code=404, detail="Sitter listing not found")
    return {"status": "success", "sitter_id": sitter_id, "is_excluded": req.is_excluded}
