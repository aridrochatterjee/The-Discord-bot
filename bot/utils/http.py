from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

import aiohttp


_session: Optional[aiohttp.ClientSession] = None


async def get_session() -> aiohttp.ClientSession:
    """Get or create the global aiohttp ClientSession."""
    global _session
    if _session is None or _session.closed:
        timeout = aiohttp.ClientTimeout(total=15)
        _session = aiohttp.ClientSession(
            timeout=timeout,
            headers={"User-Agent": "HorizonDevs-DiscordBot/1.0"},
        )
    return _session


async def close_session() -> None:
    """Close the global aiohttp ClientSession gracefully."""
    global _session
    if _session and not _session.closed:
        await _session.close()
        _session = None


async def fetch_json(
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    timeout_seconds: float = 10.0,
) -> Optional[Dict[str, Any]]:
    """Fetch and parse JSON from a remote URL."""
    session = await get_session()
    try:
        async with session.get(
            url,
            headers=headers,
            params=params,
            timeout=aiohttp.ClientTimeout(total=timeout_seconds),
        ) as resp:
            if resp.status == 200:
                return await resp.json()
            return None
    except (asyncio.TimeoutError, aiohttp.ClientError):
        return None


async def post_json(
    url: str,
    payload: Dict[str, Any],
    *,
    headers: Optional[Dict[str, str]] = None,
    timeout_seconds: float = 15.0,
) -> Optional[Dict[str, Any]]:
    """Send a POST request with a JSON body and parse response JSON."""
    session = await get_session()
    try:
        async with session.post(
            url,
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=timeout_seconds),
        ) as resp:
            if resp.status in (200, 201):
                return await resp.json()
            return None
    except (asyncio.TimeoutError, aiohttp.ClientError):
        return None
