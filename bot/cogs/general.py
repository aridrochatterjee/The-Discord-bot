from __future__ import annotations

import discord
from discord.ext import commands


class General(commands.Cog):
    """General bot commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ============================================================
    # PING
    # ============================================================

    @commands.hybrid_command(
        name="ping",
        description="Check the bot's latency.",
    )
    async def ping(self, ctx: commands.Context) -> None:
        """Show the bot's current latency."""

        latency = round(self.bot.latency * 1000)

        embed = discord.Embed(
            title="Pong",
            description=f"Latency: **{latency}ms**",
            color=discord.Color.blurple(),
        )

        await ctx.send(embed=embed)

    # ============================================================
    # SERVER INFO
    # ============================================================

    @commands.hybrid_command(
        name="server_info",
        description="Show information about this server.",
    )
    @commands.guild_only()
    async def server_info(self, ctx: commands.Context) -> None:
        """Display useful information about the current server."""

        guild = ctx.guild

        if guild is None:
            return

        owner = guild.owner

        embed = discord.Embed(
            title=guild.name,
            description="Server information",
            color=discord.Color.blurple(),
        )

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        embed.add_field(
            name="Owner",
            value=owner.mention if owner else "Unknown",
            inline=True,
        )

        embed.add_field(
            name="Members",
            value=str(guild.member_count),
            inline=True,
        )

        embed.add_field(
            name="Server ID",
            value=f"`{guild.id}`",
            inline=True,
        )

        embed.add_field(
            name="Channels",
            value=str(len(guild.channels)),
            inline=True,
        )

        embed.add_field(
            name="Roles",
            value=str(len(guild.roles)),
            inline=True,
        )

        embed.add_field(
            name="Created",
            value=discord.utils.format_dt(
                guild.created_at,
                style="F",
            ),
            inline=False,
        )

        await ctx.send(embed=embed)

    # ============================================================
    # USER INFO
    # ============================================================

    @commands.hybrid_command(
        name="user_info",
        description="Show information about a user.",
    )
    @commands.guild_only()
    async def user_info(
        self,
        ctx: commands.Context,
        member: discord.Member | None = None,
    ) -> None:
        """Display useful information about a server member."""

        member = member or ctx.author

        embed = discord.Embed(
            title=str(member),
            color=member.color
            if member.color != discord.Color.default()
            else discord.Color.blurple(),
        )

        embed.set_thumbnail(url=member.display_avatar.url)

        embed.add_field(
            name="User ID",
            value=f"`{member.id}`",
            inline=True,
        )

        embed.add_field(
            name="Joined Server",
            value=discord.utils.format_dt(
                member.joined_at,
                style="F",
            )
            if member.joined_at
            else "Unknown",
            inline=True,
        )

        embed.add_field(
            name="Account Created",
            value=discord.utils.format_dt(
                member.created_at,
                style="F",
            ),
            inline=True,
        )

        roles = [
            role.mention
            for role in member.roles
            if not role.is_default()
        ]

        embed.add_field(
            name=f"Roles ({len(roles)})",
            value=", ".join(roles[-10:]) if roles else "None",
            inline=False,
        )

        embed.set_footer(
            text=f"Requested by {ctx.author}",
            icon_url=ctx.author.display_avatar.url,
        )

        await ctx.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    """Load the General cog."""

    await bot.add_cog(General(bot))