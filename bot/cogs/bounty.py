
"""
Horizon Devs - Bounty Cog
=========================

Community coding bounty system powered by Dev Karma.

Commands
--------
/bounty create
    Create a coding bounty and escrow Dev Karma.

/bounty list
    Show open bounties.

/bounty view
    View a specific bounty.

/bounty accept
    Accept a solver's solution and award the bounty.

/bounty cancel
    Cancel your bounty and refund the escrowed reward.

Members can also submit solutions directly from the
"Submit Solution" button attached to bounty messages.

The database layer is responsible for:
    - escrow
    - ownership checks
    - duplicate/invalid state checks
    - reward transfer
    - cancellation/refunds
    - bounty state
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

import discord
from discord.ext import commands

from bot.database.client import get_supabase
from bot.database.queries import (
    accept_bounty,
    cancel_bounty,
    create_bounty,
    get_bounty,
    list_open_bounties,
    update_bounty_message,
)

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

MAX_TITLE_LENGTH = 100
MAX_DESCRIPTION_LENGTH = 1800
MAX_SOLUTION_EXPLANATION = 1500
MAX_SOLUTION_URL = 500

MAX_REWARD = 1_000_000
MAX_LIST_RESULTS = 10

BOUNTY_THREAD_ARCHIVE_MINUTES = 4320  # 3 days

BOUNTY_COLOR = discord.Color.gold()
SUCCESS_COLOR = discord.Color.green()
ERROR_COLOR = discord.Color.red()
INFO_COLOR = discord.Color.blurple()


# =============================================================================
# HELPERS
# =============================================================================


def now_utc() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(timezone.utc)


def clean_text(
    value: str,
    maximum: int,
) -> str:
    """Clean and limit user-provided text."""
    value = value.strip()

    if len(value) > maximum:
        return value[:maximum]

    return value


def normalize_url(
    value: str,
) -> Optional[str]:
    """
    Validate a normal HTTP/HTTPS URL.

    Returns None for an empty or invalid URL.
    """

    value = value.strip()

    if not value:
        return None

    if len(value) > MAX_SOLUTION_URL:
        return None

    if not value.startswith(("http://", "https://")):
        value = f"https://{value}"

    try:
        parsed = urlparse(value)
    except ValueError:
        return None

    if parsed.scheme not in {"http", "https"}:
        return None

    if not parsed.netloc:
        return None

    return value


def format_reward(
    reward: int,
) -> str:
    """Format Dev Karma reward."""
    return f"{reward:,} Dev Karma"


def get_status_display(
    status: str,
) -> str:
    """Return a consistent human-readable bounty status."""

    normalized = status.upper()

    statuses = {
        "OPEN": "🟢 OPEN",
        "RESOLVED": "✅ RESOLVED",
        "CANCELLED": "🚫 CANCELLED",
        "CANCELED": "🚫 CANCELLED",
        "EXPIRED": "⏰ EXPIRED",
    }

    return statuses.get(
        normalized,
        normalized,
    )


def is_admin_or_owner(
    member: discord.Member,
    guild: discord.Guild,
) -> bool:
    """Check whether a member has administrative authority."""
    return (
        member.id == guild.owner_id
        or member.guild_permissions.administrator
    )


async def safe_send(
    ctx: commands.Context,
    content: Optional[str] = None,
    *,
    embed: Optional[discord.Embed] = None,
    ephemeral: bool = False,
) -> Optional[discord.Message]:
    """
    Send a context response safely for both slash and prefix commands.

    Hybrid commands can have either an interaction response or
    a normal channel message depending on how they were invoked.
    """

    try:
        if ctx.interaction:
            if not ctx.interaction.response.is_done():
                return await ctx.interaction.response.send_message(
                    content=content,
                    embed=embed,
                    ephemeral=ephemeral,
                )

            return await ctx.interaction.followup.send(
                content=content,
                embed=embed,
                ephemeral=ephemeral,
                wait=True,
            )

        return await ctx.send(
            content=content,
            embed=embed,
        )

    except discord.HTTPException:
        logger.exception(
            "Failed to send bounty response in guild %s",
            ctx.guild.id if ctx.guild else "DM",
        )

        return None


# =============================================================================
# SOLUTION MODAL
# =============================================================================


class BountySolutionModal(
    discord.ui.Modal,
):
    """Modal used by members to submit a bounty solution."""

    def __init__(
        self,
        bounty_id: int,
        bounty_title: str,
        thread_id: Optional[int] = None,
    ) -> None:
        super().__init__(
            title=f"Solve Bounty #{bounty_id}"
        )

        self.bounty_id = bounty_id
        self.bounty_title = bounty_title
        self.thread_id = thread_id

        self.solution_url_input = discord.ui.TextInput(
            label="Solution / PR / Gist URL",
            placeholder=(
                "https://github.com/... "
                "or https://gist.github.com/..."
            ),
            required=False,
            max_length=MAX_SOLUTION_URL,
        )

        self.explanation_input = discord.ui.TextInput(
            label="Explanation & Fix Details",
            style=discord.TextStyle.paragraph,
            placeholder=(
                "Explain the root cause, your fix, "
                "or how your solution works."
            ),
            required=True,
            min_length=10,
            max_length=MAX_SOLUTION_EXPLANATION,
        )

        self.add_item(self.solution_url_input)
        self.add_item(self.explanation_input)

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """Process a submitted bounty solution."""

        if interaction.guild is None:
            await interaction.response.send_message(
                "This can only be used inside a server.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(
            ephemeral=True
        )

        # ---------------------------------------------------------------------
        # Reload bounty state
        # ---------------------------------------------------------------------

        try:
            bounty = await get_bounty(
                self.bounty_id
            )
        except Exception:
            logger.exception(
                "Failed to fetch bounty %s while submitting solution",
                self.bounty_id,
            )

            await interaction.followup.send(
                "I couldn't check this bounty right now.",
                ephemeral=True,
            )
            return

        if not bounty:
            await interaction.followup.send(
                f"Bounty `#{self.bounty_id}` doesn't exist.",
                ephemeral=True,
            )
            return

        status = str(
            bounty.get("status", "")
        ).upper()

        if status != "OPEN":
            await interaction.followup.send(
                f"This bounty is no longer open. "
                f"Current status: **{get_status_display(status)}**.",
                ephemeral=True,
            )
            return

        # ---------------------------------------------------------------------
        # Clean solution data
        # ---------------------------------------------------------------------

        solution_url = (
            self.solution_url_input.value.strip()
            or None
        )

        explanation = clean_text(
            self.explanation_input.value,
            MAX_SOLUTION_EXPLANATION,
        )

        if not explanation:
            await interaction.followup.send(
                "Please provide an explanation of your solution.",
                ephemeral=True,
            )
            return

        if solution_url:
            solution_url = normalize_url(
                solution_url
            )

            if not solution_url:
                await interaction.followup.send(
                    "That solution URL is invalid. "
                    "Use an `http://` or `https://` URL.",
                    ephemeral=True,
                )
                return

        # ---------------------------------------------------------------------
        # Locate discussion thread
        # ---------------------------------------------------------------------

        thread: Optional[discord.Thread] = None

        if self.thread_id:
            thread = interaction.guild.get_thread(
                self.thread_id
            )

        if thread is None and self.thread_id:
            try:
                fetched_channel = await self._fetch_thread(
                    interaction,
                    self.thread_id,
                )

                if isinstance(
                    fetched_channel,
                    discord.Thread,
                ):
                    thread = fetched_channel

            except discord.HTTPException:
                logger.warning(
                    "Could not fetch bounty thread %s",
                    self.thread_id,
                )

        target_channel = (
            thread
            if thread is not None
            else interaction.channel
        )

        if target_channel is None:
            await interaction.followup.send(
                "I couldn't find a channel to post your solution.",
                ephemeral=True,
            )
            return

        # ---------------------------------------------------------------------
        # Build solution embed
        # ---------------------------------------------------------------------

        creator_id = bounty.get(
            "creator_id"
        )

        creator_mention = (
            f"<@{creator_id}>"
            if creator_id
            else "the bounty creator"
        )

        embed = discord.Embed(
            title=(
                f"Proposed Solution • "
                f"Bounty #{self.bounty_id}"
            ),
            description=(
                f"**Solver:** {interaction.user.mention}\n"
                f"**For:** {creator_mention}"
            ),
            color=SUCCESS_COLOR,
            timestamp=now_utc(),
        )

        embed.add_field(
            name="Approach",
            value=explanation[:1024],
            inline=False,
        )

        if solution_url:
            embed.add_field(
                name="Solution",
                value=(
                    f"[Open Solution / Pull Request]"
                    f"({solution_url})"
                ),
                inline=False,
            )

        embed.set_footer(
            text=(
                f"Bounty #{self.bounty_id} • "
                "Review this solution and use "
                f"/bounty accept {self.bounty_id}"
            ),
            icon_url=interaction.user.display_avatar.url,
        )

        # ---------------------------------------------------------------------
        # Publish solution
        # ---------------------------------------------------------------------

        try:
            await target_channel.send(
                embed=embed
            )

        except discord.Forbidden:
            logger.warning(
                "Missing permission to post solution "
                "for bounty %s",
                self.bounty_id,
            )

            await interaction.followup.send(
                "I couldn't post your solution because "
                "I don't have permission to send messages there.",
                ephemeral=True,
            )
            return

        except discord.HTTPException:
            logger.exception(
                "Discord error posting solution for bounty %s",
                self.bounty_id,
            )

            await interaction.followup.send(
                "Discord rejected the solution message. "
                "Please try again later.",
                ephemeral=True,
            )
            return

        # ---------------------------------------------------------------------
        # Success
        # ---------------------------------------------------------------------

        await interaction.followup.send(
            f"Your solution for **Bounty #{self.bounty_id}** "
            "has been posted for review.",
            ephemeral=True,
        )

    async def _fetch_thread(
        self,
        interaction: discord.Interaction,
        thread_id: int,
    ) -> Optional[discord.abc.GuildChannel]:
        """Try to fetch a thread that isn't cached."""

        try:
            channel = await interaction.guild.fetch_channel(
                thread_id
            )
        except (
            discord.NotFound,
            discord.Forbidden,
            discord.HTTPException,
        ):
            return None

        return channel


# =============================================================================
# BOUNTY VIEW
# =============================================================================


class BountyView(
    discord.ui.View
):
    """
    Persistent bounty message view.

    The custom ID intentionally stays stable:
        bounty:submit_solution

    The clicked message ID is used to locate the corresponding
    bounty record.
    """

    def __init__(self) -> None:
        super().__init__(
            timeout=None
        )

    @discord.ui.button(
        label="Submit Solution",
        style=discord.ButtonStyle.success,
        custom_id="bounty:submit_solution",
    )
    async def submit_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        """Open the solution modal for the clicked bounty."""

        if interaction.guild is None:
            await interaction.response.send_message(
                "This can only be used inside a server.",
                ephemeral=True,
            )
            return

        if interaction.message is None:
            await interaction.response.send_message(
                "I couldn't identify the bounty message.",
                ephemeral=True,
            )
            return

        # ---------------------------------------------------------------------
        # Find bounty by Discord message ID
        # ---------------------------------------------------------------------

        bounty = None

        try:
            supabase = get_supabase()

            if supabase:
                result = (
                    await supabase
                    .table("bounties")
                    .select("*")
                    .eq(
                        "message_id",
                        interaction.message.id,
                    )
                    .limit(1)
                    .execute()
                )

                if result.data:
                    bounty = result.data[0]

        except Exception:
            logger.exception(
                "Failed to find bounty for message %s",
                interaction.message.id,
            )

        if not bounty:
            await interaction.response.send_message(
                "I couldn't find the bounty associated with this message.",
                ephemeral=True,
            )
            return

        # ---------------------------------------------------------------------
        # Verify state
        # ---------------------------------------------------------------------

        status = str(
            bounty.get("status", "")
        ).upper()

        if status != "OPEN":
            await interaction.response.send_message(
                f"This bounty is currently "
                f"**{get_status_display(status)}**.",
                ephemeral=True,
            )
            return

        bounty_id = bounty.get("id")

        if not bounty_id:
            await interaction.response.send_message(
                "This bounty record is missing its ID.",
                ephemeral=True,
            )
            return

        # ---------------------------------------------------------------------
        # Open modal
        # ---------------------------------------------------------------------

        modal = BountySolutionModal(
            bounty_id=int(bounty_id),
            bounty_title=(
                bounty.get(
                    "title",
                    "Coding Bounty",
                )
            ),
            thread_id=bounty.get(
                "thread_id"
            ),
        )

        await interaction.response.send_modal(
            modal
        )


# =============================================================================
# BOUNTY COG
# =============================================================================


class Bounty(
    commands.Cog,
    name="Bounty",
):
    """Dev Karma coding bounty system."""

    def __init__(
        self,
        bot: commands.Bot,
    ) -> None:
        self.bot = bot

        logger.info(
            "Bounty cog initialized successfully."
        )

    # =========================================================================
    # PERSISTENT VIEW REGISTRATION
    # =========================================================================

    async def cog_load(self) -> None:
        """
        Register the persistent bounty view.

        This allows the Submit Solution button to continue
        working after the bot restarts.
        """

        try:
            self.bot.add_view(
                BountyView()
            )

            logger.info(
                "Persistent bounty view registered."
            )

        except Exception:
            logger.exception(
                "Failed to register persistent bounty view."
            )

    # =========================================================================
    # BOUNTY GROUP
    # =========================================================================

    @commands.hybrid_group(
        name="bounty",
        description=(
            "Dev Karma coding bounties "
            "and community help requests."
        ),
    )
    @commands.guild_only()
    async def bounty_group(
        self,
        ctx: commands.Context,
    ) -> None:
        """Bounty command group."""

        if ctx.invoked_subcommand is None:
            await self.list_bounties_cmd(
                ctx
            )

    # =========================================================================
    # CREATE
    # =========================================================================

    @bounty_group.command(
        name="create",
        description=(
            "Create a coding bounty "
            "with an escrowed Dev Karma reward."
        ),
    )
    @commands.guild_only()
    async def create_bounty_cmd(
        self,
        ctx: commands.Context,
        title: str,
        reward_karma: int,
        *,
        description: str,
    ) -> None:
        """Create a new coding bounty."""

        if ctx.guild is None:
            return

        # ---------------------------------------------------------------------
        # Validate title
        # ---------------------------------------------------------------------

        title = clean_text(
            title,
            MAX_TITLE_LENGTH,
        )

        if len(title) < 3:
            await safe_send(
                ctx,
                "Bounty title must be at least 3 characters.",
                ephemeral=True,
            )
            return

        # ---------------------------------------------------------------------
        # Validate description
        # ---------------------------------------------------------------------

        description = clean_text(
            description,
            MAX_DESCRIPTION_LENGTH,
        )

        if len(description) < 10:
            await safe_send(
                ctx,
                "Bounty description must be at least 10 characters.",
                ephemeral=True,
            )
            return

        # ---------------------------------------------------------------------
        # Validate reward
        # ---------------------------------------------------------------------

        if reward_karma <= 0:
            await safe_send(
                ctx,
                "Bounty reward must be at least 1 Dev Karma.",
                ephemeral=True,
            )
            return

        if reward_karma > MAX_REWARD:
            await safe_send(
                ctx,
                f"Bounty reward cannot exceed "
                f"{MAX_REWARD:,} Dev Karma.",
                ephemeral=True,
            )
            return

        # ---------------------------------------------------------------------
        # Defer slash interaction
        # ---------------------------------------------------------------------

        if (
            ctx.interaction
            and not ctx.interaction.response.is_done()
        ):
            await ctx.interaction.response.defer()

        # ---------------------------------------------------------------------
        # Create database record
        # ---------------------------------------------------------------------

        try:
            success, msg, bounty_id = await create_bounty(
                guild_id=ctx.guild.id,
                channel_id=ctx.channel.id,
                creator_id=ctx.author.id,
                title=title,
                description=description,
                reward_karma=reward_karma,
            )

        except Exception:
            logger.exception(
                "Failed to create bounty for user %s",
                ctx.author.id,
            )

            await safe_send(
                ctx,
                "Something went wrong while creating the bounty.",
                ephemeral=True,
            )
            return

        if not success or not bounty_id:
            await safe_send(
                ctx,
                f"Could not create bounty: "
                f"{msg or 'unknown database error'}",
                ephemeral=True,
            )
            return

        # ---------------------------------------------------------------------
        # Build bounty embed
        # ---------------------------------------------------------------------

        embed = discord.Embed(
            title=f"Bounty #{bounty_id}: {title}",
            description=description,
            color=BOUNTY_COLOR,
            timestamp=now_utc(),
        )

        embed.add_field(
            name="Reward",
            value=(
                f"**{format_reward(reward_karma)}**\n"
                "Held in escrow until the bounty is resolved."
            ),
            inline=True,
        )

        embed.add_field(
            name="Creator",
            value=ctx.author.mention,
            inline=True,
        )

        embed.add_field(
            name="Status",
            value="🟢 **OPEN**",
            inline=True,
        )

        embed.set_footer(
            text=(
                f"Bounty #{bounty_id} • "
                "Submit a solution using the button below."
            ),
            icon_url=ctx.author.display_avatar.url,
        )

        # ---------------------------------------------------------------------
        # Publish bounty
        # ---------------------------------------------------------------------

        try:
            bounty_message = await ctx.channel.send(
                embed=embed,
                view=BountyView(),
            )

        except discord.Forbidden:
            logger.warning(
                "Missing permission to publish bounty %s",
                bounty_id,
            )

            await safe_send(
                ctx,
                "The bounty was created, but I don't have "
                "permission to publish it in this channel.",
                ephemeral=True,
            )
            return

        except discord.HTTPException:
            logger.exception(
                "Failed to publish bounty %s",
                bounty_id,
            )

            await safe_send(
                ctx,
                "The bounty was created, but Discord failed "
                "to publish the message.",
                ephemeral=True,
            )
            return

        # ---------------------------------------------------------------------
        # Create discussion thread
        # ---------------------------------------------------------------------

        thread: Optional[discord.Thread] = None

        try:
            thread_name = (
                f"Bounty #{bounty_id}: "
                f"{title[:60]}"
            )

            thread = await bounty_message.create_thread(
                name=thread_name,
                auto_archive_duration=BOUNTY_THREAD_ARCHIVE_MINUTES,
            )

            await thread.send(
                f"Discussion for **Bounty #{bounty_id}: {title}**\n\n"
                f"Reward: **{format_reward(reward_karma)}** "
                f"escrowed by {ctx.author.mention}.\n\n"
                "Post debugging ideas, questions, and solution "
                "proposals here."
            )

        except discord.Forbidden:
            logger.warning(
                "Missing permission to create thread "
                "for bounty %s",
                bounty_id,
            )

        except discord.HTTPException:
            logger.exception(
                "Failed to create thread for bounty %s",
                bounty_id,
            )

        # ---------------------------------------------------------------------
        # Link Discord message to database
        # ---------------------------------------------------------------------

        try:
            await update_bounty_message(
                bounty_id=bounty_id,
                message_id=bounty_message.id,
                thread_id=(
                    thread.id
                    if thread
                    else None
                ),
            )

        except Exception:
            logger.exception(
                "Failed to update Discord IDs "
                "for bounty %s",
                bounty_id,
            )

        # ---------------------------------------------------------------------
        # Final response
        # ---------------------------------------------------------------------

        await safe_send(
            ctx,
            f"Bounty **#{bounty_id}** created with "
            f"**{format_reward(reward_karma)}** escrowed.",
            ephemeral=True,
        )

    # =========================================================================
    # VIEW
    # =========================================================================

    @bounty_group.command(
        name="view",
        description="View a specific coding bounty.",
    )
    @commands.guild_only()
    async def view_bounty_cmd(
        self,
        ctx: commands.Context,
        bounty_id: int,
    ) -> None:
        """Display detailed information about a bounty."""

        if ctx.guild is None:
            return

        if bounty_id <= 0:
            await safe_send(
                ctx,
                "Bounty ID must be a positive number.",
                ephemeral=True,
            )
            return

        try:
            bounty = await get_bounty(
                bounty_id
            )

        except Exception:
            logger.exception(
                "Failed to retrieve bounty %s",
                bounty_id,
            )

            await safe_send(
                ctx,
                "I couldn't retrieve that bounty right now.",
                ephemeral=True,
            )
            return

        if not bounty:
            await safe_send(
                ctx,
                f"Bounty `#{bounty_id}` was not found.",
                ephemeral=True,
            )
            return

        status = str(
            bounty.get(
                "status",
                "UNKNOWN",
            )
        ).upper()

        title = bounty.get(
            "title",
            "Untitled Bounty",
        )

        description = bounty.get(
            "description",
            "No description.",
        )

        reward = int(
            bounty.get(
                "reward_karma",
                0,
            )
            or 0
        )

        creator_id = bounty.get(
            "creator_id"
        )

        creator = (
            f"<@{creator_id}>"
            if creator_id
            else "Unknown"
        )

        embed = discord.Embed(
            title=f"Bounty #{bounty_id}: {title}",
            description=description,
            color=(
                SUCCESS_COLOR
                if status == "RESOLVED"
                else (
                    ERROR_COLOR
                    if status in {
                        "CANCELLED",
                        "CANCELED",
                    }
                    else BOUNTY_COLOR
                )
            ),
        )

        embed.add_field(
            name="Reward",
            value=format_reward(reward),
            inline=True,
        )

        embed.add_field(
            name="Creator",
            value=creator,
            inline=True,
        )

        embed.add_field(
            name="Status",
            value=get_status_display(status),
            inline=True,
        )

        if status == "OPEN":
            embed.add_field(
                name="How to contribute",
                value=(
                    "Use **Submit Solution** on the bounty "
                    "message or discuss your approach in "
                    "the bounty thread."
                ),
                inline=False,
            )

        embed.set_footer(
            text=(
                f"Horizon Devs Bounty System • "
                f"Bounty #{bounty_id}"
            )
        )

        await safe_send(
            ctx,
            embed=embed,
        )

    # =========================================================================
    # ACCEPT
    # =========================================================================

    @bounty_group.command(
        name="accept",
        description=(
            "Accept a solver's solution and "
            "award the escrowed Dev Karma."
        ),
    )
    @commands.guild_only()
    async def accept_bounty_cmd(
        self,
        ctx: commands.Context,
        bounty_id: int,
        solver: discord.Member,
    ) -> None:
        """Accept a bounty solution."""

        if ctx.guild is None:
            return

        if bounty_id <= 0:
            await safe_send(
                ctx,
                "Bounty ID must be a positive number.",
                ephemeral=True,
            )
            return

        if solver.bot:
            await safe_send(
                ctx,
                "A bot cannot receive a bounty reward.",
                ephemeral=True,
            )
            return

        if solver.id == ctx.author.id:
            await safe_send(
                ctx,
                "You cannot award your own bounty to yourself.",
                ephemeral=True,
            )
            return

        member = ctx.author

        if not isinstance(
            member,
            discord.Member,
        ):
            await safe_send(
                ctx,
                "I couldn't verify your server permissions.",
                ephemeral=True,
            )
            return

        is_admin = is_admin_or_owner(
            member,
            ctx.guild,
        )

        try:
            success, msg = await accept_bounty(
                bounty_id=bounty_id,
                solver_id=solver.id,
                caller_id=ctx.author.id,
                is_admin=is_admin,
            )

        except Exception:
            logger.exception(
                "Failed to accept bounty %s",
                bounty_id,
            )

            await safe_send(
                ctx,
                "Something went wrong while accepting the bounty.",
                ephemeral=True,
            )
            return

        if not success:
            await safe_send(
                ctx,
                msg or "The bounty could not be accepted.",
                ephemeral=True,
            )
            return

        # ---------------------------------------------------------------------
        # Success embed
        # ---------------------------------------------------------------------

        embed = discord.Embed(
            title=f"Bounty #{bounty_id} Resolved",
            description=(
                f"**Solver:** {solver.mention}\n"
                f"**Confirmed by:** {ctx.author.mention}\n\n"
                "The escrowed Dev Karma reward has been "
                "transferred to the solver."
            ),
            color=SUCCESS_COLOR,
            timestamp=now_utc(),
        )

        embed.set_thumbnail(
            url=solver.display_avatar.url
        )

        embed.set_footer(
            text="Horizon Devs Bounty System"
        )

        await safe_send(
            ctx,
            embed=embed,
        )

    # =========================================================================
    # CANCEL
    # =========================================================================

    @bounty_group.command(
        name="cancel",
        description=(
            "Cancel an open bounty and "
            "refund its escrowed reward."
        ),
    )
    @commands.guild_only()
    async def cancel_bounty_cmd(
        self,
        ctx: commands.Context,
        bounty_id: int,
    ) -> None:
        """Cancel an open bounty."""

        if ctx.guild is None:
            return

        if bounty_id <= 0:
            await safe_send(
                ctx,
                "Bounty ID must be a positive number.",
                ephemeral=True,
            )
            return

        member = ctx.author

        if not isinstance(
            member,
            discord.Member,
        ):
            await safe_send(
                ctx,
                "I couldn't verify your server membership.",
                ephemeral=True,
            )
            return

        is_admin = is_admin_or_owner(
            member,
            ctx.guild,
        )

        try:
            success, msg = await cancel_bounty(
                bounty_id=bounty_id,
                caller_id=ctx.author.id,
                is_admin=is_admin,
            )

        except Exception:
            logger.exception(
                "Failed to cancel bounty %s",
                bounty_id,
            )

            await safe_send(
                ctx,
                "Something went wrong while cancelling the bounty.",
                ephemeral=True,
            )
            return

        if not success:
            await safe_send(
                ctx,
                msg or "The bounty could not be cancelled.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=f"Bounty #{bounty_id} Cancelled",
            description=(
                msg
                or "The bounty was cancelled and its "
                "escrowed reward was refunded."
            ),
            color=ERROR_COLOR,
            timestamp=now_utc(),
        )

        embed.set_footer(
            text="Horizon Devs Bounty System"
        )

        await safe_send(
            ctx,
            embed=embed,
        )

    # =========================================================================
    # LIST
    # =========================================================================

    @bounty_group.command(
        name="list",
        description="List currently open coding bounties.",
    )
    @commands.guild_only()
    async def list_bounties_cmd(
        self,
        ctx: commands.Context,
    ) -> None:
        """Display open bounties."""

        if ctx.guild is None:
            return

        try:
            bounties = await list_open_bounties(
                guild_id=ctx.guild.id,
                limit=MAX_LIST_RESULTS,
            )

        except Exception:
            logger.exception(
                "Failed to list bounties in guild %s",
                ctx.guild.id,
            )

            await safe_send(
                ctx,
                "I couldn't retrieve the open bounties right now.",
                ephemeral=True,
            )
            return

        if not bounties:
            embed = discord.Embed(
                title="Open Bounties",
                description=(
                    "There are no open coding bounties "
                    "right now.\n\n"
                    "Create one with `/bounty create`."
                ),
                color=INFO_COLOR,
            )

            await safe_send(
                ctx,
                embed=embed,
            )
            return

        embed = discord.Embed(
            title="Horizon Devs — Open Bounties",
            description=(
                "Pick a challenge, help another developer, "
                "and earn Dev Karma."
            ),
            color=BOUNTY_COLOR,
        )

        for bounty in bounties:
            bounty_id = bounty.get(
                "id",
                "?",
            )

            title = clean_text(
                str(
                    bounty.get(
                        "title",
                        "Untitled Bounty",
                    )
                ),
                80,
            )

            description = clean_text(
                str(
                    bounty.get(
                        "description",
                        "No description.",
                    )
                ),
                180,
            )

            reward = int(
                bounty.get(
                    "reward_karma",
                    0,
                )
                or 0
            )

            creator_id = bounty.get(
                "creator_id"
            )

            creator = (
                f"<@{creator_id}>"
                if creator_id
                else "Unknown"
            )

            embed.add_field(
                name=(
                    f"#{bounty_id} • {title}"
                ),
                value=(
                    f"{description}\n\n"
                    f"**Reward:** {format_reward(reward)}\n"
                    f"**Creator:** {creator}\n"
                    f"Use `/bounty view {bounty_id}` "
                    "for details."
                ),
                inline=False,
            )

        embed.set_footer(
            text=(
                f"Showing up to {MAX_LIST_RESULTS} open bounties • "
                "Horizon Devs"
            )
        )

        await safe_send(
            ctx,
            embed=embed,
        )


# =============================================================================
# SETUP
# =============================================================================


async def setup(
    bot: commands.Bot,
) -> None:
    """Load the Bounty cog."""

    await bot.add_cog(
        Bounty(bot)
    )

    logger.info(
        "Bounty cog loaded successfully."
    )