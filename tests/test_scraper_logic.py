import re
import pytest
from app.services.scraper.parser import (
    extract_price,
    parse_sitter_name_and_headline,
    build_sitter_record,
    extract_all_services_and_prices,
)
from app.services.scraper.geocoding import extract_postal_code_fsa, geocode_postal_code_with_city
from app.services.scraper.postal_data import lookup_fsa_data

def extract_service_price(card_text: str, service_type: str, price_text: str = ""):
    """Helper forwarding to parser's extract_price, returning (raw_price, price_numeric, rate_unit)."""
    price_numeric, raw_price, rate_unit = extract_price(price_text, card_text, service_type)
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


def test_fsa_extraction_and_offline_lookup():
    card = "Toronto, ON, M5V"
    postal = extract_postal_code_fsa(card)
    assert postal == "M5V"
    
    fsa_info = lookup_fsa_data(postal)
    assert fsa_info is not None
    lat, lng, hood = fsa_info
    assert round(lat, 2) == 43.64
    assert round(lng, 2) == -79.40
    assert "Entertainment District" in hood or "King West" in hood


def test_parse_sitter_name_and_headline_with_fsa():
    card = """
    1. Dustin T.Star Sitter
    Safe, Fun and Reliable Pet Care 🌈
    Toronto, ON, M4V
    $28
    total per walk
    5.0 out of 5 stars
    • 6 reviews
    """
    name, headline, hood, postal, lat, lng = parse_sitter_name_and_headline(
        "1. Dustin T.Star Sitter", card, "https://rover.com/members/dustin-t"
    )
    assert name == "Dustin T."
    assert headline == "Safe, Fun and Reliable Pet Care 🌈"
    assert postal == "M4V"
    assert lat is not None and lng is not None
    assert round(lat, 2) == 43.69
    assert round(lng, 2) == -79.40
    assert hood is not None
    assert "Summerhill" in hood or "Forest Hill" in hood


def test_build_sitter_record_with_fsa_coordinates():
    card = {
        "url": "https://rover.com/members/dustin-t",
        "extractedName": "1. Dustin T.Star Sitter",
        "priceText": "$28\ntotal per walk",
        "neighborhood": "",
        "cardText": "1. Dustin T.Star Sitter\nSafe, Fun and Reliable Pet Care 🌈\nToronto, ON, M4V\n$28\ntotal per walk\n5.0 out of 5 stars\n• 6 reviews",
        "photoUrl": "https://example.com/dustin.jpg"
    }
    record = build_sitter_record(card, "dog-walking", "Toronto, ON", center_lat=43.6532, center_lng=-79.3832)
    assert record is not None
    assert record["name"] == "Dustin T."
    assert record["postal_code"] == "M4V"
    assert record["lat"] is not None
    assert record["lat"] != 43.6532  # Resolved to M4V centroid (43.6864), not generic city center!
    assert round(record["lat"], 2) == 43.69


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


def test_all_services_master_catalog_extraction():
    card = """
    1. Taylor B.
    $25 per walk
    $65 per night
    $20 per visit
    $35 per day
    5.0 stars (50 reviews)
    """
    extracted = extract_all_services_and_prices(card, price_text="$25 per walk")
    types = {srv["service_type"]: srv["price_numeric"] for srv in extracted}
    assert types["dog-walking"] == 25.0
    assert types["overnight-boarding"] == 65.0
    assert types["drop-in-visits"] == 20.0
    assert types["day-care"] == 35.0


def test_rover_service_param_mapping():
    from app.services.scraper.rover_strategy import ROVER_SERVICE_PARAM_MAP
    assert ROVER_SERVICE_PARAM_MAP["overnight-boarding"] == "overnight-boarding"
    assert ROVER_SERVICE_PARAM_MAP["house-sitting"] == "overnight-traveling"
    assert ROVER_SERVICE_PARAM_MAP["drop-in-visits"] == "drop-in"
    assert ROVER_SERVICE_PARAM_MAP["day-care"] == "doggy-day-care"
    assert ROVER_SERVICE_PARAM_MAP["dog-walking"] == "dog-walking"


def test_extract_all_services_with_house_sitting_context():
    card = """
    1. Sarah P.
    $75 per night
    $25 per walk
    """
    extracted = extract_all_services_and_prices(card, price_text="$75 per night", current_service="house-sitting")
    types = {srv["service_type"]: srv["price_numeric"] for srv in extracted}
    assert types.get("house-sitting") == 75.0
    assert types.get("dog-walking") == 25.0

