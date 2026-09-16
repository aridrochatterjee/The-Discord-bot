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


def test_check_thank_cooldown_active():
    from datetime import datetime, timedelta, timezone
    from bot.database.queries import check_thank_cooldown

    now = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)
    
    # 2 hours ago -> ~22 hours left
    last_thanked = now - timedelta(hours=2)
    on_cd, hours, minutes = check_thank_cooldown(last_thanked, now=now)
    assert on_cd is True
    assert hours == 22
    assert minutes == 0

    # 23 hours and 30 minutes ago -> 30 minutes left
    last_thanked = now - timedelta(hours=23, minutes=30)
    on_cd, hours, minutes = check_thank_cooldown(last_thanked, now=now)
    assert on_cd is True
    assert hours == 0
    assert minutes == 30


def test_check_thank_cooldown_expired():
    from datetime import datetime, timedelta, timezone
    from bot.database.queries import check_thank_cooldown

    now = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)

    # 24 hours and 1 minute ago -> expired
    last_thanked = now - timedelta(hours=24, minutes=1)
    on_cd, hours, minutes = check_thank_cooldown(last_thanked, now=now)
    assert on_cd is False
    assert hours == 0
    assert minutes == 0

    # Exactly 24 hours ago -> expired
    last_thanked = now - timedelta(hours=24)
    on_cd, hours, minutes = check_thank_cooldown(last_thanked, now=now)
    assert on_cd is False
    assert hours == 0
    assert minutes == 0


def test_check_thank_cooldown_naive_datetime():
    from datetime import datetime, timedelta
    from bot.database.queries import check_thank_cooldown

    # Should handle naive datetime without throwing TypeError
    now = datetime(2026, 9, 12, 12, 0, 0)
    last_thanked = now - timedelta(hours=5)
    on_cd, hours, minutes = check_thank_cooldown(last_thanked, now=now)
    assert on_cd is True
    assert hours == 19

