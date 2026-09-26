"""Staff member lookup, profile notes, and moderation history."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import discord
from discord.ext import commands

from bot.database.queries import (
    get_member_profile,
    get_moderation_cases,
    remove_member_profile,
    set_member_profile,
)

logger = logging.getLogger(__name__)

PROFILE_TEXT_LIMIT = 1000
HISTORY_LIMIT = 10


class MemberProfile(commands.Cog):
    """Staff-only member information and profile management."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # --------------------------------------------------------
    # Permissions and responses
    # --------------------------------------------------------

    @staticmethod
    def is_staff(member: discord.Member) -> bool:
        """Require Manage Server or Administrator permission."""
        permissions = member.guild_permissions
        return permissions.manage_guild or permissions.administrator

    async def require_staff(self, ctx: commands.Context) -> bool:
        if ctx.guild is None or not isinstance(ctx.author, discord.Member):
            await self.send_embed(
                ctx,
                "Server Only",
                "These commands can only be used inside a server.",
                discord.Color.red(),
            )
            return False

        if not self.is_staff(ctx.author):
            await self.send_embed(
                ctx,
                "Permission Denied",
                "You need **Manage Server** permission to use this command.",
                discord.Color.red(),
            )
            return False

        return True

    async def defer_private(self, ctx: commands.Context) -> None:
        """Defer slash commands privately; prefix commands need no defer."""
        if ctx.interaction and not ctx.interaction.response.is_done():
            await ctx.interaction.response.defer(ephemeral=True)

    async def send_embed(
        self,
        ctx: commands.Context,
        title: str,
        description: str,
        color: discord.Color = discord.Color.blurple(),
    ) -> None:
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_footer(text=f"{ctx.guild.name if ctx.guild else 'Member tools'}")

        try:
            if ctx.interaction:
                if ctx.interaction.response.is_done():
                    await ctx.interaction.followup.send(
                        embed=embed,
                        ephemeral=True,
                    )
                else:
                    await ctx.interaction.response.send_message(
                        embed=embed,
                        ephemeral=True,
                    )
            else:
                await ctx.send(embed=embed)
        except discord.HTTPException:
            logger.exception("Could not send member-profile response.")

    # --------------------------------------------------------
    # Formatting
    # --------------------------------------------------------

    @staticmethod
    def discord_timestamp(value: datetime | None) -> str:
        if value is None:
            return "Unavailable"
        if value.tzinfo is None:
            value = value.replace(tzinfo=discord.utils.utcnow().tzinfo)
        return discord.utils.format_dt(value, style="F")

    @staticmethod
    def clip(value: Any, limit: int = 1000) -> str:
        text = str(value or "").strip()
        if not text:
            return "Not provided"
        if len(text) > limit:
            return text[: limit - 3] + "..."
        return text

    @staticmethod
    def get_member_label(guild: discord.Guild, user_id: int) -> str:
        member = guild.get_member(user_id)
        if member:
            return f"{member.mention} (`{member.id}`)"
        return f"User ID: `{user_id}`"

    # --------------------------------------------------------
    # Command group
    # --------------------------------------------------------

    @commands.hybrid_group(
        name="member",
        description="Staff member lookup, profiles, and history.",
        invoke_without_command=True,
    )
    async def member(self, ctx: commands.Context) -> None:
        """Show available staff member commands."""
        if not await self.require_staff(ctx):
            return

        await self.send_embed(
            ctx,
            "Member Staff Tools",
            (
                "`/member lookup <member>` — view a member's server information\n"
                "`/member profile set <member> <bio> [notes]` — save staff profile details\n"
                "`/member profile remove <member>` — remove saved profile details\n"
                "`/member history <member>` — view bot-recorded moderation history"
            ),
        )

    # --------------------------------------------------------
    # Member lookup
    # --------------------------------------------------------

    @member.command(
        name="lookup",
        description="View a member's Discord and server information.",
    )
    async def lookup(
        self,
        ctx: commands.Context,
        member: discord.Member,
    ) -> None:
        """Display the member's current details and staff profile."""
        if not await self.require_staff(ctx):
            return

        await self.defer_private(ctx)

        guild = ctx.guild
        if guild is None:
            return

        try:
            profile = await get_member_profile(
                guild_id=guild.id,
                user_id=member.id,
            )
        except Exception:
            logger.exception("Failed to load profile for user %s", member.id)
            profile = None

        created = self.discord_timestamp(member.created_at)
        joined = self.discord_timestamp(member.joined_at)

        roles = [
            role.mention
            for role in reversed(member.roles)
            if role != guild.default_role
        ]
        roles_text = ", ".join(roles) if roles else "No assigned roles"

        embed = discord.Embed(
            title="Member Overview",
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        embed.add_field(
            name="Identity",
            value=(
                f"**Display name:** {discord.utils.escape_markdown(member.display_name)}\n"
                f"**Username:** `{member.name}`\n"
                f"**User ID:** `{member.id}`"
            ),
            inline=False,
        )
        embed.add_field(
            name="Discord Account",
            value=f"**Created:** {created}",
            inline=False,
        )
        embed.add_field(
            name="This Server",
            value=(
                f"**Joined:** {joined}\n"
                f"**Nickname:** {member.nick or 'None'}\n"
                f"**Boosting:** {'Yes' if member.premium_since else 'No'}\n"
                f"**Roles:** {roles_text}"
            ),
            inline=False,
        )

        bio = profile.get("bio") if isinstance(profile, dict) else None
        notes = profile.get("notes") if isinstance(profile, dict) else None

        embed.add_field(
            name="Staff Profile",
            value=f"**Bio:** {self.clip(bio)}\n**Staff notes:** {self.clip(notes)}",
            inline=False,
        )

        embed.set_footer(text=f"Requested by {ctx.author}")
        await self.send_existing_embed(ctx, embed)

    # --------------------------------------------------------
    # Profile subgroup
    # --------------------------------------------------------

    @member.group(
        name="profile",
        description="Manage staff-entered member profile information.",
        invoke_without_command=True,
    )
    async def profile(self, ctx: commands.Context) -> None:
        if not await self.require_staff(ctx):
            return

        await self.send_embed(
            ctx,
            "Member Profile",
            (
                "`/member profile set <member> <bio> [notes]`\n"
                "`/member profile remove <member>`"
            ),
        )

    @profile.command(
        name="set",
        description="Save a staff bio and notes for a member.",
    )
    async def profile_set(
        self,
        ctx: commands.Context,
        member: discord.Member,
        bio: str,
        *,
        notes: str = "",
    ) -> None:
        """Create or update a member's staff-entered profile."""
        if not await self.require_staff(ctx):
            return

        await self.defer_private(ctx)

        bio = bio.strip()
        notes = notes.strip()

        if not bio:
            await self.send_embed(
                ctx,
                "Invalid Bio",
                "Please provide a non-empty bio.",
                discord.Color.red(),
            )
            return

        if len(bio) > PROFILE_TEXT_LIMIT or len(notes) > PROFILE_TEXT_LIMIT:
            await self.send_embed(
                ctx,
                "Text Too Long",
                f"Bio and notes must each be {PROFILE_TEXT_LIMIT} characters or fewer.",
                discord.Color.red(),
            )
            return

        guild = ctx.guild
        if guild is None:
            return

        try:
            saved = await set_member_profile(
                guild_id=guild.id,
                user_id=member.id,
                bio=bio,
                notes=notes,
                updated_by=ctx.author.id,
            )
        except Exception:
            logger.exception("Failed to save profile for user %s", member.id)
            saved = False

        if not saved:
            await self.send_embed(
                ctx,
                "Profile Not Saved",
                "The profile could not be saved. Check the database connection and table setup.",
                discord.Color.red(),
            )
            return

        await self.send_embed(
            ctx,
            "Profile Saved",
            f"Updated the staff profile for {member.mention}.",
            discord.Color.green(),
        )

    @profile.command(
        name="remove",
        description="Remove a member's saved staff profile.",
    )
    async def profile_remove(
        self,
        ctx: commands.Context,
        member: discord.Member,
    ) -> None:
        """Delete the saved staff bio and notes for a member."""
        if not await self.require_staff(ctx):
            return

        await self.defer_private(ctx)

        guild = ctx.guild
        if guild is None:
            return

        try:
            removed = await remove_member_profile(
                guild_id=guild.id,
                user_id=member.id,
            )
        except Exception:
            logger.exception("Failed to remove profile for user %s", member.id)
            removed = False

        if not removed:
            await self.send_embed(
                ctx,
                "Profile Not Removed",
                "No profile was removed. It may not exist, or the database operation failed.",
                discord.Color.orange(),
            )
            return

        await self.send_embed(
            ctx,
            "Profile Removed",
            f"Removed the saved staff profile for {member.mention}.",
            discord.Color.green(),
        )

    # --------------------------------------------------------
    # Moderation history
    # --------------------------------------------------------

    @member.command(
        name="history",
        description="View bot-recorded moderation actions for a member.",
    )
    async def history(
        self,
        ctx: commands.Context,
        member: discord.Member,
    ) -> None:
        """Show recent moderation cases stored by this bot."""
        if not await self.require_staff(ctx):
            return

        await self.defer_private(ctx)

        guild = ctx.guild
        if guild is None:
            return

        try:
            cases = await get_moderation_cases(
                guild_id=guild.id,
                user_id=member.id,
            )
        except Exception:
            logger.exception("Failed to load history for user %s", member.id)
            await self.send_embed(
                ctx,
                "History Unavailable",
                "Could not retrieve moderation history from the database.",
                discord.Color.red(),
            )
            return

        if not cases:
            await self.send_embed(
                ctx,
                "Moderation History",
                (
                    f"No bot-recorded moderation cases were found for {member.mention}.\n\n"
                    "This does not confirm whether the member has ever been moderated "
                    "outside this bot or before history logging was enabled."
                ),
            )
            return

        embed = discord.Embed(
            title=f"Moderation History — {member}",
            description=f"Showing up to the {HISTORY_LIMIT} most recent recorded cases.",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        for index, case in enumerate(cases[:HISTORY_LIMIT], start=1):
            action = self.clip(case.get("action"), 100)
            reason = self.clip(case.get("reason"), 500)
            moderator_id = case.get("moderator_id")
            created_at = case.get("created_at")

            try:
                moderator_id_int = int(moderator_id)
                moderator_label = self.get_member_label(
                    guild,
                    moderator_id_int,
                )
            except (TypeError, ValueError):
                moderator_label = "Unavailable"

            if isinstance(created_at, str):
                try:
                    parsed_date = datetime.fromisoformat(
                        created_at.replace("Z", "+00:00")
                    )
                    date_label = self.discord_timestamp(parsed_date)
                except ValueError:
                    date_label = created_at
            elif isinstance(created_at, datetime):
                date_label = self.discord_timestamp(created_at)
            else:
                date_label = "Date unavailable"

            embed.add_field(
                name=f"{index}. {action}",
                value=(
                    f"**When:** {date_label}\n"
                    f"**Moderator:** {moderator_label}\n"
                    f"**Reason:** {reason}"
                ),
                inline=False,
            )

        embed.set_footer(text=f"Member ID: {member.id}")
        await self.send_existing_embed(ctx, embed)

    async def send_existing_embed(
        self,
        ctx: commands.Context,
        embed: discord.Embed,
    ) -> None:
        """Send an already-built embed privately for slash usage."""
        try:
            if ctx.interaction:
                if ctx.interaction.response.is_done():
                    await ctx.interaction.followup.send(
                        embed=embed,
                        ephemeral=True,
                    )
                else:
                    await ctx.interaction.response.send_message(
                        embed=embed,
                        ephemeral=True,
                    )
            else:
                await ctx.send(embed=embed)
        except discord.HTTPException:
            logger.exception("Could not send member-profile embed.")


async def setup(bot: commands.Bot) -> None:
    """Load the member profile cog."""
    await bot.add_cog(MemberProfile(bot))