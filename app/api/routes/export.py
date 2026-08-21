"""
Export API routes.

Provides endpoints to:
- Export a single session as CSV
- Export all historical data as master CSV
- Download SQLite database binary
"""
import csv
import io
import os
import logging
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse

from app.config import settings
from app.db.repository import get_session_by_id, get_master_historical_data

logger = logging.getLogger("rover.api.export")
router = APIRouter(prefix="/api/export", tags=["Export"])


@router.get("/csv/{session_id}")
async def export_csv(session_id: int):
    """Generates a CSV file download containing all sitter listings for a specific search session."""
    session = get_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    sitters = session.get("sitters", [])
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "ID", "Name", "Raw_Price", "Price_Numeric", "Rating",
        "Review_Count", "Headline", "Neighborhood", "Latitude", "Longitude", "Service_Radius_KM",
        "Service_Type", "Location_Query", "Page", "Profile_URL", "Is_Excluded", "Excluded_Reason"
    ])

    for s in sitters:
        writer.writerow([
            s.get("id"),
            s.get("name"),
            s.get("raw_price"),
            s.get("price_numeric"),
            s.get("rating"),
            s.get("reviews_count"),
            s.get("headline"),
            s.get("neighborhood"),
            s.get("lat"),
            s.get("lng"),
            s.get("service_radius_km"),
            s.get("service_type"),
            s.get("location_query"),
            s.get("page"),
            s.get("profile_url"),
            s.get("is_excluded"),
            s.get("excluded_reason")
        ])

    output.seek(0)
    loc_slug = session.get("location", "search").replace(" ", "_")
    srv_slug = session.get("service_type", "service")
    filename = f"rover_session_{session_id}_{srv_slug}_{loc_slug}.csv"

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/master-csv")
async def export_master_csv():
    """
    Exports ALL historical search sessions and sitters into a master timestamped CSV archive.
    """
    rows = get_master_historical_data()
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Session_ID", "Session_Date_ISO", "Session_Location", "Service_Type", "Search_Radius_KM",
        "Sitter_ID", "Sitter_Name", "Raw_Price", "Price_Numeric", "Rating",
        "Review_Count", "Neighborhood", "Latitude", "Longitude", "Service_Radius_KM", "Profile_URL",
        "Is_Excluded", "Excluded_Reason"
    ])

    for r in rows:
        writer.writerow([
            r.get("session_id"),
            r.get("session_date"),
            r.get("session_location"),
            r.get("session_service"),
            r.get("session_radius_km"),
            r.get("sitter_id"),
            r.get("sitter_name"),
            r.get("raw_price"),
            r.get("price_numeric"),
            r.get("rating"),
            r.get("reviews_count"),
            r.get("neighborhood"),
            r.get("lat"),
            r.get("lng"),
            r.get("service_radius_km"),
            r.get("profile_url"),
            r.get("is_excluded"),
            r.get("excluded_reason")
        ])

    output.seek(0)
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="rover_market_historical_master_archive.csv"'}
    )


@router.get("/database")
async def export_database_binary():
    """
    Directly downloads the active SQLite database file for backup and permanent archiving.
    """
    if not os.path.exists(settings.db_path):
        raise HTTPException(status_code=404, detail="Database file not found")

    return FileResponse(
        path=settings.db_path,
        filename="rover_market_database.db",
        media_type="application/x-sqlite3"
    )
