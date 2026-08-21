import re
import pytest

def extract_service_price(card_text: str, service_type: str, price_text: str = ""):
    """Helper implementing the scraper's exact service pricing logic."""
    expected_units = {
        "dog-walking": ["walk"],
        "drop-in-visits": ["visit"],
        "overnight-boarding": ["night"],
        "house-sitting": ["night"],
        "day-care": ["day"]
    }
    target_tokens = expected_units.get(service_type, ["walk", "night", "visit", "day"])
    
    price_numeric = None
    raw_price = None
    rate_unit = None

    # 1. Primary Strategy: Check dedicated price element
    if price_text:
        pm = re.search(r'\$\s*(\d+(?:\.\d+)?)\s*(?:total\s+)?(?:per\s+|/)?(walk|night|visit|day)?', price_text, re.IGNORECASE)
        if pm:
            price_numeric = float(pm.group(1))
            raw_price = f"${pm.group(1)}"
            matched_unit = pm.group(2)
            if matched_unit:
                rate_unit = f"per {matched_unit.lower()}"

    # 2. Secondary Strategy: Regex on explicit "$XX total per [unit]"
    if price_numeric is None or rate_unit is None:
        matches = re.findall(r'\$\s*(\d+(?:\.\d+)?)\s*(?:total\s+)?(?:per\s+|/)(walk|night|visit|day)', card_text, re.IGNORECASE)
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

    # 3. Tertiary: Header lines
    if price_numeric is None:
        lines = [l.strip() for l in card_text.split('\n') if l.strip()]
        for i, line in enumerate(lines[:8]):
            if line.startswith("“") or line.startswith('"') or line.lower().startswith("about:"):
                break
            stand_m = re.match(r'^\$\s*(\d+(?:\.\d+)?)$', line)
            if stand_m:
                price_numeric = float(stand_m.group(1))
                raw_price = f"${stand_m.group(1)}"
                rate_unit = f"per {target_tokens[0]}"
                if i + 1 < len(lines):
                    next_l = lines[i+1].lower()
                    if "walk" in next_l: rate_unit = "per walk"
                    elif "night" in next_l: rate_unit = "per night"
                    elif "visit" in next_l: rate_unit = "per visit"
                    elif "day" in next_l: rate_unit = "per day"
                break

    return raw_price, price_numeric, rate_unit


def test_dog_walking_price_extraction():
    card = """
    1. Dustin T.
    Safe, Fun and Reliable Pet Care 🌈
    Toronto, ON, M4V
    $23
    total per walk
    5.0 out of 5 stars
    • 6 reviews
    3 repeat clients
    Review: “Charged $5 for parking”
    """
    raw, num, unit = extract_service_price(card, "dog-walking", price_text="$23\ntotal per walk")
    assert raw == "$23"
    assert num == 23.0
    assert unit == "per walk"


def test_bio_dollar_amounts_do_not_leak():
    card = """
    4. Sinead D.
    Star Sitter
    I love pets and I love to help!
    Toronto, ON, M6C
    $24
    total per walk
    5.0 out of 5 stars
    About: My overnight boarding is $65 and house sitting is $80. Also covered by $2000000 insurance.
    """
    raw, num, unit = extract_service_price(card, "dog-walking")
    assert num == 24.0
    assert raw == "$24"
    assert unit == "per walk"


def test_overnight_boarding_service_matching():
    card = """
    7. Jane D.
    Toronto, ON
    $60
    per night
    5.0 stars (15 reviews)
    """
    raw, num, unit = extract_service_price(card, "overnight-boarding")
    assert num == 60.0
    assert unit == "per night"


def test_drop_in_visits_service_matching():
    card = """
    8. Sam K.
    $28
    total per visit
    4.9 stars
    """
    raw, num, unit = extract_service_price(card, "drop-in-visits")
    assert num == 28.0
    assert unit == "per visit"


def test_day_care_service_matching():
    card = """
    9. Alex M.
    $35
    total per day
    5.0 stars
    """
    raw, num, unit = extract_service_price(card, "day-care")
    assert num == 35.0
    assert unit == "per day"
