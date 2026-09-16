
"""
Community Cog
-------------

Horizon Devs community features.

Current features:
    /showcase - Submit a developer project showcase.

Showcase features:
    - Supabase persistence
    - GitHub repository link
    - Live demo link
    - Project description
    - Tech stack
    - Upvote button
    - One vote per user (handled by database layer)
    - Persistent voting button
    - Automatic discussion thread
"""

from __future__ import annotations

import logging
from typing import Optional
from urllib.parse import urlparse

import discord
from discord.ext import commands

from bot.database.queries import (
    create_showcase,
    update_showcase_message,
    vote_showcase,
)

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

MAX_PROJECT_TITLE = 100
MAX_TECH_STACK = 150
MAX_DESCRIPTION = 1000

MAX_GITHUB_URL = 500
MAX_DEMO_URL = 500

THREAD_NAME_LIMIT = 100

SHOWCASE_COLOR = discord.Color.teal()


# =============================================================================
# URL HELPERS
# =============================================================================


def normalize_url(url: str) -> Optional[str]:
    """
    Normalize and validate a user-provided URL.

    Accepted examples:
        github.com/user/project
        https://github.com/user/project
        https://example.com

    Rejected:
        javascript:...
        discord.gg/...
        random malformed values
    """

    clean = url.strip()

    if not clean:
        return None

    if len(clean) > MAX_GITHUB_URL:
        return None

    # Add protocol when the user omitted it.
    if not clean.startswith(("http://", "https://")):
        clean = f"https://{clean}"

    try:
        parsed = urlparse(clean)
    except ValueError:
        return None

    if parsed.scheme not in {"http", "https"}:
        return None

    if not parsed.netloc:
        return None

    # Prevent obviously malformed hosts.
    if "." not in parsed.netloc and parsed.netloc.lower() != "localhost":
        return None

    return clean


def normalize_github_url(url: str) -> Optional[str]:
    """
    Normalize a GitHub repository URL.

    Only github.com URLs are accepted for the GitHub field.
    """

    clean = normalize_url(url)

    if not clean:
        return None

    try:
        parsed = urlparse(clean)
    except ValueError:
        return None

    hostname = (parsed.hostname or "").lower()

    if hostname not in {"github.com", "www.github.com"}:
        return None

    # A repository URL should have at least:
    # /username/repository
    parts = [
        part
        for part in parsed.path.strip("/").split("/")
        if part
    ]

    if len(parts) < 2:
        return None

    return clean


# =============================================================================
# SHOWCASE VOTE BUTTON
# =============================================================================


class ShowcaseVoteButton(discord.ui.Button):
    """
    Persistent upvote button for a showcase.

    The database is responsible for preventing duplicate votes.
    """

    def __init__(
        self,
        showcase_id: int,
        upvotes: int = 0,
    ) -> None:
        super().__init__(
            label=f"Upvote ({upvotes})",
            style=discord.ButtonStyle.success,
            custom_id=f"showcase:vote:{showcase_id}",
        )

        self.showcase_id = showcase_id

    async def callback(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """Process a showcase upvote."""

        try:
            success, message, new_votes = await vote_showcase(
                showcase_id=self.showcase_id,
                user_id=interaction.user.id,
            )

        except Exception:
            logger.exception(
                "Failed to vote on showcase %s by user %s",
                self.showcase_id,
                interaction.user.id,
            )

            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Something went wrong while processing your vote.",
                    ephemeral=True,
                )

            return

        if not success:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    message or "You couldn't vote on this showcase.",
                    ephemeral=True,
                )

            return

        # Update the button attached to this interaction.
        self.label = f"Upvote ({new_votes})"

        # Update the showcase embed.
        message_obj = interaction.message

        if message_obj and message_obj.embeds:
            try:
                embed = message_obj.embeds[0]

                embed.set_footer(
                    text=(
                        f"{new_votes} upvotes • "
                        "Horizon Devs Showcase"
                    ),
                    icon_url=(
                        embed.footer.icon_url
                        if embed.footer
                        else discord.Embed.Empty
                    ),
                )

                # Create a fresh view so the persistent button has
                # the latest vote count.
                updated_view = ShowcaseView(
                    showcase_id=self.showcase_id,
                    upvotes=new_votes,
                )

                await message_obj.edit(
                    embed=embed,
                    view=updated_view,
                )

            except discord.NotFound:
                logger.warning(
                    "Showcase message no longer exists: %s",
                    self.showcase_id,
                )

            except discord.Forbidden:
                logger.warning(
                    "Missing permission to update showcase %s",
                    self.showcase_id,
                )

            except discord.HTTPException:
                logger.exception(
                    "Failed to update showcase message %s",
                    self.showcase_id,
                )

        # Respond to the interaction exactly once.
        if not interaction.response.is_done():
            await interaction.response.send_message(
                f"{message or 'Vote recorded.'} "
                f"Total votes: **{new_votes}**",
                ephemeral=True,
            )


# =============================================================================
# SHOWCASE VIEW
# =============================================================================


class ShowcaseView(discord.ui.View):
    """
    Persistent view attached to showcase messages.

    timeout=None is required for persistent Discord components.
    """

    def __init__(
        self,
        showcase_id: int,
        upvotes: int = 0,
    ) -> None:
        super().__init__(timeout=None)

        self.add_item(
            ShowcaseVoteButton(
                showcase_id=showcase_id,
                upvotes=upvotes,
            )
        )


# =============================================================================
# SHOWCASE MODAL
# =============================================================================


class ShowcaseModal(
    discord.ui.Modal,
    title="Submit Project Showcase",
):
    """Interactive project submission form."""

    project_title = discord.ui.TextInput(
        label="Project Name",
        placeholder="e.g. CodePulse — Live Pair Programming Tool",
        min_length=2,
        max_length=MAX_PROJECT_TITLE,
        required=True,
    )

    tech_stack = discord.ui.TextInput(
        label="Tech Stack",
        placeholder="e.g. React, TypeScript, Node.js, Supabase",
        min_length=2,
        max_length=MAX_TECH_STACK,
        required=True,
    )

    description = discord.ui.TextInput(
        label="Project Summary",
        style=discord.TextStyle.paragraph,
        placeholder=(
            "What does it do? What problem does it solve? "
            "What did you learn?"
        ),
        min_length=10,
        max_length=MAX_DESCRIPTION,
        required=True,
    )

    github_url = discord.ui.TextInput(
        label="GitHub Repository (Optional)",
        placeholder="https://github.com/username/project",
        max_length=MAX_GITHUB_URL,
        required=False,
    )

    demo_url = discord.ui.TextInput(
        label="Live Demo (Optional)",
        placeholder="https://myproject.com",
        max_length=MAX_DEMO_URL,
        required=False,
    )

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """Handle showcase submission."""

        # ---------------------------------------------------------------------
        # Basic context validation
        # ---------------------------------------------------------------------

        if interaction.guild is None:
            await interaction.response.send_message(
                "Showcases can only be submitted inside a server.",
                ephemeral=True,
            )
            return

        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "I couldn't identify your server membership.",
                ephemeral=True,
            )
            return

        if interaction.channel is None:
            await interaction.response.send_message(
                "I couldn't determine which channel to publish this in.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        author = interaction.user
        guild = interaction.guild
        channel = interaction.channel

        # ---------------------------------------------------------------------
        # Clean input
        # ---------------------------------------------------------------------

        title = self.project_title.value.strip()
        tech_stack = self.tech_stack.value.strip()
        description = self.description.value.strip()

        github_input = self.github_url.value.strip()
        demo_input = self.demo_url.value.strip()

        # ---------------------------------------------------------------------
        # Validate required fields
        # ---------------------------------------------------------------------

        if not title:
            await interaction.followup.send(
                "Project name cannot be empty.",
                ephemeral=True,
            )
            return

        if not tech_stack:
            await interaction.followup.send(
                "Tech stack cannot be empty.",
                ephemeral=True,
            )
            return

        if not description:
            await interaction.followup.send(
                "Project description cannot be empty.",
                ephemeral=True,
            )
            return

        # ---------------------------------------------------------------------
        # Validate URLs
        # ---------------------------------------------------------------------

        clean_github: Optional[str] = None

        if github_input:
            clean_github = normalize_github_url(github_input)

            if not clean_github:
                await interaction.followup.send(
                    "That GitHub URL doesn't look valid.\n"
                    "Example: `https://github.com/username/project`",
                    ephemeral=True,
                )
                return

        clean_demo: Optional[str] = None

        if demo_input:
            clean_demo = normalize_url(demo_input)

            if not clean_demo:
                await interaction.followup.send(
                    "That demo URL doesn't look valid.\n"
                    "Example: `https://example.com`",
                    ephemeral=True,
                )
                return

        # ---------------------------------------------------------------------
        # Save to database
        # ---------------------------------------------------------------------

        try:
            showcase_data = await create_showcase(
                author_id=author.id,
                guild_id=guild.id,
                title=title,
                description=description,
                tech_stack=tech_stack,
                github_url=clean_github,
                demo_url=clean_demo,
            )

        except Exception:
            logger.exception(
                "Failed to create showcase for user %s in guild %s",
                author.id,
                guild.id,
            )

            await interaction.followup.send(
                "I couldn't save your showcase right now. "
                "Please try again later.",
                ephemeral=True,
            )
            return

        if not showcase_data:
            logger.error(
                "create_showcase returned no data for user %s",
                author.id,
            )

            await interaction.followup.send(
                "The showcase couldn't be created.",
                ephemeral=True,
            )
            return

        showcase_id = showcase_data.get("id")

        if not showcase_id:
            logger.error(
                "Showcase was created without an ID: %r",
                showcase_data,
            )

            await interaction.followup.send(
                "The showcase was saved, but I couldn't publish it "
                "because it has no database ID.",
                ephemeral=True,
            )
            return

        # ---------------------------------------------------------------------
        # Build embed
        # ---------------------------------------------------------------------

        embed = discord.Embed(
            title=title,
            description=description,
            color=SHOWCASE_COLOR,
        )

        embed.set_author(
            name=f"{author.display_name}'s Project Showcase",
            icon_url=author.display_avatar.url,
        )

        embed.add_field(
            name="Tech Stack",
            value=f"`{tech_stack}`",
            inline=False,
        )

        links: list[str] = []

        if clean_github:
            links.append(
                f"[GitHub Repository]({clean_github})"
            )

        if clean_demo:
            links.append(
                f"[Live Demo]({clean_demo})"
            )

        if links:
            embed.add_field(
                name="Project Links",
                value=" • ".join(links),
                inline=False,
            )

        guild_icon_url = (
            guild.icon.url
            if guild.icon
            else None
        )

        embed.set_footer(
            text="0 upvotes • Horizon Devs Showcase",
            icon_url=guild_icon_url or discord.Embed.Empty,
        )

        # ---------------------------------------------------------------------
        # Publish showcase
        # ---------------------------------------------------------------------

        view = ShowcaseView(
            showcase_id=showcase_id,
            upvotes=0,
        )

        try:
            message = await channel.send(
                embed=embed,
                view=view,
            )

        except discord.Forbidden:
            logger.exception(
                "Missing permission to publish showcase %s "
                "in channel %s",
                showcase_id,
                channel.id,
            )

            await interaction.followup.send(
                "I saved your showcase, but I don't have permission "
                "to publish it in this channel.",
                ephemeral=True,
            )
            return

        except discord.HTTPException:
            logger.exception(
                "Discord API error publishing showcase %s",
                showcase_id,
            )

            await interaction.followup.send(
                "I saved your showcase, but Discord rejected the "
                "publication. Please contact a moderator.",
                ephemeral=True,
            )
            return

        # ---------------------------------------------------------------------
        # Associate Discord message with database record
        # ---------------------------------------------------------------------

        try:
            await update_showcase_message(
                showcase_id=showcase_id,
                message_id=message.id,
                channel_id=channel.id,
            )

        except Exception:
            # The showcase is already published, so don't tell the user
            # that the entire operation failed.
            logger.exception(
                "Failed to associate showcase %s with Discord message %s",
                showcase_id,
                message.id,
            )

        # ---------------------------------------------------------------------
        # Create discussion thread
        # ---------------------------------------------------------------------

        try:
            thread_name = (
                f"{title[:THREAD_NAME_LIMIT - 13]} Discussion"
            )

            thread = await message.create_thread(
                name=thread_name,
                auto_archive_duration=1440,
            )

            await thread.send(
                f"Welcome to the discussion for **{title}**!\n"
                f"Share feedback, bug reports, and suggestions "
                f"with {author.mention} here."
            )

        except discord.Forbidden:
            logger.warning(
                "Missing permission to create showcase thread %s",
                showcase_id,
            )

        except discord.HTTPException:
            logger.warning(
                "Failed to create discussion thread for showcase %s",
                showcase_id,
            )

        # ---------------------------------------------------------------------
        # Success response
        # ---------------------------------------------------------------------

        await interaction.followup.send(
            "Your project showcase has been published!",
            ephemeral=True,
        )


# =============================================================================
# COMMUNITY COG
# =============================================================================


class Community(commands.Cog, name="Community"):
    """
    Community functionality.

    Currently focused on project showcases.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

        logger.info(
            "Community cog initialized successfully."
        )

    # =========================================================================
    # LIFECYCLE
    # =========================================================================

    async def cog_load(self) -> None:
        """
        Register persistent views when the cog loads.

        Existing showcase messages keep working after a bot restart.
        """

        logger.info(
            "Community cog loaded. Persistent showcase views "
            "will be restored from database records when available."
        )

        # The existing query layer shown in the supplied cog does not expose
        # a function for retrieving ALL showcase IDs/message records.
        #
        # Therefore we intentionally don't invent a database function here.
        #
        # When your query layer provides something like:
        #
        #     get_all_showcases()
        #
        # you can restore every persistent ShowcaseView here.
        #
        # The button custom_id itself remains deterministic, so newly created
        # views work normally. Existing views require registration after
        # restart if Discord sends their component interaction to the bot.

    # =========================================================================
    # /SHOWCASE
    # =========================================================================

    @commands.hybrid_command(
        name="showcase",
        description=(
            "Submit your developer project to the community."
        ),
    )
    @commands.guild_only()
    async def showcase(
        self,
        ctx: commands.Context,
    ) -> None:
        """Open the project showcase submission modal."""

        if ctx.interaction:
            await ctx.interaction.response.send_modal(
                ShowcaseModal()
            )
            return

        # Prefix commands cannot open a Discord modal.
        embed = discord.Embed(
            title="Horizon Devs Project Showcase",
            description=(
                "Use the slash command **/showcase** "
                "to open the project submission form."
            ),
            color=discord.Color.blurple(),
        )

        await ctx.send(embed=embed)


# =============================================================================
# SETUP
# =============================================================================


async def setup(
    bot: commands.Bot,
) -> None:
    """Load the Community cog."""

    await bot.add_cog(
        Community(bot)
    )

    logger.info(
        "Community cog loaded successfully."
    )