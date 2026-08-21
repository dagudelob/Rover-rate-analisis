"""
Scraping API routes.

Provides endpoints to:
- Retrieve supported Rover services
- Stream live multi-page scraping events via Server-Sent Events (SSE)
"""
import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.services.scraper import SERVICE_NAMES, scrape_rover_with_events
from app.services.scraper.factory import get_scraper_strategy, list_supported_platforms
from app.services.analytics import calculate_market_statistics, detect_outliers_iqr
from app.db.repository import save_scrape_results

logger = logging.getLogger("rover.api.scraping")
router = APIRouter(prefix="/api", tags=["Scraping"])


@router.get("/platforms")
async def get_platforms():
    """Returns all supported pet care marketplace platforms (Rover, Wag, Care)."""
    return {"platforms": list_supported_platforms()}


@router.get("/services")
async def get_services(platform: str = Query("rover", description="Marketplace platform ID")):
    """Returns available service categories for the specified platform."""
    try:
        strategy = get_scraper_strategy(platform)
        return strategy.get_supported_services()
    except ValueError:
        return SERVICE_NAMES


@router.get("/scrape/stream")
async def scrape_stream(
    location: str = Query(..., description="Geographic location or postal code"),
    service_type: str = Query("dog-walking", description="Service category"),
    platform: str = Query("rover", description="Marketplace platform (rover, wag, care)"),
    radius_km: Optional[float] = Query(None, ge=0.5, le=100.0, description="Custom distance radius in km"),
    max_pages: int = Query(5, ge=1, le=15, description="Max pagination depth"),
    max_results: Optional[int] = Query(100, ge=1, le=200, description="Target limit of sitters to import"),
    proxy_url: Optional[str] = Query(None, description="Optional HTTP/SOCKS proxy"),
):
    """
    Triggers an asynchronous multi-page scraping task and streams live status events via SSE.
    """
    async def event_generator():
        event_queue = asyncio.Queue()

        def push_event(event_type: str, data: dict):
            event_queue.put_nowait({"type": event_type, "data": data})

        async def run_scraper():
            try:
                strategy = get_scraper_strategy(platform)
                result = await strategy.scrape(
                    location=location,
                    service_type=service_type,
                    radius_km=radius_km,
                    max_pages=max_pages,
                    max_results=max_results,
                    proxy_url=proxy_url,
                    event_callback=push_event,
                )

                records = result["records"]
                stats = calculate_market_statistics(records)
                outliers = detect_outliers_iqr(records)

                session_id = save_scrape_results(
                    location=location,
                    service_type=service_type,
                    radius_km=radius_km,
                    center_lat=result.get("center_lat"),
                    center_lng=result.get("center_lng"),
                    pages_requested=max_pages,
                    pages_completed=result["pages_completed"],
                    stats=stats,
                    records=records,
                )

                push_event("complete", {
                    "session_id": session_id,
                    "stats": stats,
                    "auto_outliers": outliers,
                    "records": records,
                    "location": location,
                    "service_type": service_type,
                    "radius_km": radius_km,
                    "center_lat": result.get("center_lat"),
                    "center_lng": result.get("center_lng"),
                })
            except Exception as e:
                logger.error("Error during scrape execution: %s", e, exc_info=True)
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
            "X-Accel-Buffering": "no",
        },
    )
