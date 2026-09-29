"""
Unit and integration tests for Supabase real-time synchronization layer.
"""
from unittest.mock import MagicMock, patch
import pytest

from app.db.supabase_sync import sync_scrape_session_to_supabase
from app.db.supabase_client import get_supabase_client
from app.config import settings


def test_supabase_sync_disabled_when_settings_empty():
    """Verifies sync returns None when Supabase is not configured."""
    with patch.object(settings, "supabase_url", None), patch.object(settings, "supabase_key", None):
        res = sync_scrape_session_to_supabase(
            location="Toronto, ON",
            service_type="dog-walking",
            radius_km=5.0,
            center_lat=43.65,
            center_lng=-79.38,
            pages_requested=1,
            pages_completed=1,
            stats={"min_price": 20.0, "avg_price": 25.0, "max_price": 30.0},
            records=[],
        )
        assert res is None


def test_supabase_sync_resilient_to_network_failure():
    """Verifies that an exception during Supabase client calls is caught and handled gracefully."""
    with patch.object(settings, "supabase_url", "https://mock.supabase.co"), patch.object(settings, "supabase_key", "mock-key"):
        with patch("app.db.supabase_sync.get_supabase_client") as mock_client_factory:
            mock_supabase = MagicMock()
            mock_supabase.table.side_effect = RuntimeError("Connection timeout to remote postgres")
            mock_client_factory.return_value = mock_supabase

            res = sync_scrape_session_to_supabase(
                location="Toronto, ON",
                service_type="dog-walking",
                radius_km=5.0,
                center_lat=43.65,
                center_lng=-79.38,
                pages_requested=1,
                pages_completed=1,
                stats={"min_price": 20.0, "avg_price": 25.0, "max_price": 30.0},
                records=[{"name": "Test Sitter", "profile_url": "https://rover.com/members/test-1", "price_numeric": 25}],
            )
            # Must return None and NOT raise RuntimeError
            assert res is None


def test_supabase_sync_successful_batch_flow():
    """Verifies full execution pipeline: session insert, sitters upsert, session_sitters link, services upsert."""
    with patch.object(settings, "supabase_url", "https://mock.supabase.co"), patch.object(settings, "supabase_key", "mock-key"):
        with patch("app.db.supabase_sync.get_supabase_client") as mock_client_factory:
            mock_supabase = MagicMock()
            mock_client_factory.return_value = mock_supabase

            # Mock search_sessions insert
            mock_sessions_table = MagicMock()
            mock_sessions_insert = MagicMock()
            mock_sessions_insert.execute.return_value = MagicMock(data=[{"id": 42}])
            mock_sessions_table.insert.return_value = mock_sessions_insert

            # Mock sitters upsert
            mock_sitters_table = MagicMock()
            mock_sitters_upsert = MagicMock()
            mock_sitters_upsert.execute.return_value = MagicMock(data=[{"id": 101, "member_id": "alex-101"}])
            mock_sitters_table.upsert.return_value = mock_sitters_upsert

            # Mock session_sitters
            mock_ss_table = MagicMock()
            mock_ss_upsert = MagicMock()
            mock_ss_upsert.execute.return_value = MagicMock(data=[{"session_id": 42, "sitter_id": 101}])
            mock_ss_table.upsert.return_value = mock_ss_upsert

            # Mock sitter_services
            mock_srv_table = MagicMock()
            mock_srv_upsert = MagicMock()
            mock_srv_upsert.execute.return_value = MagicMock(data=[{"id": 201}])
            mock_srv_table.upsert.return_value = mock_srv_upsert

            def table_router(name):
                if name == "search_sessions":
                    return mock_sessions_table
                elif name == "sitters":
                    return mock_sitters_table
                elif name == "session_sitters":
                    return mock_ss_table
                elif name == "sitter_services":
                    return mock_srv_table
                return MagicMock()

            mock_supabase.table.side_effect = table_router

            records = [
                {
                    "name": "Alex",
                    "member_id": "alex-101",
                    "profile_url": "https://rover.com/members/alex-101/",
                    "rating_numeric": 4.9,
                    "reviews_count": 15,
                    "services": [
                        {"service_type": "dog-walking", "service_name": "Dog Walking", "price_numeric": 30.0, "rate_unit": "per walk"}
                    ]
                }
            ]

            session_id = sync_scrape_session_to_supabase(
                location="Toronto, ON",
                service_type="dog-walking",
                radius_km=5.0,
                center_lat=43.65,
                center_lng=-79.38,
                pages_requested=1,
                pages_completed=1,
                stats={"min_price": 30.0, "avg_price": 30.0, "max_price": 30.0},
                records=records,
            )

            assert session_id == 42
            assert mock_sessions_table.insert.called
            assert mock_sitters_table.upsert.called
            assert mock_ss_table.upsert.called
            assert mock_srv_table.upsert.called
