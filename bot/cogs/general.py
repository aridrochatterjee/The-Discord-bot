from __future__ import annotations

import discord
from discord.ext import commands


class General(commands.Cog):
    """General bot commands and server utilities."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ============================================================
    # PING
    # ============================================================

    @commands.hybrid_command(
        name="ping",
        description="Check if the bot is alive.",
    )
    async def ping(self, ctx: commands.Context) -> None:
        """Check the bot's latency."""

        latency = round(self.bot.latency * 1000)

        embed = discord.Embed(
            title="Pong!",
            description=(
                f"{ctx.author.mention}, **{latency}ms**\n"
                "Stop pinging me, I'm alive 😭"
            ),
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

        if guild.banner:
            embed.set_image(url=guild.banner.url)

        embed.add_field(
            name="Owner",
            value=owner.mention if owner else "Unknown",
            inline=True,
        )

        embed.add_field(
            name="Members",
            value=str(guild.member_count or 0),
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
            name="Boost Level",
            value=str(guild.premium_tier),
            inline=True,
        )

        embed.add_field(
            name="Boosts",
            value=str(guild.premium_subscription_count),
            inline=True,
        )

        embed.add_field(
            name="Server ID",
            value=f"`{guild.id}`",
            inline=True,
        )

        embed.add_field(
            name="Verification",
            value=str(
                guild.verification_level
            ).replace("_", " ").title(),
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

        embed.set_footer(
            text=f"Requested by {ctx.author}",
            icon_url=ctx.author.display_avatar.url,
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

        if member is None:
            member = ctx.author

        if not isinstance(member, discord.Member):
            return

        color = (
            member.color
            if member.color != discord.Color.default()
            else discord.Color.blurple()
        )

        embed = discord.Embed(
            title=member.display_name,
            description=member.mention,
            color=color,
        )

        embed.set_thumbnail(
            url=member.display_avatar.url,
        )

        embed.add_field(
            name="Username",
            value=str(member),
            inline=True,
        )

        embed.add_field(
            name="User ID",
            value=f"`{member.id}`",
            inline=True,
        )

        embed.add_field(
            name="Bot",
            value="Yes" if member.bot else "No",
            inline=True,
        )

        embed.add_field(
            name="Display Name",
            value=member.display_name,
            inline=True,
        )

        embed.add_field(
            name="Joined Server",
            value=(
                discord.utils.format_dt(
                    member.joined_at,
                    style="F",
                )
                if member.joined_at
                else "Unknown"
            ),
            inline=False,
        )

        embed.add_field(
            name="Account Created",
            value=discord.utils.format_dt(
                member.created_at,
                style="F",
            ),
            inline=False,
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

        if member.premium_since:
            embed.add_field(
                name="Boosting Since",
                value=discord.utils.format_dt(
                    member.premium_since,
                    style="F",
                ),
                inline=False,
            )

        embed.set_footer(
            text=f"Requested by {ctx.author}",
            icon_url=ctx.author.display_avatar.url,
        )

        await ctx.send(embed=embed)

    # ============================================================
    # AVATAR
    # ============================================================

    @commands.hybrid_command(
        name="avatar",
        description="Show a user's avatar.",
    )
    async def avatar(
        self,
        ctx: commands.Context,
        user: discord.User | None = None,
    ) -> None:
        """Display a user's avatar."""

        if user is None:
            user = ctx.author

        embed = discord.Embed(
            title=f"{user.display_name}'s Avatar",
            color=discord.Color.blurple(),
        )

        embed.set_image(url=user.display_avatar.url)

        embed.add_field(
            name="PNG",
            value=(
                f"[Open]("
                f"{user.display_avatar.replace(format='png').url}"
                f")"
            ),
            inline=True,
        )

        embed.add_field(
            name="JPG",
            value=(
                f"[Open]("
                f"{user.display_avatar.replace(format='jpg').url}"
                f")"
            ),
            inline=True,
        )

        embed.add_field(
            name="WEBP",
            value=(
                f"[Open]("
                f"{user.display_avatar.replace(format='webp').url}"
                f")"
            ),
            inline=True,
        )

        await ctx.send(embed=embed)

    # ============================================================
    # BANNER
    # ============================================================

    @commands.hybrid_command(
        name="banner",
        description="Show a user's profile banner.",
    )
    async def banner(
        self,
        ctx: commands.Context,
        user: discord.User | None = None,
    ) -> None:
        """Display a user's profile banner."""

        if user is None:
            user = ctx.author

        fetched_user = await self.bot.fetch_user(user.id)

        if fetched_user.banner is None:
            await ctx.send(
                f"{user.mention} doesn't have a profile banner."
            )
            return

        embed = discord.Embed(
            title=f"{user.display_name}'s Banner",
            color=discord.Color.blurple(),
        )

        embed.set_image(url=fetched_user.banner.url)

        await ctx.send(embed=embed)

    # ============================================================
    # SERVER ICON
    # ============================================================

    @commands.hybrid_command(
        name="server_icon",
        description="Show the server icon.",
    )
    @commands.guild_only()
    async def server_icon(self, ctx: commands.Context) -> None:
        """Display the current server's icon."""

        guild = ctx.guild

        if guild is None:
            return

        if guild.icon is None:
            await ctx.send(
                "This server doesn't have an icon."
            )
            return

        embed = discord.Embed(
            title=f"{guild.name} Icon",
            color=discord.Color.blurple(),
        )

        embed.set_image(url=guild.icon.url)

        await ctx.send(embed=embed)

    # ============================================================
    # SERVER BANNER
    # ============================================================

    @commands.hybrid_command(
        name="server_banner",
        description="Show the server banner.",
    )
    @commands.guild_only()
    async def server_banner(
        self,
        ctx: commands.Context,
    ) -> None:
        """Display the current server's banner."""

        guild = ctx.guild

        if guild is None:
            return

        if guild.banner is None:
            await ctx.send(
                "This server doesn't have a banner."
            )
            return

        embed = discord.Embed(
            title=f"{guild.name} Banner",
            color=discord.Color.blurple(),
        )

        embed.set_image(url=guild.banner.url)

        await ctx.send(embed=embed)

    # ============================================================
    # MEMBER COUNT
    # ============================================================

    @commands.hybrid_command(
        name="member_count",
        description="Show server member statistics.",
    )
    @commands.guild_only()
    async def member_count(
        self,
        ctx: commands.Context,
    ) -> None:
        """Display member statistics."""

        guild = ctx.guild

        if guild is None:
            return

        members = guild.members

        total = len(members)

        humans = sum(
            not member.bot
            for member in members
        )

        bots = sum(
            member.bot
            for member in members
        )

        online = sum(
            member.status != discord.Status.offline
            for member in members
        )

        embed = discord.Embed(
            title=f"{guild.name} Members",
            color=discord.Color.blurple(),
        )

        embed.add_field(
            name="Total",
            value=f"**{total}**",
            inline=True,
        )

        embed.add_field(
            name="Humans",
            value=f"**{humans}**",
            inline=True,
        )

        embed.add_field(
            name="Bots",
            value=f"**{bots}**",
            inline=True,
        )

        embed.add_field(
            name="Currently Online",
            value=f"**{online}**",
            inline=True,
        )

        await ctx.send(embed=embed)

    # ============================================================
    # ROLE INFO
    # ============================================================

    @commands.hybrid_command(
        name="role_info",
        description="Show information about a role.",
    )
    @commands.guild_only()
    async def role_info(
        self,
        ctx: commands.Context,
        role: discord.Role,
    ) -> None:
        """Display information about a role."""

        role_color = (
            role.color
            if role.color != discord.Color.default()
            else discord.Color.blurple()
        )

        embed = discord.Embed(
            title=role.name,
            color=role_color,
        )

        embed.add_field(
            name="Role ID",
            value=f"`{role.id}`",
            inline=True,
        )

        embed.add_field(
            name="Position",
            value=str(role.position),
            inline=True,
        )

        embed.add_field(
            name="Members",
            value=str(len(role.members)),
            inline=True,
        )

        embed.add_field(
            name="Mentionable",
            value="Yes" if role.mentionable else "No",
            inline=True,
        )

        embed.add_field(
            name="Hoisted",
            value="Yes" if role.hoist else "No",
            inline=True,
        )

        embed.add_field(
            name="Managed",
            value="Yes" if role.managed else "No",
            inline=True,
        )

        embed.add_field(
            name="Created",
            value=discord.utils.format_dt(
                role.created_at,
                style="F",
            ),
            inline=False,
        )

        embed.set_footer(
            text=f"Requested by {ctx.author}",
        )

        await ctx.send(embed=embed)

    # ============================================================
    # CHANNEL INFO
    # ============================================================

    @commands.hybrid_command(
        name="channel_info",
        description="Show information about a channel.",
    )
    @commands.guild_only()
    async def channel_info(
        self,
        ctx: commands.Context,
        channel: discord.abc.GuildChannel | None = None,
    ) -> None:
        """Display information about a channel."""

        if channel is None:
            channel = ctx.channel

        if not isinstance(
            channel,
            discord.abc.GuildChannel,
        ):
            await ctx.send(
                "That isn't a valid server channel."
            )
            return

        embed = discord.Embed(
            title=channel.name,
            color=discord.Color.blurple(),
        )

        embed.add_field(
            name="Channel ID",
            value=f"`{channel.id}`",
            inline=True,
        )

        embed.add_field(
            name="Type",
            value=str(
                channel.type
            ).replace("_", " ").title(),
            inline=True,
        )

        embed.add_field(
            name="Position",
            value=str(channel.position),
            inline=True,
        )

        if channel.category:
            embed.add_field(
                name="Category",
                value=channel.category.mention,
                inline=True,
            )

        embed.add_field(
            name="Created",
            value=discord.utils.format_dt(
                channel.created_at,
                style="F",
            ),
            inline=False,
        )

        embed.set_footer(
            text=f"Requested by {ctx.author}",
        )

        await ctx.send(embed=embed)

    # ============================================================
    # SNOWFLAKE
    # ============================================================

    @commands.hybrid_command(
        name="snowflake",
        description="Show the creation date of a Discord ID.",
    )
    async def snowflake(
        self,
        ctx: commands.Context,
        snowflake_id: int,
    ) -> None:
        """Decode a Discord snowflake ID."""

        try:
            timestamp = discord.utils.snowflake_time(
                snowflake_id
            )
        except (ValueError, OverflowError):
            await ctx.send(
                "That doesn't look like a valid Discord ID."
            )
            return

        embed = discord.Embed(
            title="Snowflake Information",
            color=discord.Color.blurple(),
        )

        embed.add_field(
            name="ID",
            value=f"`{snowflake_id}`",
            inline=False,
        )

        embed.add_field(
            name="Created",
            value=discord.utils.format_dt(
                timestamp,
                style="F",
            ),
            inline=False,
        )

        embed.add_field(
            name="Relative",
            value=discord.utils.format_dt(
                timestamp,
                style="R",
            ),
            inline=False,
        )

        await ctx.send(embed=embed)

    # ============================================================
    # SAY
    # ============================================================

    @commands.hybrid_command(
        name="say",
        description="Make the bot send a message.",
    )
    @commands.guild_only()
    @commands.has_permissions(
        manage_messages=True
    )
    @commands.bot_has_permissions(
        send_messages=True
    )
    async def say(
        self,
        ctx: commands.Context,
        *,
        message: str,
    ) -> None:
        """Send a message as the bot."""

        if not message.strip():
            await ctx.send(
                "You need to provide a message."
            )
            return

        # Prevent accidental mass mentions.
        message = discord.utils.escape_mentions(
            message
        )

        await ctx.send(message)

        # Delete the original prefix command message
        # when possible.
        if ctx.message:
            try:
                await ctx.message.delete()
            except discord.HTTPException:
                pass

    # ============================================================
    # ERROR HANDLER
    # ============================================================

    @say.error
    async def say_error(
        self,
        ctx: commands.Context,
        error: commands.CommandError,
    ) -> None:
        """Handle /say permission errors."""

        if isinstance(
            error,
            commands.MissingPermissions,
        ):
            await ctx.send(
                "You need **Manage Messages** "
                "to use this command."
            )

        elif isinstance(
            error,
            commands.BotMissingPermissions,
        ):
            await ctx.send(
                "I don't have permission to send "
                "messages here."
            )

    # ============================================================
    # COG ERROR HANDLER
    # ============================================================

    async def cog_command_error(
        self,
        ctx: commands.Context,
        error: commands.CommandError,
    ) -> None:
        """Handle errors for commands in this cog."""

        if isinstance(
            error,
            commands.CommandNotFound,
        ):
            return

        if isinstance(
            error,
            commands.CommandOnCooldown,
        ):
            await ctx.send(
                f"Slow down. Try again in "
                f"**{error.retry_after:.1f}s**."
            )
            return

        if isinstance(
            error,
            commands.MissingRequiredArgument,
        ):
            await ctx.send(
                f"Missing argument: "
                f"`{error.param.name}`."
            )
            return

        if isinstance(
            error,
            commands.MemberNotFound,
        ):
            await ctx.send(
                "I couldn't find that member."
            )
            return

        if isinstance(
            error,
            commands.RoleNotFound,
        ):
            await ctx.send(
                "I couldn't find that role."
            )
            return

        if isinstance(
            error,
            commands.ChannelNotFound,
        ):
            await ctx.send(
                "I couldn't find that channel."
            )
            return

        if isinstance(
            error,
            commands.BadArgument,
        ):
            await ctx.send(
                "One of the arguments you provided "
                "is invalid."
            )
            return

        if isinstance(
            error,
            commands.MissingPermissions,
        ):
            await ctx.send(
                "You don't have permission "
                "to use this command."
            )
            return

        if isinstance(
            error,
            commands.BotMissingPermissions,
        ):
            await ctx.send(
                "I don't have the permissions "
                "I need to do that."
            )
            return

        raise error


# ================================================================
# COG SETUP
# ================================================================

async def setup(bot: commands.Bot) -> None:
    """Load the General cog."""

    await bot.add_cog(
        General(bot)
    )
