"""
Scraper Factory and Registry.

Enables dynamic resolution of platform scraping strategies (Rover, Wag, Care).
"""
from typing import Dict, List
from app.services.scraper.strategy import BaseScraperStrategy
from app.services.scraper.rover_strategy import RoverScraperStrategy
from app.services.scraper.wag_strategy import WagScraperStrategy
from app.services.scraper.care_strategy import CareScraperStrategy

_STRATEGY_REGISTRY: Dict[str, BaseScraperStrategy] = {
    "rover": RoverScraperStrategy(),
    "wag": WagScraperStrategy(),
    "care": CareScraperStrategy(),
}


def get_scraper_strategy(platform: str = "rover") -> BaseScraperStrategy:
    """Returns the registered scraping strategy instance for the given platform."""
    key = platform.lower().strip()
    strategy = _STRATEGY_REGISTRY.get(key)
    if not strategy:
        raise ValueError(f"Unsupported scraping platform '{platform}'. Supported: {list(_STRATEGY_REGISTRY.keys())}")
    return strategy


def list_supported_platforms() -> List[Dict[str, str]]:
    """Returns a list of all registered platform keys and their display labels."""
    return [
        {"id": "rover", "name": "Rover.com", "badge": "🐾 Primary Market"},
        {"id": "wag", "name": "Wag! Walking", "badge": "⚡ On-Demand"},
        {"id": "care", "name": "Care.com Pet Care", "badge": "🛡️ Verified Care"},
    ]


def register_scraper_strategy(platform: str, strategy: BaseScraperStrategy) -> None:
    """Registers a new platform scraping strategy at runtime (Open/Closed Principle)."""
    _STRATEGY_REGISTRY[platform.lower()] = strategy
