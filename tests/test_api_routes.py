"""
Integration tests for FastAPI application endpoints.
Uses TestClient to verify route status codes and responses.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.db.schema import init_db
from app.db.repository import save_scrape_results

@pytest.fixture(scope="module")
def client():
    """Initializes schema and returns a TestClient instance."""
    init_db()
    app = create_app()
    with TestClient(app) as c:
        yield c


def test_serve_index_html(client):
    response = client.get("/")
    assert response.status_code == 200


def test_get_services_endpoint(client):
    response = client.get("/api/services")
    assert response.status_code == 200
    data = response.json()
    assert "overnight-boarding" in data
    assert "dog-walking" in data


def test_get_history_empty_or_list(client):
    response = client.get("/api/history")
    assert response.status_code == 200
    data = response.json()
    assert "sessions" in data
    assert isinstance(data["sessions"], list)


def test_analyze_selected_sessions_endpoint(client):
    sample_records = [
        {"name": "Sitter A", "price_numeric": 25.0, "reviews_count": 5, "profile_url": "https://rover.com/members/sitter-a"},
        {"name": "Sitter B", "price_numeric": 35.0, "reviews_count": 10, "profile_url": "https://rover.com/members/sitter-b"},
    ]
    sid = save_scrape_results("Toronto", "dog-walking", 5, 0, 0, 1, 1, {"min_price": 25, "avg_price": 30, "median_price": 30, "p25_price": 25, "p75_price": 35, "max_price": 35}, sample_records)

    payload = {"session_ids": [sid]}
    response = client.post("/api/history/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["total_sitters"] == 2
    assert "stats" in data


def test_database_reset_endpoint(client):
    response = client.post("/api/database/reset")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"


def test_analytics_recalculate_empty(client):
    payload = {
        "records": [
            {"name": "Sitter 1", "price_numeric": 25.0, "reviews_count": 5},
            {"name": "Sitter 2", "price_numeric": 35.0, "reviews_count": 10},
        ],
        "excluded_indices": []
    }
    response = client.post("/api/analytics/recalculate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "stats" in data
    assert data["stats"]["active_sitters"] == 2
    assert data["stats"]["median_price"] == 30.0


def test_analytics_temporal_trends(client):
    response = client.get("/api/analytics/temporal-trends")
    assert response.status_code == 200
    data = response.json()
    assert "trends" in data
    assert isinstance(data["trends"], list)


def test_export_master_csv(client):
    response = client.get("/api/export/master-csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "Sitter_ID" in response.text
    assert "Member_ID" in response.text
