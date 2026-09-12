from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from bot.database.client import get_supabase


# Cooldown duration for thanking the same user (1 day / 24 hours per user pair)
THANK_COOLDOWN_SECONDS: int = 86400


def check_thank_cooldown(
    last_time: datetime, now: Optional[datetime] = None
) -> Tuple[bool, int, int]:
    """
    Check if a thank action is on cooldown (limit: once per day / 24 hours per user pair).

    Args:
        last_time: When the user last thanked this recipient (must be timezone-aware or UTC).
        now: Current time (defaults to datetime.now(timezone.utc)).

    Returns:
        Tuple[is_on_cooldown, hours_remaining, minutes_remaining]
    """
    if now is None:
        now = datetime.now(timezone.utc)

    if last_time.tzinfo is None:
        last_time = last_time.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    diff = (now - last_time).total_seconds()
    if diff < THANK_COOLDOWN_SECONDS:
        remaining_sec = max(0.0, THANK_COOLDOWN_SECONDS - diff)
        hours = int(remaining_sec // 3600)
        minutes = int((remaining_sec % 3600) // 60)
        return True, hours, minutes
    return False, 0, 0


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
    Enforces a strict 1-thank-per-day limiter per recipient.
    
    Returns:
        Tuple[success, message, new_total_points]
    """
    if from_user_id == to_user_id:
        return False, "You cannot give reputation to yourself!", 0

    supabase = get_supabase()
    if not supabase:
        return False, "Database persistence is not configured on this bot.", 0

    # Check 1-per-day cooldown: has from_user given rep to to_user within the past 24 hours?
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
                is_on_cd, hours, minutes = check_thank_cooldown(last_time)
                if is_on_cd:
                    if hours > 0:
                        wait_str = f"{hours} hour(s) and {minutes} minute(s)"
                    else:
                        wait_str = f"{max(1, minutes)} minute(s)"
                    return (
                        False,
                        f"You can only thank this user once per day. Please wait {wait_str} before thanking them again.",
                        0,
                    )
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


async def adjust_reputation_points(user_id: int, guild_id: int, delta: int) -> int:
    """Adjust reputation points for a user by delta (positive or negative)."""
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
    current = int(res.data[0]["points"]) if res.data else 0
    new_total = max(0, current + delta)
    now_iso = datetime.now(timezone.utc).isoformat()
    await (
        supabase.table("reputation")
        .upsert(
            {
                "user_id": user_id,
                "guild_id": guild_id,
                "points": new_total,
                "updated_at": now_iso,
            },
            on_conflict="user_id,guild_id",
        )
        .execute()
    )
    return new_total


# =============================================================================
# DEVELOPER CHALLENGE QUERIES
# =============================================================================

async def create_challenge(
    guild_id: int,
    channel_id: int,
    author_id: int,
    title: str,
    description: str,
    day_number: Optional[int] = None,
    rules: Optional[str] = None,
    easy_points: int = 5,
    medium_points: int = 10,
    hard_points: int = 15,
    deadline: Optional[datetime] = None,
) -> Optional[int]:
    """Create a new developer challenge record."""
    supabase = get_supabase()
    if not supabase:
        return None

    deadline_iso = deadline.isoformat() if deadline else None
    res = await (
        supabase.table("challenges")
        .insert(
            {
                "guild_id": guild_id,
                "channel_id": channel_id,
                "author_id": author_id,
                "day_number": day_number,
                "title": title,
                "description": description,
                "rules": rules,
                "easy_points": easy_points,
                "medium_points": medium_points,
                "hard_points": hard_points,
                "deadline": deadline_iso,
                "is_active": True,
            }
        )
        .execute()
    )

    if res.data:
        return int(res.data[0]["id"])
    return None


async def update_challenge_message(
    challenge_id: int,
    message_id: int,
    thread_id: Optional[int] = None,
) -> None:
    """Attach message ID and thread ID to a challenge."""
    supabase = get_supabase()
    if not supabase:
        return
    data: Dict[str, Any] = {"message_id": message_id}
    if thread_id:
        data["thread_id"] = thread_id
    await supabase.table("challenges").update(data).eq("id", challenge_id).execute()


async def get_challenge(challenge_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve a challenge by its ID."""
    supabase = get_supabase()
    if not supabase:
        return None
    res = await supabase.table("challenges").select("*").eq("id", challenge_id).execute()
    return res.data[0] if res.data else None


async def get_challenge_by_message(message_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve a challenge by its Discord message ID."""
    supabase = get_supabase()
    if not supabase:
        return None
    res = await supabase.table("challenges").select("*").eq("message_id", message_id).execute()
    return res.data[0] if res.data else None


async def list_challenges(guild_id: int, active_only: bool = False, limit: int = 10) -> List[Dict[str, Any]]:
    """List challenges in a guild."""
    supabase = get_supabase()
    if not supabase:
        return []
    query = supabase.table("challenges").select("*").eq("guild_id", guild_id)
    if active_only:
        query = query.eq("is_active", True)
    res = await query.order("created_at", desc=True).limit(limit).execute()
    return res.data or []


async def close_challenge(challenge_id: int) -> bool:
    """Close an active challenge."""
    supabase = get_supabase()
    if not supabase:
        return False
    res = await supabase.table("challenges").update({"is_active": False}).eq("id", challenge_id).execute()
    return bool(res.data)


async def submit_challenge_entry(
    challenge_id: int,
    guild_id: int,
    user_id: int,
    github_url: str,
    demo_url: Optional[str] = None,
    difficulty_tier: str = "Easy",
    notes: Optional[str] = None,
) -> Tuple[bool, str]:
    """Submit or update a developer's challenge entry."""
    supabase = get_supabase()
    if not supabase:
        return False, "Database is not configured."

    challenge = await get_challenge(challenge_id)
    if not challenge:
        return False, "Challenge not found."
    if not challenge.get("is_active", True):
        return False, "This challenge has ended and is no longer accepting submissions."

    res = await (
        supabase.table("challenge_submissions")
        .upsert(
            {
                "challenge_id": challenge_id,
                "guild_id": guild_id,
                "user_id": user_id,
                "github_url": github_url,
                "demo_url": demo_url,
                "difficulty_tier": difficulty_tier,
                "notes": notes,
                "status": "SUBMITTED",
            },
            on_conflict="challenge_id,user_id",
        )
        .execute()
    )
    if res.data:
        return True, "Solution submitted successfully!"
    return False, "Failed to record challenge submission."


async def award_challenge_points(
    challenge_id: int,
    guild_id: int,
    user_id: int,
    points: int,
    reason: str = "Challenge completion",
) -> Tuple[bool, str]:
    """Award points for a challenge submission to user's Dev Karma."""
    supabase = get_supabase()
    if not supabase:
        return False, "Database is not configured."

    new_total = await adjust_reputation_points(user_id=user_id, guild_id=guild_id, delta=points)
    now_iso = datetime.now(timezone.utc).isoformat()

    # Log in reputation_logs
    await (
        supabase.table("reputation_logs")
        .insert(
            {
                "from_user_id": 0,  # 0 indicates system / event award
                "to_user_id": user_id,
                "guild_id": guild_id,
                "reason": f"Challenge #{challenge_id}: {reason}",
                "created_at": now_iso,
            }
        )
        .execute()
    )

    # Update submission status
    await (
        supabase.table("challenge_submissions")
        .update({"awarded_points": points, "status": "ACCEPTED"})
        .eq("challenge_id", challenge_id)
        .eq("user_id", user_id)
        .execute()
    )

    return True, f"Awarded {points} Dev Karma points! New balance: {new_total}"


# =============================================================================
# DEV KARMA BOUNTY QUERIES
# =============================================================================

async def create_bounty(
    guild_id: int,
    channel_id: int,
    creator_id: int,
    title: str,
    description: str,
    reward_karma: int,
) -> Tuple[bool, str, Optional[int]]:
    """Create a new Dev Karma bounty, escrowing karma from the creator."""
    if reward_karma <= 0:
        return False, "Bounty reward must be at least 1 karma point.", None

    supabase = get_supabase()
    if not supabase:
        return False, "Database is not configured.", None

    # Check creator's karma balance
    current_karma = await get_reputation(user_id=creator_id, guild_id=guild_id)
    if current_karma < reward_karma:
        return (
            False,
            f"Insufficient Dev Karma! You have {current_karma} point(s), but this bounty requires {reward_karma}.",
            None,
        )

    # Escrow karma from creator
    await adjust_reputation_points(user_id=creator_id, guild_id=guild_id, delta=-reward_karma)

    # Insert bounty
    res = await (
        supabase.table("bounties")
        .insert(
            {
                "guild_id": guild_id,
                "channel_id": channel_id,
                "creator_id": creator_id,
                "title": title,
                "description": description,
                "reward_karma": reward_karma,
                "status": "OPEN",
            }
        )
        .execute()
    )

    if res.data:
        bounty_id = int(res.data[0]["id"])
        return True, "Bounty created successfully with reward escrowed.", bounty_id

    # Refund if insertion failed
    await adjust_reputation_points(user_id=creator_id, guild_id=guild_id, delta=reward_karma)
    return False, "Failed to create bounty in database.", None


async def update_bounty_message(
    bounty_id: int,
    message_id: int,
    thread_id: Optional[int] = None,
) -> None:
    """Attach message ID and thread ID to a bounty."""
    supabase = get_supabase()
    if not supabase:
        return
    data: Dict[str, Any] = {"message_id": message_id}
    if thread_id:
        data["thread_id"] = thread_id
    await supabase.table("bounties").update(data).eq("id", bounty_id).execute()


async def get_bounty(bounty_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve a bounty by ID."""
    supabase = get_supabase()
    if not supabase:
        return None
    res = await supabase.table("bounties").select("*").eq("id", bounty_id).execute()
    return res.data[0] if res.data else None


async def list_open_bounties(guild_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """List open bounties in a guild."""
    supabase = get_supabase()
    if not supabase:
        return []
    res = await (
        supabase.table("bounties")
        .select("*")
        .eq("guild_id", guild_id)
        .eq("status", "OPEN")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []


async def accept_bounty(
    bounty_id: int,
    solver_id: int,
    caller_id: int,
    is_admin: bool = False,
) -> Tuple[bool, str]:
    """Transfer the escrowed karma to the solver and mark bounty resolved."""
    supabase = get_supabase()
    if not supabase:
        return False, "Database is not configured."

    bounty = await get_bounty(bounty_id)
    if not bounty:
        return False, f"Bounty #{bounty_id} was not found."

    if bounty.get("status") != "OPEN":
        return False, f"Bounty #{bounty_id} is already {bounty.get('status')}."

    creator_id = int(bounty["creator_id"])
    if caller_id != creator_id and not is_admin:
        return False, "Only the bounty creator or an administrator can accept a solution."

    if solver_id == creator_id:
        return False, "Creators cannot claim their own bounty reward!"

    reward = int(bounty["reward_karma"])
    guild_id = int(bounty["guild_id"])

    # Award escrowed karma to solver
    await adjust_reputation_points(user_id=solver_id, guild_id=guild_id, delta=reward)
    now_iso = datetime.now(timezone.utc).isoformat()

    # Log transfer in reputation_logs
    await (
        supabase.table("reputation_logs")
        .insert(
            {
                "from_user_id": creator_id,
                "to_user_id": solver_id,
                "guild_id": guild_id,
                "reason": f"Bounty #{bounty_id}: {bounty.get('title', 'Help awarded')}",
                "created_at": now_iso,
            }
        )
        .execute()
    )

    # Mark resolved
    await (
        supabase.table("bounties")
        .update({"status": "RESOLVED", "solver_id": solver_id, "resolved_at": now_iso})
        .eq("id", bounty_id)
        .execute()
    )

    return True, f"Bounty #{bounty_id} resolved! {reward} Dev Karma awarded to solver."


async def cancel_bounty(
    bounty_id: int,
    caller_id: int,
    is_admin: bool = False,
) -> Tuple[bool, str]:
    """Cancel an open bounty and refund the escrowed karma back to the creator."""
    supabase = get_supabase()
    if not supabase:
        return False, "Database is not configured."

    bounty = await get_bounty(bounty_id)
    if not bounty:
        return False, f"Bounty #{bounty_id} was not found."

    if bounty.get("status") != "OPEN":
        return False, f"Bounty #{bounty_id} cannot be cancelled because it is {bounty.get('status')}."

    creator_id = int(bounty["creator_id"])
    if caller_id != creator_id and not is_admin:
        return False, "Only the bounty creator or an administrator can cancel this bounty."

    reward = int(bounty["reward_karma"])
    guild_id = int(bounty["guild_id"])
    now_iso = datetime.now(timezone.utc).isoformat()

    # Refund karma
    await adjust_reputation_points(user_id=creator_id, guild_id=guild_id, delta=reward)

    # Mark cancelled
    await (
        supabase.table("bounties")
        .update({"status": "CANCELLED", "resolved_at": now_iso})
        .eq("id", bounty_id)
        .execute()
    )

    return True, f"Bounty #{bounty_id} has been cancelled. {reward} Dev Karma refunded."

