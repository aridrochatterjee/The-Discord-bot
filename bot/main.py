from __future__ import annotations

import logging
import discord
from discord.ext import commands

from bot.config import TOKEN
from bot.database.client import init_supabase
from bot.utils.http import close_session, get_session


logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("bot")


class DiscordBot(commands.Bot):
    """Main Horizon Devs Discord bot."""

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
        """Load database, shared sessions, cogs, and sync slash commands."""
        # 1. Initialize Supabase client
        await init_supabase()

        # 2. Warm up shared aiohttp ClientSession
        await get_session()

        # 3. Load bot extensions
        await self.load_extension("bot.cogs.general")
        await self.load_extension("bot.cogs.moderation")
        await self.load_extension("bot.cogs.dev_tools")
        await self.load_extension("bot.cogs.community")
        await self.load_extension("bot.cogs.reputation")
        await self.load_extension("bot.cogs.help")
        await self.load_extension("bot.utils.status")

        # 4. Register persistent views
        from bot.cogs.community import TechRolesView
        self.add_view(TechRolesView())

        # 5. Sync slash command tree
        await self.tree.sync()
        logger.info("Slash command tree synced successfully.")

    async def close(self) -> None:
        """Gracefully cleanup connections when the bot stops."""
        await close_session()
        await super().close()

    async def on_command_error(
        self,
        ctx: commands.Context,
        error: commands.CommandError,
    ) -> None:
        """Global handler for prefix and hybrid command errors."""
        if isinstance(error, commands.CommandNotFound):
            return

        if isinstance(error, commands.MissingPermissions):
            perms = ", ".join(error.missing_permissions)
            embed = discord.Embed(
                title="❌ Permission Denied",
                description=f"You need the following permission(s): `{perms}`",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
            return

        if isinstance(error, commands.BotMissingPermissions):
            perms = ", ".join(error.missing_permissions)
            embed = discord.Embed(
                title="❌ Bot Missing Permissions",
                description=f"I require the following permission(s) to do that: `{perms}`",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
            return

        if isinstance(error, commands.BadArgument):
            embed = discord.Embed(
                title="❌ Invalid Argument",
                description=str(error),
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
            return

        logger.error(f"Unhandled command error in {ctx.command}: {error}", exc_info=error)


bot = DiscordBot()


@bot.event
async def on_ready() -> None:
    """Run when the bot is connected and ready."""
    if bot.user is None:
        return

    print("-" * 40)
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("Horizon Devs Assistant is online.")
    print("Prefix commands: .command")
    print("Slash commands:  /command")
    print("-" * 40)


def main() -> None:
    """Start the Discord bot."""
    if not TOKEN:
        raise ValueError("DISCORD_TOKEN is not set in the .env file.")
    bot.run(TOKEN)


if __name__ == "__main__":
    main()