import os
from pathlib import Path

import discord
from discord import app_commands
from dotenv import load_dotenv


# Load environment variables
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise ValueError("DISCORD_TOKEN is not set in the .env file.")


# Configure Discord intents
intents = discord.Intents.default()


class DiscordBot(discord.Client):
    def __init__(self) -> None:
        super().__init__(intents=intents)

        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        await self.tree.sync()


bot = DiscordBot()


@bot.event
async def on_ready() -> None:
    print(f"✅ Logged in as {bot.user}")


@bot.tree.command(
    name="ping",
    description="Check if the bot is alive.",
)
async def ping(interaction: discord.Interaction) -> None:
    latency = round(bot.latency * 1000)

    await interaction.response.send_message(
        f"{interaction.user.mention}, {latency}ms : stop pinging me. I'm alive 😭"
    )



@bot.tree.command(
    name="purge",
    description="Delete a specified number of messages.",
)
@app_commands.describe(amount="Number of messages to delete")
async def purge(
    interaction: discord.Interaction,
    amount: app_commands.Range[int, 1, 100],
) -> None:

    # Check if the command is used in a server
    if interaction.guild is None:
        await interaction.response.send_message(
            "This command can only be used in a server.",
            ephemeral=True,
        )
        return

    # Check permissions
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message(
            " You don't have permission to manage messages.",
            ephemeral=True,
        )
        return

    # Check bot permissions
    if not interaction.app_permissions.manage_messages:
        await interaction.response.send_message(
            "I don't have permission to manage messages.",
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True)

    channel = interaction.channel

    if not isinstance(channel, discord.TextChannel):
        await interaction.followup.send(
            "This command can only be used in a text channel.",
            ephemeral=True,
        )
        return

    deleted = await channel.purge(limit=amount)

    await interaction.followup.send(
        f"Deleted {len(deleted)} messages.",
        ephemeral=False,
    )


bot.run(TOKEN)