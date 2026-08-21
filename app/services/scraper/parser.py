"""
DOM card data extraction and sitter record parsing.

Responsible for:
- The JavaScript evaluate() call that extracts raw card data from the page DOM
- Price extraction with service-specific unit validation (3-tier strategy)
- Sitter name, headline, rating, and review count parsing
- Coordinate offset computation for the heatmap
- Assembling the final typed sitter record dict

No browser lifecycle or HTTP concerns live here — this module only transforms raw data.
"""
import logging
import math
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger("rover.services.scraper.parser")

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

# JavaScript injected into the page to extract raw card data.
# Kept here (not in browser.py) because it is parsing logic — it defines what fields we want.
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

        // Find the price badge element — the first element whose text starts with "$N"
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

        const img = card.querySelector('img');
        results.push({
            url: cleanUrl,
            extractedName: extractedName,
            priceText: priceText,
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

    Returns (price_numeric, raw_price, rate_unit) — all may be None if no price found.

    Tier 1: dedicated price badge element text
    Tier 2: regex scan for "$XX per [unit]" pattern in card text
    Tier 3: first standalone "$XX" in header lines (bio/review lines are skipped)
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

    # Tier 3 — standalone "$XX" in first 8 header lines (skips bio and reviews)
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
    Scans for all 5 Rover service categories and their respective unit rates.
    Returns a list of dicts: [{"service_type": "...", "service_name": "...", "price_numeric": XX.X, "rate_unit": "..."}]
    """
    extracted_services: List[Dict[str, Any]] = []
    seen_types = set()

    # Pattern mapping for unit detection
    unit_to_service = {
        "walk": ("dog-walking", "Dog Walking", "per walk"),
        "visit": ("drop-in-visits", "Drop-In Visits", "per visit"),
        "night": ("overnight-boarding", "Overnight Boarding", "per night"),
        "day": ("day-care", "Day Care", "per day"),
    }

    # Scan card for explicit "$XX per [unit]" declarations
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

    # If badge price exists but not captured in card regex, assign to default service
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


# ── Name / Headline / Rating Parsing ──────────────────────────────────────────

def parse_sitter_name_and_headline(
    extracted_name: str, card_text: str, profile_url: str
) -> tuple[str, Optional[str]]:
    """
    Cleans the sitter name (strips numbering and badge text) and extracts
    the headline from the card text.
    Returns (name, headline).
    """
    name = extracted_name
    if name:
        name = re.sub(r"^\d+\.\s*", "", name)
        name = re.sub(
            r"(Star Sitter|Repeat Clients?|Highly Responsive).*$", "", name, flags=re.IGNORECASE
        ).strip()

    lines = [ln.strip() for ln in card_text.split("\n") if ln.strip()]
    headline: Optional[str] = None
    skip_terms = {
        "view all", "photo", "total", "per walk", "per night",
        "highly responsive", "repeat clients", "out of 5 stars", "$",
    }

    for line in lines:
        if any(term in line.lower() for term in skip_terms):
            continue
        if not name:
            name = re.sub(r"^\d+\.\s*", "", line)
            name = re.sub(
                r"(Star Sitter|Repeat Clients?|Highly Responsive).*$", "", name, flags=re.IGNORECASE
            ).strip()
        elif not headline and len(line) > 5 and not line.startswith("★") and not line.startswith("•"):
            headline = line
            break

    if not name and profile_url:
        slug = profile_url.split("/members/")[-1].strip("/")
        name = " ".join(word.capitalize() for word in slug.split("-")[:2])

    return name or "Rover Sitter", headline


def parse_rating_and_reviews(card_text: str) -> tuple[Optional[str], Optional[float], Optional[str], int]:
    """
    Extracts rating, rating_numeric, reviews text, and reviews_count from card text.
    Returns (rating, rating_numeric, reviews, reviews_count).
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


# ── Coordinate Computation ─────────────────────────────────────────────────────

def compute_sitter_coordinates(
    total_idx: int,
    center_lat: float,
    center_lng: float,
    radius_km: Optional[float],
) -> tuple[float, float, float]:
    """
    Approximates sitter coordinates using a golden-spiral offset within the search radius.
    Returns (lat, lng, service_radius_km).

    Note: these are approximate display coordinates for the heatmap, not real sitter addresses.
    """
    max_offset_km = radius_km if radius_km else 4.0
    angle = (total_idx * 137.5077) % 360
    dist_km = 0.25 + (total_idx % 15) * (max_offset_km / 15.0)

    d_lat = (dist_km / 111.0) * math.cos(math.radians(angle))
    d_lng = (dist_km / (111.0 * math.cos(math.radians(center_lat)))) * math.sin(math.radians(angle))

    lat = round(center_lat + d_lat, 6)
    lng = round(center_lng + d_lng, 6)
    service_radius_km = round(1.2 + (total_idx % 5) * 0.7, 1)

    return lat, lng, service_radius_km


# ── Record Assembly ────────────────────────────────────────────────────────────

def build_sitter_record(
    card: Dict[str, Any],
    service_type: str,
    location: str,
    radius_km: Optional[float],
    center_lat: float,
    center_lng: float,
    total_idx: int,
) -> Optional[Dict[str, Any]]:
    """
    Parses a raw card dict (from CARD_EXTRACTOR_JS) into a typed sitter record.
    Returns None if no price could be extracted (record is discarded).
    """
    profile_url = card["url"]
    card_text = card["cardText"]
    price_text = card.get("priceText", "")
    photo_url = card.get("photoUrl")
    extracted_name = card.get("extractedName", "")

    price_numeric, raw_price, rate_unit = extract_price(price_text, card_text, service_type)
    if price_numeric is None:
        return None

    name, headline = parse_sitter_name_and_headline(extracted_name, card_text, profile_url)
    rating, rating_numeric, reviews, reviews_count = parse_rating_and_reviews(card_text)
    lat, lng, service_radius_km = compute_sitter_coordinates(total_idx, center_lat, center_lng, radius_km)
    all_services = extract_all_services_and_prices(card_text, price_text)

    # Ensure the primary requested service is present in the services catalog
    has_primary = any(s["service_type"] == service_type for s in all_services)
    if not has_primary and price_numeric is not None:
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
        "neighborhood": location,
        "profile_url": profile_url,
        "photo_url": photo_url,
        "service_type": service_type,
        "location_query": location,
        "radius_km": radius_km,
        "lat": lat,
        "lng": lng,
        "service_radius_km": service_radius_km,
        "services": all_services,
    }
