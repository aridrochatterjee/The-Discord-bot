from __future__ import annotations

import asyncio
from collections import defaultdict, deque

import pytest

import bot.cogs.gpt as gpt_module
from bot.cogs.gpt import (
    GLOBAL_REQUEST_LIMIT,
    GLOBAL_REQUEST_WINDOW,
    GPT,
    USER_COOLDOWN,
)


def make_rate_limit_cog() -> GPT:
    """Create the rate-limit portion of GPT without external API setup."""

    cog = object.__new__(GPT)

    cog.user_last_request = {}
    cog.user_requests = defaultdict(deque)
    cog.global_requests = deque()
    cog.rate_limit_lock = asyncio.Lock()

    return cog


def test_clean_old_requests_removes_expired_items_at_boundary() -> None:
    requests = deque([89.0, 90.0, 95.0])

    GPT._clean_old_requests(
        requests,
        window=10.0,
        now=100.0,
    )

    assert list(requests) == [95.0]


@pytest.mark.asyncio
async def test_first_request_is_allowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cog = make_rate_limit_cog()

    monkeypatch.setattr(
        gpt_module.time,
        "monotonic",
        lambda: 100.0,
    )

    allowed, error = await cog.check_rate_limit(123)

    assert allowed is True
    assert error is None


@pytest.mark.asyncio
async def test_user_cooldown_rejects_early_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cog = make_rate_limit_cog()

    now = 100.0

    monkeypatch.setattr(
        gpt_module.time,
        "monotonic",
        lambda: now,
    )

    allowed, error = await cog.check_rate_limit(123)

    assert allowed is True
    assert error is None

    now = 100.0 + USER_COOLDOWN - 0.1

    allowed, error = await cog.check_rate_limit(123)

    assert allowed is False
    assert error is not None
    assert "wait" in error.lower()


@pytest.mark.asyncio
async def test_rejected_retry_does_not_extend_user_cooldown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cog = make_rate_limit_cog()

    now = 100.0

    monkeypatch.setattr(
        gpt_module.time,
        "monotonic",
        lambda: now,
    )

    allowed, _ = await cog.check_rate_limit(123)
    assert allowed is True

    now = 100.0 + USER_COOLDOWN - 0.1

    allowed, _ = await cog.check_rate_limit(123)
    assert allowed is False

    now = 100.0 + USER_COOLDOWN

    allowed, error = await cog.check_rate_limit(123)

    assert allowed is True
    assert error is None


@pytest.mark.asyncio
async def test_global_request_limit_rejects_next_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cog = make_rate_limit_cog()

    monkeypatch.setattr(
        gpt_module.time,
        "monotonic",
        lambda: 100.0,
    )

    for user_id in range(GLOBAL_REQUEST_LIMIT):
        allowed, error = await cog.check_rate_limit(user_id)

        assert allowed is True
        assert error is None

    allowed, error = await cog.check_rate_limit(
        GLOBAL_REQUEST_LIMIT
    )

    assert allowed is False
    assert error is not None


@pytest.mark.asyncio
async def test_global_limit_expires_at_window_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cog = make_rate_limit_cog()

    now = 100.0

    monkeypatch.setattr(
        gpt_module.time,
        "monotonic",
        lambda: now,
    )

    for user_id in range(GLOBAL_REQUEST_LIMIT):
        allowed, _ = await cog.check_rate_limit(user_id)
        assert allowed is True

    now = 100.0 + GLOBAL_REQUEST_WINDOW

    allowed, error = await cog.check_rate_limit(
        GLOBAL_REQUEST_LIMIT
    )

    assert allowed is True
    assert error is None
