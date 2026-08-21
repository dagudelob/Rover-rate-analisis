import asyncio
import json
import io
import csv
import logging
from typing import Optional, List
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, HTTPException, Response
from fastapi.responses import StreamingResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os

from scraper import scrape_rover_with_events, SERVICE_NAMES
from analytics import calculate_market_statistics, detect_outliers_iqr
from database import (
    init_db,
    save_scrape_results,
    update_sitter_exclusion,
    delete_session,
    delete_sessions,
    get_all_sessions,
    get_session_by_id,
    get_master_historical_data,
    get_temporal_trends_data,
    DB_PATH
)

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("rover.api")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager: initializes database schema on startup."""
    logger.info("Initializing Rover Market Intelligence database schema and indexes...")
    init_db()
    logger.info("Application startup complete.")
    yield
    logger.info("Application shutting down.")

app = FastAPI(
    title="Rover.com Market Intelligence Platform",
    description="Anti-detection multi-page scraper, outlier studio, historical data archive & analytics for Rover.com",
    version="2.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

class RecalculateRequest(BaseModel):
    session_id: Optional[int] = None
    records: Optional[List[dict]] = None
    excluded_indices: List[int] = []

class SitterExclusionRequest(BaseModel):
    is_excluded: bool
    reason: Optional[str] = "Manual outlier toggle"

class DeleteSessionsRequest(BaseModel):
    session_ids: List[int]

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Serves the main single page dashboard interface."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h1>Rover Market Intelligence API is running.</h1>")

@app.get("/api/services")
async def get_services():
    """Returns available Rover service categories."""
    return SERVICE_NAMES

@app.get("/api/history")
async def list_history():
    """Returns search history sessions."""
    sessions = get_all_sessions()
    return {"sessions": sessions}

@app.delete("/api/history/{session_id}")
async def delete_history_session(session_id: int):
    """Deletes a single search session and associated sitters."""
    success = delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "success", "deleted_session_id": session_id}

@app.delete("/api/history")
async def delete_history_sessions_batch(req: DeleteSessionsRequest):
    """Batch deletes multiple search sessions."""
    count = delete_sessions(req.session_ids)
    return {"status": "success", "deleted_count": count}

@app.get("/api/history/{session_id}")
async def get_session_details(session_id: int):
    """Returns complete session details including full analytics distribution and geospatial data."""
    session = get_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    sitters = session.get("sitters", [])
    
    # Check if any sitters were previously marked as excluded in DB
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

@app.post("/api/analytics/recalculate")
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
        "auto_outliers": auto_outliers
    }

@app.post("/api/sitters/{sitter_id}/exclude")
async def toggle_sitter_exclusion(sitter_id: int, req: SitterExclusionRequest):
    """Persists a sitter exclusion state into the database."""
    success = update_sitter_exclusion(sitter_id, req.is_excluded, req.reason)
    if not success:
        raise HTTPException(status_code=404, detail="Sitter listing not found")
    return {"status": "success", "sitter_id": sitter_id, "is_excluded": req.is_excluded}

@app.get("/api/analytics/temporal-trends")
async def temporal_trends():
    """Returns consolidated historical session data for seasonal/temporal trend visualization."""
    trends = get_temporal_trends_data()
    return {"trends": trends}

@app.get("/api/scrape/stream")
async def scrape_stream(
    location: str = Query(..., description="Geographic location or postal code"),
    service_type: str = Query("dog-walking", description="Rover service category"),
    radius_km: Optional[float] = Query(None, ge=0.5, le=100.0, description="Custom distance radius in kilometers (optional)"),
    max_pages: int = Query(5, ge=1, le=15, description="Max pagination depth (e.g. 5 pages for ~100 sitters)"),
    max_results: Optional[int] = Query(100, ge=1, le=200, description="Target limit of sitters to import (up to 100+)"),
    proxy_url: Optional[str] = Query(None, description="Optional HTTP/SOCKS proxy")
):
    """
    Triggers an asynchronous multi-page scraping task (up to 100 sitters) and streams live events via SSE.
    """
    async def event_generator():
        event_queue = asyncio.Queue()

        def push_event(event_type: str, data: dict):
            event_queue.put_nowait({"type": event_type, "data": data})

        async def run_scraper():
            try:
                result = await scrape_rover_with_events(
                    location=location,
                    service_type=service_type,
                    radius_km=radius_km,
                    max_pages=max_pages,
                    max_results=max_results,
                    proxy_url=proxy_url,
                    event_callback=push_event
                )
                
                stats = calculate_market_statistics(result["records"])
                outliers = detect_outliers_iqr(result["records"])
                
                session_id = save_scrape_results(
                    location=location,
                    service_type=service_type,
                    radius_km=radius_km,
                    center_lat=result.get("center_lat"),
                    center_lng=result.get("center_lng"),
                    pages_requested=max_pages,
                    pages_completed=result["pages_completed"],
                    stats=stats,
                    records=result["records"]
                )
                
                push_event("complete", {
                    "session_id": session_id,
                    "stats": stats,
                    "auto_outliers": outliers,
                    "records": result["records"],
                    "location": location,
                    "service_type": service_type,
                    "radius_km": radius_km,
                    "center_lat": result.get("center_lat"),
                    "center_lng": result.get("center_lng")
                })
            except Exception as e:
                logger.error(f"Error during scrape streaming execution: {e}", exc_info=True)
                push_event("error", {"message": str(e)})
            finally:
                push_event("end", {})

        asyncio.create_task(run_scraper())

        while True:
            item = await event_queue.get()
            event_type = item["type"]
            event_data = item["data"]
            
            if event_type == "end":
                yield "event: end\ndata: {}\n\n"
                break

            json_payload = json.dumps(event_data, ensure_ascii=False)
            yield f"event: {event_type}\ndata: {json_payload}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@app.get("/api/export/csv/{session_id}")
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
    filename = f"rover_session_{session_id}_{session['service_type']}_{session['location'].replace(' ', '_')}.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.get("/api/export/master-csv")
async def export_master_csv():
    """
    Exports ALL historical search sessions and sitters into a master timestamped CSV archive
    for longitudinal and yearly variation analysis.
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
        headers={"Content-Disposition": "attachment; filename=rover_market_historical_master_archive.csv"}
    )

@app.get("/api/export/database")
async def export_database_binary():
    """
    Directly downloads the active SQLite database file for external backup and permanent archiving.
    """
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="Database file not found")
    
    return FileResponse(
        path=DB_PATH,
        filename="rover_market_database.db",
        media_type="application/x-sqlite3"
    )
