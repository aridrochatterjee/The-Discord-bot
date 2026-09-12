from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import discord
from discord.ext import commands

from bot.database.queries import (
    award_challenge_points,
    close_challenge,
    create_challenge,
    get_challenge,
    get_challenge_by_message,
    list_challenges,
    submit_challenge_entry,
    update_challenge_message,
)
from bot.utils.checks import is_admin_or_owner


# =============================================================================
# CHALLENGE SUBMISSION MODAL
# =============================================================================

class ChallengeSubmissionModal(discord.ui.Modal):
    """Modal for members to submit their challenge solution."""

    def __init__(self, challenge_id: int, challenge_title: str, thread_id: Optional[int] = None) -> None:
        super().__init__(title=f"Submit: {challenge_title[:35]}")
        self.challenge_id = challenge_id
        self.thread_id = thread_id

        self.github_url_input = discord.ui.TextInput(
            label="GitHub Repository / Code URL",
            placeholder="https://github.com/username/project",
            required=True,
            max_length=200,
        )
        self.add_item(self.github_url_input)

        self.demo_url_input = discord.ui.TextInput(
            label="Live Demo URL (Optional)",
            placeholder="https://your-demo.app or None",
            required=False,
            max_length=200,
        )
        self.add_item(self.demo_url_input)

        self.difficulty_input = discord.ui.TextInput(
            label="Difficulty Tier Attempted",
            placeholder="Easy, Medium, or Hard",
            default="Medium",
            required=True,
            max_length=20,
        )
        self.add_item(self.difficulty_input)

        self.notes_input = discord.ui.TextInput(
            label="Implementation Notes & Features",
            style=discord.TextStyle.paragraph,
            placeholder="Explain how you solved it, your architecture, or special features...",
            required=False,
            max_length=1000,
        )
        self.add_item(self.notes_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("❌ This can only be used in a server.", ephemeral=True)
            return

        github_url = self.github_url_input.value.strip()
        demo_url = self.demo_url_input.value.strip() or None
        difficulty = self.difficulty_input.value.strip().capitalize()
        notes = self.notes_input.value.strip() or "No notes provided."

        if not (github_url.startswith("http://") or github_url.startswith("https://")):
            await interaction.response.send_message(
                "❌ Please provide a valid URL starting with `http://` or `https://`.",
                ephemeral=True,
            )
            return

        success, msg = await submit_challenge_entry(
            challenge_id=self.challenge_id,
            guild_id=interaction.guild.id,
            user_id=interaction.user.id,
            github_url=github_url,
            demo_url=demo_url,
            difficulty_tier=difficulty,
            notes=notes,
        )

        if not success:
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True)
            return

        await interaction.response.send_message(
            f"✅ Solution recorded for Challenge #{self.challenge_id}! Good luck!",
            ephemeral=True,
        )

        # Announce submission in the challenge discussion thread
        thread: Optional[discord.Thread] = None
        if self.thread_id:
            thread = interaction.guild.get_thread(self.thread_id)
        if not thread and isinstance(interaction.channel, discord.TextChannel):
            for t in interaction.channel.threads:
                if t.id == self.thread_id:
                    thread = t
                    break

        target_channel = thread if thread else interaction.channel
        if target_channel:
            embed = discord.Embed(
                title="🚀 Challenge Entry Submitted!",
                description=f"**Developer:** {interaction.user.mention}\n**Difficulty Tier:** `{difficulty}`",
                color=discord.Color.green(),
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(name="🔗 GitHub Repo", value=f"[View Code]({github_url})", inline=True)
            if demo_url:
                embed.add_field(name="🌐 Live Demo", value=f"[Open Demo]({demo_url})", inline=True)
            embed.add_field(name="📝 Implementation Notes", value=notes[:1024], inline=False)
            embed.set_footer(
                text=f"Challenge #{self.challenge_id} • Awaiting Admin/Owner Review",
                icon_url=interaction.user.display_avatar.url,
            )
            try:
                await target_channel.send(embed=embed)
            except Exception:
                pass


# =============================================================================
# PERSISTENT CHALLENGE VIEW
# =============================================================================

class ChallengeView(discord.ui.View):
    """Persistent button view for challenge messages."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

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
        """Handle member clicking the submit button."""
        if interaction.guild is None or interaction.message is None:
            await interaction.response.send_message("❌ Cannot submit outside of a server.", ephemeral=True)
            return

        challenge = await get_challenge_by_message(interaction.message.id)
        if not challenge:
            await interaction.response.send_message("❌ Challenge record not found.", ephemeral=True)
            return

        if not challenge.get("is_active", True):
            await interaction.response.send_message(
                "⏳ This challenge has ended and is no longer accepting entries.",
                ephemeral=True,
            )
            return

        modal = ChallengeSubmissionModal(
            challenge_id=int(challenge["id"]),
            challenge_title=challenge.get("title", "Developer Challenge"),
            thread_id=challenge.get("thread_id"),
        )
        await interaction.response.send_modal(modal)


# =============================================================================
# CHALLENGE COG
# =============================================================================

class Challenge(commands.Cog, name="Challenge"):
    """Daily developer challenges and hackathon event management."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_group(
        name="challenge",
        description="Horizon Devs daily developer challenges and hackathons.",
    )
    async def challenge_group(self, ctx: commands.Context) -> None:
        """Challenge management and participation."""
        if ctx.invoked_subcommand is None:
            await self.list_cmd(ctx)


    # -------------------------------------------------------------------------
    # POST CHALLENGE (Admin & Owner Only)
    # -------------------------------------------------------------------------
    @challenge_group.command(
        name="post",
        description="Post a new developer challenge (Owner/Admin only).",
    )
    @commands.guild_only()
    @is_admin_or_owner()
    async def post_challenge(
        self,
        ctx: commands.Context,
        title: str,
        description: str,
        day_number: Optional[int] = None,
        rules: Optional[str] = "🚫 No AI APIs • 🚫 No chatbot/shortcut libraries • ✅ Your own logic",
        easy_points: int = 5,
        medium_points: int = 10,
        hard_points: int = 15,
        duration_days: int = 3,
        ping_role: Optional[discord.Role] = None,
    ) -> None:
        """Post a formatted developer challenge with auto-created thread and submit button."""
        if ctx.guild is None:
            return

        if ctx.interaction and not ctx.interaction.response.is_done():
            await ctx.interaction.response.defer(ephemeral=True)

        now = datetime.now(timezone.utc)
        deadline = now + timedelta(days=duration_days)
        deadline_unix = int(deadline.timestamp())

        day_prefix = f"DAY {day_number} — " if day_number else ""
        embed_title = f"🤖 {day_prefix}{title.upper()}"

        embed = discord.Embed(
            title=embed_title,
            description=description,
            color=discord.Color.from_rgb(88, 101, 242),  # Discord Blurple
            timestamp=now,
        )

        if rules:
            embed.add_field(
                name="📋 Rules & Constraints",
                value=rules,
                inline=False,
            )

        points_text = (
            f"🟢 **EASY** — {easy_points} POINTS\n"
            f"🟡 **MEDIUM** — {medium_points} POINTS\n"
            f"🔴 **HARD** — {hard_points} POINTS\n\n"
            f"*Higher difficulty = more Dev Karma points for the leaderboard!*"
        )
        embed.add_field(name="🎯 Difficulty & Dev Karma Rewards", value=points_text, inline=False)

        embed.add_field(
            name="⏳ Deadline",
            value=f"You have **{duration_days} DAYS** to complete this challenge.\nEnds <t:{deadline_unix}:R> (<t:{deadline_unix}:f>)",
            inline=False,
        )

        embed.set_footer(
            text="Click 'Submit Solution' below to submit your code • Horizon Devs",
            icon_url=ctx.guild.icon.url if ctx.guild.icon else None,
        )

        # Mention role if requested
        content = ping_role.mention if ping_role else None
        view = ChallengeView()

        msg = await ctx.channel.send(content=content, embed=embed, view=view)

        # Create linked discussion/submissions thread
        thread_name = f"{day_prefix}{title[:40]} - Submissions"
        thread: Optional[discord.Thread] = None
        try:
            thread = await msg.create_thread(
                name=thread_name,
                auto_archive_duration=4320,  # 3 days
            )
            await thread.send(
                f"👋 Welcome to the discussion & solution thread for **{title}**!\n"
                f"Share your progress, ask questions, or click **Submit Solution** on the main announcement to enter."
            )
        except Exception:
            pass

        # Save record in Supabase
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

        if challenge_id:
            await update_challenge_message(
                challenge_id=challenge_id,
                message_id=msg.id,
                thread_id=thread.id if thread else None,
            )

        if ctx.interaction:
            await ctx.interaction.followup.send(
                f"✅ Challenge posted successfully! (ID: `#{challenge_id or 'local'}`)",
                ephemeral=True,
            )

    # -------------------------------------------------------------------------
    # AWARD POINTS (Admin & Owner Only)
    # -------------------------------------------------------------------------
    @challenge_group.command(
        name="award",
        description="Award Dev Karma points to a challenge participant (Owner/Admin only).",
    )
    @commands.guild_only()
    @is_admin_or_owner()
    async def award_points(
        self,
        ctx: commands.Context,
        challenge_id: int,
        member: discord.Member,
        points: int,
        *,
        reason: str = "Accepted challenge submission",
    ) -> None:
        """Award points to a solver and update their submission status."""
        if ctx.guild is None:
            return

        if points <= 0:
            await ctx.send("❌ Awarded points must be greater than 0.", ephemeral=True)
            return

        success, msg = await award_challenge_points(
            challenge_id=challenge_id,
            guild_id=ctx.guild.id,
            user_id=member.id,
            points=points,
            reason=reason,
        )

        if not success:
            await ctx.send(f"❌ {msg}", ephemeral=True)
            return

        embed = discord.Embed(
            title="🏆 Challenge Karma Awarded!",
            description=f"Congratulations {member.mention}! You were awarded **{points} Dev Karma** for Challenge `#{challenge_id}`.\n\n*Reason: {reason}*",
            color=discord.Color.gold(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Awarded by {ctx.author.display_name} • Horizon Devs")
        await ctx.send(embed=embed)

    # -------------------------------------------------------------------------
    # END CHALLENGE (Admin & Owner Only)
    # -------------------------------------------------------------------------
    @challenge_group.command(
        name="end",
        description="Close a challenge to stop accepting new submissions (Owner/Admin only).",
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

        success = await close_challenge(challenge_id)
        if not success:
            await ctx.send(f"❌ Challenge `#{challenge_id}` could not be closed or does not exist.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🔒 Challenge Closed",
            description=f"Challenge `#{challenge_id}` has officially ended. Submissions are now locked.",
            color=discord.Color.dark_grey(),
        )
        await ctx.send(embed=embed)

    # -------------------------------------------------------------------------
    # LIST CHALLENGES
    # -------------------------------------------------------------------------
    @challenge_group.command(
        name="list",
        description="List recent developer challenges in this server.",
    )
    @commands.guild_only()
    async def list_cmd(self, ctx: commands.Context) -> None:
        """Display recent challenges and their status."""
        if ctx.guild is None:
            return

        challenges = await list_challenges(guild_id=ctx.guild.id, limit=10)
        if not challenges:
            embed = discord.Embed(
                title="🤖 Developer Challenges",
                description="No challenges have been posted yet. Check back soon!",
                color=discord.Color.blue(),
            )
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(
            title="🤖 Horizon Devs — Developer Challenges",
            description="Complete community challenges to sharpen your skills and earn **Dev Karma**!",
            color=discord.Color.blue(),
        )

        for c in challenges:
            status = "🟢 Active" if c.get("is_active") else "🔴 Ended"
            day_str = f"Day {c.get('day_number')}: " if c.get("day_number") else ""
            title = f"{day_str}{c.get('title', 'Challenge')}"
            pts = f"Points: {c.get('easy_points')}/{c.get('medium_points')}/{c.get('hard_points')}"
            
            deadline_str = ""
            if c.get("deadline"):
                try:
                    dt = datetime.fromisoformat(c["deadline"].replace("Z", "+00:00"))
                    deadline_str = f" • Ends <t:{int(dt.timestamp())}:R>"
                except Exception:
                    pass

            embed.add_field(
                name=f"#{c.get('id')} {title} [{status}]",
                value=f"{pts}{deadline_str}\n{c.get('description', '')[:120]}...",
                inline=False,
            )

        await ctx.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Challenge(bot))
