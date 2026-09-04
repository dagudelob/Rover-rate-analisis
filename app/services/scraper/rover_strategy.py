"""
Concrete Rover.com Scraper Strategy.

Implements BaseScraperStrategy for Rover.com using Playwright Stealth,
DOM evaluate extraction, progressive scrolling, and sequential multi-service execution.
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

CORE_ROVER_SERVICES = [
    "dog-walking",
    "overnight-boarding",
    "house-sitting",
    "drop-in-visits",
    "day-care",
]

# Exact URL query parameter tokens accepted by Rover.com search backend.
# Crucial: Rover falls back to default 'overnight-boarding' if unknown tokens like 'house-sitting' are passed.
ROVER_SERVICE_PARAM_MAP: Dict[str, str] = {
    "overnight-boarding": "overnight-boarding",
    "house-sitting": "overnight-traveling",
    "drop-in-visits": "drop-in",
    "day-care": "doggy-day-care",
    "dog-walking": "dog-walking",
}


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
        """Executes data extraction on Rover.com (single or sequential multi-service)."""
        def emit(event_type: str, data: Dict[str, Any]) -> None:
            if event_callback:
                event_callback(event_type, data)

        services_to_scrape = (
            CORE_ROVER_SERVICES if service_type == "all-services" else [service_type]
        )

        radius_label = f"{radius_km}km" if radius_km else "Default (All)"
        emit("log", {
            "message": (
                f"Starting Rover extraction for '{location}' | Mode: '{service_type}' "
                f"({len(services_to_scrape)} service passes) | Radius: {radius_label} | "
                f"Pages per service: {max_pages} | Target Limit: {max_results or 100}"
            )
        })

        center_coords = geocode_location(location)
        center_lat, center_lng = center_coords if center_coords else (43.6532, -79.3832)
        emit("log", {"message": f"Resolved base location coordinates: [{center_lat:.4f}, {center_lng:.4f}]"})

        radius_miles = convert_km_to_rover_radius_miles(radius_km)
        encoded_location = urllib.parse.quote(location)

        playwright, browser, context, page = await create_browser_context(proxy_url)
        emit("log", {"message": "Launching Chromium browser with stealth anti-detection flags..."})

        sitter_map: Dict[str, Dict[str, Any]] = {}
        pages_completed_total = 0

        try:
            for srv_idx, current_service in enumerate(services_to_scrape, 1):
                srv_display_name = SERVICE_NAMES.get(current_service, current_service.title())
                rover_param = ROVER_SERVICE_PARAM_MAP.get(current_service, current_service)
                emit("log", {
                    "message": f"[{srv_idx}/{len(services_to_scrape)}] 🚀 Scraping real rates for service: '{srv_display_name}' ({rover_param})..."
                })

                for current_page in range(1, max_pages + 1):
                    url = (
                        f"https://www.rover.com/search/?service_type={rover_param}"
                        f"&location={encoded_location}&page={current_page}"
                    )
                    if radius_miles is not None:
                        url += f"&radius={radius_miles}"

                    emit("log", {"message": f"[*] [{srv_display_name} - Page {current_page}/{max_pages}] Navigating: {url}"})
                    emit("page_start", {
                        "service": current_service,
                        "service_name": srv_display_name,
                        "page": current_page,
                        "max_pages": max_pages,
                        "url": url
                    })

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
                            emit("log", {"message": f"No more sitters on page {current_page} for {srv_display_name}."})
                            break

                        page_new_records = 0
                        for card in cards_data:
                            profile_url = card.get("url")
                            if not profile_url:
                                continue

                            record = build_sitter_record(
                                card=card,
                                service_type=current_service,
                                location=location,
                                radius_km=radius_km,
                                total_idx=len(sitter_map),
                                center_lat=center_lat,
                                center_lng=center_lng,
                            )
                            if not record:
                                continue

                            if profile_url in sitter_map:
                                existing = sitter_map[profile_url]
                                existing_services = existing.get("services", [])
                                if not any(s.get("service_type") == current_service for s in existing_services):
                                    existing_services.append({
                                        "service_type": current_service,
                                        "service_name": srv_display_name,
                                        "price_numeric": record["price_numeric"],
                                        "rate_unit": record["rate_unit"],
                                    })
                                existing["services"] = existing_services
                                if not existing.get("lat") and record.get("lat"):
                                    existing["lat"] = record.get("lat")
                                    existing["lng"] = record.get("lng")
                                if not existing.get("postal_code") and record.get("postal_code"):
                                    existing["postal_code"] = record.get("postal_code")
                            else:
                                if max_results and len(sitter_map) >= max_results and service_type != "all-services":
                                    break
                                sitter_map[profile_url] = record
                                page_new_records += 1

                        pages_completed_total += 1
                        emit("page_done", {
                            "service": current_service,
                            "page": current_page,
                            "records_found": page_new_records,
                            "total_unique_sitters": len(sitter_map),
                        })

                    except Exception as nav_err:
                        emit("log", {"message": f"[!] Error on page {current_page} ({current_service}): {nav_err}"})
                        break

                    if current_page < max_pages:
                        delay = random.uniform(settings.scraper_page_delay_min, settings.scraper_page_delay_max)
                        await asyncio.sleep(delay)

                if srv_idx < len(services_to_scrape):
                    srv_pause = random.uniform(2.0, 4.0)
                    emit("log", {"message": f"Completed {srv_display_name}. Pausing {srv_pause:.1f}s before next service pass..."})
                    await asyncio.sleep(srv_pause)

        finally:
            await browser.close()
            await playwright.stop()

        all_records = list(sitter_map.values())
        emit("log", {"message": f"Scraping complete. Total unique sitters populated: {len(all_records)}."})

        return {
            "location": location,
            "service_type": service_type,
            "radius_km": radius_km,
            "center_lat": center_lat,
            "center_lng": center_lng,
            "pages_completed": pages_completed_total,
            "records": all_records,
        }
