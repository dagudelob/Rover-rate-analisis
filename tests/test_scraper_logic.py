import re
import pytest
from app.services.scraper.parser import extract_price

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
