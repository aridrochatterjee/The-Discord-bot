import discord
from discord import app_commands
from discord.ext import commands


class Moderation(commands.Cog):
    """Moderation commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="purge",
        description="Delete a specified number of messages.",
    )
    @app_commands.describe(amount="Number of messages to delete")
    async def purge(
        self,
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 1, 100],
    ) -> None:

        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message(
                "You don't have permission to manage messages.",
                ephemeral=True,
            )
            return

        if not interaction.app_permissions.manage_messages:
            await interaction.response.send_message(
                "I don't have permission to manage messages.",
                ephemeral=True,
            )
            return

        channel = interaction.channel

        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "This command can only be used in a text channel.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        deleted = await channel.purge(limit=amount)

        await interaction.followup.send(
            f"🗑️ Deleted {len(deleted)} messages.",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Moderation(bot))