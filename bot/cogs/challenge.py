from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlparse

import discord
from discord.ext import commands

from bot.database.queries import (
    award_challenge_points,
    close_challenge,
    create_challenge,
    get_challenge,
    get_challenge_by_message,
    list_challenges,
    submit_challenge_entry,
    update_challenge_message,
)
from bot.utils.checks import is_admin_or_owner


# =============================================================================
# CONFIGURATION
# =============================================================================

MIN_DURATION_DAYS = 1
MAX_DURATION_DAYS = 30

MIN_POINTS = 0
MAX_POINTS = 1000

MAX_TITLE_LENGTH = 100
MAX_DESCRIPTION_LENGTH = 4000
MAX_RULES_LENGTH = 2000
MAX_NOTES_LENGTH = 1000
MAX_URL_LENGTH = 500

MAX_CHALLENGES_TO_LIST = 10

VALID_DIFFICULTIES = {
    "easy": "Easy",
    "medium": "Medium",
    "hard": "Hard",
}


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def utc_now() -> datetime:
    """Return the current UTC time."""
    return datetime.now(timezone.utc)


def clean_text(value: Optional[str]) -> str:
    """Clean normal single-line user input."""
    if not value:
        return ""

    return " ".join(value.strip().split())


def clean_multiline_text(value: Optional[str]) -> str:
    """Clean multiline user input while preserving line breaks."""
    if not value:
        return ""

    lines = []

    for line in value.strip().splitlines():
        line = line.strip()

        if line:
            lines.append(line)

    return "\n".join(lines)


def truncate_text(value: str, limit: int) -> str:
    """Safely truncate text for Discord."""
    if len(value) <= limit:
        return value

    if limit <= 3:
        return value[:limit]

    return value[: limit - 3].rstrip() + "..."


def parse_datetime(value: object) -> Optional[datetime]:
    """Convert a database timestamp into a timezone-aware datetime."""

    if isinstance(value, datetime):
        dt = value

    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )
        except ValueError:
            return None

    else:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)


def normalize_difficulty(value: str) -> Optional[str]:
    """Normalize difficulty input."""

    if not value:
        return None

    return VALID_DIFFICULTIES.get(
        value.strip().lower()
    )


def is_valid_url(value: str) -> bool:
    """Check whether a string is a valid HTTP/HTTPS URL."""

    if not value:
        return False

    if len(value) > MAX_URL_LENGTH:
        return False

    try:
        parsed = urlparse(value)
    except ValueError:
        return False

    return (
        parsed.scheme.lower() in {"http", "https"}
        and bool(parsed.netloc)
    )


def is_valid_github_url(value: str) -> bool:
    """Check whether a URL points to GitHub."""

    if not is_valid_url(value):
        return False

    try:
        hostname = urlparse(value).hostname
    except ValueError:
        return False

    if not hostname:
        return False

    hostname = hostname.lower()

    return (
        hostname == "github.com"
        or hostname.endswith(".github.com")
    )


async def send_ephemeral_or_normal(
    ctx: commands.Context,
    message: str,
) -> None:
    """
    Send an ephemeral response for slash commands.

    Prefix commands cannot use ephemeral messages, so they receive
    a normal message instead.
    """

    if ctx.interaction is not None:
        await ctx.send(
            message,
            ephemeral=True,
        )
    else:
        await ctx.send(message)


# =============================================================================
# CHALLENGE SUBMISSION MODAL
# =============================================================================

class ChallengeSubmissionModal(discord.ui.Modal):
    """Modal used by members to submit challenge solutions."""

    def __init__(
        self,
        challenge_id: int,
        challenge_title: str,
        thread_id: Optional[int] = None,
    ) -> None:

        title = clean_text(challenge_title)

        if not title:
            title = "Developer Challenge"

        title = truncate_text(title, 35)

        super().__init__(
            title=f"Submit: {title}"
        )

        self.challenge_id = challenge_id
        self.thread_id = thread_id

        # ---------------------------------------------------------------------
        # GitHub URL
        # ---------------------------------------------------------------------

        self.github_url_input = discord.ui.TextInput(
            label="GitHub Repository",
            placeholder="https://github.com/username/project",
            required=True,
            max_length=MAX_URL_LENGTH,
        )

        self.add_item(
            self.github_url_input
        )

        # ---------------------------------------------------------------------
        # Demo URL
        # ---------------------------------------------------------------------

        self.demo_url_input = discord.ui.TextInput(
            label="Live Demo URL",
            placeholder="https://your-project.example",
            required=False,
            max_length=MAX_URL_LENGTH,
        )

        self.add_item(
            self.demo_url_input
        )

        # ---------------------------------------------------------------------
        # Difficulty
        # ---------------------------------------------------------------------

        self.difficulty_input = discord.ui.TextInput(
            label="Difficulty",
            placeholder="Easy, Medium, or Hard",
            default="Medium",
            required=True,
            max_length=20,
        )

        self.add_item(
            self.difficulty_input
        )

        # ---------------------------------------------------------------------
        # Notes
        # ---------------------------------------------------------------------

        self.notes_input = discord.ui.TextInput(
            label="Implementation Notes",
            style=discord.TextStyle.paragraph,
            placeholder=(
                "Explain what you built, important decisions, "
                "or features you added."
            ),
            required=False,
            max_length=MAX_NOTES_LENGTH,
        )

        self.add_item(
            self.notes_input
        )

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """Process a challenge submission."""

        if interaction.guild is None:
            await interaction.response.send_message(
                "This can only be used inside a server.",
                ephemeral=True,
            )
            return

        # ---------------------------------------------------------------------
        # Read input
        # ---------------------------------------------------------------------

        github_url = (
            self.github_url_input.value.strip()
        )

        demo_url = (
            self.demo_url_input.value.strip()
            or None
        )

        difficulty = normalize_difficulty(
            self.difficulty_input.value
        )

        notes = clean_multiline_text(
            self.notes_input.value
        )

        if not notes:
            notes = "No implementation notes provided."

        # ---------------------------------------------------------------------
        # Validate GitHub URL
        # ---------------------------------------------------------------------

        if not is_valid_github_url(github_url):
            await interaction.response.send_message(
                "Please provide a valid GitHub repository URL.\n\n"
                "Example:\n"
                "`https://github.com/username/project`",
                ephemeral=True,
            )
            return

        # ---------------------------------------------------------------------
        # Validate demo URL
        # ---------------------------------------------------------------------

        if demo_url and not is_valid_url(demo_url):
            await interaction.response.send_message(
                "The live demo URL is invalid.\n"
                "Use a URL beginning with `https://`.",
                ephemeral=True,
            )
            return

        # ---------------------------------------------------------------------
        # Validate difficulty
        # ---------------------------------------------------------------------

        if difficulty is None:
            await interaction.response.send_message(
                "Difficulty must be one of:\n"
                "`Easy`, `Medium`, or `Hard`.",
                ephemeral=True,
            )
            return

        # ---------------------------------------------------------------------
        # Fetch challenge
        # ---------------------------------------------------------------------

        try:
            challenge = await get_challenge(
                self.challenge_id
            )
        except Exception:
            challenge = None

        if not challenge:
            await interaction.response.send_message(
                "This challenge could not be found.",
                ephemeral=True,
            )
            return

        # ---------------------------------------------------------------------
        # Verify guild
        # ---------------------------------------------------------------------

        challenge_guild_id = challenge.get(
            "guild_id"
        )

        if challenge_guild_id is not None:

            try:
                challenge_guild_id = int(
                    challenge_guild_id
                )
            except (TypeError, ValueError):
                await interaction.response.send_message(
                    "This challenge has an invalid database record.",
                    ephemeral=True,
                )
                return

            if challenge_guild_id != interaction.guild.id:
                await interaction.response.send_message(
                    "This challenge belongs to another server.",
                    ephemeral=True,
                )
                return

        # ---------------------------------------------------------------------
        # Check active status
        # ---------------------------------------------------------------------

        if not challenge.get(
            "is_active",
            True,
        ):
            await interaction.response.send_message(
                "This challenge has already ended.",
                ephemeral=True,
            )
            return

        # ---------------------------------------------------------------------
        # Check deadline
        # ---------------------------------------------------------------------

        deadline = parse_datetime(
            challenge.get("deadline")
        )

        if deadline and utc_now() >= deadline:
            await interaction.response.send_message(
                "The submission deadline has passed.",
                ephemeral=True,
            )
            return

        # ---------------------------------------------------------------------
        # Save submission
        # ---------------------------------------------------------------------

        try:
            success, message = await submit_challenge_entry(
                challenge_id=self.challenge_id,
                guild_id=interaction.guild.id,
                user_id=interaction.user.id,
                github_url=github_url,
                demo_url=demo_url,
                difficulty_tier=difficulty,
                notes=notes,
            )

        except Exception:
            await interaction.response.send_message(
                "Something went wrong while saving your submission.",
                ephemeral=True,
            )
            return

        if not success:
            await interaction.response.send_message(
                f"{message}",
                ephemeral=True,
            )
            return

        # ---------------------------------------------------------------------
        # Confirm submission
        # ---------------------------------------------------------------------

        await interaction.response.send_message(
            (
                f"Your solution for **Challenge "
                f"#{self.challenge_id}** has been submitted.\n\n"
                f"**Difficulty:** {difficulty}\n"
                "**Status:** Awaiting review"
            ),
            ephemeral=True,
        )

        # ---------------------------------------------------------------------
        # Find discussion thread
        # ---------------------------------------------------------------------

        thread: Optional[discord.Thread] = None

        if self.thread_id:

            thread = interaction.guild.get_thread(
                self.thread_id
            )

        if (
            thread is None
            and isinstance(
                interaction.channel,
                discord.TextChannel,
            )
            and self.thread_id
        ):

            try:
                for active_thread in interaction.channel.threads:

                    if active_thread.id == self.thread_id:
                        thread = active_thread
                        break

            except (discord.HTTPException, discord.Forbidden):
                thread = None

        target_channel = (
            thread
            or interaction.channel
        )

        if target_channel is None:
            return

        # ---------------------------------------------------------------------
        # Submission announcement
        # ---------------------------------------------------------------------

        embed = discord.Embed(
            title="New Challenge Submission",
            description=(
                f"**Developer:** "
                f"{interaction.user.mention}\n"
                f"**Difficulty:** `{difficulty}`\n"
                "**Status:** `Awaiting Review`"
            ),
            color=discord.Color.green(),
            timestamp=utc_now(),
        )

        embed.add_field(
            name="GitHub",
            value=(
                f"[View Repository]"
                f"({github_url})"
            ),
            inline=True,
        )

        if demo_url:
            embed.add_field(
                name="Live Demo",
                value=(
                    f"[Open Demo]"
                    f"({demo_url})"
                ),
                inline=True,
            )

        embed.add_field(
            name="Implementation Notes",
            value=truncate_text(
                notes,
                1024,
            ),
            inline=False,
        )

        embed.set_footer(
            text=(
                f"Challenge #{self.challenge_id} "
                "• Awaiting admin review"
            )
        )

        try:
            await target_channel.send(
                embed=embed
            )
        except (
            discord.Forbidden,
            discord.HTTPException,
        ):
            # The database submission succeeded, so we do not tell the
            # user their submission failed just because the announcement
            # could not be posted.
            pass


# =============================================================================
# PERSISTENT CHALLENGE VIEW
# =============================================================================

class ChallengeView(discord.ui.View):
    """
    Persistent view attached to challenge announcements.

    timeout=None allows the button to remain active across restarts when
    the view is registered with the bot.
    """

    def __init__(self) -> None:
        super().__init__(
            timeout=None
        )

    @discord.ui.button(
        label="Submit Solution",
        style=discord.ButtonStyle.success,
        emoji="🚀",
        custom_id="challenge:submit",
    )
    async def submit_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        """Open the challenge submission modal."""

        if (
            interaction.guild is None
            or interaction.message is None
        ):
            await interaction.response.send_message(
                "This button can only be used inside a server.",
                ephemeral=True,
            )
            return

        # ---------------------------------------------------------------------
        # Get challenge
        # ---------------------------------------------------------------------

        try:
            challenge = await get_challenge_by_message(
                interaction.message.id
            )
        except Exception:
            await interaction.response.send_message(
                "I couldn't load this challenge right now.",
                ephemeral=True,
            )
            return

        if not challenge:
            await interaction.response.send_message(
                "This challenge record no longer exists.",
                ephemeral=True,
            )
            return

        # ---------------------------------------------------------------------
        # Verify guild
        # ---------------------------------------------------------------------

        challenge_guild_id = challenge.get(
            "guild_id"
        )

        if challenge_guild_id is not None:

            try:
                challenge_guild_id = int(
                    challenge_guild_id
                )
            except (TypeError, ValueError):
                await interaction.response.send_message(
                    "This challenge has an invalid database record.",
                    ephemeral=True,
                )
                return

            if challenge_guild_id != interaction.guild.id:
                await interaction.response.send_message(
                    "This challenge belongs to another server.",
                    ephemeral=True,
                )
                return

        # ---------------------------------------------------------------------
        # Check active state
        # ---------------------------------------------------------------------

        if not challenge.get(
            "is_active",
            True,
        ):
            await interaction.response.send_message(
                "This challenge has ended and is no longer accepting "
                "submissions.",
                ephemeral=True,
            )
            return

        # ---------------------------------------------------------------------
        # Check deadline
        # ---------------------------------------------------------------------

        deadline = parse_datetime(
            challenge.get("deadline")
        )

        if deadline and utc_now() >= deadline:
            await interaction.response.send_message(
                "The submission deadline has passed.",
                ephemeral=True,
            )
            return

        # ---------------------------------------------------------------------
        # Validate challenge ID
        # ---------------------------------------------------------------------

        challenge_id = challenge.get("id")

        if challenge_id is None:
            await interaction.response.send_message(
                "This challenge has an invalid database record.",
                ephemeral=True,
            )
            return

        try:
            challenge_id = int(
                challenge_id
            )
        except (TypeError, ValueError):
            await interaction.response.send_message(
                "This challenge has an invalid ID.",
                ephemeral=True,
            )
            return

        # ---------------------------------------------------------------------
        # Open modal
        # ---------------------------------------------------------------------

        modal = ChallengeSubmissionModal(
            challenge_id=challenge_id,
            challenge_title=str(
                challenge.get(
                    "title",
                    "Developer Challenge",
                )
            ),
            thread_id=challenge.get(
                "thread_id"
            ),
        )

        await interaction.response.send_modal(
            modal
        )


# =============================================================================
# CHALLENGE COG
# =============================================================================

class Challenge(
    commands.Cog,
    name="Challenge",
):
    """Developer challenge management."""

    def __init__(
        self,
        bot: commands.Bot,
    ) -> None:
        self.bot = bot

    # =========================================================================
    # /CHALLENGE
    # =========================================================================

    @commands.hybrid_group(
        name="challenge",
        description=(
            "Create, manage, and participate in developer challenges."
        ),
    )
    async def challenge_group(
        self,
        ctx: commands.Context,
    ) -> None:
        """Main challenge command group."""

        if ctx.invoked_subcommand is None:
            await self.list_cmd(ctx)

    # =========================================================================
    # /CHALLENGE POST
    # =========================================================================

    @challenge_group.command(
        name="post",
        description="Post a new developer challenge.",
    )
    @commands.guild_only()
    @is_admin_or_owner()
    async def post_challenge(
        self,
        ctx: commands.Context,
        title: str,
        description: str,
        day_number: Optional[int] = None,
        rules: Optional[str] = (
            "No AI APIs • No chatbot/shortcut libraries • "
            "Build the solution yourself."
        ),
        easy_points: int = 5,
        medium_points: int = 10,
        hard_points: int = 15,
        duration_days: int = 3,
        ping_role: Optional[discord.Role] = None,
    ) -> None:
        """Create and publish a developer challenge."""

        if ctx.guild is None:
            return

        # ---------------------------------------------------------------------
        # Clean values
        # ---------------------------------------------------------------------

        title = clean_text(title)
        description = clean_multiline_text(
            description
        )
        rules = (
            clean_multiline_text(rules)
            if rules
            else None
        )

        # ---------------------------------------------------------------------
        # Validate title
        # ---------------------------------------------------------------------

        if not title:
            await send_ephemeral_or_normal(
                ctx,
                "Challenge title cannot be empty.",
            )
            return

        if len(title) > MAX_TITLE_LENGTH:
            await send_ephemeral_or_normal(
                ctx,
                (
                    f"Challenge title must be "
                    f"{MAX_TITLE_LENGTH} characters or fewer."
                ),
            )
            return

        # ---------------------------------------------------------------------
        # Validate description
        # ---------------------------------------------------------------------

        if not description:
            await send_ephemeral_or_normal(
                ctx,
                "Challenge description cannot be empty.",
            )
            return

        if len(description) > MAX_DESCRIPTION_LENGTH:
            await send_ephemeral_or_normal(
                ctx,
                (
                    f"Challenge description must be "
                    f"{MAX_DESCRIPTION_LENGTH} characters or fewer."
                ),
            )
            return

        # ---------------------------------------------------------------------
        # Validate rules
        # ---------------------------------------------------------------------

        if rules and len(rules) > MAX_RULES_LENGTH:
            await send_ephemeral_or_normal(
                ctx,
                (
                    f"Challenge rules must be "
                    f"{MAX_RULES_LENGTH} characters or fewer."
                ),
            )
            return

        # ---------------------------------------------------------------------
        # Validate day number
        # ---------------------------------------------------------------------

        if (
            day_number is not None
            and day_number <= 0
        ):
            await send_ephemeral_or_normal(
                ctx,
                "Day number must be greater than 0.",
            )
            return

        # ---------------------------------------------------------------------
        # Validate points
        # ---------------------------------------------------------------------

        points = {
            "Easy": easy_points,
            "Medium": medium_points,
            "Hard": hard_points,
        }

        for difficulty, value in points.items():

            if (
                value < MIN_POINTS
                or value > MAX_POINTS
            ):
                await send_ephemeral_or_normal(
                    ctx,
                    (
                        f"{difficulty} points must be between "
                        f"{MIN_POINTS} and {MAX_POINTS}."
                    ),
                )
                return

        # ---------------------------------------------------------------------
        # Validate point progression
        # ---------------------------------------------------------------------

        if not (
            easy_points
            <= medium_points
            <= hard_points
        ):
            await send_ephemeral_or_normal(
                ctx,
                (
                    "Reward points must follow this order:\n"
                    "`Easy ≤ Medium ≤ Hard`."
                ),
            )
            return

        # ---------------------------------------------------------------------
        # Validate duration
        # ---------------------------------------------------------------------

        if not (
            MIN_DURATION_DAYS
            <= duration_days
            <= MAX_DURATION_DAYS
        ):
            await send_ephemeral_or_normal(
                ctx,
                (
                    f"Challenge duration must be between "
                    f"{MIN_DURATION_DAYS} and "
                    f"{MAX_DURATION_DAYS} days."
                ),
            )
            return

        # ---------------------------------------------------------------------
        # Defer slash command
        # ---------------------------------------------------------------------

        if (
            ctx.interaction is not None
            and not ctx.interaction.response.is_done()
        ):
            await ctx.interaction.response.defer(
                ephemeral=True
            )

        now = utc_now()

        deadline = (
            now
            + timedelta(days=duration_days)
        )

        deadline_unix = int(
            deadline.timestamp()
        )

        # ---------------------------------------------------------------------
        # Create database record FIRST
        # ---------------------------------------------------------------------

        try:
            challenge_id = await create_challenge(
                guild_id=ctx.guild.id,
                channel_id=ctx.channel.id,
                author_id=ctx.author.id,
                title=title,
                description=description,
                day_number=day_number,
                rules=rules,
                easy_points=easy_points,
                medium_points=medium_points,
                hard_points=hard_points,
                deadline=deadline,
            )

        except Exception:
            challenge_id = None

        if not challenge_id:

            message = (
                "I couldn't create the challenge in the database. "
                "Nothing was posted."
            )

            if ctx.interaction is not None:
                await ctx.interaction.followup.send(
                    message,
                    ephemeral=True,
                )
            else:
                await ctx.send(message)

            return

        # ---------------------------------------------------------------------
        # Build announcement
        # ---------------------------------------------------------------------

        day_prefix = (
            f"DAY {day_number} — "
            if day_number is not None
            else ""
        )

        embed = discord.Embed(
            title=f"{day_prefix}{title}",
            description=description,
            color=discord.Color.blurple(),
            timestamp=now,
        )

        # ---------------------------------------------------------------------
        # Rules
        # ---------------------------------------------------------------------

        if rules:
            embed.add_field(
                name="Rules",
                value=rules,
                inline=False,
            )

        # ---------------------------------------------------------------------
        # Rewards
        # ---------------------------------------------------------------------

        reward_text = (
            f"🟢 **Easy** — `{easy_points}` Dev Karma\n"
            f"🟡 **Medium** — `{medium_points}` Dev Karma\n"
            f"🔴 **Hard** — `{hard_points}` Dev Karma"
        )

        embed.add_field(
            name="Difficulty & Rewards",
            value=reward_text,
            inline=False,
        )

        # ---------------------------------------------------------------------
        # Deadline
        # ---------------------------------------------------------------------

        embed.add_field(
            name="Deadline",
            value=(
                f"**{duration_days} day(s)**\n"
                f"Ends <t:{deadline_unix}:R>\n"
                f"<t:{deadline_unix}:f>"
            ),
            inline=False,
        )

        # ---------------------------------------------------------------------
        # Submission instructions
        # ---------------------------------------------------------------------

        embed.add_field(
            name="How to Submit",
            value=(
                "Finish your project, then click "
                "**Submit Solution** below."
            ),
            inline=False,
        )

        # ---------------------------------------------------------------------
        # Footer
        # ---------------------------------------------------------------------

        if ctx.guild.icon:
            embed.set_footer(
                text=(
                    "Horizon Devs • Developer Challenges"
                ),
                icon_url=ctx.guild.icon.url,
            )
        else:
            embed.set_footer(
                text=(
                    "Horizon Devs • Developer Challenges"
                )
            )

        view = ChallengeView()

        content = (
            ping_role.mention
            if ping_role
            else None
        )

        # ---------------------------------------------------------------------
        # Post announcement
        # ---------------------------------------------------------------------

        try:
            message = await ctx.channel.send(
                content=content,
                embed=embed,
                view=view,
            )

        except (
            discord.Forbidden,
            discord.HTTPException,
        ):

            # Prevent orphaned active challenges.
            try:
                await close_challenge(
                    int(challenge_id)
                )
            except Exception:
                pass

            error_message = (
                "I couldn't post the challenge announcement. "
                "The challenge has been closed."
            )

            if ctx.interaction is not None:
                await ctx.interaction.followup.send(
                    error_message,
                    ephemeral=True,
                )
            else:
                await ctx.send(
                    error_message
                )

            return

        # ---------------------------------------------------------------------
        # Create discussion thread
        # ---------------------------------------------------------------------

        thread: Optional[discord.Thread] = None

        thread_name = (
            f"{day_prefix}"
            f"{truncate_text(title, 45)}"
            " • Submissions"
        )

        try:
            thread = await message.create_thread(
                name=thread_name,
                auto_archive_duration=4320,
            )

            await thread.send(
                f"**{title} — Discussion**\n\n"
                "Use this thread to discuss the challenge, "
                "share progress, ask questions, and help other "
                "developers.\n\n"
                "When you're finished, use the **Submit Solution** "
                "button on the main challenge post."
            )

        except (
            discord.Forbidden,
            discord.HTTPException,
        ):
            thread = None

        # ---------------------------------------------------------------------
        # Link Discord message/thread to database
        # ---------------------------------------------------------------------

        try:
            await update_challenge_message(
                challenge_id=int(
                    challenge_id
                ),
                message_id=message.id,
                thread_id=(
                    thread.id
                    if thread
                    else None
                ),
            )
        except Exception:
            pass

        # ---------------------------------------------------------------------
        # Success response
        # ---------------------------------------------------------------------

        success_message = (
            f"Challenge **#{challenge_id}** posted successfully."
        )

        if thread:
            success_message += (
                "\nDiscussion thread created."
            )

        if ctx.interaction is not None:
            await ctx.interaction.followup.send(
                success_message,
                ephemeral=True,
            )
        else:
            await ctx.send(
                success_message
            )

    # =========================================================================
    # /CHALLENGE AWARD
    # =========================================================================

    @challenge_group.command(
        name="award",
        description="Award Dev Karma for a completed challenge.",
    )
    @commands.guild_only()
    @is_admin_or_owner()
    async def award_points(
        self,
        ctx: commands.Context,
        challenge_id: int,
        member: discord.Member,
        points: int,
        *,
        reason: str = "Accepted challenge submission",
    ) -> None:
        """Award Dev Karma to a challenge participant."""

        if ctx.guild is None:
            return

        # ---------------------------------------------------------------------
        # Validate values
        # ---------------------------------------------------------------------

        if challenge_id <= 0:
            await send_ephemeral_or_normal(
                ctx,
                "Challenge ID must be greater than 0.",
            )
            return

        if points <= 0:
            await send_ephemeral_or_normal(
                ctx,
                "Awarded points must be greater than 0.",
            )
            return

        if points > MAX_POINTS:
            await send_ephemeral_or_normal(
                ctx,
                (
                    f"You cannot award more than "
                    f"{MAX_POINTS} points at once."
                ),
            )
            return

        reason = clean_text(reason)

        if not reason:
            reason = "Accepted challenge submission"

        # ---------------------------------------------------------------------
        # Get challenge
        # ---------------------------------------------------------------------

        try:
            challenge = await get_challenge(
                challenge_id
            )
        except Exception:
            challenge = None

        if not challenge:
            await send_ephemeral_or_normal(
                ctx,
                f"Challenge `#{challenge_id}` was not found.",
            )
            return

        # ---------------------------------------------------------------------
        # Verify guild
        # ---------------------------------------------------------------------

        challenge_guild_id = challenge.get(
            "guild_id"
        )

        if challenge_guild_id is not None:

            try:
                challenge_guild_id = int(
                    challenge_guild_id
                )
            except (TypeError, ValueError):
                await send_ephemeral_or_normal(
                    ctx,
                    "The challenge database record is invalid.",
                )
                return

            if challenge_guild_id != ctx.guild.id:
                await send_ephemeral_or_normal(
                    ctx,
                    "That challenge belongs to another server.",
                )
                return

        # ---------------------------------------------------------------------
        # Award points
        # ---------------------------------------------------------------------

        try:
            success, message = await award_challenge_points(
                challenge_id=challenge_id,
                guild_id=ctx.guild.id,
                user_id=member.id,
                points=points,
                reason=reason,
            )
        except Exception:
            success = False
            message = (
                "Something went wrong while awarding Dev Karma."
            )

        if not success:
            await send_ephemeral_or_normal(
                ctx,
                message,
            )
            return

        # ---------------------------------------------------------------------
        # Public reward message
        # ---------------------------------------------------------------------

        embed = discord.Embed(
            title="Challenge Reward",
            description=(
                f"{member.mention} received "
                f"**{points} Dev Karma** for "
                f"Challenge `#{challenge_id}`."
            ),
            color=discord.Color.gold(),
        )

        embed.add_field(
            name="Reason",
            value=truncate_text(
                reason,
                1024,
            ),
            inline=False,
        )

        embed.set_thumbnail(
            url=member.display_avatar.url
        )

        embed.set_footer(
            text=(
                f"Awarded by "
                f"{ctx.author.display_name} • "
                "Horizon Devs"
            )
        )

        await ctx.send(
            embed=embed
        )

    # =========================================================================
    # /CHALLENGE END
    # =========================================================================

    @challenge_group.command(
        name="end",
        description="Close a challenge.",
    )
    @commands.guild_only()
    @is_admin_or_owner()
    async def end_challenge(
        self,
        ctx: commands.Context,
        challenge_id: int,
    ) -> None:
        """Close an active challenge."""

        if ctx.guild is None:
            return

        if challenge_id <= 0:
            await send_ephemeral_or_normal(
                ctx,
                "Challenge ID must be greater than 0.",
            )
            return

        # ---------------------------------------------------------------------
        # Get challenge
        # ---------------------------------------------------------------------

        try:
            challenge = await get_challenge(
                challenge_id
            )
        except Exception:
            challenge = None

        if not challenge:
            await send_ephemeral_or_normal(
                ctx,
                f"Challenge `#{challenge_id}` was not found.",
            )
            return

        # ---------------------------------------------------------------------
        # Verify guild
        # ---------------------------------------------------------------------

        challenge_guild_id = challenge.get(
            "guild_id"
        )

        if challenge_guild_id is not None:

            try:
                challenge_guild_id = int(
                    challenge_guild_id
                )
            except (TypeError, ValueError):
                await send_ephemeral_or_normal(
                    ctx,
                    "The challenge database record is invalid.",
                )
                return

            if challenge_guild_id != ctx.guild.id:
                await send_ephemeral_or_normal(
                    ctx,
                    "That challenge belongs to another server.",
                )
                return

        # ---------------------------------------------------------------------
        # Check status
        # ---------------------------------------------------------------------

        if not challenge.get(
            "is_active",
            True,
        ):
            await send_ephemeral_or_normal(
                ctx,
                f"Challenge `#{challenge_id}` is already closed.",
            )
            return

        # ---------------------------------------------------------------------
        # Close
        # ---------------------------------------------------------------------

        try:
            success = await close_challenge(
                challenge_id
            )
        except Exception:
            success = False

        if not success:
            await send_ephemeral_or_normal(
                ctx,
                (
                    f"Challenge `#{challenge_id}` "
                    "could not be closed."
                ),
            )
            return

        # ---------------------------------------------------------------------
        # Response
        # ---------------------------------------------------------------------

        embed = discord.Embed(
            title="Challenge Closed",
            description=(
                f"Challenge `#{challenge_id}` has ended.\n\n"
                "New submissions are no longer accepted."
            ),
            color=discord.Color.dark_grey(),
        )

        embed.set_footer(
            text=(
                f"Closed by "
                f"{ctx.author.display_name}"
            )
        )

        await ctx.send(
            embed=embed
        )

    # =========================================================================
    # /CHALLENGE LIST
    # =========================================================================

    @challenge_group.command(
        name="list",
        description="List recent developer challenges.",
    )
    @commands.guild_only()
    async def list_cmd(
        self,
        ctx: commands.Context,
    ) -> None:
        """List recent challenges in the current server."""

        if ctx.guild is None:
            return

        try:
            challenges = await list_challenges(
                guild_id=ctx.guild.id,
                limit=MAX_CHALLENGES_TO_LIST,
            )
        except Exception:
            await send_ephemeral_or_normal(
                ctx,
                "I couldn't load the challenge list right now.",
            )
            return

        # ---------------------------------------------------------------------
        # No challenges
        # ---------------------------------------------------------------------

        if not challenges:

            embed = discord.Embed(
                title="Developer Challenges",
                description=(
                    "No challenges have been posted yet.\n"
                    "Check back soon."
                ),
                color=discord.Color.blurple(),
            )

            await ctx.send(
                embed=embed
            )

            return

        # ---------------------------------------------------------------------
        # Build list embed
        # ---------------------------------------------------------------------

        embed = discord.Embed(
            title="Horizon Devs — Developer Challenges",
            description=(
                "Build projects, submit your work, "
                "and earn Dev Karma."
            ),
            color=discord.Color.blurple(),
        )

        now = utc_now()

        for challenge in challenges:

            challenge_id = challenge.get(
                "id",
                "?",
            )

            title = clean_text(
                str(
                    challenge.get(
                        "title",
                        "Untitled Challenge",
                    )
                )
            )

            if not title:
                title = "Untitled Challenge"

            day_number = challenge.get(
                "day_number"
            )

            if day_number:
                display_title = (
                    f"Day {day_number}: {title}"
                )
            else:
                display_title = title

            display_title = truncate_text(
                display_title,
                220,
            )

            is_active = bool(
                challenge.get(
                    "is_active",
                    False,
                )
            )

            deadline = parse_datetime(
                challenge.get(
                    "deadline"
                )
            )

            # -------------------------------------------------------------
            # Status
            # -------------------------------------------------------------

            if is_active:

                if deadline and now >= deadline:
                    status = "🟠 Deadline passed"
                else:
                    status = "🟢 Active"

            else:
                status = "⚪ Closed"

            # -------------------------------------------------------------
            # Rewards
            # -------------------------------------------------------------

            easy = challenge.get(
                "easy_points",
                0,
            )

            medium = challenge.get(
                "medium_points",
                0,
            )

            hard = challenge.get(
                "hard_points",
                0,
            )

            # -------------------------------------------------------------
            # Deadline
            # -------------------------------------------------------------

            deadline_text = ""

            if deadline:

                timestamp = int(
                    deadline.timestamp()
                )

                if (
                    is_active
                    and deadline > now
                ):
                    deadline_text = (
                        f"\nEnds <t:{timestamp}:R>"
                    )
                else:
                    deadline_text = (
                        f"\nEnded <t:{timestamp}:R>"
                    )

            # -------------------------------------------------------------
            # Description
            # -------------------------------------------------------------

            description = clean_multiline_text(
                str(
                    challenge.get(
                        "description",
                        "",
                    )
                )
            )

            if not description:
                description = (
                    "No description provided."
                )

            description = truncate_text(
                description,
                180,
            )

            # -------------------------------------------------------------
            # Field
            # -------------------------------------------------------------

            embed.add_field(
                name=(
                    f"#{challenge_id} • "
                    f"{display_title}"
                ),
                value=(
                    f"{status}\n"
                    f"**Rewards:** "
                    f"{easy} / {medium} / {hard} Dev Karma"
                    f"{deadline_text}\n"
                    f"{description}"
                ),
                inline=False,
            )

        # ---------------------------------------------------------------------
        # Footer
        # ---------------------------------------------------------------------

        embed.set_footer(
            text=(
                "Horizon Devs • "
                "Use /challenge post to create a challenge"
            )
        )

        await ctx.send(
            embed=embed
        )


# =============================================================================
# COG SETUP
# =============================================================================

async def setup(
    bot: commands.Bot,
) -> None:
    """Load the Challenge cog."""

    await bot.add_cog(
        Challenge(bot)
    )