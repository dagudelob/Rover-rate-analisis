"""
Scraper orchestration service.

Provides backwards-compatible facade functions while utilizing
the Strategy Pattern and Factory Pattern underneath.
"""
from typing import Any, Callable, Dict, Optional
from app.services.scraper.parser import SERVICE_NAMES
from app.services.scraper.factory import get_scraper_strategy

__all__ = ["scrape_rover_with_events", "SERVICE_NAMES", "get_scraper_strategy"]


async def scrape_rover_with_events(
    location: str,
    service_type: str = "dog-walking",
    max_pages: int = 5,
    radius_km: Optional[float] = None,
    max_results: Optional[int] = 100,
    proxy_url: Optional[str] = None,
    event_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    """Facade delegating execution to the RoverScraperStrategy via Factory."""
    strategy = get_scraper_strategy("rover")
    return await strategy.scrape(
        location=location,
        service_type=service_type,
        max_pages=max_pages,
        radius_km=radius_km,
        max_results=max_results,
        proxy_url=proxy_url,
        event_callback=event_callback,
    )
