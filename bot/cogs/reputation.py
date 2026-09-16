from __future__ import annotations

from typing import Optional, Tuple

import discord
from discord.ext import commands

from bot.database.queries import (
    get_reputation,
    get_top_reputation,
    give_reputation,
    remove_reputation_points,
    reset_guild_reputation,
)


# =============================================================================
# KARMA TIERS
# =============================================================================

# Each tier contains:
#
#     (minimum_points, title)
#
# Keep this ordered from lowest to highest.
#
# You can change the requirements/titles later without touching the commands.

KARMA_TIERS: list[tuple[int, str]] = [
    (0, "🌱 Newcomer"),
    (5, "🛠️ Junior Helper"),
    (15, "💻 Code Contributor"),
    (30, "🔧 Problem Solver"),
    (50, "🚀 Project Builder"),
    (75, "🏆 Community Mentor"),
    (110, "⚡ Senior Contributor"),
    (150, "🧠 Technical Leader"),
    (200, "💎 Engineering Veteran"),
    (300, "👑 Horizon Dev Master"),
    (500, "🧙 Horizon Tech Sage"),
]


def get_karma_tier(points: int) -> Tuple[str, Optional[int]]:
    """
    Calculate the user's current Karma tier.

    Returns:
        Tuple[current_tier_title, next_tier_requirement]

    If the user has reached the maximum tier, the second value is None.
    """
    points = max(0, points)

    current_title = KARMA_TIERS[0][1]
    next_threshold: Optional[int] = None

    for index, (threshold, title) in enumerate(KARMA_TIERS):
        if points >= threshold:
            current_title = title

            if index + 1 < len(KARMA_TIERS):
                next_threshold = KARMA_TIERS[index + 1][0]

    return current_title, next_threshold


def format_progress_bar(
    current: int,
    target: Optional[int],
    length: int = 10,
) -> str:
    """Generate an ASCII progress bar toward the next Karma tier."""
    current = max(0, current)

    if target is None or current >= target:
        return f"`[{'█' * length}]` Max Tier"

    previous_threshold = 0

    for threshold, _ in KARMA_TIERS:
        if threshold <= current:
            previous_threshold = threshold
        else:
            break

    tier_range = max(1, target - previous_threshold)
    progress = max(0, current - previous_threshold)

    pct = min(1.0, progress / tier_range)

    filled = int(round(pct * length))

    bar = (
        "█" * filled
        + "░" * (length - filled)
    )

    return f"`[{bar}]` {current}/{target} points"


# =============================================================================
# ADMIN CHECK
# =============================================================================

def is_admin_or_owner() -> commands.Check:
    """
    Allow server administrators and the bot owner to use admin commands.
    """

    async def predicate(ctx: commands.Context) -> bool:
        if ctx.guild is None:
            return False

        # Bot owner always has access.
        if await ctx.bot.is_owner(ctx.author):
            return True

        # Discord administrator permission.
        if isinstance(ctx.author, discord.Member):
            return ctx.author.guild_permissions.administrator

        return False

    return commands.check(predicate)


# =============================================================================
# RESET CONFIRMATION VIEW
# =============================================================================

class KarmaResetView(discord.ui.View):
    """
    Confirmation UI for destructive Karma reset operations.
    """

    def __init__(
        self,
        author_id: int,
        guild_id: int,
        reset_type: str,
    ) -> None:
        super().__init__(timeout=30)

        self.author_id = author_id
        self.guild_id = guild_id
        self.reset_type = reset_type
        self.message: Optional[discord.Message] = None

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ) -> bool:
        """Only the administrator who started the reset can confirm it."""

        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ You did not start this reset.",
                ephemeral=True,
            )
            return False

        return True

    @discord.ui.button(
        label="Confirm Reset",
        style=discord.ButtonStyle.danger,
        emoji="🗑️",
    )
    async def confirm(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        """Confirm and execute the reset."""

        # Disable all buttons immediately.
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

        success, affected_count = await reset_guild_reputation(
            guild_id=self.guild_id,
            admin_user_id=interaction.user.id,
            reason=f"{self.reset_type} command",
        )

        if not success:
            await interaction.response.edit_message(
                content=(
                    "❌ **Reset failed.**\n"
                    "The database operation could not be completed."
                ),
                embed=None,
                view=self,
            )
            self.stop()
            return

        embed = discord.Embed(
            title=f"🗑️ {self.reset_type} Complete",
            description=(
                "All current Dev Karma for this server has been cleared.\n\n"
                "The historical reputation audit logs were preserved."
            ),
            color=discord.Color.red(),
        )

        embed.add_field(
            name="Accounts Cleared",
            value=f"`{affected_count}`",
            inline=True,
        )

        embed.add_field(
            name="Current Karma",
            value="`0`",
            inline=True,
        )

        embed.add_field(
            name="Leaderboard",
            value="Empty",
            inline=True,
        )

        embed.set_footer(
            text=f"Reset by {interaction.user.display_name}",
            icon_url=interaction.user.display_avatar.url,
        )

        await interaction.response.edit_message(
            content=None,
            embed=embed,
            view=self,
        )

        self.stop()

    @discord.ui.button(
        label="Cancel",
        style=discord.ButtonStyle.secondary,
        emoji="✖️",
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        """Cancel the reset."""

        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

        embed = discord.Embed(
            title="Reset Cancelled",
            description=(
                "No Karma or leaderboard data was changed."
            ),
            color=discord.Color.green(),
        )

        await interaction.response.edit_message(
            content=None,
            embed=embed,
            view=self,
        )

        self.stop()

    async def on_timeout(self) -> None:
        """Disable the buttons when the confirmation expires."""

        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except (discord.NotFound, discord.HTTPException):
                pass


# =============================================================================
# REPUTATION COG
# =============================================================================

class Reputation(commands.Cog, name="Reputation"):
    """Dev Karma and gratitude system for Horizon Devs."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # =========================================================================
    # THANK / GIVE KARMA
    # =========================================================================

    @commands.hybrid_command(
        name="thank",
        description=(
            "Award 1 Dev Karma to a member who helped you."
        ),
    )
    @commands.guild_only()
    async def thank(
        self,
        ctx: commands.Context,
        member: discord.Member,
        *,
        reason: str = "Helping a fellow developer",
    ) -> None:
        """Award one Dev Karma point to a helpful member."""

        if ctx.guild is None:
            return

        if member.id == ctx.author.id:
            await ctx.send(
                "❌ You cannot give Dev Karma to yourself!",
                ephemeral=True,
            )
            return

        if member.bot:
            await ctx.send(
                "❌ Bots cannot collect Dev Karma.",
                ephemeral=True,
            )
            return

        reason = reason.strip()

        if not reason:
            reason = "Helping a fellow developer"

        if len(reason) > 500:
            await ctx.send(
                "❌ Your reason must be 500 characters or fewer.",
                ephemeral=True,
            )
            return

        success, message, new_points = await give_reputation(
            from_user_id=ctx.author.id,
            to_user_id=member.id,
            guild_id=ctx.guild.id,
            reason=reason,
        )

        if not success:
            embed = discord.Embed(
                title="⏳ Could Not Award Karma",
                description=message,
                color=discord.Color.orange(),
            )

            await ctx.send(
                embed=embed,
                ephemeral=True,
            )
            return

        tier, next_threshold = get_karma_tier(new_points)

        progress = format_progress_bar(
            new_points,
            next_threshold,
        )

        embed = discord.Embed(
            title="✨ Dev Karma Awarded",
            description=(
                f"{ctx.author.mention} recognized "
                f"{member.mention} for their contribution.\n\n"
                f"**Reason**\n"
                f"*{reason}*"
            ),
            color=discord.Color.gold(),
        )

        embed.add_field(
            name="Karma",
            value=f"⭐ **{new_points}**",
            inline=True,
        )

        embed.add_field(
            name="Developer Tier",
            value=tier,
            inline=True,
        )

        embed.add_field(
            name="Progress",
            value=progress,
            inline=False,
        )

        embed.set_thumbnail(
            url=member.display_avatar.url,
        )

        embed.set_footer(
            text=(
                f"Awarded by {ctx.author.display_name} "
                "• Horizon Devs Karma"
            ),
            icon_url=ctx.author.display_avatar.url,
        )

        await ctx.send(embed=embed)

    # =========================================================================
    # VIEW KARMA
    # =========================================================================

    @commands.hybrid_command(
        name="karma",
        description=(
            "Check your or another developer's Dev Karma."
        ),
    )
    @commands.guild_only()
    async def karma(
        self,
        ctx: commands.Context,
        member: Optional[discord.Member] = None,
    ) -> None:
        """View a member's current Dev Karma and developer tier."""

        if ctx.guild is None:
            return

        target = member or ctx.author

        if not isinstance(target, discord.Member):
            return

        points = await get_reputation(
            target.id,
            ctx.guild.id,
        )

        tier, next_threshold = get_karma_tier(points)

        progress = format_progress_bar(
            points,
            next_threshold,
        )

        embed = discord.Embed(
            title=f"⭐ Dev Karma — {target.display_name}",
            color=discord.Color.gold(),
        )

        embed.set_thumbnail(
            url=target.display_avatar.url,
        )

        embed.add_field(
            name="Current Karma",
            value=f"⭐ **{points}** points",
            inline=True,
        )

        embed.add_field(
            name="Developer Tier",
            value=tier,
            inline=True,
        )

        embed.add_field(
            name="Next Tier",
            value=(
                f"`{next_threshold}` points"
                if next_threshold is not None
                else "🏆 Maximum tier reached"
            ),
            inline=True,
        )

        embed.add_field(
            name="Progress",
            value=progress,
            inline=False,
        )

        embed.set_footer(
            text=(
                f"Requested by {ctx.author.display_name} "
                "• Use /thank @member to award Karma"
            ),
            icon_url=ctx.author.display_avatar.url,
        )

        await ctx.send(embed=embed)

    # =========================================================================
    # LEADERBOARD
    # =========================================================================

    @commands.hybrid_command(
        name="leaderboard",
        description=(
            "View the top Dev Karma contributors in this server."
        ),
    )
    @commands.guild_only()
    async def leaderboard(
        self,
        ctx: commands.Context,
    ) -> None:
        """Display the server's top 10 Dev Karma contributors."""

        if ctx.guild is None:
            return

        top_users = await get_top_reputation(
            ctx.guild.id,
            limit=10,
        )

        if not top_users:
            embed = discord.Embed(
                title="🏆 Horizon Devs Leaderboard",
                description=(
                    "The leaderboard is currently empty.\n\n"
                    "Help someone with code, debugging, architecture, "
                    "or another developer problem and use "
                    "`/thank @member` to recognize them."
                ),
                color=discord.Color.blurple(),
            )

            await ctx.send(embed=embed)
            return

        medals = {
            1: "🥇",
            2: "🥈",
            3: "🥉",
        }

        lines: list[str] = []

        for index, row in enumerate(top_users, start=1):
            user_id = row.get("user_id")
            points = int(row.get("points", 0))

            tier, _ = get_karma_tier(points)

            prefix = medals.get(
                index,
                f"**{index}.**",
            )

            lines.append(
                f"{prefix} <@{user_id}> "
                f"— **{points}** pts\n"
                f"　└ {tier}"
            )

        embed = discord.Embed(
            title=f"🏆 {ctx.guild.name} — Dev Karma Leaderboard",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )

        embed.set_footer(
            text=(
                "Recognize great help with /thank @member "
                "• Horizon Devs"
            ),
            icon_url=(
                ctx.guild.icon.url
                if ctx.guild.icon
                else None
            ),
        )

        await ctx.send(embed=embed)

    # =========================================================================
    # REMOVE KARMA
    # =========================================================================

    @commands.hybrid_command(
        name="remove_karma",
        description=(
            "Remove Dev Karma from a member."
        ),
    )
    @commands.guild_only()
    @is_admin_or_owner()
    async def remove_karma(
        self,
        ctx: commands.Context,
        member: discord.Member,
        amount: int,
        *,
        reason: str,
    ) -> None:
        """
        Remove Dev Karma from a member.

        Example:
            /remove_karma @Aridro 25 Invalid challenge submission
        """

        if ctx.guild is None:
            return

        if member.bot:
            await ctx.send(
                "❌ Bots do not have Dev Karma.",
                ephemeral=True,
            )
            return

        if amount <= 0:
            await ctx.send(
                "❌ Amount must be greater than `0`.",
                ephemeral=True,
            )
            return

        if amount > 1_000_000:
            await ctx.send(
                "❌ Amount cannot exceed `1,000,000`.",
                ephemeral=True,
            )
            return

        reason = reason.strip()

        if not reason:
            await ctx.send(
                "❌ A reason is required.",
                ephemeral=True,
            )
            return

        if len(reason) > 500:
            await ctx.send(
                "❌ Reason must be 500 characters or fewer.",
                ephemeral=True,
            )
            return

        success, message, old_balance, new_balance = (
            await remove_reputation_points(
                admin_user_id=ctx.author.id,
                user_id=member.id,
                guild_id=ctx.guild.id,
                amount=amount,
                reason=reason,
            )
        )

        if not success:
            await ctx.send(
                f"❌ {message}",
                ephemeral=True,
            )
            return

        actually_removed = old_balance - new_balance

        embed = discord.Embed(
            title="🛑 Dev Karma Removed",
            description=(
                f"{member.mention} had Dev Karma removed "
                f"by {ctx.author.mention}."
            ),
            color=discord.Color.red(),
        )

        embed.add_field(
            name="Previous Karma",
            value=f"⭐ `{old_balance}`",
            inline=True,
        )

        embed.add_field(
            name="Removed",
            value=f"➖ `{actually_removed}`",
            inline=True,
        )

        embed.add_field(
            name="New Karma",
            value=f"⭐ `{new_balance}`",
            inline=True,
        )

        embed.add_field(
            name="Reason",
            value=reason,
            inline=False,
        )

        new_tier, _ = get_karma_tier(new_balance)

        embed.add_field(
            name="Current Tier",
            value=new_tier,
            inline=False,
        )

        embed.set_thumbnail(
            url=member.display_avatar.url,
        )

        embed.set_footer(
            text=(
                f"Moderation action by {ctx.author.display_name} "
                "• Horizon Devs"
            ),
            icon_url=ctx.author.display_avatar.url,
        )

        await ctx.send(embed=embed)

    # =========================================================================
    # KARMA RESET
    # =========================================================================

    @commands.hybrid_command(
        name="karma_reset",
        description=(
            "Reset all Dev Karma in this server."
        ),
    )
    @commands.guild_only()
    @is_admin_or_owner()
    async def karma_reset(
        self,
        ctx: commands.Context,
    ) -> None:
        """
        Reset all current Dev Karma in this server.

        Historical reputation logs are preserved.
        """

        if ctx.guild is None:
            return

        embed = discord.Embed(
            title="⚠️ Reset Dev Karma?",
            description=(
                "**This is a destructive action.**\n\n"
                "This will reset the current Dev Karma balance "
                "for **every member in this server**.\n\n"
                "The reputation history/audit logs will be preserved, "
                "but the current balances and leaderboard will be cleared.\n\n"
                "**This action cannot be undone automatically.**"
            ),
            color=discord.Color.red(),
        )

        embed.add_field(
            name="Server",
            value=ctx.guild.name,
            inline=True,
        )

        embed.add_field(
            name="Action",
            value="Reset all Karma",
            inline=True,
        )

        embed.set_footer(
            text="This confirmation expires in 30 seconds.",
        )

        view = KarmaResetView(
            author_id=ctx.author.id,
            guild_id=ctx.guild.id,
            reset_type="Dev Karma Reset",
        )

        message = await ctx.send(
            embed=embed,
            view=view,
        )

        view.message = message

    # =========================================================================
    # LEADERBOARD RESET
    # =========================================================================

    @commands.hybrid_command(
        name="leaderboard_reset",
        description=(
            "Reset the Dev Karma leaderboard in this server."
        ),
    )
    @commands.guild_only()
    @is_admin_or_owner()
    async def leaderboard_reset(
        self,
        ctx: commands.Context,
    ) -> None:
        """
        Reset the server leaderboard.

        Because the leaderboard is calculated from reputation.points,
        this also clears the current Dev Karma balances.
        """

        if ctx.guild is None:
            return

        embed = discord.Embed(
            title="⚠️ Reset Leaderboard?",
            description=(
                "**This is a destructive action.**\n\n"
                "Your leaderboard is powered by the server's "
                "Dev Karma balances.\n\n"
                "Resetting it will therefore clear the current "
                "Dev Karma for **every member** in this server.\n\n"
                "Historical reputation logs will be preserved.\n\n"
                "**This action cannot be undone automatically.**"
            ),
            color=discord.Color.red(),
        )

        embed.add_field(
            name="Server",
            value=ctx.guild.name,
            inline=True,
        )

        embed.add_field(
            name="Action",
            value="Reset leaderboard + current Karma",
            inline=True,
        )

        embed.set_footer(
            text="This confirmation expires in 30 seconds.",
        )

        view = KarmaResetView(
            author_id=ctx.author.id,
            guild_id=ctx.guild.id,
            reset_type="Leaderboard Reset",
        )

        message = await ctx.send(
            embed=embed,
            view=view,
        )

        view.message = message


# =============================================================================
# COG SETUP
# =============================================================================

async def setup(bot: commands.Bot) -> None:
    """Load the Reputation cog."""
    await bot.add_cog(Reputation(bot))