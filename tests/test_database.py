import pytest
import os
import sqlite3
from app.db.connection import get_db
from app.db.schema import init_db
from app.db.repository import (
    save_scrape_results,
    get_all_sessions,
    get_session_by_id,
    get_sessions_sitters_combined,
    clear_entire_database,
    get_master_historical_data,
    delete_session,
    delete_sessions,
    upsert_sitters_and_services_bulk,
    get_all_normalized_sitters_with_services,
)

def test_database_lifecycle_and_schema():
    init_db()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row["name"] for row in cursor.fetchall()}
        assert "search_sessions" in tables
        assert "sitters" in tables
        assert "session_sitters" in tables
        assert "sitter_services" in tables

def test_save_and_retrieve_session():
    init_db()
    sample_records = [
        {
            "name": "Alex P.",
            "raw_price": "$25",
            "price_numeric": 25.0,
            "rating": "5.0 ★",
            "rating_numeric": 5.0,
            "reviews": "10 reviews",
            "reviews_count": 10,
            "headline": "Loving dog walker in Downtown",
            "neighborhood": "Downtown",
            "profile_url": "https://rover.com/members/alex-p-test",
            "photo_url": "https://example.com/photo.jpg",
            "service_type": "dog-walking",
            "location_query": "Toronto, ON",
            "radius_km": 5.0,
            "services": [
                {"service_type": "dog-walking", "service_name": "Dog Walking", "price_numeric": 25.0, "rate_unit": "per walk"}
            ]
        }
    ]
    sample_stats = {
        "min_price": 25.0,
        "avg_price": 25.0,
        "median_price": 25.0,
        "p25_price": 25.0,
        "p75_price": 25.0,
        "max_price": 25.0
    }
    session_id = save_scrape_results(
        location="Toronto, ON",
        service_type="dog-walking",
        radius_km=5.0,
        center_lat=43.6532,
        center_lng=-79.3832,
        pages_requested=1,
        pages_completed=1,
        stats=sample_stats,
        records=sample_records
    )
    assert session_id > 0
    
    session = get_session_by_id(session_id)
    assert session is not None
    assert session["location"] == "Toronto, ON"
    assert len(session["sitters"]) == 1
    assert session["sitters"][0]["name"] == "Alex P."

def test_multi_session_combined_analysis():
    init_db()
    stats = {"min_price": 20, "avg_price": 20, "median_price": 20, "p25_price": 20, "p75_price": 20, "max_price": 20}
    s1 = save_scrape_results("City A", "dog-walking", 5, 0, 0, 1, 1, stats, [{"name": "Sitter 1", "price_numeric": 20, "profile_url": "https://rover.com/members/sitter-1"}])
    s2 = save_scrape_results("City B", "dog-walking", 5, 0, 0, 1, 1, stats, [{"name": "Sitter 2", "price_numeric": 30, "profile_url": "https://rover.com/members/sitter-2"}])

    combined = get_sessions_sitters_combined([s1, s2])
    assert len(combined["sessions"]) == 2
    assert len(combined["sitters"]) == 2

def test_delete_session_and_batch():
    init_db()
    stats = {"min_price": 20, "avg_price": 20, "median_price": 20, "p25_price": 20, "p75_price": 20, "max_price": 20}
    s1 = save_scrape_results("City A", "dog-walking", 5, 0, 0, 1, 1, stats, [{"name": "Sitter 1", "price_numeric": 20, "profile_url": "https://rover.com/members/sitter-1"}])
    s2 = save_scrape_results("City B", "dog-walking", 5, 0, 0, 1, 1, stats, [{"name": "Sitter 2", "price_numeric": 20, "profile_url": "https://rover.com/members/sitter-2"}])
    
    # Test single delete
    assert delete_session(s1) is True
    assert get_session_by_id(s1) is None
    
    # Test batch delete
    assert delete_sessions([s2]) == 1
    assert get_session_by_id(s2) is None

def test_clear_entire_database():
    init_db()
    stats = {"min_price": 20, "avg_price": 20, "median_price": 20, "p25_price": 20, "p75_price": 20, "max_price": 20}
    save_scrape_results("City A", "dog-walking", 5, 0, 0, 1, 1, stats, [{"name": "Sitter 1", "price_numeric": 20, "profile_url": "https://rover.com/members/sitter-1"}])
    
    clear_entire_database()
    assert len(get_all_sessions()) == 0

def test_etl_bulk_upsert_sitters_and_services():
    init_db()
    sample_sitters = [
        {
            "member_id": "sarah-walker-1",
            "name": "Sarah W.",
            "profile_url": "https://rover.com/members/sarah-walker-1",
            "headline": "Full-time professional dog lover",
            "neighborhood": "The Annex",
            "photo_url": "https://example.com/sarah.jpg",
            "rating_numeric": 4.95,
            "reviews_count": 42,
            "services": [
                {"service_type": "dog-walking", "service_name": "Dog Walking", "price_numeric": 28.0, "rate_unit": "per walk"},
                {"service_type": "overnight-boarding", "service_name": "Overnight Boarding", "price_numeric": 65.0, "rate_unit": "per night"},
                {"service_type": "drop-in-visits", "service_name": "Drop-in Visits", "price_numeric": 22.0, "rate_unit": "per visit"}
            ]
        }
    ]

    result = upsert_sitters_and_services_bulk(sample_sitters, location="Toronto, ON", platform="rover")
    assert result["sitters_upserted"] == 1
    assert result["services_upserted"] == 3

    normalized = get_all_normalized_sitters_with_services()
    assert len(normalized) >= 1
    sarah = next(s for s in normalized if s["member_id"] == "sarah-walker-1")
    assert sarah["name"] == "Sarah W."
    assert sarah["neighborhood"] == "The Annex"
    assert len(sarah["services"]) == 3
    service_types = {srv["service_type"] for srv in sarah["services"]}
    assert service_types == {"dog-walking", "overnight-boarding", "drop-in-visits"}
