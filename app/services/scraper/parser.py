"""
DOM card data extraction and sitter record parsing.

Responsible for:
- JavaScript evaluate() call that extracts raw card data, text, badges, neighborhood, and postal code FSA from the DOM
- Real Price extraction with service-specific unit validation
- Sitter name, headline, neighborhood/area, postal code FSA, rating, and review count parsing
- Multi-service rate extraction
"""
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.services.scraper.geocoding import extract_postal_code_fsa, geocode_postal_code_with_city
from app.services.scraper.postal_data import lookup_fsa_data

logger = logging.getLogger("rover.services.scraper.parser")

PROV_STATE_RE = re.compile(
    r"\b(ON|BC|AB|QC|MB|SK|NS|NB|PE|NL|AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)\b",
    re.IGNORECASE
)

# ── Service-to-Unit Token Mapping ──────────────────────────────────────────────

SERVICE_UNIT_EXPECTATIONS: Dict[str, List[str]] = {
    "all-services":       ["walk", "night", "visit", "day"],
    "dog-walking":        ["walk"],
    "drop-in-visits":     ["visit", "drop-in", "drop in"],
    "overnight-boarding": ["night"],
    "house-sitting":      ["night"],
    "day-care":           ["day"],
}

SERVICE_NAMES: Dict[str, str] = {
    "all-services":       "🌐 All Services (Master Sitter Catalog)",
    "dog-walking":        "Dog Walking",
    "overnight-boarding": "Overnight Boarding",
    "drop-in-visits":     "Drop-in Visits",
    "house-sitting":      "House Sitting",
    "day-care":           "Day Care",
}

# JavaScript injected into the page to extract raw card data from Rover DOM.
CARD_EXTRACTOR_JS = """
() => {
    const results = [];
    const memberLinks = Array.from(document.querySelectorAll("a[href*='/members/']"));
    const seenUrls = new Set();

    for (const a of memberLinks) {
        let rawHref = a.getAttribute('href') || '';
        let fullHref = rawHref.startsWith('/') ? 'https://www.rover.com' + rawHref : rawHref;
        const cleanUrl = fullHref.split('?')[0];

        if (seenUrls.has(cleanUrl)) continue;
        seenUrls.add(cleanUrl);

        // Walk up the DOM to find the card container for this sitter
        let card = a;
        let current = a;
        while (current && current.parentElement &&
               current.parentElement.tagName !== 'BODY' &&
               current.parentElement.tagName !== 'MAIN') {
            current = current.parentElement;
            const txt = current.innerText || '';
            if (txt.includes('$') && (
                txt.includes('per walk') || txt.includes('per night') ||
                txt.includes('per visit') || txt.includes('per day') ||
                txt.includes('stars') || txt.includes('reviews') || txt.includes('(')
            )) {
                card = current;
                break;
            }
        }

        // Find the price badge element
        let priceText = '';
        const allElements = Array.from(card.querySelectorAll('*'));
        for (const el of allElements) {
            const t = (el.innerText || '').trim();
            if (/^\\$\\s*\\d+/.test(t) && (t.includes('per') || t.includes('total') || t.length < 25)) {
                priceText = t;
                break;
            }
        }

        // Extract sitter name from heading elements
        let extractedName = '';
        const nameHeading = card.querySelector('h2, h3, [class*="name"], [data-testid*="name"]');
        if (nameHeading) {
            extractedName = (nameHeading.innerText || '').trim();
        }
        if (!extractedName) {
            extractedName = (a.innerText || '').trim();
        }

        // Extract location / postal code / neighborhood elements
        let neighborhood = '';
        const locationEl = card.querySelector('[class*="location"], [class*="neighborhood"], [data-testid*="location"], [data-testid*="neighborhood"]');
        if (locationEl) {
            neighborhood = (locationEl.innerText || '').trim();
        }

        const img = card.querySelector('img');
        results.push({
            url: cleanUrl,
            extractedName: extractedName,
            priceText: priceText,
            neighborhood: neighborhood,
            cardText: card.innerText || '',
            photoUrl: img ? (img.getAttribute('src') || '') : ''
        });
    }
    return results;
}
"""


# ── Price Extraction ───────────────────────────────────────────────────────────

def extract_price(
    price_text: str,
    card_text: str,
    service_type: str,
) -> tuple[Optional[float], Optional[str], Optional[str]]:
    """
    3-tier price extraction pipeline with service-unit validation.
    Returns (price_numeric, raw_price, rate_unit).
    """
    target_tokens = SERVICE_UNIT_EXPECTATIONS.get(service_type, ["walk", "night", "visit", "day"])
    price_numeric: Optional[float] = None
    raw_price: Optional[str] = None
    rate_unit: Optional[str] = None

    # Tier 1 — dedicated badge
    if price_text:
        m = re.search(
            r"\$\s*(\d+(?:\.\d+)?)\s*(?:total\s+)?(?:per\s+|/)?(walk|night|visit|day)?",
            price_text,
            re.IGNORECASE,
        )
        if m:
            price_numeric = float(m.group(1))
            raw_price = f"${m.group(1)}"
            if m.group(2):
                rate_unit = f"per {m.group(2).lower()}"

    # Tier 2 — explicit "$XX per [unit]" anywhere in card
    if price_numeric is None or rate_unit is None:
        matches = re.findall(
            r"\$\s*(\d+(?:\.\d+)?)\s*(?:total\s+)?(?:per\s+|/)(walk|night|visit|day)",
            card_text,
            re.IGNORECASE,
        )
        for price_str, unit_str in matches:
            unit_clean = unit_str.lower()
            if any(tok in unit_clean for tok in target_tokens):
                price_numeric = float(price_str)
                raw_price = f"${price_str}"
                rate_unit = f"per {unit_clean}"
                break
        if price_numeric is None and matches:
            first_p, first_u = matches[0]
            price_numeric = float(first_p)
            raw_price = f"${first_p}"
            rate_unit = f"per {first_u.lower()}"

    # Tier 3 — standalone "$XX" in first 8 header lines
    if price_numeric is None:
        lines = [ln.strip() for ln in card_text.split("\n") if ln.strip()]
        for i, line in enumerate(lines[:8]):
            if line.startswith("\u201c") or line.startswith('"') or line.lower().startswith("about:"):
                break
            m = re.match(r"^\$\s*(\d+(?:\.\d+)?)$", line)
            if m:
                price_numeric = float(m.group(1))
                raw_price = f"${m.group(1)}"
                rate_unit = f"per {target_tokens[0]}"
                if i + 1 < len(lines):
                    next_l = lines[i + 1].lower()
                    if "walk" in next_l:
                        rate_unit = "per walk"
                    elif "night" in next_l:
                        rate_unit = "per night"
                    elif "visit" in next_l:
                        rate_unit = "per visit"
                    elif "day" in next_l:
                        rate_unit = "per day"
                break

    if rate_unit is None and target_tokens:
        rate_unit = f"per {target_tokens[0]}"

    return price_numeric, raw_price, rate_unit


def extract_all_services_and_prices(card_text: str, price_text: str = "") -> List[Dict[str, Any]]:
    """
    Extracts all services and corresponding rates advertised by a sitter.
    """
    extracted_services: List[Dict[str, Any]] = []
    seen_types = set()

    unit_to_service = {
        "walk": ("dog-walking", "Dog Walking", "per walk"),
        "visit": ("drop-in-visits", "Drop-In Visits", "per visit"),
        "night": ("overnight-boarding", "Overnight Boarding", "per night"),
        "day": ("day-care", "Day Care", "per day"),
    }

    all_matches = re.findall(
        r"\$\s*(\d+(?:\.\d+)?)\s*(?:total\s+)?(?:per\s+|/)(walk|night|visit|day)",
        card_text,
        re.IGNORECASE,
    )
    for price_str, unit_str in all_matches:
        u_key = unit_str.lower()
        if u_key in unit_to_service:
            srv_type, srv_name, rate_unit = unit_to_service[u_key]
            if srv_type not in seen_types:
                seen_types.add(srv_type)
                extracted_services.append({
                    "service_type": srv_type,
                    "service_name": srv_name,
                    "price_numeric": float(price_str),
                    "rate_unit": rate_unit,
                })

    if price_text:
        pm = re.search(r"\$\s*(\d+(?:\.\d+)?)\s*(?:total\s+)?(?:per\s+|/)?(walk|night|visit|day)?", price_text, re.IGNORECASE)
        if pm:
            num = float(pm.group(1))
            matched_u = (pm.group(2) or "walk").lower()
            srv_type, srv_name, rate_unit = unit_to_service.get(matched_u, ("dog-walking", "Dog Walking", "per walk"))
            if srv_type not in seen_types:
                seen_types.add(srv_type)
                extracted_services.append({
                    "service_type": srv_type,
                    "service_name": srv_name,
                    "price_numeric": num,
                    "rate_unit": rate_unit,
                })

    return extracted_services


# ── Name / Headline / Postal Code / Neighborhood Parsing ───────────────────────

def parse_sitter_name_and_headline(
    extracted_name: str, card_text: str, profile_url: str
) -> tuple[str, Optional[str], Optional[str], Optional[str], Optional[float], Optional[float]]:
    """
    Cleans the sitter name, extracts the headline, and detects real postal code FSA (e.g. M5V),
    neighborhood name, and resolved offline geographic coordinates (lat, lng).
    Returns (name, headline, neighborhood, postal_code, lat, lng).
    """
    name = extracted_name
    if name:
        name = re.sub(r"^\d+\.\s*", "", name)
        name = re.sub(
            r"(Star Sitter|Repeat Clients?|Highly Responsive).*$", "", name, flags=re.IGNORECASE
        ).strip()

    lines = [ln.strip() for ln in card_text.split("\n") if ln.strip()]
    headline: Optional[str] = None
    raw_location_line: Optional[str] = None
    postal_code: Optional[str] = extract_postal_code_fsa(card_text)

    skip_terms = {
        "view all", "photo", "total", "per walk", "per night", "per visit", "per day",
        "highly responsive", "repeat clients", "out of 5 stars", "$",
        "stars", "reviews",
    }

    for line in lines:
        l_lower = line.lower()
        if any(term in l_lower for term in skip_terms):
            continue
        if re.search(r"^\d+\.\s*", line) or (name and name.lower() in l_lower):
            continue

        is_loc = bool(extract_postal_code_fsa(line) or ("," in line and PROV_STATE_RE.search(line)))
        if is_loc and not raw_location_line:
            raw_location_line = line
        elif not headline and len(line) > 3 and not line.startswith("★") and not line.startswith("•"):
            headline = line

    if not name and profile_url:
        slug = profile_url.split("/members/")[-1].strip("/")
        name = " ".join(word.capitalize() for word in slug.split("-")[:2])

    neighborhood: Optional[str] = None
    lat, lng = None, None

    # Resolve accurate FSA coordinates & neighborhood from offline directory
    if postal_code:
        fsa_info = lookup_fsa_data(postal_code)
        if fsa_info:
            lat, lng, neighborhood = fsa_info

    if not neighborhood and raw_location_line:
        neighborhood = raw_location_line

    return name or "Rover Sitter", headline, neighborhood, postal_code, lat, lng


def parse_rating_and_reviews(card_text: str) -> tuple[Optional[str], Optional[float], Optional[str], int]:
    """
    Extracts rating, rating_numeric, reviews text, and reviews_count from card text.
    """
    rating: Optional[str] = None
    rating_numeric: Optional[float] = None

    rating_m = re.search(r"(\d+\.\d+)\s+out of 5 stars|(\d+\.\d+)\s*\(\d+\)", card_text)
    if rating_m:
        rat_str = rating_m.group(1) or rating_m.group(2)
        rating = rat_str
        rating_numeric = float(rat_str)

    reviews: Optional[str] = None
    reviews_count = 0
    rev_m = re.search(r"(\d+)\s+reviews?|\((\d+)\)", card_text)
    if rev_m:
        cnt_str = rev_m.group(1) or rev_m.group(2)
        reviews_count = int(cnt_str)
        reviews = f"{reviews_count} reviews"

    return rating, rating_numeric, reviews, reviews_count


# ── Record Assembly with Real Postal Code Geocoding ─────────────────────────────

def build_sitter_record(
    card: Dict[str, Any],
    service_type: str,
    location: str,
    radius_km: Optional[float] = None,
    total_idx: int = 0,
    center_lat: Optional[float] = None,
    center_lng: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """
    Parses a raw card dict into a typed sitter record with authentic postal code geocoding.
    """
    profile_url = card["url"]
    card_text = card["cardText"]
    price_text = card.get("priceText", "")
    photo_url = card.get("photoUrl")
    extracted_name = card.get("extractedName", "")
    card_neighborhood = card.get("neighborhood", "")

    price_numeric, raw_price, rate_unit = extract_price(price_text, card_text, service_type)
    if price_numeric is None:
        return None

    name, headline, parsed_neighborhood, postal_code, fsa_lat, fsa_lng = parse_sitter_name_and_headline(
        extracted_name, card_text, profile_url
    )
    neighborhood = card_neighborhood or parsed_neighborhood or location

    lat = fsa_lat
    lng = fsa_lng

    if lat is None or lng is None:
        city_coords = (center_lat, center_lng) if (center_lat is not None and center_lng is not None) else None
        coords = geocode_postal_code_with_city(postal_code, location, city_coords)
        if coords:
            lat, lng = coords

    if lat is None or lng is None:
        lat, lng = center_lat, center_lng

    rating, rating_numeric, reviews, reviews_count = parse_rating_and_reviews(card_text)
    all_services = extract_all_services_and_prices(card_text, price_text)

    # Ensure current queried service is registered
    has_current = any(s["service_type"] == service_type for s in all_services)
    if not has_current and price_numeric is not None and service_type != "all-services":
        all_services.append({
            "service_type": service_type,
            "service_name": SERVICE_NAMES.get(service_type, service_type.title()),
            "price_numeric": price_numeric,
            "rate_unit": rate_unit,
        })

    return {
        "name": name,
        "raw_price": raw_price,
        "price_numeric": price_numeric,
        "rate_unit": rate_unit,
        "rating": rating,
        "rating_numeric": rating_numeric,
        "reviews": reviews,
        "reviews_count": reviews_count,
        "headline": headline,
        "neighborhood": neighborhood,
        "postal_code": postal_code,
        "lat": lat,
        "lng": lng,
        "profile_url": profile_url,
        "photo_url": photo_url,
        "service_type": service_type,
        "location_query": location,
        "radius_km": radius_km,
        "services": all_services,
    }
