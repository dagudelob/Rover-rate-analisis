"""
Strategy Pattern for Pet Care Platform Scrapers.

Defines the abstract contract for multi-platform scraping engines.
Enables extending to Wag!, Care.com, PetSitter.com without modifying controllers.
"""
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional


class BaseScraperStrategy(ABC):
    """Abstract Strategy defining the contract for any pet care platform scraper."""

    @abstractmethod
    def get_platform_name(self) -> str:
        """Returns the unique name of the platform (e.g. 'rover', 'wag')."""
        pass

    @abstractmethod
    def get_supported_services(self) -> Dict[str, str]:
        """Returns a dict of supported service slugs to human-readable names."""
        pass

    @abstractmethod
    async def scrape(
        self,
        location: str,
        service_type: str,
        max_pages: int = 5,
        radius_km: Optional[float] = None,
        max_results: Optional[int] = 100,
        proxy_url: Optional[str] = None,
        event_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """Executes multi-page data extraction and streams progress events."""
        pass
