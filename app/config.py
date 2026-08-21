"""
Centralized application configuration.

All settings are read from environment variables with typed defaults.
Using Pydantic BaseSettings ensures values are validated at startup.
"""
import os
from typing import List


class Settings:
    """Application-wide configuration. Override any value via environment variable."""

    # Database
    db_path: str = os.environ.get(
        "DB_PATH",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rover_market.db")
    )

    # CORS — restrict to specific origins in production
    cors_origins: List[str] = os.environ.get("CORS_ORIGINS", "http://localhost:8000").split(",")

    # Scraper limits & Anti-bot throttle timings
    scraper_max_pages: int = int(os.environ.get("SCRAPER_MAX_PAGES", "15"))
    scraper_max_results: int = int(os.environ.get("SCRAPER_MAX_RESULTS", "200"))
    scraper_page_delay_min: float = float(os.environ.get("SCRAPER_PAGE_DELAY_MIN", "3.5"))
    scraper_page_delay_max: float = float(os.environ.get("SCRAPER_PAGE_DELAY_MAX", "6.5"))
    scraper_scroll_delay_min: float = float(os.environ.get("SCRAPER_SCROLL_DELAY_MIN", "900"))
    scraper_scroll_delay_max: float = float(os.environ.get("SCRAPER_SCROLL_DELAY_MAX", "1600"))
    scraper_load_delay_min: float = float(os.environ.get("SCRAPER_LOAD_DELAY_MIN", "2500"))
    scraper_load_delay_max: float = float(os.environ.get("SCRAPER_LOAD_DELAY_MAX", "4200"))

    # Browser / Anti-detection
    browser_user_agent: str = os.environ.get(
        "BROWSER_UA",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )
    browser_viewport_width: int = int(os.environ.get("BROWSER_VIEWPORT_W", "1366"))
    browser_viewport_height: int = int(os.environ.get("BROWSER_VIEWPORT_H", "768"))
    browser_locale: str = os.environ.get("BROWSER_LOCALE", "en-US")
    browser_timezone: str = os.environ.get("BROWSER_TIMEZONE", "America/Toronto")

    # Static files directory
    static_dir: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static"
    )


# Singleton settings instance — import this everywhere
settings = Settings()
