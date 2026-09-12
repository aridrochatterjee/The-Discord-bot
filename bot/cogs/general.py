import discord
from discord import app_commands
from discord.ext import commands


class General(commands.Cog):
    """General bot commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="ping",
        description="Check if the bot is alive.",
    )
    async def ping(self, interaction: discord.Interaction) -> None:
        latency = round(self.bot.latency * 1000)

        await interaction.response.send_message(
            f"{interaction.user.mention}, Pong! {latency}ms — "
            "stop pinging me, I'm alive 😭"
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(General(bot))