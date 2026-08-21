import pytest
import os
import sqlite3
from app.db.connection import get_db
from app.db.schema import init_db
from app.db.repository import (
    save_scrape_results,
    update_sitter_exclusion,
    get_all_sessions,
    get_session_by_id,
    get_master_historical_data,
    delete_session,
    delete_sessions,
)

def test_database_lifecycle_and_schema():
    init_db()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row["name"] for row in cursor.fetchall()}
        assert "search_sessions" in tables
        assert "sitter_listings" in tables

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
            "lat": 43.6532,
            "lng": -79.3832,
            "service_radius_km": 2.5,
            "page": 1
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
    
    sitter = session["sitters"][0]
    assert sitter["name"] == "Alex P."
    assert sitter["price_numeric"] == 25.0
    assert sitter["is_excluded"] == 0
    
    # Test exclusion persistence
    sitter_id = sitter["id"]
    updated = update_sitter_exclusion(sitter_id, is_excluded=True, reason="Test exclusion")
    assert updated is True
    
    session_updated = get_session_by_id(session_id)
    assert session_updated["sitters"][0]["is_excluded"] == 1
    assert session_updated["sitters"][0]["excluded_reason"] == "Test exclusion"

def test_delete_session_and_batch():
    init_db()
    stats = {"min_price": 20, "avg_price": 20, "median_price": 20, "p25_price": 20, "p75_price": 20, "max_price": 20}
    s1 = save_scrape_results("City A", "dog-walking", 5, 0, 0, 1, 1, stats, [{"name": "Sitter 1", "price_numeric": 20}])
    s2 = save_scrape_results("City B", "dog-walking", 5, 0, 0, 1, 1, stats, [{"name": "Sitter 2", "price_numeric": 20}])
    
    # Test single delete
    assert delete_session(s1) is True
    assert get_session_by_id(s1) is None
    
    # Test batch delete
    assert delete_sessions([s2]) == 1
    assert get_session_by_id(s2) is None
