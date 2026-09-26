from __future__ import annotations

import logging
from datetime import date

import discord
from discord import app_commands
from discord.ext import commands

from bot.database.queries import (
    delete_member_profile,
    get_member_profile,
    upsert_member_profile,
)

logger = logging.getLogger("bot.member_profiles")


class MemberProfiles(commands.Cog):
    """Staff-only saved profiles for community members."""

    profile = app_commands.Group(
        name="profile",
        description="Manage saved member profiles.",
        default_permissions=discord.Permissions(manage_guild=True),
        guild_only=True,
    )

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @staticmethod
    async def _is_staff(interaction: discord.Interaction) -> bool:
        """Runtime permission check; command visibility alone is not security."""
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return False

        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "You need the **Manage Server** permission to use this command.",
                ephemeral=True,
            )
            return False

        return True

    @app_commands.command(
        name="lookup",
        description="Look up a saved member profile by Discord ID.",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(
        manage_guild=True,
    )
    async def lookup(
        self,
        interaction: discord.Interaction,
        discord_id: str,
    ) -> None:
        if not await self._is_staff(interaction):
            return

        try:
            target_id = int(discord_id.strip())
            if target_id <= 0:
                raise ValueError
        except (ValueError, AttributeError):
            await interaction.response.send_message(
                "Enter a valid numeric Discord ID.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            profile = await get_member_profile(
                interaction.guild_id,
                target_id,
            )
        except Exception:
            logger.exception("Profile lookup failed.")
            await interaction.followup.send(
                "The profile database could not be reached. Please try again later.",
                ephemeral=True,
            )
            return

        if profile is None:
            await interaction.followup.send(
                f"No saved profile was found for Discord ID `{target_id}`.",
                ephemeral=True,
            )
            return

        try:
            user = self.bot.get_user(target_id) or await self.bot.fetch_user(target_id)
            username = f"{user.name} ({user.display_name})"
        except (discord.NotFound, discord.HTTPException):
            username = "Unknown Discord user"

        embed = discord.Embed(
            title="Member profile",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Username", value=username, inline=False)
        embed.add_field(name="Discord ID", value=str(target_id), inline=False)
        embed.add_field(
            name="Joined",
            value=profile.get("joined_date") or "Not recorded",
            inline=True,
        )
        embed.add_field(
            name="About",
            value=profile.get("bio") or "No bio saved.",
            inline=False,
        )
        embed.set_footer(text=f"Guild ID: {interaction.guild_id}")

        await interaction.followup.send(embed=embed, ephemeral=True)

    @profile.command(
        name="set",
        description="Add or update a member's saved profile.",
    )
    async def set_profile(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        joined_date: str,
        bio: str,
    ) -> None:
        if not await self._is_staff(interaction):
            return

        try:
            parsed_date = date.fromisoformat(joined_date.strip())
        except ValueError:
            await interaction.response.send_message(
                "Use the date format `YYYY-MM-DD`, for example `2023-01-01`.",
                ephemeral=True,
            )
            return

        bio = bio.strip()
        if not bio:
            await interaction.response.send_message(
                "The bio cannot be empty.",
                ephemeral=True,
            )
            return

        if len(bio) > 1000:
            await interaction.response.send_message(
                "Keep the bio to 1,000 characters or fewer.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            await upsert_member_profile(
                guild_id=interaction.guild_id,
                discord_id=member.id,
                joined_date=parsed_date.isoformat(),
                bio=bio,
                staff_id=interaction.user.id,
            )
        except Exception:
            logger.exception("Saving member profile failed.")
            await interaction.followup.send(
                "Could not save the profile. Check the bot logs and Supabase setup.",
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            f"Saved the profile for {member.mention}.",
            ephemeral=True,
        )

    @profile.command(
        name="remove",
        description="Remove a member's saved profile.",
    )
    async def remove_profile(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
    ) -> None:
        if not await self._is_staff(interaction):
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            deleted = await delete_member_profile(
                guild_id=interaction.guild_id,
                discord_id=member.id,
            )
        except Exception:
            logger.exception("Removing member profile failed.")
            await interaction.followup.send(
                "Could not remove the profile. Check the bot logs and Supabase setup.",
                ephemeral=True,
            )
            return

        if not deleted:
            await interaction.followup.send(
                f"No saved profile exists for {member.mention}.",
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            f"Removed the saved profile for {member.mention}.",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MemberProfiles(bot))