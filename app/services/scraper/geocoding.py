"""
Geocoding utilities for the Rover scraper.

Converts human-readable location strings and Postal Code FSAs (e.g. M5V, M4Y, M6K, V6B, H2Y, etc.)
to authentic geographic coordinates using offline high-precision FSA centroid datasets and cached fallback lookups.
"""
import json
import logging
import re
import urllib.parse
import urllib.request
from typing import Dict, Optional, Tuple

from app.services.scraper.postal_data import lookup_fsa_data

logger = logging.getLogger("rover.services.scraper.geocoding")

# In-memory geocode cache to avoid duplicate API lookups and respect rate limits
_GEOCODE_CACHE: Dict[str, Optional[Tuple[float, float]]] = {}


def extract_postal_code_fsa(text: str) -> Optional[str]:
    """
    Extracts Canadian 3-character FSA (e.g. 'M5V', 'M4Y', 'K1A', 'V6B', 'H2Y') or US 5-digit zip.
    """
    if not text:
        return None

    # Canadian FSA pattern: Letter-Digit-Letter (e.g. M5V, V6B, H2X, T2P)
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
        req = urllib.request.Request(url, headers={"User-Agent": "RoverMarketIntelligence/3.5 (contact@roverintel.local)"})
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


def geocode_postal_code_with_city(
    postal_code: Optional[str],
    fallback_city: str,
    city_center: Optional[Tuple[float, float]] = None
) -> Optional[Tuple[float, float]]:
    """
    Geocodes a postal code FSA (e.g. 'M5V', 'M4Y') with instant zero-latency offline lookup.
    Falls back to bounded geocoding or city center coordinates.
    """
    if postal_code:
        clean_code = postal_code.strip().upper()
        
        # 1. High-precision instant offline FSA centroid lookup
        fsa_match = lookup_fsa_data(clean_code)
        if fsa_match:
            return fsa_match[0], fsa_match[1]

        # 2. Check in-memory cache
        cache_key = f"{clean_code}_{fallback_city.strip().lower()}"
        if cache_key in _GEOCODE_CACHE and _GEOCODE_CACHE[cache_key] is not None:
            return _GEOCODE_CACHE[cache_key]

        # 3. Targeted structured query with country restriction to avoid foreign matches
        try:
            country_param = ""
            if "canada" in fallback_city.lower() or ", on" in fallback_city.lower() or ", bc" in fallback_city.lower() or ", ab" in fallback_city.lower() or ", qc" in fallback_city.lower():
                country_param = "&countrycodes=ca"
            elif ", usa" in fallback_city.lower() or ", us" in fallback_city.lower():
                country_param = "&countrycodes=us"

            encoded_q = urllib.parse.quote(f"{clean_code}, {fallback_city}")
            url = f"https://nominatim.openstreetmap.org/search?format=json&q={encoded_q}{country_param}&limit=1"
            req = urllib.request.Request(url, headers={"User-Agent": "RoverMarketIntelligence/3.5"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data:
                    coords = (float(data[0]["lat"]), float(data[0]["lon"]))
                    _GEOCODE_CACHE[cache_key] = coords
                    return coords
        except Exception as exc:
            logger.debug("Online postal geocoding failed for %s: %s", clean_code, exc)

    # 4. Fallback to city center coordinates
    if city_center and city_center[0] and city_center[1]:
        return city_center

    return geocode_location(fallback_city)


def convert_km_to_rover_radius_miles(radius_km: Optional[float]) -> Optional[int]:
    """
    Converts a distance in kilometers to Rover's closest supported integer mile radius parameter.
    """
    if radius_km is None or radius_km <= 0:
        return None
    miles = radius_km * 0.621371
    return max(1, round(miles))
