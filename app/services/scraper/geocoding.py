"""
Geocoding utilities for the Rover scraper.

Converts human-readable location strings and 3-character Postal Code FSAs (e.g. M5V, M4Y, M6K)
to geographic coordinates with in-memory caching.
"""
import json
import logging
import re
import urllib.parse
import urllib.request
from typing import Dict, Optional, Tuple

logger = logging.getLogger("rover.services.scraper.geocoding")

# In-memory geocode cache to avoid duplicate API lookups and respect rate limits
_GEOCODE_CACHE: Dict[str, Optional[Tuple[float, float]]] = {}


def extract_postal_code_fsa(text: str) -> Optional[str]:
    """
    Extracts Canadian 3-character FSA (e.g. 'M5V', 'M4Y', 'K1A') or US 5-digit/3-digit zip.
    """
    if not text:
        return None

    # Canadian FSA pattern: Letter-Digit-Letter (e.g. M5V, V6B)
    canadian_match = re.search(r"\b([A-CEGHJ-NPR-TVXY]\d[A-CEGHJ-NPR-TV-Z])\b", text, re.IGNORECASE)
    if canadian_match:
        return canadian_match.group(1).upper()

    # US 5-digit zip code
    us_match = re.search(r"\b(\d{5})\b", text)
    if us_match:
        return us_match.group(1)

    return None


def geocode_location(location_name: str) -> Optional[Tuple[float, float]]:
    """
    Geocodes a textual location string to (latitude, longitude) via Nominatim/OpenStreetMap.
    Results are cached in memory.
    """
    if not location_name:
        return None

    cache_key = location_name.strip().lower()
    if cache_key in _GEOCODE_CACHE:
        return _GEOCODE_CACHE[cache_key]

    try:
        encoded = urllib.parse.quote(location_name)
        url = f"https://nominatim.openstreetmap.org/search?format=json&q={encoded}&limit=1"
        req = urllib.request.Request(url, headers={"User-Agent": "RoverMarketIntelligence/3.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data:
                coords = (float(data[0]["lat"]), float(data[0]["lon"]))
                _GEOCODE_CACHE[cache_key] = coords
                return coords
    except Exception as exc:
        logger.warning("Geocoding failed for '%s': %s", location_name, exc)

    _GEOCODE_CACHE[cache_key] = None
    return None


def geocode_postal_code_with_city(postal_code: str, fallback_city: str) -> Optional[Tuple[float, float]]:
    """
    Geocodes a postal code FSA (e.g. 'M5V, Toronto, ON') with fallback to city center coordinates.
    """
    if not postal_code:
        return geocode_location(fallback_city)

    # Try specific query: "M5V, Toronto, ON"
    query = f"{postal_code}, {fallback_city}"
    coords = geocode_location(query)
    if coords:
        return coords

    # Fallback to pure postal code query
    coords = geocode_location(postal_code)
    if coords:
        return coords

    # Fallback to city center
    return geocode_location(fallback_city)


def convert_km_to_rover_radius_miles(radius_km: Optional[float]) -> Optional[int]:
    """
    Converts a distance in kilometers to Rover's closest supported integer mile radius parameter.
    """
    if radius_km is None or radius_km <= 0:
        return None
    miles = radius_km * 0.621371
    return max(1, round(miles))
