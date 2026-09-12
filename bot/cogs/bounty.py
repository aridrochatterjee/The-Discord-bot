from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import discord
from discord.ext import commands

from bot.database.queries import (
    accept_bounty,
    cancel_bounty,
    create_bounty,
    get_bounty,
    list_open_bounties,
    update_bounty_message,
)


# =============================================================================
# BOUNTY SOLUTION PROPOSAL MODAL
# =============================================================================

class BountySolutionModal(discord.ui.Modal):
    """Modal for members to submit a proposed fix/solution to a bounty."""

    def __init__(self, bounty_id: int, bounty_title: str, thread_id: Optional[int] = None) -> None:
        super().__init__(title=f"Solve Bounty #{bounty_id}")
        self.bounty_id = bounty_id
        self.bounty_title = bounty_title
        self.thread_id = thread_id

        self.solution_url_input = discord.ui.TextInput(
            label="Solution / Pull Request / Gist URL",
            placeholder="https://github.com/... or https://gist.github.com/...",
            required=False,
            max_length=200,
        )
        self.add_item(self.solution_url_input)

        self.explanation_input = discord.ui.TextInput(
            label="Explanation & Fix Details",
            style=discord.TextStyle.paragraph,
            placeholder="Explain how you fixed the issue, the root cause, or provide code...",
            required=True,
            max_length=1500,
        )
        self.add_item(self.explanation_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("❌ This can only be used in a server.", ephemeral=True)
            return

        bounty = await get_bounty(self.bounty_id)
        if not bounty or bounty.get("status") != "OPEN":
            await interaction.response.send_message("❌ This bounty is no longer open.", ephemeral=True)
            return

        solution_url = self.solution_url_input.value.strip() or None
        explanation = self.explanation_input.value.strip()

        await interaction.response.send_message(
            f"✅ Proposed solution posted for Bounty #{self.bounty_id}!",
            ephemeral=True,
        )

        # Announce solution in thread
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
            creator_id = bounty.get("creator_id")
            creator_mention = f"<@{creator_id}>" if creator_id else "Creator"

            embed = discord.Embed(
                title=f"💡 Proposed Solution for Bounty #{self.bounty_id}",
                description=f"**Solver:** {interaction.user.mention}\n**Attention:** {creator_mention}",
                color=discord.Color.green(),
                timestamp=datetime.now(timezone.utc),
            )
            if solution_url:
                embed.add_field(name="🔗 Solution Link", value=f"[Open Solution Link]({solution_url})", inline=False)
            embed.add_field(name="📝 Explanation & Approach", value=explanation[:1024], inline=False)
            embed.set_footer(
                text=f"Creator can accept with /bounty accept {self.bounty_id} @{interaction.user.name}",
                icon_url=interaction.user.display_avatar.url,
            )
            try:
                await target_channel.send(embed=embed)
            except Exception:
                pass


# =============================================================================
# PERSISTENT BOUNTY VIEW
# =============================================================================

class BountyView(discord.ui.View):
    """Persistent button view attached to bounty announcements."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Submit Solution",
        style=discord.ButtonStyle.success,
        emoji="💡",
        custom_id="bounty:submit_solution",
    )
    async def submit_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        """Handle member clicking the submit solution button."""
        if interaction.guild is None or interaction.message is None:
            await interaction.response.send_message("❌ Cannot use outside of a server.", ephemeral=True)
            return

        # Fetch bounty from message ID if possible or prompt modal
        from bot.database.client import get_supabase
        supabase = get_supabase()
        bounty = None
        if supabase:
            res = await supabase.table("bounties").select("*").eq("message_id", interaction.message.id).execute()
            if res.data:
                bounty = res.data[0]

        if not bounty:
            await interaction.response.send_message("❌ Bounty record not found.", ephemeral=True)
            return

        if bounty.get("status") != "OPEN":
            await interaction.response.send_message(
                f"⏳ This bounty is already {bounty.get('status', 'closed')}.",
                ephemeral=True,
            )
            return

        modal = BountySolutionModal(
            bounty_id=int(bounty["id"]),
            bounty_title=bounty.get("title", "Coding Bounty"),
            thread_id=bounty.get("thread_id"),
        )
        await interaction.response.send_modal(modal)


# =============================================================================
# BOUNTY COG
# =============================================================================

class Bounty(commands.Cog, name="Bounty"):
    """Dev Karma bounties for challenging bugs, code reviews, and features."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_group(
        name="bounty",
        description="Dev Karma coding bounties and help requests.",
    )
    async def bounty_group(self, ctx: commands.Context) -> None:
        """Dev Karma bounties management."""
        if ctx.invoked_subcommand is None:
            await self.list_bounties_cmd(ctx)


    # -------------------------------------------------------------------------
    # CREATE BOUNTY (/bounty create)
    # -------------------------------------------------------------------------
    @bounty_group.command(
        name="create",
        description="Post a coding bounty, staking your Dev Karma as an escrowed reward.",
    )
    @commands.guild_only()
    async def create_bounty_cmd(
        self,
        ctx: commands.Context,
        title: str,
        reward_karma: int,
        *,
        description: str,
    ) -> None:
        """Create a new Dev Karma bounty and escrow reward points."""
        if ctx.guild is None:
            return

        if reward_karma <= 0:
            await ctx.send("❌ Bounty reward must be at least 1 Dev Karma point.", ephemeral=True)
            return

        if ctx.interaction and not ctx.interaction.response.is_done():
            await ctx.interaction.response.defer()

        success, msg, bounty_id = await create_bounty(
            guild_id=ctx.guild.id,
            channel_id=ctx.channel.id,
            creator_id=ctx.author.id,
            title=title,
            description=description,
            reward_karma=reward_karma,
        )

        if not success or not bounty_id:
            await ctx.send(f"❌ Could not create bounty: {msg}", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"💰 Dev Karma Bounty #{bounty_id}: {title}",
            description=description,
            color=discord.Color.gold(),
            timestamp=datetime.now(timezone.utc),
        )

        embed.add_field(
            name="🏆 Bounty Reward",
            value=f"**{reward_karma} Dev Karma Points** *(held in escrow)*",
            inline=True,
        )
        embed.add_field(
            name="👤 Creator",
            value=ctx.author.mention,
            inline=True,
        )
        embed.add_field(
            name="📋 Status",
            value="🟢 **OPEN**",
            inline=True,
        )

        embed.set_footer(
            text=f"Bounty #{bounty_id} • Click 'Submit Solution' or discuss in the thread below",
            icon_url=ctx.author.display_avatar.url,
        )

        view = BountyView()
        msg_obj = await ctx.channel.send(embed=embed, view=view)

        # Create linked discussion thread
        thread: Optional[discord.Thread] = None
        try:
            thread = await msg_obj.create_thread(
                name=f"Bounty #{bounty_id}: {title[:40]}",
                auto_archive_duration=4320,  # 3 days
            )
            await thread.send(
                f"👋 Discussion and solution proposals for **Bounty #{bounty_id}: {title}**!\n"
                f"Reward: **{reward_karma} Dev Karma points** escrowed by {ctx.author.mention}.\n"
                f"When solved, the creator can run `/bounty accept {bounty_id} @solver`."
            )
        except Exception:
            pass

        await update_bounty_message(
            bounty_id=bounty_id,
            message_id=msg_obj.id,
            thread_id=thread.id if thread else None,
        )

        if ctx.interaction:
            await ctx.interaction.followup.send(
                f"✅ Bounty `#{bounty_id}` created! {reward_karma} Dev Karma points escrowed.",
                ephemeral=True,
            )

    # -------------------------------------------------------------------------
    # ACCEPT BOUNTY (/bounty accept)
    # -------------------------------------------------------------------------
    @bounty_group.command(
        name="accept",
        description="Accept a solver's solution and transfer the escrowed Dev Karma reward.",
    )
    @commands.guild_only()
    async def accept_bounty_cmd(
        self,
        ctx: commands.Context,
        bounty_id: int,
        solver: discord.Member,
    ) -> None:
        """Transfer escrowed karma to the solver and mark bounty resolved."""
        if ctx.guild is None:
            return

        is_admin = False
        if isinstance(ctx.author, discord.Member):
            is_admin = ctx.author.guild_permissions.administrator or ctx.author.id == ctx.guild.owner_id

        success, msg = await accept_bounty(
            bounty_id=bounty_id,
            solver_id=solver.id,
            caller_id=ctx.author.id,
            is_admin=is_admin,
        )

        if not success:
            await ctx.send(f"❌ {msg}", ephemeral=True)
            return

        embed = discord.Embed(
            title="🎉 Bounty Solved & Awarded!",
            description=(
                f"**Bounty `#{bounty_id}`** has been marked as **RESOLVED**!\n\n"
                f"🏆 **Winner:** {solver.mention}\n"
                f"🤝 **Confirmed by:** {ctx.author.mention}\n\n"
                f"The escrowed Dev Karma reward has been transferred to {solver.display_name}!"
            ),
            color=discord.Color.green(),
        )
        embed.set_thumbnail(url=solver.display_avatar.url)
        embed.set_footer(text="Dev Karma Bounty System • Horizon Devs")
        await ctx.send(embed=embed)

    # -------------------------------------------------------------------------
    # CANCEL BOUNTY (/bounty cancel)
    # -------------------------------------------------------------------------
    @bounty_group.command(
        name="cancel",
        description="Cancel an open bounty and refund your escrowed Dev Karma.",
    )
    @commands.guild_only()
    async def cancel_bounty_cmd(
        self,
        ctx: commands.Context,
        bounty_id: int,
    ) -> None:
        """Cancel an open bounty and refund the escrowed karma."""
        if ctx.guild is None:
            return

        is_admin = False
        if isinstance(ctx.author, discord.Member):
            is_admin = ctx.author.guild_permissions.administrator or ctx.author.id == ctx.guild.owner_id

        success, msg = await cancel_bounty(
            bounty_id=bounty_id,
            caller_id=ctx.author.id,
            is_admin=is_admin,
        )

        if not success:
            await ctx.send(f"❌ {msg}", ephemeral=True)
            return

        embed = discord.Embed(
            title="🚫 Bounty Cancelled",
            description=msg,
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed)

    # -------------------------------------------------------------------------
    # LIST BOUNTIES (/bounty list)
    # -------------------------------------------------------------------------
    @bounty_group.command(
        name="list",
        description="List currently open Dev Karma coding bounties.",
    )
    @commands.guild_only()
    async def list_bounties_cmd(self, ctx: commands.Context) -> None:
        """Display open coding bounties in the server."""
        if ctx.guild is None:
            return

        bounties = await list_open_bounties(guild_id=ctx.guild.id, limit=10)
        if not bounties:
            embed = discord.Embed(
                title="💰 Dev Karma Bounties",
                description="No open bounties right now. Post one with `/bounty create` to get help with code!",
                color=discord.Color.gold(),
            )
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(
            title="💰 Horizon Devs — Open Coding Bounties",
            description="Solve these community challenges to earn escrowed **Dev Karma**!",
            color=discord.Color.gold(),
        )

        for b in bounties:
            creator_mention = f"<@{b.get('creator_id')}>"
            reward = b.get("reward_karma", 0)
            embed.add_field(
                name=f"#{b.get('id')} {b.get('title', 'Bounty')} — 🪙 {reward} Karma",
                value=f"Posted by {creator_mention}\n{b.get('description', '')[:120]}...",
                inline=False,
            )

        embed.set_footer(text="Use /bounty create <title> <reward> <description> to post a bounty")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Bounty(bot))
