from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlparse
import discord
from discord.ext import commands
from bot.database.queries import (
    award_challenge_points,
    close_challenge,
    create_challenge,
    get_challenge,
    get_challenge_by_message,
    get_challenge_submissions,
    list_challenges,
    submit_challenge_entry,
    update_challenge_submission_attachment,
    update_challenge_message,
    update_challenge_submission_message,
    update_challenge_submission_status,
)
from bot.utils.checks import is_admin_or_owner
# =============================================================================
# CONFIGURATION
# =============================================================================
MIN_DURATION_DAYS = 1
MAX_DURATION_DAYS = 30
MIN_POINTS = 0
MAX_POINTS = 1000
MAX_TITLE_LENGTH = 100
MAX_DESCRIPTION_LENGTH = 4000
MAX_RULES_LENGTH = 2000
MAX_NOTES_LENGTH = 1000
MAX_URL_LENGTH = 500
MAX_CHALLENGES_TO_LIST = 10
VALID_DIFFICULTIES = {
    "easy": "Easy",
    "medium": "Medium",
    "hard": "Hard",
}
# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================
def utc_now() -> datetime:
    """Return the current UTC time."""
    return datetime.now(timezone.utc)
def clean_text(value: Optional[str]) -> str:
    """Clean normal single-line user input."""
    if not value:
        return ""
    return " ".join(value.strip().split())
def clean_multiline_text(value: Optional[str]) -> str:
    """Clean multiline user input while preserving line breaks."""
    if not value:
        return ""
    lines = []
    for line in value.strip().splitlines():
        line = line.strip()
        if line:
            lines.append(line)
    return "\n".join(lines)
def truncate_text(value: str, limit: int) -> str:
    """Safely truncate text for Discord."""
    if len(value) <= limit:
        return value
    if limit <= 3:
        return value[:limit]
    return value[: limit - 3].rstrip() + "..."


def split_code_for_discord(code: str) -> list[str]:
    """Split code into Discord-safe chunks without changing its contents."""
    # Leave room for the surrounding ```text fences.
    max_chunk_length = 1970
    chunks: list[str] = []
    remaining = code

    while len(remaining) > max_chunk_length:
        split_at = remaining.rfind("\n", 0, max_chunk_length + 1)
        if split_at <= 0:
            split_at = max_chunk_length
        else:
            split_at += 1
        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:]

    if remaining or not chunks:
        chunks.append(remaining)

    return chunks
def parse_datetime(value: object) -> Optional[datetime]:
    """Convert a database timestamp into a timezone-aware datetime."""
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
def normalize_difficulty(value: str) -> Optional[str]:
    """Normalize difficulty input."""
    if not value:
        return None
    return VALID_DIFFICULTIES.get(
        value.strip().lower()
    )
def is_valid_url(value: str) -> bool:
    """Check whether a string is a valid HTTP/HTTPS URL."""
    if not value:
        return False
    if len(value) > MAX_URL_LENGTH:
        return False
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    return (
        parsed.scheme.lower() in {"http", "https"}
        and bool(parsed.netloc)
    )
def is_valid_github_url(value: str) -> bool:
    """Check whether a URL points to GitHub."""
    if not is_valid_url(value):
        return False
    try:
        hostname = urlparse(value).hostname
    except ValueError:
        return False
    if not hostname:
        return False
    hostname = hostname.lower()
    return (
        hostname == "github.com"
        or hostname.endswith(".github.com")
    )
async def send_ephemeral_or_normal(
    ctx: commands.Context,
    message: str,
) -> None:
    """
    Send an ephemeral response for slash commands.
    Prefix commands cannot use ephemeral messages, so they receive
    a normal message instead.
    """
    if ctx.interaction is not None:
        await ctx.send(
            message,
            ephemeral=True,
        )
    else:
        await ctx.send(message)
# =============================================================================
# CHALLENGE SUBMISSION MODAL
# =============================================================================
class ChallengeSubmissionModal(discord.ui.Modal):
    """Modal used by members to submit challenge solutions."""
    def __init__(
        self,
        challenge_id: int,
        challenge_title: str,
        thread_id: Optional[int] = None,
    ) -> None:
        title = clean_text(challenge_title)
        if not title:
            title = "Developer Challenge"
        title = truncate_text(title, 35)
        super().__init__(
            title=f"Submit: {title}"
        )
        self.challenge_id = challenge_id
        self.thread_id = thread_id
        # ---------------------------------------------------------------------
        # GitHub URL (optional)
        # ---------------------------------------------------------------------
        self.github_url_input = discord.ui.TextInput(
            label="GitHub Repository (optional)",
            placeholder="https://github.com/username/project",
            required=False,
            max_length=MAX_URL_LENGTH,
        )
        self.add_item(self.github_url_input)
        # ---------------------------------------------------------------------
        # Code (optional)
        # ---------------------------------------------------------------------
        self.code_input = discord.ui.TextInput(
            label="Code (optional)",
            style=discord.TextStyle.paragraph,
            placeholder="Paste your solution/code here if you are not submitting a repository.",
            required=False,
            max_length=4000,
        )
        self.add_item(self.code_input)
        # ---------------------------------------------------------------------
        # Demo URL
        # ---------------------------------------------------------------------
        self.demo_url_input = discord.ui.TextInput(
            label="Live Demo URL",
            placeholder="https://your-project.example",
            required=False,
            max_length=MAX_URL_LENGTH,
        )
        self.add_item(
            self.demo_url_input
        )
        # ---------------------------------------------------------------------
        # Difficulty
        # ---------------------------------------------------------------------
        self.difficulty_input = discord.ui.TextInput(
            label="Difficulty",
            placeholder="Easy, Medium, or Hard",
            default="Medium",
            required=True,
            max_length=20,
        )
        self.add_item(
            self.difficulty_input
        )
        # ---------------------------------------------------------------------
        # Notes
        # ---------------------------------------------------------------------
        self.notes_input = discord.ui.TextInput(
            label="Implementation Notes",
            style=discord.TextStyle.paragraph,
            placeholder=(
                "Explain what you built, important decisions, "
                "or features you added."
            ),
            required=False,
            max_length=MAX_NOTES_LENGTH,
        )
        self.add_item(
            self.notes_input
        )
    async def on_submit(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """Process a challenge submission."""
        if interaction.guild is None:
            await interaction.followup.send(
                "This can only be used inside a server.",
                ephemeral=True,
            )
            return

        # A submission touches the database and Discord, so acknowledge the
        # modal immediately. All later responses use the follow-up webhook.
        await interaction.response.defer(ephemeral=True)
        # ---------------------------------------------------------------------
        # Read input
        # ---------------------------------------------------------------------
        github_url = (
            self.github_url_input.value.strip()
            or None
        )
        # Preserve source code exactly as entered. Indentation and whitespace
        # are part of the submitted source and must never be normalized.
        code = self.code_input.value
        if code == "":
            code = None
        demo_url = (
            self.demo_url_input.value.strip()
            or None
        )
        difficulty = normalize_difficulty(
            self.difficulty_input.value
        )
        notes = clean_multiline_text(
            self.notes_input.value
        )
        if not notes:
            notes = None
        # ---------------------------------------------------------------------
        # Validate submission content
        # ---------------------------------------------------------------------
        if not any((github_url, demo_url, code, notes)):
            await interaction.followup.send(
                "Please submit at least one of the following: code, "
                "GitHub repository, live demo URL, or implementation notes.",
                ephemeral=True,
            )
            return
        # ---------------------------------------------------------------------
        # Validate GitHub URL when provided
        # ---------------------------------------------------------------------
        if github_url and not is_valid_github_url(github_url):
            await interaction.followup.send(
                "The GitHub repository URL is invalid.\n\n"
                "Example:\n"
                "`https://github.com/username/project`",
                ephemeral=True,
            )
            return
        # ---------------------------------------------------------------------
        # Validate demo URL
        # ---------------------------------------------------------------------
        if demo_url and not is_valid_url(demo_url):
            await interaction.followup.send(
                "The live demo URL is invalid.\n"
                "Use a URL beginning with `https://`.",
                ephemeral=True,
            )
            return
        # ---------------------------------------------------------------------
        # Validate difficulty
        # ---------------------------------------------------------------------
        if difficulty is None:
            await interaction.followup.send(
                "Difficulty must be one of:\n"
                "`Easy`, `Medium`, or `Hard`.",
                ephemeral=True,
            )
            return
        # ---------------------------------------------------------------------
        # Fetch challenge
        # ---------------------------------------------------------------------
        try:
            challenge = await get_challenge(
                self.challenge_id
            )
        except Exception:
            challenge = None
        if not challenge:
            await interaction.followup.send(
                "This challenge could not be found.",
                ephemeral=True,
            )
            return
        # ---------------------------------------------------------------------
        # Verify guild
        # ---------------------------------------------------------------------
        challenge_guild_id = challenge.get(
            "guild_id"
        )
        if challenge_guild_id is not None:
            try:
                challenge_guild_id = int(
                    challenge_guild_id
                )
            except (TypeError, ValueError):
                await interaction.followup.send(
                    "This challenge has an invalid database record.",
                    ephemeral=True,
                )
                return
            if challenge_guild_id != interaction.guild.id:
                await interaction.followup.send(
                    "This challenge belongs to another server.",
                    ephemeral=True,
                )
                return
        # ---------------------------------------------------------------------
        # Check active status
        # ---------------------------------------------------------------------
        if not challenge.get(
            "is_active",
            True,
        ):
            await interaction.followup.send(
                "This challenge has already ended.",
                ephemeral=True,
            )
            return
        # ---------------------------------------------------------------------
        # Check deadline
        # ---------------------------------------------------------------------
        deadline = parse_datetime(
            challenge.get("deadline")
        )
        if deadline and utc_now() >= deadline:
            await interaction.followup.send(
                "The submission deadline has passed.",
                ephemeral=True,
            )
            return
        # ---------------------------------------------------------------------
        # Save submission
        # ---------------------------------------------------------------------
        try:
            success, message = await submit_challenge_entry(
                challenge_id=self.challenge_id,
                guild_id=interaction.guild.id,
                user_id=interaction.user.id,
                github_url=github_url,
                demo_url=demo_url,
                difficulty_tier=difficulty,
                notes=notes,
                code=code,
            )
        except Exception:
            await interaction.followup.send(
                "Something went wrong while saving your submission.",
                ephemeral=True,
            )
            return
        if not success:
            await interaction.followup.send(
                f"{message}",
                ephemeral=True,
            )
            return
        # ---------------------------------------------------------------------
        # Confirm submission
        # ---------------------------------------------------------------------
        attachment_view = SubmissionAttachmentView(self.challenge_id, interaction.user.id)
        await interaction.followup.send(
            (
                f"Your solution for **Challenge #{self.challenge_id}** has been submitted.\n\n"
                f"**Difficulty:** {difficulty}\n"
                "**Status:** Awaiting review\n\n"
                "You can optionally attach your complete project as a `.zip` file below."
            ),
            view=attachment_view,
            ephemeral=True,
        )
        # ---------------------------------------------------------------------
        # Find discussion thread
        # ---------------------------------------------------------------------
        thread: Optional[discord.Thread] = None
        if self.thread_id:
            thread = interaction.guild.get_thread(
                self.thread_id
            )
        if (
            thread is None
            and isinstance(
                interaction.channel,
                discord.TextChannel,
            )
            and self.thread_id
        ):
            try:
                for active_thread in interaction.channel.threads:
                    if active_thread.id == self.thread_id:
                        thread = active_thread
                        break
            except (discord.HTTPException, discord.Forbidden):
                thread = None
        target_channel = (
            thread
            or interaction.channel
        )
        if target_channel is None:
            return
        # ---------------------------------------------------------------------
        # Submission announcement
        # ---------------------------------------------------------------------
        embed = discord.Embed(
            title="New Challenge Submission",
            description=(
                f"**Developer:** "
                f"{interaction.user.mention}\n"
                f"**Difficulty:** `{difficulty}`\n"
                "**Status:** `Awaiting Review`"
            ),
            color=discord.Color.green(),
            timestamp=utc_now(),
        )
        if github_url:
            embed.add_field(
                name="GitHub",
                value=(
                    f"[View Repository]"
                    f"({github_url})"
                ),
                inline=True,
            )
        if demo_url:
            embed.add_field(
                name="Live Demo",
                value=(
                    f"[Open Demo]"
                    f"({demo_url})"
                ),
                inline=True,
            )
        if code:
            embed.add_field(
                name="Submitted Code",
                value=(
                    "The complete source code is posted in the "
                    "code block message(s) below exactly as submitted."
                ),
                inline=False,
            )
        if notes:
            embed.add_field(
                name="Implementation Notes",
                value=truncate_text(
                    notes,
                    1024,
                ),
                inline=False,
            )
        embed.set_footer(
            text=(
                f"Challenge #{self.challenge_id} "
                "• Awaiting admin review"
            )
        )
        try:
            submission_message = await target_channel.send(embed=embed)
            if isinstance(target_channel, (discord.TextChannel, discord.Thread)):
                await update_challenge_submission_message(
                    challenge_id=self.challenge_id,
                    guild_id=interaction.guild.id,
                    user_id=interaction.user.id,
                    message_id=submission_message.id,
                    channel_id=target_channel.id,
                )

            if code:
                # Discord messages have a 2000-character limit. Send the
                # entire source in multiple code blocks when necessary.
                # Splitting happens only at line boundaries and does not
                # modify the submitted source text.
                code_parts = split_code_for_discord(code)
                for index, code_part in enumerate(code_parts, start=1):
                    await target_channel.send(
                        f"**Full Submitted Code ({index}/{len(code_parts)})**\n"
                        f"```text\n{code_part}\n```"
                    )
        except (discord.Forbidden, discord.HTTPException):
            # The database submission succeeded, so we do not tell the
            # user their submission failed just because the announcement
            # could not be posted.
            pass
class SubmissionAttachmentView(discord.ui.View):
    """Short-lived private controls for attaching a project archive."""

    def __init__(self, challenge_id: int, user_id: int) -> None:
        super().__init__(timeout=600)
        self.challenge_id = challenge_id
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "Only the member who created this submission can use these buttons.",
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(
        label="Attach Project ZIP",
        style=discord.ButtonStyle.primary,
        custom_id="challenge:submission_attach",
    )
    async def attach_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await interaction.response.send_modal(
            ProjectAttachmentModal(self.challenge_id)
        )

    @discord.ui.button(
        label="Done",
        style=discord.ButtonStyle.secondary,
        custom_id="challenge:submission_done",
    )
    async def done_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            content="Submission setup complete. Your submission is awaiting review.",
            view=self,
        )
        self.stop()


# =============================================================================
# PROJECT ATTACHMENT MODAL
# =============================================================================
class ProjectAttachmentModal(discord.ui.Modal):
    """Collect an optional project archive after the main submission form."""

    def __init__(self, challenge_id: int) -> None:
        super().__init__(title="Attach Project ZIP")
        self.challenge_id = challenge_id
        self.file_upload = discord.ui.FileUpload(
            custom_id=f"challenge:upload:{challenge_id}",
            required=True,
            min_values=1,
            max_values=1,
        )
        self.add_item(
            discord.ui.Label(
                text="Project archive",
                component=self.file_upload,
                description="Upload one .zip file. Maximum size: 25 MB.",
            )
        )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This can only be used inside a server.", ephemeral=True
            )
            return

        if not self.file_upload.values:
            await interaction.response.send_message(
                "Please select a ZIP file.", ephemeral=True
            )
            return

        attachment = self.file_upload.values[0]
        filename = (attachment.filename or "").strip()
        if not filename.lower().endswith(".zip"):
            await interaction.response.send_message(
                "Only `.zip` project archives are accepted.", ephemeral=True
            )
            return

        if attachment.size > 25 * 1024 * 1024:
            await interaction.response.send_message(
                "The ZIP file is too large. Please keep it under 25 MB.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            success, message = await update_challenge_submission_attachment(
                challenge_id=self.challenge_id,
                guild_id=interaction.guild.id,
                user_id=interaction.user.id,
                attachment_url=attachment.url,
                attachment_name=filename,
            )
        except Exception:
            success = False
            message = "Something went wrong while attaching your project."

        if not success:
            await interaction.followup.send(message, ephemeral=True)
            return

        # Keep the archive visible to reviewers in the same channel where the
        # user submitted the challenge. The CDN URL is also persisted in DB.
        try:
            if interaction.channel is not None:
                await interaction.channel.send(
                    f"**Project ZIP attached** — {interaction.user.mention}\n"
                    f"[Download `{filename}`]({attachment.url})"
                )
        except (discord.Forbidden, discord.HTTPException):
            pass

        await interaction.followup.send(
            f"`{filename}` was attached to Challenge #{self.challenge_id}.",
            ephemeral=True,
        )


# =============================================================================
# PERSISTENT CHALLENGE VIEW
# =============================================================================
class ChallengeView(discord.ui.View):
    """
    Persistent view attached to challenge announcements.
    timeout=None allows the button to remain active across restarts when
    the view is registered with the bot.
    """
    def __init__(self) -> None:
        super().__init__(
            timeout=None
        )
    @discord.ui.button(
        label="Submit Solution",
        style=discord.ButtonStyle.success,
        emoji="🚀",
        custom_id="challenge:submit",
    )
    async def submit_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        """Open the challenge submission modal."""
        if (
            interaction.guild is None
            or interaction.message is None
        ):
            await interaction.response.send_message(
                "This button can only be used inside a server.",
                ephemeral=True,
            )
            return
        # ---------------------------------------------------------------------
        # Get challenge
        # ---------------------------------------------------------------------
        try:
            challenge = await get_challenge_by_message(
                interaction.message.id
            )
        except Exception:
            await interaction.response.send_message(
                "I couldn't load this challenge right now.",
                ephemeral=True,
            )
            return
        if not challenge:
            await interaction.response.send_message(
                "This challenge record no longer exists.",
                ephemeral=True,
            )
            return
        # ---------------------------------------------------------------------
        # Verify guild
        # ---------------------------------------------------------------------
        challenge_guild_id = challenge.get(
            "guild_id"
        )
        if challenge_guild_id is not None:
            try:
                challenge_guild_id = int(
                    challenge_guild_id
                )
            except (TypeError, ValueError):
                await interaction.response.send_message(
                    "This challenge has an invalid database record.",
                    ephemeral=True,
                )
                return
            if challenge_guild_id != interaction.guild.id:
                await interaction.response.send_message(
                    "This challenge belongs to another server.",
                    ephemeral=True,
                )
                return
        # ---------------------------------------------------------------------
        # Check active state
        # ---------------------------------------------------------------------
        if not challenge.get(
            "is_active",
            True,
        ):
            await interaction.response.send_message(
                "This challenge has ended and is no longer accepting "
                "submissions.",
                ephemeral=True,
            )
            return
        # ---------------------------------------------------------------------
        # Check deadline
        # ---------------------------------------------------------------------
        deadline = parse_datetime(
            challenge.get("deadline")
        )
        if deadline and utc_now() >= deadline:
            await interaction.response.send_message(
                "The submission deadline has passed.",
                ephemeral=True,
            )
            return
        # ---------------------------------------------------------------------
        # Validate challenge ID
        # ---------------------------------------------------------------------
        challenge_id = challenge.get("id")
        if challenge_id is None:
            await interaction.response.send_message(
                "This challenge has an invalid database record.",
                ephemeral=True,
            )
            return
        try:
            challenge_id = int(
                challenge_id
            )
        except (TypeError, ValueError):
            await interaction.response.send_message(
                "This challenge has an invalid ID.",
                ephemeral=True,
            )
            return
        # ---------------------------------------------------------------------
        # Open modal
        # ---------------------------------------------------------------------
        modal = ChallengeSubmissionModal(
            challenge_id=challenge_id,
            challenge_title=str(
                challenge.get(
                    "title",
                    "Developer Challenge",
                )
            ),
            thread_id=challenge.get(
                "thread_id"
            ),
        )
        await interaction.response.send_modal(
            modal
        )
# =============================================================================
# CHALLENGE COG
# =============================================================================
class Challenge(
    commands.Cog,
    name="Challenge",
):
    """Developer challenge management."""
    def __init__(
        self,
        bot: commands.Bot,
    ) -> None:
        self.bot = bot
    # =========================================================================
    # /CHALLENGE
    # =========================================================================
    @commands.hybrid_group(
        name="challenge",
        description=(
            "Create, manage, and participate in developer challenges."
        ),
    )
    async def challenge_group(
        self,
        ctx: commands.Context,
    ) -> None:
        """Main challenge command group."""
        if ctx.invoked_subcommand is None:
            await self.list_cmd(ctx)
    # =========================================================================
    # /CHALLENGE POST
    # =========================================================================
    @challenge_group.command(
        name="post",
        description="Post a new developer challenge.",
    )
    @commands.guild_only()
    @is_admin_or_owner()
    async def post_challenge(
        self,
        ctx: commands.Context,
        title: str,
        description: str,
        day_number: Optional[int] = None,
        rules: Optional[str] = (
            "No AI APIs • No chatbot/shortcut libraries • "
            "Build the solution yourself."
        ),
        easy_points: int = 5,
        medium_points: int = 10,
        hard_points: int = 15,
        duration_days: int = 3,
        ping_role: Optional[discord.Role] = None,
    ) -> None:
        """Create and publish a developer challenge."""
        if ctx.guild is None:
            return
        # ---------------------------------------------------------------------
        # Clean values
        # ---------------------------------------------------------------------
        title = clean_text(title)
        description = clean_multiline_text(
            description
        )
        rules = (
            clean_multiline_text(rules)
            if rules
            else None
        )
        # ---------------------------------------------------------------------
        # Validate title
        # ---------------------------------------------------------------------
        if not title:
            await send_ephemeral_or_normal(
                ctx,
                "Challenge title cannot be empty.",
            )
            return
        if len(title) > MAX_TITLE_LENGTH:
            await send_ephemeral_or_normal(
                ctx,
                (
                    f"Challenge title must be "
                    f"{MAX_TITLE_LENGTH} characters or fewer."
                ),
            )
            return
        # ---------------------------------------------------------------------
        # Validate description
        # ---------------------------------------------------------------------
        if not description:
            await send_ephemeral_or_normal(
                ctx,
                "Challenge description cannot be empty.",
            )
            return
        if len(description) > MAX_DESCRIPTION_LENGTH:
            await send_ephemeral_or_normal(
                ctx,
                (
                    f"Challenge description must be "
                    f"{MAX_DESCRIPTION_LENGTH} characters or fewer."
                ),
            )
            return
        # ---------------------------------------------------------------------
        # Validate rules
        # ---------------------------------------------------------------------
        if rules and len(rules) > MAX_RULES_LENGTH:
            await send_ephemeral_or_normal(
                ctx,
                (
                    f"Challenge rules must be "
                    f"{MAX_RULES_LENGTH} characters or fewer."
                ),
            )
            return
        # ---------------------------------------------------------------------
        # Validate day number
        # ---------------------------------------------------------------------
        if (
            day_number is not None
            and day_number <= 0
        ):
            await send_ephemeral_or_normal(
                ctx,
                "Day number must be greater than 0.",
            )
            return
        # ---------------------------------------------------------------------
        # Validate points
        # ---------------------------------------------------------------------
        points = {
            "Easy": easy_points,
            "Medium": medium_points,
            "Hard": hard_points,
        }
        for difficulty, value in points.items():
            if (
                value < MIN_POINTS
                or value > MAX_POINTS
            ):
                await send_ephemeral_or_normal(
                    ctx,
                    (
                        f"{difficulty} points must be between "
                        f"{MIN_POINTS} and {MAX_POINTS}."
                    ),
                )
                return
        # ---------------------------------------------------------------------
        # Validate point progression
        # ---------------------------------------------------------------------
        if not (
            easy_points
            <= medium_points
            <= hard_points
        ):
            await send_ephemeral_or_normal(
                ctx,
                (
                    "Reward points must follow this order:\n"
                    "`Easy ≤ Medium ≤ Hard`."
                ),
            )
            return
        # ---------------------------------------------------------------------
        # Validate duration
        # ---------------------------------------------------------------------
        if not (
            MIN_DURATION_DAYS
            <= duration_days
            <= MAX_DURATION_DAYS
        ):
            await send_ephemeral_or_normal(
                ctx,
                (
                    f"Challenge duration must be between "
                    f"{MIN_DURATION_DAYS} and "
                    f"{MAX_DURATION_DAYS} days."
                ),
            )
            return
        # ---------------------------------------------------------------------
        # Defer slash command
        # ---------------------------------------------------------------------
        if (
            ctx.interaction is not None
            and not ctx.interaction.response.is_done()
        ):
            await ctx.interaction.response.defer(
                ephemeral=True
            )
        now = utc_now()
        deadline = (
            now
            + timedelta(days=duration_days)
        )
        deadline_unix = int(
            deadline.timestamp()
        )
        # ---------------------------------------------------------------------
        # Create database record FIRST
        # ---------------------------------------------------------------------
        try:
            challenge_id = await create_challenge(
                guild_id=ctx.guild.id,
                channel_id=ctx.channel.id,
                author_id=ctx.author.id,
                title=title,
                description=description,
                day_number=day_number,
                rules=rules,
                easy_points=easy_points,
                medium_points=medium_points,
                hard_points=hard_points,
                deadline=deadline,
            )
        except Exception:
            challenge_id = None
        if not challenge_id:
            message = (
                "I couldn't create the challenge in the database. "
                "Nothing was posted."
            )
            if ctx.interaction is not None:
                await ctx.interaction.followup.send(
                    message,
                    ephemeral=True,
                )
            else:
                await ctx.send(message)
            return
        # ---------------------------------------------------------------------
        # Build announcement
        # ---------------------------------------------------------------------
        day_prefix = (
            f"DAY {day_number} — "
            if day_number is not None
            else ""
        )
        embed = discord.Embed(
            title=f"{day_prefix}{title}",
            description=description,
            color=discord.Color.blurple(),
            timestamp=now,
        )
        # ---------------------------------------------------------------------
        # Rules
        # ---------------------------------------------------------------------
        if rules:
            embed.add_field(
                name="Rules",
                value=rules,
                inline=False,
            )
        # ---------------------------------------------------------------------
        # Rewards
        # ---------------------------------------------------------------------
        reward_text = (
            f"🟢 **Easy** — `{easy_points}` Dev Karma\n"
            f"🟡 **Medium** — `{medium_points}` Dev Karma\n"
            f"🔴 **Hard** — `{hard_points}` Dev Karma"
        )
        embed.add_field(
            name="Difficulty & Rewards",
            value=reward_text,
            inline=False,
        )
        # ---------------------------------------------------------------------
        # Deadline
        # ---------------------------------------------------------------------
        embed.add_field(
            name="Deadline",
            value=(
                f"**{duration_days} day(s)**\n"
                f"Ends <t:{deadline_unix}:R>\n"
                f"<t:{deadline_unix}:f>"
            ),
            inline=False,
        )
        # ---------------------------------------------------------------------
        # Submission instructions
        # ---------------------------------------------------------------------
        embed.add_field(
            name="How to Submit",
            value=(
                "Finish your project, then click "
                "**Submit Solution** below."
            ),
            inline=False,
        )
        # ---------------------------------------------------------------------
        # Footer
        # ---------------------------------------------------------------------
        if ctx.guild.icon:
            embed.set_footer(
                text=(
                    "Horizon Devs • Developer Challenges"
                ),
                icon_url=ctx.guild.icon.url,
            )
        else:
            embed.set_footer(
                text=(
                    "Horizon Devs • Developer Challenges"
                )
            )
        view = ChallengeView()
        content = (
            ping_role.mention
            if ping_role
            else None
        )
        # ---------------------------------------------------------------------
        # Post announcement
        # ---------------------------------------------------------------------
        try:
            message = await ctx.channel.send(
                content=content,
                embed=embed,
                view=view,
            )
        except (
            discord.Forbidden,
            discord.HTTPException,
        ):
            # Prevent orphaned active challenges.
            try:
                await close_challenge(
                    int(challenge_id)
                )
            except Exception:
                pass
            error_message = (
                "I couldn't post the challenge announcement. "
                "The challenge has been closed."
            )
            if ctx.interaction is not None:
                await ctx.interaction.followup.send(
                    error_message,
                    ephemeral=True,
                )
            else:
                await ctx.send(
                    error_message
                )
            return
        # ---------------------------------------------------------------------
        # Create discussion thread
        # ---------------------------------------------------------------------
        thread: Optional[discord.Thread] = None
        thread_name = (
            f"{day_prefix}"
            f"{truncate_text(title, 45)}"
            " • Submissions"
        )
        try:
            thread = await message.create_thread(
                name=thread_name,
                auto_archive_duration=4320,
            )
            await thread.send(
                f"**{title} — Discussion**\n\n"
                "Use this thread to discuss the challenge, "
                "share progress, ask questions, and help other "
                "developers.\n\n"
                "When you're finished, use the **Submit Solution** "
                "button on the main challenge post."
            )
        except (
            discord.Forbidden,
            discord.HTTPException,
        ):
            thread = None
        # ---------------------------------------------------------------------
        # Link Discord message/thread to database
        # ---------------------------------------------------------------------
        try:
            await update_challenge_message(
                challenge_id=int(
                    challenge_id
                ),
                message_id=message.id,
                thread_id=(
                    thread.id
                    if thread
                    else None
                ),
            )
        except Exception:
            pass
        # ---------------------------------------------------------------------
        # Success response
        # ---------------------------------------------------------------------
        success_message = (
            f"Challenge **#{challenge_id}** posted successfully."
        )
        if thread:
            success_message += (
                "\nDiscussion thread created."
            )
        if ctx.interaction is not None:
            await ctx.interaction.followup.send(
                success_message,
                ephemeral=True,
            )
        else:
            await ctx.send(
                success_message
            )
    async def _update_submission_message(
        self,
        ctx: commands.Context,
        challenge_id: int,
        member: discord.Member,
        status: str,
        award_points: int = 0,
    ) -> None:
        """Update the original submission embed after review."""
        if ctx.guild is None:
            return

        submissions = await get_challenge_submissions(
            challenge_id=challenge_id,
            guild_id=ctx.guild.id,
            limit=100,
        )
        submission = next(
            (
                item
                for item in submissions
                if int(item.get("user_id") or 0) == member.id
            ),
            None,
        )
        if not submission:
            return

        message_id = submission.get("submission_message_id")
        channel_id = submission.get("submission_channel_id")
        if not message_id or not channel_id:
            return

        try:
            channel = ctx.guild.get_channel(int(channel_id))
            if channel is None:
                channel = await self.bot.fetch_channel(int(channel_id))
            if not isinstance(channel, (discord.TextChannel, discord.Thread)):
                return
            message = await channel.fetch_message(int(message_id))
        except (discord.NotFound, discord.Forbidden, discord.HTTPException, ValueError):
            return

        if not message.embeds:
            return

        embed = message.embeds[0].copy()
        if status == "APPROVED":
            embed.title = "Challenge Submission Approved"
            embed.description = (
                f"**Developer:** {member.mention}\n"
                f"**Difficulty:** `{submission.get('difficulty_tier') or 'Unknown'}`\n"
                f"**Status:** `Approved`\n"
                f"**Dev Karma Awarded:** `{award_points}`"
            )
            embed.color = discord.Color.green()
            embed.set_footer(
                text=f"Approved by {ctx.author.display_name} • Horizon Devs"
            )
        else:
            embed.title = "Challenge Submission Rejected"
            embed.description = (
                f"**Developer:** {member.mention}\n"
                f"**Difficulty:** `{submission.get('difficulty_tier') or 'Unknown'}`\n"
                "**Status:** `Rejected`\n"
                "**Dev Karma Awarded:** `0`"
            )
            embed.color = discord.Color.red()
            embed.set_footer(
                text=f"Rejected by {ctx.author.display_name} • Horizon Devs"
            )

        try:
            await message.edit(embed=embed)
        except (discord.Forbidden, discord.NotFound, discord.HTTPException):
            pass

    async def _send_review_dm(
        self,
        member: discord.Member,
        challenge_id: int,
        status: str,
        award_points: int = 0,
        reviewer: Optional[discord.abc.User] = None,
    ) -> None:
        """Notify the submitter privately about the review result."""
        try:
            if status == "APPROVED":
                embed = discord.Embed(
                    title="Challenge Submission Approved",
                    description=(
                        f"Your submission for Challenge `#{challenge_id}` has been **approved**.\n\n"
                        f"**Dev Karma awarded:** `{award_points}` points\n"
                        "Thank you for participating in the Horizon Devs challenge."
                    ),
                    color=discord.Color.green(),
                )
            else:
                embed = discord.Embed(
                    title="Challenge Submission Rejected",
                    description=(
                        f"Your submission for Challenge `#{challenge_id}` has been **rejected**.\n\n"
                        "**Dev Karma awarded:** `0` points\n"
                        "You can improve your solution and submit again if the challenge is still active."
                    ),
                    color=discord.Color.red(),
                )
            if reviewer is not None:
                embed.set_footer(text=f"Reviewed by {reviewer.display_name} • Horizon Devs")
            await member.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            # DMs can be disabled. Review itself has already succeeded.
            pass

    # =========================================================================
    # /CHALLENGE ATTACH
    # =========================================================================
    @challenge_group.command(
        name="attach",
        description="Attach a ZIP file to your challenge submission.",
    )
    @commands.guild_only()
    async def attach_submission(
        self,
        ctx: commands.Context,
        challenge_id: int,
        zip_file: discord.Attachment,
    ) -> None:
        """Attach an optional ZIP project archive to an existing submission."""
        if ctx.guild is None:
            return

        if ctx.interaction is not None:
            await ctx.defer(ephemeral=True)

        if challenge_id <= 0:
            await send_ephemeral_or_normal(
                ctx,
                "Challenge ID must be greater than 0.",
            )
            return

        filename = (zip_file.filename or "").lower()
        if not filename.endswith(".zip"):
            await send_ephemeral_or_normal(
                ctx,
                "Only `.zip` project files can be attached.",
            )
            return

        # Keep the archive reasonably sized for Discord. The bot stores the
        # Discord CDN URL; it does not need to download the archive.
        if zip_file.size > 25 * 1024 * 1024:
            await send_ephemeral_or_normal(
                ctx,
                "The ZIP file is too large. Please keep it under 25 MB.",
            )
            return

        try:
            success, message = await update_challenge_submission_attachment(
                challenge_id=challenge_id,
                guild_id=ctx.guild.id,
                user_id=ctx.author.id,
                attachment_url=zip_file.url,
                attachment_name=zip_file.filename,
            )
        except Exception:
            success = False
            message = "Something went wrong while attaching the ZIP file."

        if not success:
            await send_ephemeral_or_normal(ctx, message)
            return

        # Post the archive in the challenge discussion/submission channel so
        # reviewers have the actual Discord attachment as well as its URL.
        try:
            await ctx.send(
                f"**Project ZIP attached for Challenge #{challenge_id}**\n"
                f"[Download `{zip_file.filename}`]({zip_file.url})"
            )
        except (discord.Forbidden, discord.HTTPException):
            pass

        await send_ephemeral_or_normal(
            ctx,
            f"Your ZIP file `{zip_file.filename}` was attached to Challenge #{challenge_id}.",
        )

    # =========================================================================
    # /APPROVE
    # =========================================================================
    @commands.hybrid_command(
        name="approve",
        description="Approve a challenge submission and award Dev Karma.",
    )
    @commands.guild_only()
    @is_admin_or_owner()
    async def approve(
        self,
        ctx: commands.Context,
        challenge_id: int,
        member: discord.Member,
        award_points: int,
    ) -> None:
        """Approve one challenge submission and award Dev Karma."""
        if ctx.guild is None:
            return

        # Acknowledge slash interactions before Supabase/network work.
        if ctx.interaction is not None:
            await ctx.defer()

        if challenge_id <= 0:
            await send_ephemeral_or_normal(ctx, "Challenge ID must be greater than 0.")
            return
        if award_points <= 0:
            await send_ephemeral_or_normal(ctx, "Award points must be greater than 0.")
            return
        if award_points > MAX_POINTS:
            await send_ephemeral_or_normal(ctx, f"You cannot award more than {MAX_POINTS} points at once.")
            return
        try:
            challenge = await get_challenge(challenge_id)
        except Exception:
            challenge = None
        if not challenge:
            await send_ephemeral_or_normal(ctx, f"Challenge `#{challenge_id}` was not found.")
            return
        challenge_guild_id = challenge.get("guild_id")
        if challenge_guild_id is not None:
            try:
                challenge_guild_id = int(challenge_guild_id)
            except (TypeError, ValueError):
                await send_ephemeral_or_normal(ctx, "The challenge database record is invalid.")
                return
            if challenge_guild_id != ctx.guild.id:
                await send_ephemeral_or_normal(ctx, "That challenge belongs to another server.")
                return
        try:
            success, message = await award_challenge_points(
                challenge_id=challenge_id,
                guild_id=ctx.guild.id,
                user_id=member.id,
                points=award_points,
                reason="Approved challenge submission",
            )
        except Exception:
            success = False
            message = "Something went wrong while approving the submission."
        if not success:
            await send_ephemeral_or_normal(ctx, message)
            return
        embed = discord.Embed(
            title="Challenge Submission Approved",
            description=(
                f"{member.mention} has been awarded **{award_points} Dev Karma** "
                f"for Challenge `#{challenge_id}`."
            ),
            color=discord.Color.green(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Approved by {ctx.author.display_name} • Horizon Devs")
        await ctx.send(embed=embed)
        await self._update_submission_message(
            ctx, challenge_id, member, "APPROVED", award_points
        )
        await self._send_review_dm(
            member, challenge_id, "APPROVED", award_points, ctx.author
        )

    # =========================================================================
    # /REJECT
    # =========================================================================
    @commands.hybrid_command(
        name="reject",
        description="Reject a challenge submission without awarding Dev Karma.",
    )
    @commands.guild_only()
    @is_admin_or_owner()
    async def reject(
        self,
        ctx: commands.Context,
        challenge_id: int,
        member: discord.Member,
    ) -> None:
        """Reject one challenge submission without awarding karma."""
        if ctx.guild is None:
            return

        # Acknowledge slash interactions before Supabase/network work.
        if ctx.interaction is not None:
            await ctx.defer()

        if challenge_id <= 0:
            await send_ephemeral_or_normal(ctx, "Challenge ID must be greater than 0.")
            return
        try:
            challenge = await get_challenge(challenge_id)
        except Exception:
            challenge = None
        if not challenge:
            await send_ephemeral_or_normal(ctx, f"Challenge `#{challenge_id}` was not found.")
            return
        challenge_guild_id = challenge.get("guild_id")
        if challenge_guild_id is not None:
            try:
                challenge_guild_id = int(challenge_guild_id)
            except (TypeError, ValueError):
                await send_ephemeral_or_normal(ctx, "The challenge database record is invalid.")
                return
            if challenge_guild_id != ctx.guild.id:
                await send_ephemeral_or_normal(ctx, "That challenge belongs to another server.")
                return
        try:
            success, message = await update_challenge_submission_status(
                challenge_id=challenge_id,
                guild_id=ctx.guild.id,
                user_id=member.id,
                status="REJECTED",
            )
        except Exception:
            success = False
            message = "Something went wrong while rejecting the submission."
        if not success:
            await send_ephemeral_or_normal(ctx, message)
            return
        embed = discord.Embed(
            title="Challenge Submission Rejected",
            description=(
                f"The submission from {member.mention} for Challenge `#{challenge_id}` "
                "was rejected.\n\nNo Dev Karma was awarded."
            ),
            color=discord.Color.red(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Rejected by {ctx.author.display_name} • Horizon Devs")
        await ctx.send(embed=embed)
        await self._update_submission_message(
            ctx, challenge_id, member, "REJECTED"
        )
        await self._send_review_dm(
            member, challenge_id, "REJECTED", 0, ctx.author
        )

    # /CHALLENGE END
    # =========================================================================
    @challenge_group.command(
        name="end",
        description="Close a challenge.",
    )
    @commands.guild_only()
    @is_admin_or_owner()
    async def end_challenge(
        self,
        ctx: commands.Context,
        challenge_id: int,
    ) -> None:
        """Close an active challenge."""
        if ctx.guild is None:
            return
        if challenge_id <= 0:
            await send_ephemeral_or_normal(
                ctx,
                "Challenge ID must be greater than 0.",
            )
            return
        # ---------------------------------------------------------------------
        # Get challenge
        # ---------------------------------------------------------------------
        try:
            challenge = await get_challenge(
                challenge_id
            )
        except Exception:
            challenge = None
        if not challenge:
            await send_ephemeral_or_normal(
                ctx,
                f"Challenge `#{challenge_id}` was not found.",
            )
            return
        # ---------------------------------------------------------------------
        # Verify guild
        # ---------------------------------------------------------------------
        challenge_guild_id = challenge.get(
            "guild_id"
        )
        if challenge_guild_id is not None:
            try:
                challenge_guild_id = int(
                    challenge_guild_id
                )
            except (TypeError, ValueError):
                await send_ephemeral_or_normal(
                    ctx,
                    "The challenge database record is invalid.",
                )
                return
            if challenge_guild_id != ctx.guild.id:
                await send_ephemeral_or_normal(
                    ctx,
                    "That challenge belongs to another server.",
                )
                return
        # ---------------------------------------------------------------------
        # Check status
        # ---------------------------------------------------------------------
        if not challenge.get(
            "is_active",
            True,
        ):
            await send_ephemeral_or_normal(
                ctx,
                f"Challenge `#{challenge_id}` is already closed.",
            )
            return
        # ---------------------------------------------------------------------
        # Close
        # ---------------------------------------------------------------------
        try:
            success = await close_challenge(
                challenge_id
            )
        except Exception:
            success = False
        if not success:
            await send_ephemeral_or_normal(
                ctx,
                (
                    f"Challenge `#{challenge_id}` "
                    "could not be closed."
                ),
            )
            return
        # ---------------------------------------------------------------------
        # Response
        # ---------------------------------------------------------------------
        embed = discord.Embed(
            title="Challenge Closed",
            description=(
                f"Challenge `#{challenge_id}` has ended.\n\n"
                "New submissions are no longer accepted."
            ),
            color=discord.Color.dark_grey(),
        )
        embed.set_footer(
            text=(
                f"Closed by "
                f"{ctx.author.display_name}"
            )
        )
        await ctx.send(
            embed=embed
        )
    # =========================================================================
    # /CHALLENGE LIST
    # =========================================================================
    @challenge_group.command(
        name="list",
        description="List recent developer challenges.",
    )
    @commands.guild_only()
    async def list_cmd(
        self,
        ctx: commands.Context,
    ) -> None:
        """List recent challenges in the current server."""
        if ctx.guild is None:
            return
        try:
            challenges = await list_challenges(
                guild_id=ctx.guild.id,
                limit=MAX_CHALLENGES_TO_LIST,
            )
        except Exception:
            await send_ephemeral_or_normal(
                ctx,
                "I couldn't load the challenge list right now.",
            )
            return
        # ---------------------------------------------------------------------
        # No challenges
        # ---------------------------------------------------------------------
        if not challenges:
            embed = discord.Embed(
                title="Developer Challenges",
                description=(
                    "No challenges have been posted yet.\n"
                    "Check back soon."
                ),
                color=discord.Color.blurple(),
            )
            await ctx.send(
                embed=embed
            )
            return
        # ---------------------------------------------------------------------
        # Build list embed
        # ---------------------------------------------------------------------
        embed = discord.Embed(
            title="Horizon Devs — Developer Challenges",
            description=(
                "Build projects, submit your work, "
                "and earn Dev Karma."
            ),
            color=discord.Color.blurple(),
        )
        now = utc_now()
        for challenge in challenges:
            challenge_id = challenge.get(
                "id",
                "?",
            )
            title = clean_text(
                str(
                    challenge.get(
                        "title",
                        "Untitled Challenge",
                    )
                )
            )
            if not title:
                title = "Untitled Challenge"
            day_number = challenge.get(
                "day_number"
            )
            if day_number:
                display_title = (
                    f"Day {day_number}: {title}"
                )
            else:
                display_title = title
            display_title = truncate_text(
                display_title,
                220,
            )
            is_active = bool(
                challenge.get(
                    "is_active",
                    False,
                )
            )
            deadline = parse_datetime(
                challenge.get(
                    "deadline"
                )
            )
            # -------------------------------------------------------------
            # Status
            # -------------------------------------------------------------
            if is_active:
                if deadline and now >= deadline:
                    status = "🟠 Deadline passed"
                else:
                    status = "🟢 Active"
            else:
                status = "⚪ Closed"
            # -------------------------------------------------------------
            # Rewards
            # -------------------------------------------------------------
            easy = challenge.get(
                "easy_points",
                0,
            )
            medium = challenge.get(
                "medium_points",
                0,
            )
            hard = challenge.get(
                "hard_points",
                0,
            )
            # -------------------------------------------------------------
            # Deadline
            # -------------------------------------------------------------
            deadline_text = ""
            if deadline:
                timestamp = int(
                    deadline.timestamp()
                )
                if (
                    is_active
                    and deadline > now
                ):
                    deadline_text = (
                        f"\nEnds <t:{timestamp}:R>"
                    )
                else:
                    deadline_text = (
                        f"\nEnded <t:{timestamp}:R>"
                    )
            # -------------------------------------------------------------
            # Description
            # -------------------------------------------------------------
            description = clean_multiline_text(
                str(
                    challenge.get(
                        "description",
                        "",
                    )
                )
            )
            if not description:
                description = (
                    "No description provided."
                )
            description = truncate_text(
                description,
                180,
            )
            # -------------------------------------------------------------
            # Field
            # -------------------------------------------------------------
            embed.add_field(
                name=(
                    f"#{challenge_id} • "
                    f"{display_title}"
                ),
                value=(
                    f"{status}\n"
                    f"**Rewards:** "
                    f"{easy} / {medium} / {hard} Dev Karma"
                    f"{deadline_text}\n"
                    f"{description}"
                ),
                inline=False,
            )
        # ---------------------------------------------------------------------
        # Footer
        # ---------------------------------------------------------------------
        embed.set_footer(
            text=(
                "Horizon Devs • "
                "Use /challenge post to create a challenge"
            )
        )
        await ctx.send(
            embed=embed
        )
# =============================================================================
# COG SETUP
# =============================================================================
async def setup(
    bot: commands.Bot,
) -> None:
    """Load the Challenge cog."""
    await bot.add_cog(
        Challenge(bot)
    )
