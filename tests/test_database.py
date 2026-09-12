import pytest
from bot.database.client import get_supabase, init_supabase
from bot.database.queries import get_reputation, give_reputation, vote_showcase


@pytest.mark.asyncio
async def test_supabase_unconfigured_fallback():
    # When credentials are not set, init should return None without crashing
    client = get_supabase()
    # If no credentials in .env yet, client should be None
    if client is None:
        rep = await get_reputation(123456789, 987654321)
        assert rep == 0


@pytest.mark.asyncio
async def test_reputation_self_thank_prevented():
    # Users must not be able to thank themselves
    success, message, points = await give_reputation(
        from_user_id=12345,
        to_user_id=12345,
        guild_id=99999,
        reason="Cheating karma",
    )
    assert success is False
    assert "yourself" in message.lower()
    assert points == 0
