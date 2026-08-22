"""
Pydantic request/response schemas for all API endpoints.

Centralizing all Pydantic models here ensures a single source of truth
for API contracts and makes them easy to reuse across route files.
"""
from typing import List, Optional

from pydantic import BaseModel


class RecalculateRequest(BaseModel):
    """Request body for POST /api/analytics/recalculate."""

    session_id: Optional[int] = None
    records: Optional[List[dict]] = None
    excluded_indices: List[int] = []


class SitterExclusionRequest(BaseModel):
    """Request body for POST /api/sitters/{sitter_id}/exclude."""

    is_excluded: bool
    reason: Optional[str] = "Manual outlier toggle"


class DeleteSessionsRequest(BaseModel):
    """Request body for DELETE/POST /api/history (batch delete)."""

    session_ids: List[int]


class AnalyzeSessionsRequest(BaseModel):
    """Request body for POST /api/history/analyze."""

    session_ids: List[int]
