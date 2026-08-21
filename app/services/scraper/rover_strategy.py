"""
Concrete Rover.com Scraper Strategy.

Implements BaseScraperStrategy for Rover.com using Playwright Stealth,
DOM evaluate extraction, and progressive scrolling.
"""
import asyncio
import logging
import random
import urllib.parse
from typing import Any, Callable, Dict, List, Optional

from app.config import settings
from app.services.scraper.strategy import BaseScraperStrategy
from app.services.scraper.browser import create_browser_context
from app.services.scraper.geocoding import geocode_location, convert_km_to_rover_radius_miles
from app.services.scraper.parser import CARD_EXTRACTOR_JS, SERVICE_NAMES, build_sitter_record

logger = logging.getLogger("rover.services.scraper.rover")


class RoverScraperStrategy(BaseScraperStrategy):
    """Concrete scraping engine for Rover.com platform."""

    def get_platform_name(self) -> str:
        return "rover"

    def get_supported_services(self) -> Dict[str, str]:
        return SERVICE_NAMES

    async def scrape(
        self,
        location: str,
        service_type: str = "dog-walking",
        max_pages: int = 5,
        radius_km: Optional[float] = None,
        max_results: Optional[int] = 100,
        proxy_url: Optional[str] = None,
        event_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """Executes multi-page data extraction on Rover.com."""
        def emit(event_type: str, data: Dict[str, Any]) -> None:
            if event_callback:
                event_callback(event_type, data)

        records: List[Dict[str, Any]] = []
        seen_profiles: set = set()
        pages_completed = 0

        radius_label = f"{radius_km}km" if radius_km else "Default (All)"
        emit("log", {
            "message": (
                f"Starting multi-page extraction for '{location}' | Service: '{service_type}' | "
                f"Radius: {radius_label} | Max Pages: {max_pages} | Target Limit: {max_results or 100}"
            )
        })

        center_coords = geocode_location(location)
        center_lat, center_lng = center_coords if center_coords else (43.6532, -79.3832)
        emit("log", {"message": f"Resolved location coordinates: [{center_lat:.4f}, {center_lng:.4f}]"})

        radius_miles = convert_km_to_rover_radius_miles(radius_km)
        encoded_location = urllib.parse.quote(location)

        playwright, browser, context, page = await create_browser_context(proxy_url)
        emit("log", {"message": "Launching Chromium browser with stealth anti-detection flags..."})

        try:
            for current_page in range(1, max_pages + 1):
                url = (
                    f"https://www.rover.com/search/?service_type={service_type}"
                    f"&location={encoded_location}&page={current_page}"
                )
                if radius_miles is not None:
                    url += f"&radius={radius_miles}"

                emit("log", {"message": f"[*] [Page {current_page}/{max_pages}] Navigating to {url}"})
                emit("page_start", {"page": current_page, "max_pages": max_pages, "url": url})

                try:
                    response = await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    status = response.status if response else "200"
                    emit("log", {
                        "message": f"Page {current_page} loaded (HTTP {status}). Pausing stochastic human delay..."
                    })

                    await page.wait_for_timeout(
                        random.uniform(settings.scraper_load_delay_min, settings.scraper_load_delay_max)
                    )

                    emit("log", {"message": f"Progressive scrolling page {current_page}..."})
                    for _ in range(3):
                        await page.evaluate("window.scrollBy({ top: window.innerHeight * 0.75, behavior: 'smooth' });")
                        await page.wait_for_timeout(
                            random.uniform(settings.scraper_scroll_delay_min, settings.scraper_scroll_delay_max)
                        )

                    cards_data: List[Dict[str, Any]] = await page.evaluate(CARD_EXTRACTOR_JS)
                    emit("log", {"message": f"Extracted {len(cards_data)} sitters from page {current_page}."})

                    if not cards_data:
                        emit("log", {"message": f"No more sitters on page {current_page}. Reached pagination end."})
                        break

                    page_new_records = 0
                    for card in cards_data:
                        if max_results and len(records) >= max_results:
                            break
                        profile_url = card["url"]
                        if profile_url in seen_profiles:
                            continue
                        seen_profiles.add(profile_url)

                        record = build_sitter_record(
                            card=card,
                            service_type=service_type,
                            location=location,
                            radius_km=radius_km,
                            center_lat=center_lat,
                            center_lng=center_lng,
                            total_idx=len(records),
                        )
                        if record:
                            records.append(record)
                            page_new_records += 1

                    pages_completed += 1
                    emit("page_done", {
                        "page": current_page,
                        "records_found": page_new_records,
                        "total_records_so_far": len(records),
                    })

                    if max_results and len(records) >= max_results:
                        emit("log", {"message": f"Reached target cap ({len(records)}/{max_results}). Done."})
                        break

                except Exception as nav_err:
                    emit("log", {"message": f"[!] Error on page {current_page}: {nav_err}"})
                    break

                if current_page < max_pages and (not max_results or len(records) < max_results):
                    delay = random.uniform(settings.scraper_page_delay_min, settings.scraper_page_delay_max)
                    emit("log", {"message": f"Waiting {delay:.2f}s before page {current_page + 1}..."})
                    await asyncio.sleep(delay)

        finally:
            await browser.close()
            await playwright.stop()

        emit("log", {"message": f"Scraping complete. Total sitters imported: {len(records)}."})

        return {
            "location": location,
            "service_type": service_type,
            "radius_km": radius_km,
            "center_lat": center_lat,
            "center_lng": center_lng,
            "pages_requested": max_pages,
            "pages_completed": pages_completed,
            "records": records,
        }
