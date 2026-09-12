from __future__ import annotations

from typing import Optional, Tuple

import discord
from discord.ext import commands

from bot.database.queries import (
    get_reputation,
    get_top_reputation,
    give_reputation,
)


def get_karma_tier(points: int) -> Tuple[str, Optional[int]]:
    """
    Compute a title tier and points required for the next tier.
    
    Returns:
        Tuple[tier_title, next_tier_threshold_or_None]
    """
    if points < 5:
        return "🌱 Junior Helper", 5
    elif points < 15:
        return "🛠️ Code Contributor", 15
    elif points < 30:
        return "🏆 Community Mentor", 30
    elif points < 50:
        return "⚡ Lead Architect", 50
    else:
        return "🧙‍♂️ Horizon Tech Sage", None


def format_progress_bar(current: int, target: Optional[int], length: int = 10) -> str:
    """Generate a visual ASCII progress bar toward the next tier."""
    if not target or current >= target:
        return f"`[{'█' * length}]` Max Tier"

    # Assume baseline is 0 or proportional
    pct = min(1.0, max(0.0, current / target))
    filled = int(round(pct * length))
    bar = "█" * filled + "░" * (length - filled)
    return f"`[{bar}]` {current}/{target} points"


class Reputation(commands.Cog, name="Reputation"):
    """Dev karma and gratitude system for Horizon Devs."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # =========================================================================
    # THANK / GIVE KARMA (/thank)
    # =========================================================================

    @commands.hybrid_command(
        name="thank",
        description="Award Dev Karma to a member who helped you (limit: once per day per user).",
    )
    @commands.guild_only()
    async def thank(
        self,
        ctx: commands.Context,
        member: discord.Member,
        *,
        reason: str = "Helping a fellow developer",
    ) -> None:
        """Award 1 reputation point to a helpful server member (limit: once per day per user)."""
        if ctx.guild is None:
            return

        if member.id == ctx.author.id:
            await ctx.send("❌ You cannot give reputation to yourself!", ephemeral=True)
            return

        if member.bot:
            await ctx.send("❌ Bots appreciate the sentiment, but cannot collect Dev Karma!", ephemeral=True)
            return

        if ctx.interaction and not ctx.interaction.response.is_done():
            await ctx.interaction.response.defer()

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
            await ctx.send(embed=embed)
            return

        tier, _ = get_karma_tier(new_points)

        embed = discord.Embed(
            title="✨ Dev Karma Awarded!",
            description=(
                f"{ctx.author.mention} recognized {member.mention} for their support!\n\n"
                f"**Reason:** *\"{reason}\"*\n\n"
                f"**Total Karma:** ⭐ `{new_points}` points • **Title:** {tier}"
            ),
            color=discord.Color.gold(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(
            text=f"Awarded by {ctx.author.display_name} • Horizon Devs Karma",
            icon_url=ctx.author.display_avatar.url,
        )

        await ctx.send(embed=embed)

    # =========================================================================
    # VIEW KARMA (/karma)
    # =========================================================================

    @commands.hybrid_command(
        name="karma",
        description="Check your or another developer's Dev Karma points and rank tier.",
    )
    @commands.guild_only()
    async def karma(
        self,
        ctx: commands.Context,
        member: Optional[discord.Member] = None,
    ) -> None:
        """View a member's current Dev Karma level and points."""
        if ctx.guild is None:
            return

        target = member or ctx.author
        if not isinstance(target, discord.Member):
            return

        if ctx.interaction and not ctx.interaction.response.is_done():
            await ctx.interaction.response.defer()

        points = await get_reputation(target.id, ctx.guild.id)
        tier, next_threshold = get_karma_tier(points)
        progress = format_progress_bar(points, next_threshold)

        embed = discord.Embed(
            title=f"⭐ Dev Karma: {target.display_name}",
            color=discord.Color.gold(),
        )
        embed.set_thumbnail(url=target.display_avatar.url)

        embed.add_field(name="Current Points", value=f"⭐ **{points}** karma", inline=True)
        embed.add_field(name="Developer Rank", value=tier, inline=True)
        embed.add_field(name="Next Tier Progress", value=progress, inline=False)

        embed.set_footer(
            text=f"Requested by {ctx.author.display_name} • Use /thank @member to award points",
            icon_url=ctx.author.display_avatar.url,
        )

        await ctx.send(embed=embed)

    # =========================================================================
    # LEADERBOARD (/leaderboard)
    # =========================================================================

    @commands.hybrid_command(
        name="leaderboard",
        description="View the top contributors and most helpful developers in this server.",
    )
    @commands.guild_only()
    async def leaderboard(
        self,
        ctx: commands.Context,
    ) -> None:
        """Display the server's top 10 karma contributors."""
        if ctx.guild is None:
            return

        if ctx.interaction and not ctx.interaction.response.is_done():
            await ctx.interaction.response.defer()

        top_users = await get_top_reputation(ctx.guild.id, limit=10)

        if not top_users:
            embed = discord.Embed(
                title="🏆 Horizon Devs Leaderboard",
                description=(
                    "No one has earned Dev Karma in this server yet!\n\n"
                    "Help out a peer with code, architecture, or debugging, and earn points with `/thank @member`."
                ),
                color=discord.Color.blurple(),
            )
            await ctx.send(embed=embed)
            return

        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        lines = []

        for idx, row in enumerate(top_users, start=1):
            user_id = row.get("user_id")
            points = row.get("points", 0)
            prefix = medals.get(idx, f"**{idx}.**")
            lines.append(f"{prefix} <@{user_id}> — **{points}** pts")

        embed = discord.Embed(
            title=f"🏆 {ctx.guild.name} — Top Contributors",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )
        embed.set_footer(
            text="Recognize great help with /thank @member • Horizon Devs",
            icon_url=ctx.guild.icon.url if ctx.guild.icon else None,
        )

        await ctx.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    """Load the Reputation cog."""
    await bot.add_cog(Reputation(bot))
