from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from bot.database.client import get_supabase


# =============================================================================
# REPUTATION / KARMA QUERIES
# =============================================================================

async def get_reputation(user_id: int, guild_id: int) -> int:
    """Fetch the total reputation points for a user in a guild."""
    supabase = get_supabase()
    if not supabase:
        return 0

    res = await (
        supabase.table("reputation")
        .select("points")
        .eq("user_id", user_id)
        .eq("guild_id", guild_id)
        .execute()
    )

    if res.data:
        return int(res.data[0].get("points", 0))
    return 0


async def give_reputation(
    from_user_id: int,
    to_user_id: int,
    guild_id: int,
    reason: str = "Helping a fellow developer",
) -> Tuple[bool, str, int]:
    """
    Award reputation points from one user to another.
    
    Returns:
        Tuple[success, message, new_total_points]
    """
    if from_user_id == to_user_id:
        return False, "You cannot give reputation to yourself!", 0

    supabase = get_supabase()
    if not supabase:
        return False, "Database persistence is not configured on this bot.", 0

    # Check cooldown: has from_user given rep to to_user recently (e.g. past 10 minutes)?
    # For now, check reputation_logs
    recent_logs = await (
        supabase.table("reputation_logs")
        .select("created_at")
        .eq("from_user_id", from_user_id)
        .eq("to_user_id", to_user_id)
        .eq("guild_id", guild_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    if recent_logs.data:
        last_time_str = recent_logs.data[0].get("created_at")
        if last_time_str:
            try:
                # Parse ISO timestamp
                last_time = datetime.fromisoformat(last_time_str.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                diff = (now - last_time).total_seconds()
                if diff < 600:  # 10 minute cooldown
                    remaining = int((600 - diff) // 60) + 1
                    return False, f"You recently gave reputation to this user. Please wait {remaining} more minute(s).", 0
            except Exception:
                pass

    # Fetch current points
    current_res = await (
        supabase.table("reputation")
        .select("points")
        .eq("user_id", to_user_id)
        .eq("guild_id", guild_id)
        .execute()
    )

    current_points = int(current_res.data[0]["points"]) if current_res.data else 0
    new_points = current_points + 1
    now_iso = datetime.now(timezone.utc).isoformat()

    # Upsert reputation
    await (
        supabase.table("reputation")
        .upsert(
            {
                "user_id": to_user_id,
                "guild_id": guild_id,
                "points": new_points,
                "last_thanked_at": now_iso,
                "updated_at": now_iso,
            },
            on_conflict="user_id,guild_id",
        )
        .execute()
    )

    # Log the action
    await (
        supabase.table("reputation_logs")
        .insert(
            {
                "from_user_id": from_user_id,
                "to_user_id": to_user_id,
                "guild_id": guild_id,
                "reason": reason,
                "created_at": now_iso,
            }
        )
        .execute()
    )

    return True, f"Reputation awarded! {reason}", new_points


async def get_top_reputation(guild_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Get the top contributors in a guild by reputation points."""
    supabase = get_supabase()
    if not supabase:
        return []

    res = await (
        supabase.table("reputation")
        .select("user_id, points, last_thanked_at")
        .eq("guild_id", guild_id)
        .order("points", desc=True)
        .limit(limit)
        .execute()
    )

    return res.data or []


# =============================================================================
# SHOWCASE QUERIES
# =============================================================================

async def create_showcase(
    author_id: int,
    guild_id: int,
    title: str,
    description: str,
    tech_stack: str,
    github_url: Optional[str] = None,
    demo_url: Optional[str] = None,
    message_id: Optional[int] = None,
    channel_id: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Save a project showcase submission."""
    supabase = get_supabase()
    if not supabase:
        return None

    res = await (
        supabase.table("showcases")
        .insert(
            {
                "author_id": author_id,
                "guild_id": guild_id,
                "title": title,
                "description": description,
                "tech_stack": tech_stack,
                "github_url": github_url,
                "demo_url": demo_url,
                "message_id": message_id,
                "channel_id": channel_id,
                "upvotes": 0,
            }
        )
        .execute()
    )

    return res.data[0] if res.data else None


async def vote_showcase(showcase_id: int, user_id: int) -> Tuple[bool, str, int]:
    """
    Vote for a project showcase.
    
    Returns:
        Tuple[success, message, current_upvote_count]
    """
    supabase = get_supabase()
    if not supabase:
        return False, "Database persistence is not configured.", 0

    # Fetch showcase
    sc_res = await supabase.table("showcases").select("*").eq("id", showcase_id).execute()
    if not sc_res.data:
        return False, "Showcase not found.", 0

    showcase = sc_res.data[0]
    if int(showcase["author_id"]) == user_id:
        return False, "You cannot upvote your own project showcase!", showcase.get("upvotes", 0)

    # Check if user already voted
    vote_check = await (
        supabase.table("showcase_votes")
        .select("user_id")
        .eq("showcase_id", showcase_id)
        .eq("user_id", user_id)
        .execute()
    )

    current_upvotes = int(showcase.get("upvotes", 0))

    if vote_check.data:
        # Toggle: remove vote
        await (
            supabase.table("showcase_votes")
            .delete()
            .eq("showcase_id", showcase_id)
            .eq("user_id", user_id)
            .execute()
        )
        new_upvotes = max(0, current_upvotes - 1)
        await supabase.table("showcases").update({"upvotes": new_upvotes}).eq("id", showcase_id).execute()
        return True, "Removed your upvote from this project.", new_upvotes

    # Add vote
    await (
        supabase.table("showcase_votes")
        .insert({"showcase_id": showcase_id, "user_id": user_id})
        .execute()
    )
    new_upvotes = current_upvotes + 1
    await supabase.table("showcases").update({"upvotes": new_upvotes}).eq("id", showcase_id).execute()
    return True, "Upvoted project showcase!", new_upvotes


async def update_showcase_message(
    showcase_id: int,
    message_id: int,
    channel_id: int,
) -> None:
    """Associate a showcase record with its posted Discord message ID."""
    supabase = get_supabase()
    if not supabase:
        return
    await (
        supabase.table("showcases")
        .update({"message_id": message_id, "channel_id": channel_id})
        .eq("id", showcase_id)
        .execute()
    )


async def get_showcase_by_message(message_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve a showcase by its Discord message ID."""
    supabase = get_supabase()
    if not supabase:
        return None

    res = await (
        supabase.table("showcases")
        .select("*")
        .eq("message_id", message_id)
        .execute()
    )
    return res.data[0] if res.data else None


async def get_showcase_by_id(showcase_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve a showcase by its database ID."""
    supabase = get_supabase()
    if not supabase:
        return None

    res = await (
        supabase.table("showcases")
        .select("*")
        .eq("id", showcase_id)
        .execute()
    )
    return res.data[0] if res.data else None


async def get_recent_showcases(guild_id: int, limit: int = 5) -> List[Dict[str, Any]]:
    """Fetch recent showcases submitted to a guild."""
    supabase = get_supabase()
    if not supabase:
        return []

    res = await (
        supabase.table("showcases")
        .select("*")
        .eq("guild_id", guild_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []


async def get_user_showcases(author_id: int, guild_id: int) -> List[Dict[str, Any]]:
    """Fetch all showcases by a specific author in a guild."""
    supabase = get_supabase()
    if not supabase:
        return []

    res = await (
        supabase.table("showcases")
        .select("*")
        .eq("author_id", author_id)
        .eq("guild_id", guild_id)
        .order("created_at", desc=True)
        .execute()
    )
    return res.data or []

