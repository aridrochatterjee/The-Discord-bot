from __future__ import annotations

import logging
from typing import Optional

from supabase import AsyncClient, create_async_client

from bot.config import SUPABASE_KEY, SUPABASE_URL


logger = logging.getLogger("bot.database")

_client: Optional[AsyncClient] = None


async def init_supabase() -> Optional[AsyncClient]:
    """
    Initialize the asynchronous Supabase client.
    
    If credentials are missing, logs an informative warning rather than crashing,
    enabling the bot to run stateless commands while the database is being set up.
    """
    global _client

    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.warning(
            "[Supabase] SUPABASE_URL or SUPABASE_KEY is missing in .env. "
            "Database-backed features (showcases, karma) will be unavailable until configured."
        )
        return None

    try:
        _client = await create_async_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("[Supabase] Successfully initialized async client.")
        return _client
    except Exception as e:
        logger.error(f"[Supabase] Failed to initialize client: {e}")
        return None


def get_supabase() -> Optional[AsyncClient]:
    """Get the current initialized Supabase client instance."""
    return _client
