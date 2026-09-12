from __future__ import annotations

import discord
from discord.ext import commands, tasks


STATUS_ROTATE_SECONDS = 10


class StatusManager(commands.Cog):
    """Manage the bot's rotating Discord status."""

    FUN_MESSAGES = (
        "Works on my machine.",
        "git commit -m 'final_final_REAL'",
        "Production is just beta with confidence.",
        "Fixing one bug, unlocking three more.",
        "Ctrl+C. Ctrl+V. Senior Developer.",
        "This shouldn't be in production.",
        "Definitely not a skill issue.",
        "Writing code future me will hate.",
        "Pushing directly to main. What could go wrong?",
        "It compiled. Nobody knows why.",
    )

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.index = 0
        self.rotate_status.start()

    def total_users(self) -> int:
        """Return the total members across all servers."""

        return sum(
            guild.member_count or 0
            for guild in self.bot.guilds
        )

    def get_status(self) -> str:
        """Return the next status in the rotation."""

        statuses = (
            f"{self.total_users():,} users",
            f"{len(self.bot.guilds):,} servers",
            *self.FUN_MESSAGES,
        )

        status = statuses[self.index % len(statuses)]
        self.index += 1

        return status

    @tasks.loop(seconds=STATUS_ROTATE_SECONDS)
    async def rotate_status(self) -> None:
        """Update the bot's Discord presence."""

        await self.bot.change_presence(
            status=discord.Status.online,
            activity=discord.Game(name=self.get_status()),
        )

    @rotate_status.before_loop
    async def before_rotate_status(self) -> None:
        """Wait until the bot is ready."""

        await self.bot.wait_until_ready()

    def cog_unload(self) -> None:
        """Stop the background task when the cog unloads."""

        self.rotate_status.cancel()


async def setup(bot: commands.Bot) -> None:
    """Load the status manager."""

    await bot.add_cog(StatusManager(bot))