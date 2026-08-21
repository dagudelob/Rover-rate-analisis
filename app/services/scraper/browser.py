"""
Playwright browser lifecycle and anti-detection configuration.

Responsible for launching the browser with stealth settings,
configuring headers and viewport, and applying playwright-stealth patches.
All browser-specific setup lives here — no parsing, no scraping logic.
"""
import logging
from typing import Any, Dict, Optional

from playwright.async_api import Browser, BrowserContext, Page, async_playwright
from playwright_stealth import Stealth

from app.config import settings

logger = logging.getLogger("rover.services.scraper.browser")

# The Stealth singleton is stateless and reusable across pages
_stealth = Stealth()


async def create_browser_context(proxy_url: Optional[str] = None) -> tuple:
    """
    Launches a Chromium browser instance with anti-detection flags and
    returns (playwright_instance, browser, context, page).

    The caller is responsible for closing the browser when done.
    """
    playwright = await async_playwright().__aenter__()

    browser: Browser = await playwright.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
        ],
    )

    context_kwargs: Dict[str, Any] = {
        "user_agent": settings.browser_user_agent,
        "locale": settings.browser_locale,
        "timezone_id": settings.browser_timezone,
        "viewport": {
            "width": settings.browser_viewport_width,
            "height": settings.browser_viewport_height,
        },
        "extra_http_headers": {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        },
    }

    if proxy_url:
        context_kwargs["proxy"] = {"server": proxy_url}

    context: BrowserContext = await browser.new_context(**context_kwargs)
    page: Page = await context.new_page()

    # Apply playwright-stealth patches to evade automation detection
    await _stealth.apply_stealth_async(page)
    logger.info("Playwright-Stealth and browser headers configured successfully.")

    return playwright, browser, context, page
