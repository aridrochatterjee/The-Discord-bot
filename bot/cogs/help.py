
from __future__ import annotations

import discord
from discord.ext import commands


class HelpSelect(discord.ui.Select):
    """Dropdown used to switch between bot command categories."""

    def __init__(self, author: discord.User | discord.Member) -> None:
        self.author = author

        options = [
            discord.SelectOption(
                label="Developer Tools",
                description="GitHub, packages, JSON, regex, diffs, and cheat sheets",
                emoji="🛠️",
                value="dev_tools",
            ),
            discord.SelectOption(
                label="Moderation",
                description="Server moderation and automatic protection",
                emoji="🛡️",
                value="moderation",
            ),
            discord.SelectOption(
                label="General Utilities",
                description="Bot, server, and member information",
                emoji="ℹ️",
                value="general",
            ),
            discord.SelectOption(
                label="Community",
                description="Challenges, bounties, karma, and showcases",
                emoji="🌟",
                value="community",
            ),
        ]

        super().__init__(
            placeholder="Select a category...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle category selection."""

        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "Only the person who opened this help menu can use it.",
                ephemeral=True,
            )
            return

        category = self.values[0]
        embed = self.get_category_embed(category)

        await interaction.response.edit_message(
            embed=embed,
            view=self.view,
        )

    def get_category_embed(self, category: str) -> discord.Embed:
        """Build the help embed for a specific category."""

        if category == "dev_tools":
            embed = discord.Embed(
                title="🛠️ Developer Tools",
                description=(
                    "Useful tools for developers working with GitHub, "
                    "Python, JavaScript, JSON, regex, and more."
                ),
                color=discord.Color.teal(),
            )

            embed.add_field(
                name="/github <owner/repo>",
                value=(
                    "Look up a GitHub repository and view information such as "
                    "stars, forks, issues, language, and license."
                ),
                inline=False,
            )

            embed.add_field(
                name="/github-user <username>",
                value=(
                    "Look up a GitHub user and view their public profile, "
                    "repositories, followers, and other account information."
                ),
                inline=False,
            )

            embed.add_field(
                name="/github-commits <owner/repo>",
                value=(
                    "View the latest commits from a GitHub repository."
                ),
                inline=False,
            )

            embed.add_field(
                name="/pypi <package>",
                value=(
                    "Look up a Python package on PyPI, including its version, "
                    "description, license, requirements, and links."
                ),
                inline=False,
            )

            embed.add_field(
                name="/npm <package>",
                value=(
                    "Look up a Node.js package, including version, downloads, "
                    "license, dependencies, and repository information."
                ),
                inline=False,
            )

            embed.add_field(
                name="/cheat <query>",
                value=(
                    "Get a quick cheat sheet for CLI commands and programming "
                    "topics. Example: `/cheat git cherry-pick`."
                ),
                inline=False,
            )

            embed.add_field(
                name="/json <data>",
                value=(
                    "Validate and pretty-print JSON directly in Discord."
                ),
                inline=False,
            )

            embed.add_field(
                name="/diff",
                value=(
                    "Compare two pieces of text and see what changed."
                ),
                inline=False,
            )

            embed.add_field(
                name="/regex",
                value=(
                    "Test a regular expression against text and inspect "
                    "the matches."
                ),
                inline=False,
            )

        elif category == "moderation":
            embed = discord.Embed(
                title="🛡️ Moderation",
                description=(
                    "Tools for moderators and administrators to manage "
                    "the server and handle problematic content."
                ),
                color=discord.Color.red(),
            )

            embed.add_field(
                name="/ban <member> [reason]",
                value="Ban a member from the server.",
                inline=False,
            )

            embed.add_field(
                name="/kick <member> [reason]",
                value="Kick a member from the server.",
                inline=False,
            )

            embed.add_field(
                name="/softban <member> [reason]",
                value=(
                    "Ban and immediately unban a member to remove their "
                    "recent messages."
                ),
                inline=False,
            )

            embed.add_field(
                name="/timeout <member> <duration> [reason]",
                value=(
                    "Temporarily prevent a member from communicating. "
                    "Example: `/timeout @user 10m`."
                ),
                inline=False,
            )

            embed.add_field(
                name="/remove_timeout <member> [reason]",
                value="Remove an active timeout from a member.",
                inline=False,
            )

            embed.add_field(
                name="/unban <user_id> [reason]",
                value="Unban a user using their Discord ID.",
                inline=False,
            )

            embed.add_field(
                name="/purge <amount>",
                value=(
                    "Bulk-delete messages from the current channel. "
                    "Maximum: 100 messages."
                ),
                inline=False,
            )

            embed.add_field(
                name="Automatic Protection",
                value=(
                    "The bot automatically filters configured Discord "
                    "invite and blocked-domain links."
                ),
                inline=False,
            )

        elif category == "general":
            embed = discord.Embed(
                title="ℹ️ General Utilities",
                description=(
                    "Simple commands for checking the bot, server, "
                    "and Discord users."
                ),
                color=discord.Color.blurple(),
            )

            embed.add_field(
                name="/ping",
                value="Check the bot's current WebSocket latency.",
                inline=False,
            )

            embed.add_field(
                name="/server_info",
                value=(
                    "View server information such as member count, "
                    "channels, and server owner."
                ),
                inline=False,
            )

            embed.add_field(
                name="/user_info [@member]",
                value=(
                    "View information about a Discord user, including "
                    "account creation, server join date, and roles."
                ),
                inline=False,
            )

        else:
            embed = discord.Embed(
                title="🌟 Community",
                description=(
                    "Features built around developer participation, "
                    "recognition, challenges, and community projects."
                ),
                color=discord.Color.gold(),
            )

            embed.add_field(
                name="/showcase",
                value=(
                    "Share a developer project with the community, "
                    "including GitHub and demo links."
                ),
                inline=False,
            )

            embed.add_field(
                name="/challenge post",
                value=(
                    "Create a developer challenge for the community."
                ),
                inline=False,
            )

            embed.add_field(
                name="/challenge list",
                value=(
                    "View currently available developer challenges."
                ),
                inline=False,
            )

            embed.add_field(
                name="/challenge award",
                value=(
                    "Award Karma to a member who completed a challenge."
                ),
                inline=False,
            )

            embed.add_field(
                name="/challenge end",
                value=(
                    "End an active developer challenge."
                ),
                inline=False,
            )

            embed.add_field(
                name="/bounty create",
                value=(
                    "Create a coding bounty with a Karma reward."
                ),
                inline=False,
            )

            embed.add_field(
                name="/bounty list",
                value=(
                    "View currently open coding bounties."
                ),
                inline=False,
            )

            embed.add_field(
                name="/bounty accept",
                value=(
                    "Accept a bounty and assign it to a developer."
                ),
                inline=False,
            )

            embed.add_field(
                name="/bounty cancel",
                value=(
                    "Cancel an open bounty."
                ),
                inline=False,
            )

            embed.add_field(
                name="/thank <member> [reason]",
                value=(
                    "Thank another developer and award them Dev Karma."
                ),
                inline=False,
            )

            embed.add_field(
                name="/karma [@member]",
                value=(
                    "View your or another member's Dev Karma and rank."
                ),
                inline=False,
            )

            embed.add_field(
                name="/leaderboard",
                value=(
                    "View the server's top contributors and helpful members."
                ),
                inline=False,
            )

        embed.set_footer(
            text="Horizon Devs Bot • Select another category to continue"
        )

        return embed


class HelpView(discord.ui.View):
    """Interactive help menu."""

    def __init__(self, author: discord.User | discord.Member) -> None:
        super().__init__(timeout=180)

        self.author = author
        self.add_item(HelpSelect(author))


class HelpCog(commands.Cog, name="Help"):
    """Interactive help system for Horizon Devs Bot."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(
        name="help",
        description="Explore Horizon Devs bot commands and features.",
    )
    async def help_command(self, ctx: commands.Context) -> None:
        """Display the interactive help menu."""

        embed = discord.Embed(
            title="👋 Horizon Devs Bot",
            description=(
                "Welcome to the **Horizon Devs** bot.\n\n"
                "Use the dropdown below to explore available commands.\n\n"
                "**Developer Tools**\n"
                "GitHub, PyPI, npm, JSON, regex, diffs, and cheat sheets.\n\n"
                "**Moderation**\n"
                "Server moderation and automatic protection.\n\n"
                "**General Utilities**\n"
                "Bot, server, and member information.\n\n"
                "**Community**\n"
                "Challenges, bounties, Karma, and project showcases."
            ),
            color=discord.Color.blurple(),
        )

        embed.set_footer(
            text=f"Requested by {ctx.author}",
            icon_url=ctx.author.display_avatar.url,
        )

        view = HelpView(author=ctx.author)

        await ctx.send(
            embed=embed,
            view=view,
        )


async def setup(bot: commands.Bot) -> None:
    """Load the Help cog."""

    await bot.add_cog(HelpCog(bot))
