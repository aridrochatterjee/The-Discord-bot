import discord
from discord.ext import commands

from bot.config import TOKEN


class DiscordBot(commands.Bot):
    """Main Discord bot."""

    def __init__(self) -> None:
        intents = discord.Intents.default()

        # Required for prefix commands and message filtering.
        intents.message_content = True

        # Required for member-related moderation commands.
        intents.members = True

        super().__init__(
            command_prefix=".",
            intents=intents,
            help_command=None,
        )

    async def setup_hook(self) -> None:
        """Load all bot cogs and sync slash commands."""

        await self.load_extension("bot.cogs.general")
        await self.load_extension("bot.cogs.moderation")
        await self.load_extension("bot.utils.status")

        await self.tree.sync()


bot = DiscordBot()


@bot.event
async def on_ready() -> None:
    """Run when the bot is ready."""

    if bot.user is None:
        return

    print("-" * 40)
    print(f"Logged in as {bot.user}")
    print("Prefix commands: .command")
    print("Slash commands: /command")
    print("-" * 40)


def main() -> None:
    """Start the Discord bot."""

    bot.run(TOKEN)


if __name__ == "__main__":
    main()