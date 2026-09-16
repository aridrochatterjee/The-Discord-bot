from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from bot.database.client import get_supabase


# =============================================================================
# CONSTANTS
# =============================================================================

# Cooldown for thanking the same user.
THANK_COOLDOWN_SECONDS: int = 86400


# =============================================================================
# GENERAL HELPERS
# =============================================================================

def _utc_now_iso() -> str:
    """Return the current UTC timestamp as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _parse_timestamp(value: Any) -> Optional[datetime]:
    """Safely parse a timestamp returned by Supabase."""
    if not value:
        return None

    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed


def check_thank_cooldown(
    last_time: datetime,
    now: Optional[datetime] = None,
) -> Tuple[bool, int, int]:
    """
    Check whether a thank action is still on cooldown.

    Returns:
        Tuple[
            is_on_cooldown,
            hours_remaining,
            minutes_remaining,
        ]
    """
    if now is None:
        now = datetime.now(timezone.utc)

    if last_time.tzinfo is None:
        last_time = last_time.replace(tzinfo=timezone.utc)

    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    diff = (now - last_time).total_seconds()

    if diff < THANK_COOLDOWN_SECONDS:
        remaining_seconds = max(0.0, THANK_COOLDOWN_SECONDS - diff)

        hours = int(remaining_seconds // 3600)
        minutes = int((remaining_seconds % 3600) // 60)

        return True, hours, minutes

    return False, 0, 0


# =============================================================================
# REPUTATION / KARMA QUERIES
# =============================================================================

async def get_reputation(user_id: int, guild_id: int) -> int:
    """Fetch a user's total Dev Karma in a guild."""
    supabase = get_supabase()

    if not supabase:
        return 0

    try:
        res = await (
            supabase.table("reputation")
            .select("points")
            .eq("user_id", user_id)
            .eq("guild_id", guild_id)
            .limit(1)
            .execute()
        )
    except Exception:
        return 0

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
    Award one Dev Karma point from one user to another.

    A user may thank the same recipient once every 24 hours.

    Returns:
        Tuple[
            success,
            message,
            new_total_points,
        ]
    """
    if from_user_id == to_user_id:
        return False, "You cannot give reputation to yourself!", 0

    supabase = get_supabase()

    if not supabase:
        return (
            False,
            "Database persistence is not configured on this bot.",
            0,
        )

    reason = reason.strip() or "Helping a fellow developer"

    try:
        # ---------------------------------------------------------------------
        # Check cooldown
        # ---------------------------------------------------------------------

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
            last_time = _parse_timestamp(
                recent_logs.data[0].get("created_at")
            )

            if last_time:
                is_on_cooldown, hours, minutes = check_thank_cooldown(
                    last_time
                )

                if is_on_cooldown:
                    if hours > 0:
                        wait_str = (
                            f"{hours} hour(s) and "
                            f"{minutes} minute(s)"
                        )
                    else:
                        wait_str = f"{max(1, minutes)} minute(s)"

                    return (
                        False,
                        (
                            "You can only thank this user once per day. "
                            f"Please wait {wait_str}."
                        ),
                        0,
                    )

        # ---------------------------------------------------------------------
        # Fetch current points
        # ---------------------------------------------------------------------

        current_res = await (
            supabase.table("reputation")
            .select("points")
            .eq("user_id", to_user_id)
            .eq("guild_id", guild_id)
            .limit(1)
            .execute()
        )

        current_points = (
            int(current_res.data[0].get("points", 0))
            if current_res.data
            else 0
        )

        new_points = current_points + 1
        now_iso = _utc_now_iso()

        # ---------------------------------------------------------------------
        # Update reputation
        # ---------------------------------------------------------------------

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

        # ---------------------------------------------------------------------
        # Write audit log
        # ---------------------------------------------------------------------

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

    except Exception as exc:
        return (
            False,
            f"Failed to update reputation: {exc}",
            0,
        )

    return (
        True,
        f"Reputation awarded! {reason}",
        new_points,
    )


async def get_top_reputation(
    guild_id: int,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Get the top contributors in a guild by Dev Karma."""
    supabase = get_supabase()

    if not supabase:
        return []

    limit = max(1, min(limit, 100))

    try:
        res = await (
            supabase.table("reputation")
            .select("user_id, points, last_thanked_at")
            .eq("guild_id", guild_id)
            .order("points", desc=True)
            .limit(limit)
            .execute()
        )
    except Exception:
        return []

    return res.data or []


async def adjust_reputation_points(
    user_id: int,
    guild_id: int,
    delta: int,
) -> int:
    """
    Adjust a user's Dev Karma.

    Positive delta:
        Adds karma.

    Negative delta:
        Removes karma.

    Karma is always clamped to a minimum of 0.

    Returns:
        New karma balance.
    """
    supabase = get_supabase()

    if not supabase:
        return 0

    try:
        res = await (
            supabase.table("reputation")
            .select("points")
            .eq("user_id", user_id)
            .eq("guild_id", guild_id)
            .limit(1)
            .execute()
        )

        current = (
            int(res.data[0].get("points", 0))
            if res.data
            else 0
        )

        new_total = max(0, current + delta)
        now_iso = _utc_now_iso()

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

    except Exception:
        return 0


async def remove_reputation_points(
    admin_user_id: int,
    user_id: int,
    guild_id: int,
    amount: int,
    reason: str,
) -> Tuple[bool, str, int, int]:
    """
    Remove Dev Karma from a user.

    This is intended for administrator/moderator actions.

    The balance can never become negative.

    Returns:
        Tuple[
            success,
            message,
            old_balance,
            new_balance,
        ]
    """
    if amount <= 0:
        return (
            False,
            "The amount must be greater than 0.",
            0,
            0,
        )

    reason = reason.strip()

    if not reason:
        return (
            False,
            "A reason is required.",
            0,
            0,
        )

    if len(reason) > 500:
        return (
            False,
            "The reason must be 500 characters or fewer.",
            0,
            0,
        )

    if admin_user_id <= 0:
        return (
            False,
            "Invalid administrator ID.",
            0,
            0,
        )

    if user_id <= 0:
        return (
            False,
            "Invalid target user ID.",
            0,
            0,
        )

    if guild_id <= 0:
        return (
            False,
            "Invalid guild ID.",
            0,
            0,
        )

    supabase = get_supabase()

    if not supabase:
        return (
            False,
            "Database persistence is not configured.",
            0,
            0,
        )

    try:
        # ---------------------------------------------------------------------
        # Get current balance
        # ---------------------------------------------------------------------

        current_res = await (
            supabase.table("reputation")
            .select("points")
            .eq("user_id", user_id)
            .eq("guild_id", guild_id)
            .limit(1)
            .execute()
        )

        old_balance = (
            int(current_res.data[0].get("points", 0))
            if current_res.data
            else 0
        )

        # Never allow karma to go below zero.
        new_balance = max(0, old_balance - amount)
        actually_removed = old_balance - new_balance

        now_iso = _utc_now_iso()

        # ---------------------------------------------------------------------
        # Update balance
        # ---------------------------------------------------------------------

        await (
            supabase.table("reputation")
            .upsert(
                {
                    "user_id": user_id,
                    "guild_id": guild_id,
                    "points": new_balance,
                    "updated_at": now_iso,
                },
                on_conflict="user_id,guild_id",
            )
            .execute()
        )

        # ---------------------------------------------------------------------
        # Audit log
        #
        # from_user_id = administrator/moderator
        # to_user_id   = member whose karma was removed
        # ---------------------------------------------------------------------

        await (
            supabase.table("reputation_logs")
            .insert(
                {
                    "from_user_id": admin_user_id,
                    "to_user_id": user_id,
                    "guild_id": guild_id,
                    "reason": (
                        f"[KARMA REMOVAL] "
                        f"Removed {actually_removed} point(s): {reason}"
                    ),
                    "created_at": now_iso,
                }
            )
            .execute()
        )

        return (
            True,
            f"Removed {actually_removed} Dev Karma.",
            old_balance,
            new_balance,
        )

    except Exception as exc:
        return (
            False,
            f"Failed to remove Dev Karma: {exc}",
            0,
            0,
        )


async def reset_guild_reputation(
    guild_id: int,
    admin_user_id: Optional[int] = None,
    reason: str = "Administrator reset",
) -> Tuple[bool, int]:
    """
    Reset all Dev Karma for one guild.

    Reputation rows are deleted so that the leaderboard becomes empty.

    Historical reputation_logs are intentionally preserved.

    Returns:
        Tuple[
            success,
            number_of_accounts_reset,
        ]
    """
    if guild_id <= 0:
        return False, 0

    supabase = get_supabase()

    if not supabase:
        return False, 0

    try:
        # ---------------------------------------------------------------------
        # Find how many reputation accounts currently exist.
        # ---------------------------------------------------------------------

        existing = await (
            supabase.table("reputation")
            .select("user_id")
            .eq("guild_id", guild_id)
            .execute()
        )

        affected_count = len(existing.data or [])

        # ---------------------------------------------------------------------
        # Delete current reputation balances.
        #
        # We DO NOT delete reputation_logs because those are useful
        # historical/audit records.
        # ---------------------------------------------------------------------

        await (
            supabase.table("reputation")
            .delete()
            .eq("guild_id", guild_id)
            .execute()
        )

        # ---------------------------------------------------------------------
        # Write an audit entry if an administrator triggered the reset.
        #
        # Since reputation_logs requires a target user, user ID 0 is used
        # for a system-wide guild action.
        # ---------------------------------------------------------------------

        if admin_user_id is not None and admin_user_id > 0:
            await (
                supabase.table("reputation_logs")
                .insert(
                    {
                        "from_user_id": admin_user_id,
                        "to_user_id": 0,
                        "guild_id": guild_id,
                        "reason": (
                            f"[KARMA RESET] "
                            f"Reset {affected_count} account(s). "
                            f"Reason: {reason}"
                        ),
                        "created_at": _utc_now_iso(),
                    }
                )
                .execute()
            )

        return True, affected_count

    except Exception:
        return False, 0


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

    try:
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
    except Exception:
        return None

    return res.data[0] if res.data else None


async def vote_showcase(
    showcase_id: int,
    user_id: int,
) -> Tuple[bool, str, int]:
    """
    Toggle a user's vote on a project showcase.

    Returns:
        Tuple[
            success,
            message,
            current_upvote_count,
        ]
    """
    supabase = get_supabase()

    if not supabase:
        return False, "Database persistence is not configured.", 0

    try:
        # Fetch showcase
        sc_res = (
            await supabase.table("showcases")
            .select("*")
            .eq("id", showcase_id)
            .limit(1)
            .execute()
        )

        if not sc_res.data:
            return False, "Showcase not found.", 0

        showcase = sc_res.data[0]

        if int(showcase["author_id"]) == user_id:
            return (
                False,
                "You cannot upvote your own project showcase!",
                int(showcase.get("upvotes", 0)),
            )

        # Check existing vote
        vote_check = await (
            supabase.table("showcase_votes")
            .select("user_id")
            .eq("showcase_id", showcase_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )

        current_upvotes = int(showcase.get("upvotes", 0))

        # ---------------------------------------------------------------------
        # Remove existing vote
        # ---------------------------------------------------------------------

        if vote_check.data:
            await (
                supabase.table("showcase_votes")
                .delete()
                .eq("showcase_id", showcase_id)
                .eq("user_id", user_id)
                .execute()
            )

            new_upvotes = max(0, current_upvotes - 1)

            await (
                supabase.table("showcases")
                .update({"upvotes": new_upvotes})
                .eq("id", showcase_id)
                .execute()
            )

            return (
                True,
                "Removed your upvote from this project.",
                new_upvotes,
            )

        # ---------------------------------------------------------------------
        # Add vote
        # ---------------------------------------------------------------------

        await (
            supabase.table("showcase_votes")
            .insert(
                {
                    "showcase_id": showcase_id,
                    "user_id": user_id,
                }
            )
            .execute()
        )

        new_upvotes = current_upvotes + 1

        await (
            supabase.table("showcases")
            .update({"upvotes": new_upvotes})
            .eq("id", showcase_id)
            .execute()
        )

        return (
            True,
            "Upvoted project showcase!",
            new_upvotes,
        )

    except Exception as exc:
        return (
            False,
            f"Failed to update showcase vote: {exc}",
            0,
        )


async def update_showcase_message(
    showcase_id: int,
    message_id: int,
    channel_id: int,
) -> None:
    """Associate a showcase record with its Discord message ID."""
    supabase = get_supabase()

    if not supabase:
        return

    try:
        await (
            supabase.table("showcases")
            .update(
                {
                    "message_id": message_id,
                    "channel_id": channel_id,
                }
            )
            .eq("id", showcase_id)
            .execute()
        )
    except Exception:
        return


async def get_showcase_by_message(
    message_id: int,
) -> Optional[Dict[str, Any]]:
    """Retrieve a showcase by its Discord message ID."""
    supabase = get_supabase()

    if not supabase:
        return None

    try:
        res = await (
            supabase.table("showcases")
            .select("*")
            .eq("message_id", message_id)
            .limit(1)
            .execute()
        )
    except Exception:
        return None

    return res.data[0] if res.data else None


async def get_showcase_by_id(
    showcase_id: int,
) -> Optional[Dict[str, Any]]:
    """Retrieve a showcase by its database ID."""
    supabase = get_supabase()

    if not supabase:
        return None

    try:
        res = await (
            supabase.table("showcases")
            .select("*")
            .eq("id", showcase_id)
            .limit(1)
            .execute()
        )
    except Exception:
        return None

    return res.data[0] if res.data else None


async def get_recent_showcases(
    guild_id: int,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """Fetch recent showcases submitted to a guild."""
    supabase = get_supabase()

    if not supabase:
        return []

    limit = max(1, min(limit, 100))

    try:
        res = await (
            supabase.table("showcases")
            .select("*")
            .eq("guild_id", guild_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
    except Exception:
        return []

    return res.data or []


async def get_user_showcases(
    author_id: int,
    guild_id: int,
) -> List[Dict[str, Any]]:
    """Fetch all showcases submitted by a specific user."""
    supabase = get_supabase()

    if not supabase:
        return []

    try:
        res = await (
            supabase.table("showcases")
            .select("*")
            .eq("author_id", author_id)
            .eq("guild_id", guild_id)
            .order("created_at", desc=True)
            .execute()
        )
    except Exception:
        return []

    return res.data or []


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

    if easy_points < 0 or medium_points < 0 or hard_points < 0:
        return None

    if deadline and deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)

    deadline_iso = deadline.isoformat() if deadline else None

    try:
        res = await (
            supabase.table("challenges")
            .insert(
                {
                    "guild_id": guild_id,
                    "channel_id": channel_id,
                    "author_id": author_id,
                    "day_number": day_number,
                    "title": title.strip(),
                    "description": description.strip(),
                    "rules": rules.strip() if rules else None,
                    "easy_points": easy_points,
                    "medium_points": medium_points,
                    "hard_points": hard_points,
                    "deadline": deadline_iso,
                    "is_active": True,
                }
            )
            .execute()
        )
    except Exception:
        return None

    if res.data:
        return int(res.data[0]["id"])

    return None


async def update_challenge_message(
    challenge_id: int,
    message_id: int,
    thread_id: Optional[int] = None,
) -> None:
    """Attach message ID and optional thread ID to a challenge."""
    supabase = get_supabase()

    if not supabase:
        return

    data: Dict[str, Any] = {
        "message_id": message_id,
    }

    if thread_id:
        data["thread_id"] = thread_id

    try:
        await (
            supabase.table("challenges")
            .update(data)
            .eq("id", challenge_id)
            .execute()
        )
    except Exception:
        return


async def get_challenge(
    challenge_id: int,
) -> Optional[Dict[str, Any]]:
    """Retrieve a challenge by its ID."""
    supabase = get_supabase()

    if not supabase:
        return None

    try:
        res = await (
            supabase.table("challenges")
            .select("*")
            .eq("id", challenge_id)
            .limit(1)
            .execute()
        )
    except Exception:
        return None

    return res.data[0] if res.data else None


async def get_challenge_by_message(
    message_id: int,
) -> Optional[Dict[str, Any]]:
    """Retrieve a challenge by its Discord message ID."""
    supabase = get_supabase()

    if not supabase:
        return None

    try:
        res = await (
            supabase.table("challenges")
            .select("*")
            .eq("message_id", message_id)
            .limit(1)
            .execute()
        )
    except Exception:
        return None

    return res.data[0] if res.data else None


async def list_challenges(
    guild_id: int,
    active_only: bool = False,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """List challenges in a guild."""
    supabase = get_supabase()

    if not supabase:
        return []

    limit = max(1, min(limit, 100))

    try:
        query = (
            supabase.table("challenges")
            .select("*")
            .eq("guild_id", guild_id)
        )

        if active_only:
            query = query.eq("is_active", True)

        res = await (
            query
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
    except Exception:
        return []

    return res.data or []


async def close_challenge(challenge_id: int) -> bool:
    """Close an active challenge."""
    supabase = get_supabase()

    if not supabase:
        return False

    try:
        res = await (
            supabase.table("challenges")
            .update({"is_active": False})
            .eq("id", challenge_id)
            .execute()
        )
    except Exception:
        return False

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

    difficulty_tier = difficulty_tier.strip().title()

    if difficulty_tier not in {"Easy", "Medium", "Hard"}:
        return (
            False,
            "Difficulty must be Easy, Medium, or Hard.",
        )

    try:
        challenge = await get_challenge(challenge_id)

        if not challenge:
            return False, "Challenge not found."

        if not challenge.get("is_active", True):
            return (
                False,
                "This challenge has ended and is no longer accepting submissions.",
            )

        if not github_url.strip():
            return False, "GitHub URL is required."

        res = await (
            supabase.table("challenge_submissions")
            .upsert(
                {
                    "challenge_id": challenge_id,
                    "guild_id": guild_id,
                    "user_id": user_id,
                    "github_url": github_url.strip(),
                    "demo_url": demo_url.strip() if demo_url else None,
                    "difficulty_tier": difficulty_tier,
                    "notes": notes.strip() if notes else None,
                    "status": "SUBMITTED",
                },
                on_conflict="challenge_id,user_id",
            )
            .execute()
        )

    except Exception as exc:
        return (
            False,
            f"Failed to save submission: {exc}",
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
    """Award Dev Karma for an accepted challenge submission."""
    if points <= 0:
        return False, "Award points must be greater than 0."

    supabase = get_supabase()

    if not supabase:
        return False, "Database is not configured."

    try:
        new_total = await adjust_reputation_points(
            user_id=user_id,
            guild_id=guild_id,
            delta=points,
        )

        now_iso = _utc_now_iso()

        # Log the reward.
        await (
            supabase.table("reputation_logs")
            .insert(
                {
                    "from_user_id": 0,
                    "to_user_id": user_id,
                    "guild_id": guild_id,
                    "reason": (
                        f"Challenge #{challenge_id}: {reason}"
                    ),
                    "created_at": now_iso,
                }
            )
            .execute()
        )

        # Mark submission as accepted.
        await (
            supabase.table("challenge_submissions")
            .update(
                {
                    "awarded_points": points,
                    "status": "ACCEPTED",
                }
            )
            .eq("challenge_id", challenge_id)
            .eq("user_id", user_id)
            .execute()
        )

    except Exception as exc:
        return (
            False,
            f"Failed to award challenge points: {exc}",
        )

    return (
        True,
        (
            f"Awarded {points} Dev Karma points! "
            f"New balance: {new_total}"
        ),
    )


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
    """Create a Dev Karma bounty, escrowing karma from its creator."""
    if reward_karma <= 0:
        return (
            False,
            "Bounty reward must be at least 1 karma point.",
            None,
        )

    supabase = get_supabase()

    if not supabase:
        return False, "Database is not configured.", None

    try:
        # Check creator's karma.
        current_karma = await get_reputation(
            user_id=creator_id,
            guild_id=guild_id,
        )

        if current_karma < reward_karma:
            return (
                False,
                (
                    "Insufficient Dev Karma! "
                    f"You have {current_karma} point(s), "
                    f"but this bounty requires {reward_karma}."
                ),
                None,
            )

        # Escrow karma.
        new_balance = await adjust_reputation_points(
            user_id=creator_id,
            guild_id=guild_id,
            delta=-reward_karma,
        )

        # Make sure the escrow actually happened.
        if new_balance != current_karma - reward_karma:
            return (
                False,
                "Failed to escrow the bounty reward.",
                None,
            )

        # Create bounty.
        res = await (
            supabase.table("bounties")
            .insert(
                {
                    "guild_id": guild_id,
                    "channel_id": channel_id,
                    "creator_id": creator_id,
                    "title": title.strip(),
                    "description": description.strip(),
                    "reward_karma": reward_karma,
                    "status": "OPEN",
                }
            )
            .execute()
        )

        if res.data:
            bounty_id = int(res.data[0]["id"])
            return (
                True,
                "Bounty created successfully with reward escrowed.",
                bounty_id,
            )

        # Refund if insertion returned no data.
        await adjust_reputation_points(
            user_id=creator_id,
            guild_id=guild_id,
            delta=reward_karma,
        )

        return (
            False,
            "Failed to create bounty in database.",
            None,
        )

    except Exception as exc:
        # Best-effort refund if something failed after escrow.
        try:
            await adjust_reputation_points(
                user_id=creator_id,
                guild_id=guild_id,
                delta=reward_karma,
            )
        except Exception:
            pass

        return (
            False,
            f"Failed to create bounty: {exc}",
            None,
        )


async def update_bounty_message(
    bounty_id: int,
    message_id: int,
    thread_id: Optional[int] = None,
) -> None:
    """Attach message ID and optional thread ID to a bounty."""
    supabase = get_supabase()

    if not supabase:
        return

    data: Dict[str, Any] = {
        "message_id": message_id,
    }

    if thread_id:
        data["thread_id"] = thread_id

    try:
        await (
            supabase.table("bounties")
            .update(data)
            .eq("id", bounty_id)
            .execute()
        )
    except Exception:
        return


async def get_bounty(
    bounty_id: int,
) -> Optional[Dict[str, Any]]:
    """Retrieve a bounty by ID."""
    supabase = get_supabase()

    if not supabase:
        return None

    try:
        res = await (
            supabase.table("bounties")
            .select("*")
            .eq("id", bounty_id)
            .limit(1)
            .execute()
        )
    except Exception:
        return None

    return res.data[0] if res.data else None


async def list_open_bounties(
    guild_id: int,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """List open bounties in a guild."""
    supabase = get_supabase()

    if not supabase:
        return []

    limit = max(1, min(limit, 100))

    try:
        res = await (
            supabase.table("bounties")
            .select("*")
            .eq("guild_id", guild_id)
            .eq("status", "OPEN")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
    except Exception:
        return []

    return res.data or []


async def accept_bounty(
    bounty_id: int,
    solver_id: int,
    caller_id: int,
    is_admin: bool = False,
) -> Tuple[bool, str]:
    """Transfer escrowed karma to the solver and resolve the bounty."""
    supabase = get_supabase()

    if not supabase:
        return False, "Database is not configured."

    try:
        bounty = await get_bounty(bounty_id)

        if not bounty:
            return False, f"Bounty #{bounty_id} was not found."

        if bounty.get("status") != "OPEN":
            return (
                False,
                (
                    f"Bounty #{bounty_id} is already "
                    f"{bounty.get('status')}."
                ),
            )

        creator_id = int(bounty["creator_id"])

        if caller_id != creator_id and not is_admin:
            return (
                False,
                (
                    "Only the bounty creator or an administrator "
                    "can accept a solution."
                ),
            )

        if solver_id == creator_id:
            return (
                False,
                "Creators cannot claim their own bounty reward!",
            )

        reward = int(bounty["reward_karma"])
        guild_id = int(bounty["guild_id"])
        now_iso = _utc_now_iso()

        # Award escrowed karma.
        await adjust_reputation_points(
            user_id=solver_id,
            guild_id=guild_id,
            delta=reward,
        )

        # Log transfer.
        await (
            supabase.table("reputation_logs")
            .insert(
                {
                    "from_user_id": creator_id,
                    "to_user_id": solver_id,
                    "guild_id": guild_id,
                    "reason": (
                        f"Bounty #{bounty_id}: "
                        f"{bounty.get('title', 'Help awarded')}"
                    ),
                    "created_at": now_iso,
                }
            )
            .execute()
        )

        # Resolve bounty.
        await (
            supabase.table("bounties")
            .update(
                {
                    "status": "RESOLVED",
                    "solver_id": solver_id,
                    "resolved_at": now_iso,
                }
            )
            .eq("id", bounty_id)
            .execute()
        )

    except Exception as exc:
        return (
            False,
            f"Failed to resolve bounty: {exc}",
        )

    return (
        True,
        (
            f"Bounty #{bounty_id} resolved! "
            f"{reward} Dev Karma awarded to solver."
        ),
    )


async def cancel_bounty(
    bounty_id: int,
    caller_id: int,
    is_admin: bool = False,
) -> Tuple[bool, str]:
    """Cancel an open bounty and refund its escrowed karma."""
    supabase = get_supabase()

    if not supabase:
        return False, "Database is not configured."

    try:
        bounty = await get_bounty(bounty_id)

        if not bounty:
            return False, f"Bounty #{bounty_id} was not found."

        if bounty.get("status") != "OPEN":
            return (
                False,
                (
                    f"Bounty #{bounty_id} cannot be cancelled "
                    f"because it is {bounty.get('status')}."
                ),
            )

        creator_id = int(bounty["creator_id"])

        if caller_id != creator_id and not is_admin:
            return (
                False,
                (
                    "Only the bounty creator or an administrator "
                    "can cancel this bounty."
                ),
            )

        reward = int(bounty["reward_karma"])
        guild_id = int(bounty["guild_id"])
        now_iso = _utc_now_iso()

        # Refund karma.
        await adjust_reputation_points(
            user_id=creator_id,
            guild_id=guild_id,
            delta=reward,
        )

        # Mark cancelled.
        await (
            supabase.table("bounties")
            .update(
                {
                    "status": "CANCELLED",
                    "resolved_at": now_iso,
                }
            )
            .eq("id", bounty_id)
            .execute()
        )

    except Exception as exc:
        return (
            False,
            f"Failed to cancel bounty: {exc}",
        )

    return (
        True,
        (
            f"Bounty #{bounty_id} has been cancelled. "
            f"{reward} Dev Karma refunded."
        ),
    )