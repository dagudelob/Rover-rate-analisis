"""
Geocoding utilities for the Rover scraper.

Converts human-readable location strings to coordinates and
converts metric distances to Rover's mile-based radius parameter.
"""
import json
import logging
import urllib.parse
import urllib.request
from typing import Optional, Tuple

logger = logging.getLogger("rover.services.scraper.geocoding")


def geocode_location(location_name: str) -> Optional[Tuple[float, float]]:
    """
    Geocodes a textual location string to (latitude, longitude) via Nominatim/OpenStreetMap.
    Returns None if geocoding fails or the location is not found.
    """
    try:
        encoded = urllib.parse.quote(location_name)
        url = f"https://nominatim.openstreetmap.org/search?format=json&q={encoded}&limit=1"
        req = urllib.request.Request(url, headers={"User-Agent": "RoverMarketIntelligence/2.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data:
                return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as exc:
        logger.warning("Geocoding failed for '%s': %s", location_name, exc)
    return None


def convert_km_to_rover_radius_miles(radius_km: Optional[float]) -> Optional[int]:
    """
    Converts a user-supplied distance in kilometers to Rover's closest supported
    integer mile radius parameter. Returns None if no radius is provided.
    """
    if radius_km is None or radius_km <= 0:
        return None
    miles = radius_km * 0.621371
    return max(1, round(miles))
