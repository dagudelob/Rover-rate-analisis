"""
Scraper Factory and Registry.

Enables dynamic resolution of platform scraping strategies (Rover, Wag, Care).
"""
from typing import Dict
from app.services.scraper.strategy import BaseScraperStrategy
from app.services.scraper.rover_strategy import RoverScraperStrategy

_STRATEGY_REGISTRY: Dict[str, BaseScraperStrategy] = {
    "rover": RoverScraperStrategy(),
}


def get_scraper_strategy(platform: str = "rover") -> BaseScraperStrategy:
    """Returns the registered scraping strategy instance for the given platform."""
    strategy = _STRATEGY_REGISTRY.get(platform.lower())
    if not strategy:
        raise ValueError(f"Unsupported scraping platform '{platform}'. Supported: {list(_STRATEGY_REGISTRY.keys())}")
    return strategy


def register_scraper_strategy(platform: str, strategy: BaseScraperStrategy) -> None:
    """Registers a new platform scraping strategy at runtime (Open/Closed Principle)."""
    _STRATEGY_REGISTRY[platform.lower()] = strategy
