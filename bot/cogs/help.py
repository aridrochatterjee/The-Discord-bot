from __future__ import annotations

from typing import List

import discord
from discord.ext import commands


class HelpSelect(discord.ui.Select):
    """Dropdown menu to select command categories in the help interface."""

    def __init__(self, author: discord.User | discord.Member) -> None:
        self.author = author
        options = [
            discord.SelectOption(
                label="Developer Tools",
                description="Code execution, GitHub, PyPI, and cheat sheets",
                emoji="🛠️",
                value="dev_tools",
            ),
            discord.SelectOption(
                label="Moderation",
                description="Ban, kick, timeout, purge, and anti-invite filters",
                emoji="🛡️",
                value="moderation",
            ),
            discord.SelectOption(
                label="General Utilities",
                description="Latency, server stats, and user profiles",
                emoji="ℹ️",
                value="general",
            ),
            discord.SelectOption(
                label="Community & Karma",
                description="Reputation, member gratitude, and project showcase",
                emoji="🌟",
                value="community",
            ),
        ]
        super().__init__(
            placeholder="Select a category to view commands...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle user selection."""
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "❌ Only the person who invoked `/help` can use this menu.",
                ephemeral=True,
            )
            return

        choice = self.values[0]
        embed = self.get_category_embed(choice)
        await interaction.response.edit_message(embed=embed, view=self.view)

    def get_category_embed(self, category: str) -> discord.Embed:
        """Generate embed corresponding to the chosen category."""
        if category == "dev_tools":
            embed = discord.Embed(
                title="🛠️ Developer Tools Commands",
                description="Essential utilities for coding, packages, and references.",
                color=discord.Color.teal(),
            )
            embed.add_field(
                name="/run <language> <code>",
                value="Execute code in Python, JS, C++, Rust, Go, Bash, etc. in a sandbox.",
                inline=False,
            )
            embed.add_field(
                name="/github <owner/repo>",
                value="Fetch stars, forks, open issues, language, and license for any GitHub repository.",
                inline=False,
            )
            embed.add_field(
                name="/pypi <package>",
                value="Lookup package metadata, version, license, and install commands on PyPI.",
                inline=False,
            )
            embed.add_field(
                name="/cheat <query>",
                value="Quick cheat sheet notes for CLI commands or programming topics (e.g. `/cheat git cherry-pick`).",
                inline=False,
            )

        elif category == "moderation":
            embed = discord.Embed(
                title="🛡️ Moderation Commands & Protection",
                description="Server enforcement commands and automatic filtering.",
                color=discord.Color.red(),
            )
            embed.add_field(
                name="/ban <member> [reason]",
                value="Ban a member from the server and notify them via DM.",
                inline=False,
            )
            embed.add_field(
                name="/kick <member> [reason]",
                value="Kick a member from the server.",
                inline=False,
            )
            embed.add_field(
                name="/softban <member> [reason]",
                value="Ban and immediately unban to clear past 24h messages.",
                inline=False,
            )
            embed.add_field(
                name="/timeout <member> <duration> [reason]",
                value="Timeout a member (e.g. `10m`, `2h`, `7d`).",
                inline=False,
            )
            embed.add_field(
                name="/remove_timeout <member> [reason]",
                value="Remove an active timeout from a member.",
                inline=False,
            )
            embed.add_field(
                name="/unban <user_id> [reason]",
                value="Unban a member by their numeric Discord ID.",
                inline=False,
            )
            embed.add_field(
                name="/purge <amount>",
                value="Bulk delete up to 100 messages from the current channel.",
                inline=False,
            )
            embed.add_field(
                name="Auto-Filters",
                value="Automatically deletes Discord invite links and adult domain links with temporary warnings.",
                inline=False,
            )

        elif category == "general":
            embed = discord.Embed(
                title="ℹ️ General Utility Commands",
                description="Everyday informational commands.",
                color=discord.Color.blurple(),
            )
            embed.add_field(
                name="/ping",
                value="Check the bot websocket latency.",
                inline=False,
            )
            embed.add_field(
                name="/server_info",
                value="View server statistics, member counts, channel stats, and owner.",
                inline=False,
            )
            embed.add_field(
                name="/user_info [@member]",
                value="View account creation date, server join date, and roles.",
                inline=False,
            )

        else:  # community
            embed = discord.Embed(
                title="🌟 Community & Karma (Horizon Devs)",
                description="Community engagement, project discovery, and developer recognition.",
                color=discord.Color.gold(),
            )
            embed.add_field(
                name="/showcase",
                value="Submit your developer project with live demo & GitHub repo to get community feedback and upvotes.",
                inline=False,
            )
            embed.add_field(
                name="/techroles",
                value="Post the self-assignable tech stack roles panel (Frontend, Backend, Mobile, DevOps, AI, Python, etc.).",
                inline=False,
            )
            embed.add_field(
                name="/thank <member> [reason]",
                value="Award Dev Karma to a fellow developer who assisted you with code or debugging.",
                inline=False,
            )
            embed.add_field(
                name="/karma [@member]",
                value="Check your or a peer's Dev Karma points, developer rank title, and progress bar.",
                inline=False,
            )
            embed.add_field(
                name="/leaderboard",
                value="View the top 10 most helpful developers and contributors in the server.",
                inline=False,
            )

        embed.set_footer(text="Horizon Devs Bot • Use the dropdown below to switch categories")
        return embed


class HelpView(discord.ui.View):
    """Container view for the interactive help dropdown."""

    def __init__(self, author: discord.User | discord.Member) -> None:
        super().__init__(timeout=180)
        self.add_item(HelpSelect(author))


class HelpCog(commands.Cog, name="Help"):
    """Interactive help system."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(
        name="help",
        description="Explore Horizon Devs bot commands and features.",
    )
    async def help_command(self, ctx: commands.Context) -> None:
        """Display an interactive category-based help menu."""
        embed = discord.Embed(
            title="👋 Welcome to Horizon Devs Bot",
            description=(
                "I am the assistant bot for **Horizon Devs**!\n\n"
                "Use the interactive menu below to browse commands by category:\n"
                "• 🛠️ **Developer Tools** — Code runner, GitHub, PyPI, Cheat sheets\n"
                "• 🛡️ **Moderation** — Server security, punishments, auto-filter\n"
                "• ℹ️ **General Utilities** — Ping, server stats, user profiles\n"
                "• 🌟 **Community & Karma** — Reputation and project showcases\n\n"
                "*All commands support both prefix (`.command`) and slash (`/command`).*"
            ),
            color=discord.Color.blurple(),
        )
        embed.set_footer(
            text=f"Requested by {ctx.author}",
            icon_url=ctx.author.display_avatar.url,
        )

        view = HelpView(author=ctx.author)
        await ctx.send(embed=embed, view=view)


async def setup(bot: commands.Bot) -> None:
    """Load the Help cog."""
    await bot.add_cog(HelpCog(bot))
