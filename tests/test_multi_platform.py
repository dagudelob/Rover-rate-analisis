"""
Tests for Multi-Platform Scraper Strategy and Factory architecture.
Verifies registration and execution of Rover, Wag!, and Care.com strategies.
"""
import pytest
from app.services.scraper.factory import (
    get_scraper_strategy,
    list_supported_platforms,
    _STRATEGY_REGISTRY,
)
from app.services.scraper.rover_strategy import RoverScraperStrategy
from app.services.scraper.wag_strategy import WagScraperStrategy
from app.services.scraper.care_strategy import CareScraperStrategy


def test_factory_resolves_all_platforms():
    rover = get_scraper_strategy("rover")
    wag = get_scraper_strategy("wag")
    care = get_scraper_strategy("care")

    assert isinstance(rover, RoverScraperStrategy)
    assert isinstance(wag, WagScraperStrategy)
    assert isinstance(care, CareScraperStrategy)

    assert rover.get_platform_name() == "rover"
    assert wag.get_platform_name() == "wag"
    assert care.get_platform_name() == "care"


def test_factory_invalid_platform_raises_value_error():
    with pytest.raises(ValueError) as exc:
        get_scraper_strategy("unknown_platform_123")
    assert "Unsupported scraping platform" in str(exc.value)


def test_list_supported_platforms():
    platforms = list_supported_platforms()
    platform_ids = [p["id"] for p in platforms]
    assert "rover" in platform_ids
    assert "wag" in platform_ids
    assert "care" in platform_ids


def test_platform_services_catalog():
    rover_services = get_scraper_strategy("rover").get_supported_services()
    wag_services = get_scraper_strategy("wag").get_supported_services()
    care_services = get_scraper_strategy("care").get_supported_services()

    assert "dog-walking" in rover_services
    assert "dog-walking" in wag_services
    assert "dog-walking" in care_services
