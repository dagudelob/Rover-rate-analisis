"""
Pytest configuration and test database isolation fixture.

Ensures that automated tests run against an isolated temporary SQLite database
and never touch or purge the production/development rover_market.db.
"""
import os
import tempfile
import pytest
from app.config import settings
from app.db.schema import init_db


@pytest.fixture(autouse=True, scope="session")
def isolate_test_database():
    """Points settings.db_path to an isolated temporary file for the test session."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        temp_db_path = tmp.name

    original_db_path = settings.db_path
    settings.db_path = temp_db_path
    os.environ["DB_PATH"] = temp_db_path

    # Initialize schema on the isolated test database
    init_db()

    yield temp_db_path

    # Restore original path and clean up temporary database file
    settings.db_path = original_db_path
    if os.path.exists(temp_db_path):
        try:
            os.remove(temp_db_path)
        except OSError:
            pass
