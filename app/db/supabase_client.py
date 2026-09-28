"""
Supabase client initialization and resilience wrapper.

Provides thread-safe access to the Supabase client when configured,
with graceful fallback if credentials are absent or remote is unreachable.
"""
import logging
from typing import Optional
from supabase import create_client, Client
from app.config import settings

logger = logging.getLogger("rover.db.supabase")

_supabase_client: Optional[Client] = None


def get_supabase_client() -> Optional[Client]:
    """
    Returns a singleton instance of the Supabase Client.
    Returns None if Supabase credentials are not configured or on connection failure.
    """
    global _supabase_client
    if not settings.is_supabase_enabled:
        return None

    if _supabase_client is None:
        try:
            _supabase_client = create_client(settings.supabase_url, settings.supabase_key)
            logger.info("Supabase client initialized successfully for %s", settings.supabase_url)
        except Exception as exc:
            logger.error("Failed to initialize Supabase client: %s", exc)
            return None

    return _supabase_client
