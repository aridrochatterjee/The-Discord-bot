from __future__ import annotations

import logging

import discord
from discord.ext import commands

from bot.config import TOKEN
from bot.cogs.challenge import ChallengeView
from bot.cogs.bounty import BountyView
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

        # ============================================================
        # 1. INITIALIZE SUPABASE
        # ============================================================

        await init_supabase()

        # ============================================================
        # 2. WARM UP SHARED HTTP SESSION
        # ============================================================

        await get_session()

        # ============================================================
        # 3. LOAD BOT COGS
        # ============================================================

        await self.load_extension("bot.cogs.general")
        await self.load_extension("bot.cogs.moderation")
        await self.load_extension("bot.cogs.dev_tools")
        await self.load_extension("bot.cogs.community")
        await self.load_extension("bot.cogs.reputation")
        await self.load_extension("bot.cogs.challenge")
        await self.load_extension("bot.cogs.bounty")
        await self.load_extension("bot.cogs.help")

        # 🤖 OpenAI GPT Chatbot
        await self.load_extension("bot.cogs.gpt")

        # Bot status utilities
        await self.load_extension("bot.utils.status")

        logger.info("All bot extensions loaded successfully.")

        # ============================================================
        # 4. REGISTER PERSISTENT UI VIEWS
        # ============================================================

        # ShowcaseView requires a showcase_id, so it cannot be
        # registered here without loading each showcase from the database.

        self.add_view(ChallengeView())
        self.add_view(BountyView())

        logger.info("Persistent views registered successfully.")

        # ============================================================
        # 5. SYNC SLASH COMMANDS
        # ============================================================

        await self.tree.sync()

        logger.info(
            "Slash command tree synced successfully."
        )

    async def close(self) -> None:
        """Gracefully clean up connections when the bot stops."""

        await close_session()

        await super().close()

    async def on_command_error(
        self,
        ctx: commands.Context,
        error: commands.CommandError,
    ) -> None:
        """Global handler for prefix and hybrid command errors."""

        # Ignore unknown prefix commands.
        if isinstance(error, commands.CommandNotFound):
            return

        # ============================================================
        # PERMISSION ERRORS
        # ============================================================

        if isinstance(
            error,
            (
                commands.CheckFailure,
                commands.MissingPermissions,
            ),
        ):
            msg = str(error)

            if isinstance(error, commands.MissingPermissions):
                perms = ", ".join(
                    error.missing_permissions
                )

                msg = (
                    "You need the following permission(s): "
                    f"`{perms}`"
                )

            embed = discord.Embed(
                title="❌ Permission Denied",
                description=msg,
                color=discord.Color.red(),
            )

            await ctx.send(embed=embed)

            return

        # ============================================================
        # BOT MISSING PERMISSIONS
        # ============================================================

        if isinstance(
            error,
            commands.BotMissingPermissions,
        ):
            perms = ", ".join(
                error.missing_permissions
            )

            embed = discord.Embed(
                title="❌ Bot Missing Permissions",
                description=(
                    "I require the following permission(s) "
                    f"to do that: `{perms}`"
                ),
                color=discord.Color.red(),
            )

            await ctx.send(embed=embed)

            return

        # ============================================================
        # INVALID ARGUMENT
        # ============================================================

        if isinstance(
            error,
            commands.BadArgument,
        ):
            embed = discord.Embed(
                title="❌ Invalid Argument",
                description=str(error),
                color=discord.Color.red(),
            )

            await ctx.send(embed=embed)

            return

        # ============================================================
        # UNKNOWN ERROR
        # ============================================================

        logger.error(
            f"Unhandled command error in {ctx.command}: {error}",
            exc_info=error,
        )


# ============================================================
# BOT INSTANCE
# ============================================================

bot = DiscordBot()


# ============================================================
# BOT READY EVENT
# ============================================================

@bot.event
async def on_ready() -> None:
    """Run when the bot is connected and ready."""

    if bot.user is None:
        return

    print("-" * 40)

    print(
        f"Logged in as {bot.user} "
        f"(ID: {bot.user.id})"
    )

    print("Horizon Devs Assistant is online.")
    print("Prefix commands: .command")
    print("Slash commands: /command")
    print("GPT chatbot: Mention the bot!")

    print("-" * 40)


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    """Start the Discord bot."""

    if not TOKEN:
        raise ValueError(
            "DISCORD_TOKEN is not set in the .env file."
        )

    bot.run(TOKEN)


if __name__ == "__main__":
    main()