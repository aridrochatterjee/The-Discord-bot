"""Moderation Cog.

Hybrid commands support both slash and prefix usage.

Examples:
    /ban @member Spam
    !ban @member Spam

Commands:
    ban
    unban <user_id>
    kick
    purge
    softban
    timeout
    remove_timeout

Automatic filtering:
    - Discord invite links
    - Configured adult website domains

Successful moderation actions stay in the channel.
Errors and automatic-filter warnings disappear after DELETE_AFTER seconds.
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta
from typing import Awaitable, Callable
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands


# ============================================================
# CONFIGURATION
# ============================================================

# How long temporary error/warning embeds remain visible.
DELETE_AFTER = 5

# Maximum number of messages /purge or !purge can delete.
MAX_PURGE = 100

# Discord's maximum timeout duration.
MAX_TIMEOUT = timedelta(days=28)

# Regional timezone used in moderation embeds.
# CommunityOS can later make this configurable per server.
TIMEZONE = ZoneInfo("Asia/Kolkata")


# ============================================================
# LINK FILTERING
# ============================================================

# Discord invite links.
INVITE_RE = re.compile(
    r"(?:https?://)?(?:www\.)?"
    r"(?:discord\.gg|discord\.com/invite|discordapp\.com/invite)"
    r"/[A-Za-z0-9-]+",
    re.IGNORECASE,
)

# Known adult domains.
# Add/remove domains here when needed.
ADULT_DOMAINS = (
    "pornhub.com",
    "xvideos.com",
    "xnxx.com",
    "xhamster.com",
    "redtube.com",
    "youporn.com",
    "spankbang.com",
    "tube8.com",
    "beeg.com",
)


class Moderation(commands.Cog):
    """CommunityOS moderation commands and automatic filtering."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ========================================================
    # EMBEDS AND RESPONSES
    # ========================================================

    @staticmethod
    def now() -> datetime:
        """Return the current configured regional time."""

        return datetime.now(TIMEZONE)

    def embed(
        self,
        title: str,
        description: str,
        color: discord.Color = discord.Color.blurple(),
    ) -> discord.Embed:
        """Create a consistent embed."""

        now = self.now()

        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=now,
        )

        embed.set_footer(
            text=f"• {now.strftime('%d %b %Y • %I:%M %p %Z')}"
        )

        return embed

    async def defer(self, ctx: commands.Context) -> None:
        """
        Acknowledge slash commands before longer operations.

        Prefix commands don't require deferring.
        """

        interaction = ctx.interaction

        if interaction and not interaction.response.is_done():
            await interaction.response.defer()

    async def respond(
        self,
        ctx: commands.Context,
        title: str,
        description: str,
        color: discord.Color = discord.Color.blurple(),
        *,
        temporary: bool = False,
    ) -> None:
        """
        Send a response.

        Successful moderation actions remain permanently.

        Errors and warnings become temporary when:
            temporary=True
        """

        embed = self.embed(title, description, color)

        try:
            if ctx.interaction:
                message = await ctx.interaction.followup.send(
                    embed=embed,
                    wait=True,
                )
            else:
                message = await ctx.send(embed=embed)

        except discord.HTTPException:
            return

        if temporary:
            await asyncio.sleep(DELETE_AFTER)

            try:
                await message.delete()
            except (discord.Forbidden, discord.HTTPException):
                pass

    async def error(
        self,
        ctx: commands.Context,
        title: str,
        description: str,
    ) -> None:
        """Send a temporary error embed."""

        await self.respond(
            ctx,
            title,
            description,
            discord.Color.red(),
            temporary=True,
        )

    # ========================================================
    # VALIDATION
    # ========================================================

    @staticmethod
    def can_moderate(
        moderator: discord.Member,
        target: discord.Member,
    ) -> bool:
        """
        Check Discord's moderation hierarchy.

        A moderator cannot:
            - Moderate themselves.
            - Moderate the server owner.
            - Moderate someone with an equal/higher role.

        The server owner can moderate everyone except themselves.
        """

        guild = moderator.guild

        if moderator.id == target.id:
            return False

        if target.id == guild.owner_id:
            return False

        if moderator.id == guild.owner_id:
            return True

        return moderator.top_role > target.top_role

    async def validate(
        self,
        ctx: commands.Context,
        target: discord.Member,
        permission: str,
    ) -> bool:
        """Validate moderator permission, bot permission and hierarchy."""

        if ctx.guild is None:
            await self.error(
                ctx,
                "Invalid Location",
                "This command can only be used inside a server.",
            )
            return False

        if not isinstance(ctx.author, discord.Member):
            return False

        bot_member = ctx.guild.me

        # Moderator permission.
        if not getattr(
            ctx.author.guild_permissions,
            permission,
            False,
        ):
            await self.error(
                ctx,
                "Permission Denied",
                "You don't have permission to use this command.",
            )
            return False

        # Bot permission.
        if (
            bot_member is None
            or not getattr(
                bot_member.guild_permissions,
                permission,
                False,
            )
        ):
            await self.error(
                ctx,
                "Bot Permission Missing",
                "I don't have the required permission.",
            )
            return False

        # Role hierarchy.
        if not self.can_moderate(ctx.author, target):
            await self.error(
                ctx,
                "Action Denied",
                "You cannot moderate this member because of the role hierarchy.",
            )
            return False

        return True

    # ========================================================
    # TIME HELPERS
    # ========================================================

    @staticmethod
    def parse_duration(duration: str) -> timedelta | None:
        """
        Parse timeout durations.

        Supported examples:
            10m
            2h
            7d
        """

        match = re.fullmatch(
            r"(\d+)([mhd])",
            duration.lower().strip(),
        )

        if not match:
            return None

        amount = int(match.group(1))
        unit = match.group(2)

        return {
            "m": timedelta(minutes=amount),
            "h": timedelta(hours=amount),
            "d": timedelta(days=amount),
        }[unit]

    # ========================================================
    # MODERATION ACTION HELPERS
    # ========================================================

    async def notify_member(
        self,
        member: discord.Member,
        moderator: discord.Member,
        action: str,
        reason: str,
        extra: str = "",
    ) -> None:
        """
        DM the moderated user.

        DM failures do not cancel the moderation action because users
        may have direct messages disabled.
        """

        now = self.now()

        description = (
            f"**Server:** {member.guild.name}\n"
            f"**Action:** {action}\n"
            f"**Action taken by:** {moderator}\n"
            f"**Reason:** {reason}\n"
            f"**Date:** {now.strftime('%d %B %Y')}\n"
            f"**Time:** {now.strftime('%I:%M %p %Z')}"
        )

        if extra:
            description += f"\n{extra}"

        try:
            await member.send(
                embed=self.embed(
                    "Moderation Notice",
                    description,
                    discord.Color.orange(),
                )
            )

        except (discord.Forbidden, discord.HTTPException):
            pass

    async def run_action(
        self,
        ctx: commands.Context,
        member: discord.Member,
        *,
        permission: str,
        action: str,
        reason: str,
        callback: Callable[[], Awaitable[None]],
        extra: str = "",
    ) -> None:
        """
        Run a standard moderation action.

        Handles:
            - Slash interaction acknowledgement
            - Permission validation
            - Bot permissions
            - Role hierarchy
            - Discord API errors
            - DM notifications
            - Permanent action embed
        """

        await self.defer(ctx)

        if not await self.validate(ctx, member, permission):
            return

        moderator = ctx.author

        if not isinstance(moderator, discord.Member):
            return

        try:
            await callback()

        except discord.Forbidden:
            await self.error(
                ctx,
                f"{action} Failed",
                "I don't have permission or my role is too low.",
            )
            return

        except discord.HTTPException:
            await self.error(
                ctx,
                f"{action} Failed",
                "Discord returned an error while performing this action.",
            )
            return

        # Only notify the member after the action successfully completes.
        await self.notify_member(
            member,
            moderator,
            action,
            reason,
            extra,
        )

        now = self.now()

        description = (
            f"**Member:** {member.mention}\n"
            f"**Action taken by:** {moderator.mention}\n"
            f"**Reason:** {reason}\n"
            f"**Date:** {now.strftime('%d %B %Y')}\n"
            f"**Time:** {now.strftime('%I:%M %p %Z')}"
        )

        if extra:
            description += f"\n{extra}"

        await self.respond(
            ctx,
            action,
            description,
            discord.Color.green(),
        )

    # ========================================================
    # BAN
    # ========================================================

    @commands.hybrid_command(
        name="ban",
        description="Ban a member from the server.",
    )
    async def ban(
        self,
        ctx: commands.Context,
        member: discord.Member,
        *,
        reason: str = "No reason provided.",
    ) -> None:
        """Ban a member."""

        await self.run_action(
            ctx,
            member,
            permission="ban_members",
            action="Member Banned",
            reason=reason,
            callback=lambda: member.ban(reason=reason),
        )

    # ========================================================
    # KICK
    # ========================================================

    @commands.hybrid_command(
        name="kick",
        description="Kick a member from the server.",
    )
    async def kick(
        self,
        ctx: commands.Context,
        member: discord.Member,
        *,
        reason: str = "No reason provided.",
    ) -> None:
        """Kick a member."""

        await self.run_action(
            ctx,
            member,
            permission="kick_members",
            action="Member Kicked",
            reason=reason,
            callback=lambda: member.kick(reason=reason),
        )

    # ========================================================
    # SOFTBAN
    # ========================================================

    @commands.hybrid_command(
        name="softban",
        description="Ban and immediately unban a member.",
    )
    async def softban(
        self,
        ctx: commands.Context,
        member: discord.Member,
        *,
        reason: str = "No reason provided.",
    ) -> None:
        """
        Softban a member.

        Deletes recent messages, bans the user, then immediately
        unbans them so they can rejoin.
        """

        async def execute() -> None:
            await member.ban(
                reason=f"Softban: {reason}",
                delete_message_seconds=86400,
            )

            if ctx.guild:
                await ctx.guild.unban(
                    member,
                    reason=f"Softban completed: {reason}",
                )

        await self.run_action(
            ctx,
            member,
            permission="ban_members",
            action="Member Softbanned",
            reason=reason,
            callback=execute,
        )

    # ========================================================
    # TIMEOUT
    # ========================================================

    @commands.hybrid_command(
        name="timeout",
        description="Timeout a member for a specified duration.",
    )
    async def timeout(
        self,
        ctx: commands.Context,
        member: discord.Member,
        duration: str,
        *,
        reason: str = "No reason provided.",
    ) -> None:
        """
        Timeout a member.

        Duration examples:
            10m
            2h
            7d
        """

        await self.defer(ctx)

        timeout_duration = self.parse_duration(duration)

        if timeout_duration is None:
            await self.error(
                ctx,
                "Invalid Duration",
                "Use formats like `10m`, `2h`, or `7d`.",
            )
            return

        if timeout_duration > MAX_TIMEOUT:
            await self.error(
                ctx,
                "Invalid Duration",
                "A timeout cannot exceed 28 days.",
            )
            return

        await self.run_action(
            ctx,
            member,
            permission="moderate_members",
            action="Member Timed Out",
            reason=reason,
            callback=lambda: member.timeout(
                timeout_duration,
                reason=reason,
            ),
            extra=f"**Duration:** {duration}",
        )

    # ========================================================
    # REMOVE TIMEOUT
    # ========================================================

    @commands.hybrid_command(
        name="remove_timeout",
        description="Remove a member's timeout.",
    )
    async def remove_timeout(
        self,
        ctx: commands.Context,
        member: discord.Member,
        *,
        reason: str = "No reason provided.",
    ) -> None:
        """Remove a member's active timeout."""

        await self.run_action(
            ctx,
            member,
            permission="moderate_members",
            action="Timeout Removed",
            reason=reason,
            callback=lambda: member.timeout(None, reason=reason),
        )

    # ========================================================
    # UNBAN
    # ========================================================

    @commands.hybrid_command(
        name="unban",
        description="Unban a user using their Discord user ID.",
    )
    async def unban(
        self,
        ctx: commands.Context,
        user_id: str,
        *,
        reason: str = "No reason provided.",
    ) -> None:
        """Unban a user using their numeric Discord user ID."""

        await self.defer(ctx)

        if (
            ctx.guild is None
            or not isinstance(ctx.author, discord.Member)
        ):
            return

        if not user_id.isdigit():
            await self.error(
                ctx,
                "Invalid User ID",
                "Please provide a valid numeric Discord user ID.",
            )
            return

        if not ctx.author.guild_permissions.ban_members:
            await self.error(
                ctx,
                "Permission Denied",
                "You don't have permission to unban members.",
            )
            return

        bot_member = ctx.guild.me

        if (
            bot_member is None
            or not bot_member.guild_permissions.ban_members
        ):
            await self.error(
                ctx,
                "Bot Permission Missing",
                "I don't have permission to manage bans.",
            )
            return

        try:
            user = await self.bot.fetch_user(int(user_id))

            await ctx.guild.unban(
                user,
                reason=reason,
            )

        except discord.NotFound:
            await self.error(
                ctx,
                "Unban Failed",
                "That user is not currently banned.",
            )
            return

        except discord.Forbidden:
            await self.error(
                ctx,
                "Unban Failed",
                "I don't have permission to unban that user.",
            )
            return

        except discord.HTTPException:
            await self.error(
                ctx,
                "Unban Failed",
                "Discord returned an error while unbanning that user.",
            )
            return

        now = self.now()

        await self.respond(
            ctx,
            "User Unbanned",
            (
                f"**User:** {user.mention}\n"
                f"**Action taken by:** {ctx.author.mention}\n"
                f"**Reason:** {reason}\n"
                f"**Date:** {now.strftime('%d %B %Y')}\n"
                f"**Time:** {now.strftime('%I:%M %p %Z')}"
            ),
            discord.Color.green(),
        )

    # ========================================================
    # PURGE
    # ========================================================

    @commands.hybrid_command(
        name="purge",
        description="Delete messages from the current channel.",
    )
    async def purge(
        self,
        ctx: commands.Context,
        amount: int,
    ) -> None:
        """Delete messages from the current text channel."""

        await self.defer(ctx)

        if (
            ctx.guild is None
            or not isinstance(ctx.author, discord.Member)
        ):
            return

        if not ctx.author.guild_permissions.manage_messages:
            await self.error(
                ctx,
                "Permission Denied",
                "You don't have permission to manage messages.",
            )
            return

        bot_member = ctx.guild.me

        if (
            bot_member is None
            or not bot_member.guild_permissions.manage_messages
        ):
            await self.error(
                ctx,
                "Bot Permission Missing",
                "I don't have permission to manage messages.",
            )
            return

        if not isinstance(ctx.channel, discord.TextChannel):
            await self.error(
                ctx,
                "Unsupported Channel",
                "This command can only be used in a text channel.",
            )
            return

        if not 1 <= amount <= MAX_PURGE:
            await self.error(
                ctx,
                "Invalid Amount",
                f"Choose a number between 1 and {MAX_PURGE}.",
            )
            return

        try:
            # Prefix commands include the command message itself.
            limit = amount + 1 if ctx.interaction is None else amount

            deleted = await ctx.channel.purge(limit=limit)

            count = len(deleted)

            if ctx.interaction is None:
                count -= 1

        except discord.Forbidden:
            await self.error(
                ctx,
                "Purge Failed",
                "I don't have permission to delete messages here.",
            )
            return

        except discord.HTTPException:
            await self.error(
                ctx,
                "Purge Failed",
                "Discord returned an error while deleting messages.",
            )
            return

        now = self.now()

        await self.respond(
            ctx,
            "Messages Deleted",
            (
                f"**Messages:** {max(0, count)}\n"
                f"**Action taken by:** {ctx.author.mention}\n"
                f"**Date:** {now.strftime('%d %B %Y')}\n"
                f"**Time:** {now.strftime('%I:%M %p %Z')}"
            ),
            discord.Color.green(),
        )

    # ========================================================
    # AUTOMATIC LINK FILTERING
    # ========================================================

    @commands.Cog.listener()
    async def on_message(
        self,
        message: discord.Message,
    ) -> None:
        """
        Remove blocked links.

        Current filters:
            - Discord invite links
            - Configured adult website domains

        Members with Manage Messages bypass the filter.
        """

        if (
            message.author.bot
            or message.guild is None
            or not isinstance(message.author, discord.Member)
            or message.author.guild_permissions.manage_messages
        ):
            return

        content = message.content.lower()

        if INVITE_RE.search(content):
            reason = "Discord invite links are not allowed."

        elif any(domain in content for domain in ADULT_DOMAINS):
            reason = "Adult website links are not allowed."

        else:
            return

        try:
            await message.delete()

        except (discord.Forbidden, discord.HTTPException):
            return

        try:
            warning = await message.channel.send(
                embed=self.embed(
                    "Message Removed",
                    f"{message.author.mention}\n{reason}",
                    discord.Color.red(),
                )
            )

            # Filter warnings are temporary.
            await asyncio.sleep(DELETE_AFTER)

            try:
                await warning.delete()
            except (discord.Forbidden, discord.HTTPException):
                pass

        except (discord.Forbidden, discord.HTTPException):
            pass


async def setup(bot: commands.Bot) -> None:
    """Load the moderation cog."""

    await bot.add_cog(Moderation(bot))
