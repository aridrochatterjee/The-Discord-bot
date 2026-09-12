import discord
from discord.ext import commands

from bot.config import TOKEN


class DiscordBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()

        super().__init__(
            command_prefix="!",
            intents=intents,
        )

    async def setup_hook(self) -> None:
        await self.load_extension("bot.cogs.general")
        await self.load_extension("bot.cogs.moderation")

        await self.tree.sync()


bot = DiscordBot()


@bot.event
async def on_ready() -> None:
    print(f"✅ Logged in as {bot.user}")


def main() -> None:
    bot.run(TOKEN)