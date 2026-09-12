from __future__ import annotations

from typing import Optional

import discord
from discord.ext import commands

from bot.database.queries import (
    create_showcase,
    get_recent_showcases,
    get_showcase_by_id,
    get_showcase_by_message,
    update_showcase_message,
    vote_showcase,
)


def normalize_url(url: str) -> Optional[str]:
    """Ensure a URL has a valid web protocol for Discord embed links."""
    clean = url.strip()
    if not clean:
        return None
    if not clean.startswith(("http://", "https://")):
        return f"https://{clean}"
    return clean


# =============================================================================
# TECH STACK ROLE DEFINITIONS
# =============================================================================

TECH_ROLES = [
    ("🎨 Frontend", "Frontend Developer", discord.ButtonStyle.primary),
    ("⚙️ Backend", "Backend Developer", discord.ButtonStyle.primary),
    ("📱 Mobile", "Mobile Developer", discord.ButtonStyle.primary),
    ("☁️ DevOps", "DevOps & Cloud", discord.ButtonStyle.primary),
    ("🤖 AI / ML", "AI & Machine Learning", discord.ButtonStyle.secondary),
    ("🐍 Python", "Pythonista", discord.ButtonStyle.secondary),
    ("⚡ TypeScript", "TypeScript & JS", discord.ButtonStyle.secondary),
    ("🦀 Rust", "Rustacean", discord.ButtonStyle.secondary),
]


class TechRolesView(discord.ui.View):
    """Persistent view with buttons for toggling developer roles."""

    def __init__(self) -> None:
        super().__init__(timeout=None)
        for label, role_name, style in TECH_ROLES:
            custom_id = f"techrole:{role_name.lower().replace(' ', '_')}"
            button = discord.ui.Button(
                label=label,
                style=style,
                custom_id=custom_id,
            )
            button.callback = self._create_toggle_callback(role_name)
            self.add_item(button)

    def _create_toggle_callback(self, role_name: str):
        async def callback(interaction: discord.Interaction) -> None:
            if not interaction.guild or not isinstance(interaction.user, discord.Member):
                return

            guild = interaction.guild
            member = interaction.user

            # Check bot permissions
            if not guild.me.guild_permissions.manage_roles:
                await interaction.response.send_message(
                    "❌ I don't have permission to manage roles in this server.",
                    ephemeral=True,
                )
                return

            # Find or auto-create role
            role = discord.utils.get(guild.roles, name=role_name)
            if role is None:
                try:
                    role = await guild.create_role(
                        name=role_name,
                        mentionable=True,
                        reason="Auto-created by Horizon Devs Tech Roles panel",
                    )
                except discord.Forbidden:
                    await interaction.response.send_message(
                        f"❌ Could not create role `{role_name}` (insufficient permissions).",
                        ephemeral=True,
                    )
                    return

            # Toggle role
            if role in member.roles:
                await member.remove_roles(role, reason="Self-removed via Tech Roles panel")
                await interaction.response.send_message(
                    f"➖ Removed **{role.name}** role from your profile.",
                    ephemeral=True,
                )
            else:
                await member.add_roles(role, reason="Self-assigned via Tech Roles panel")
                await interaction.response.send_message(
                    f"➕ Assigned **{role.name}** role to your profile!",
                    ephemeral=True,
                )

        return callback


# =============================================================================
# SHOWCASE MODAL & PERSISTENT VIEW
# =============================================================================

class ShowcaseVoteButton(discord.ui.Button):
    """Button for upvoting a project showcase."""

    def __init__(self, showcase_id: int, upvotes: int = 0) -> None:
        super().__init__(
            label=f"⭐ Upvote ({upvotes})",
            style=discord.ButtonStyle.success,
            custom_id=f"showcase:vote:{showcase_id}",
        )
        self.showcase_id = showcase_id

    async def callback(self, interaction: discord.Interaction) -> None:
        success, message, new_votes = await vote_showcase(
            showcase_id=self.showcase_id,
            user_id=interaction.user.id,
        )

        if not success:
            await interaction.response.send_message(f"❌ {message}", ephemeral=True)
            return

        # Update button label
        self.label = f"⭐ Upvote ({new_votes})"

        # Update message view & embed
        if interaction.message:
            embeds = interaction.message.embeds
            if embeds:
                embed = embeds[0]
                # Update footer with vote count
                embed.set_footer(
                    text=f"⭐ {new_votes} upvotes • Horizon Devs Showcase",
                    icon_url=embed.footer.icon_url if embed.footer else None,
                )
                await interaction.message.edit(embed=embed, view=self.view)

        await interaction.response.send_message(f"✅ {message} (Total: {new_votes})", ephemeral=True)


class ShowcaseView(discord.ui.View):
    """Persistent view attached to showcase message cards."""

    def __init__(self, showcase_id: int, upvotes: int = 0) -> None:
        super().__init__(timeout=None)
        self.add_item(ShowcaseVoteButton(showcase_id, upvotes))


class ShowcaseModal(discord.ui.Modal, title="Submit Project Showcase"):
    """Interactive modal popup for project submissions."""

    project_title = discord.ui.TextInput(
        label="Project Name",
        placeholder="e.g. CodePulse — Live Pair Programming Tool",
        max_length=100,
        required=True,
    )

    tech_stack = discord.ui.TextInput(
        label="Tech Stack",
        placeholder="e.g. React, TypeScript, Node.js, Supabase, Tailwind",
        max_length=150,
        required=True,
    )

    description = discord.ui.TextInput(
        label="Project Summary",
        style=discord.TextStyle.paragraph,
        placeholder="What problem does it solve? What did you learn building it?",
        max_length=1000,
        required=True,
    )

    github_url = discord.ui.TextInput(
        label="GitHub Repository (Optional)",
        placeholder="https://github.com/username/project",
        required=False,
    )

    demo_url = discord.ui.TextInput(
        label="Live Demo Website (Optional)",
        placeholder="https://myproject.com",
        required=False,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return

        await interaction.response.defer(ephemeral=True)

        author = interaction.user
        guild = interaction.guild

        clean_github = normalize_url(self.github_url.value)
        clean_demo = normalize_url(self.demo_url.value)

        # 1. Save showcase to Supabase
        sc_data = await create_showcase(
            author_id=author.id,
            guild_id=guild.id,
            title=self.project_title.value.strip(),
            description=self.description.value.strip(),
            tech_stack=self.tech_stack.value.strip(),
            github_url=clean_github,
            demo_url=clean_demo,
        )

        showcase_id = sc_data["id"] if sc_data else 0

        # 2. Build Showcase Card Embed
        embed = discord.Embed(
            title=f"🚀 {self.project_title.value.strip()}",
            description=self.description.value.strip(),
            color=discord.Color.teal(),
        )
        embed.set_author(
            name=f"{author.display_name}'s Project Showcase",
            icon_url=author.display_avatar.url,
        )

        embed.add_field(
            name="🛠️ Tech Stack",
            value=f"`{self.tech_stack.value.strip()}`",
            inline=False,
        )

        links = []
        if clean_github:
            links.append(f"[📂 GitHub Repository]({clean_github})")
        if clean_demo:
            links.append(f"[🌐 Live Demo]({clean_demo})")

        if links:
            embed.add_field(name="🔗 Project Links", value=" • ".join(links), inline=False)

        embed.set_footer(
            text="⭐ 0 upvotes • Horizon Devs Showcase",
            icon_url=guild.icon.url if guild.icon else None,
        )

        # 3. Post to Channel with Upvote button
        view = ShowcaseView(showcase_id=showcase_id, upvotes=0)
        message = await interaction.channel.send(embed=embed, view=view)

        # 4. Associate message_id in database
        if showcase_id and message:
            await update_showcase_message(
                showcase_id=showcase_id,
                message_id=message.id,
                channel_id=interaction.channel.id,
            )

        # 5. Create automatic feedback discussion thread
        try:
            thread_title = f"💬 {self.project_title.value.strip()[:40]} Discussion"
            thread = await message.create_thread(
                name=thread_title,
                auto_archive_duration=1440,  # 24 hours
            )
            await thread.send(
                f"🎉 Welcome to the discussion thread for **{self.project_title.value.strip()}**!\n"
                f"Give {author.mention} your feedback, bug reports, and suggestions here."
            )
        except (discord.Forbidden, discord.HTTPException):
            pass

        await interaction.followup.send(
            "🎉 Your project showcase has been published to the channel!",
            ephemeral=True,
        )


# =============================================================================
# COMMUNITY COG
# =============================================================================

class Community(commands.Cog, name="Community"):
    """Community showcases and tech stack role assignment."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # =========================================================================
    # SHOWCASE COMMAND
    # =========================================================================

    @commands.hybrid_command(
        name="showcase",
        description="Submit your developer project or browse recent community projects.",
    )
    @commands.guild_only()
    async def showcase(self, ctx: commands.Context) -> None:
        """Submit a project showcase via modal popup."""
        if ctx.interaction:
            modal = ShowcaseModal()
            await ctx.interaction.response.send_modal(modal)
        else:
            embed = discord.Embed(
                title="🚀 Horizon Devs Project Showcase",
                description=(
                    "To submit a project, please use the slash command:\n"
                    "👉 **/showcase**\n\n"
                    "This will open an interactive form where you can specify your project name, "
                    "tech stack, summary, GitHub repo, and live demo link!"
                ),
                color=discord.Color.blurple(),
            )
            await ctx.send(embed=embed)

    # =========================================================================
    # TECH ROLES PANEL (/techroles)
    # =========================================================================

    @commands.hybrid_command(
        name="techroles",
        description="Post the self-assignable tech stack roles panel (Admins/Mods).",
    )
    @commands.has_permissions(manage_roles=True)
    @commands.guild_only()
    async def techroles(self, ctx: commands.Context) -> None:
        """Post an interactive tech stack role selection board."""
        embed = discord.Embed(
            title="🏷️ Horizon Devs — Choose Your Tech Roles",
            description=(
                "Click the buttons below to toggle your development specializations!\n\n"
                "• **Frontend** (React, Vue, Web)\n"
                "• **Backend** (APIs, Microservices, Databases)\n"
                "• **Mobile** (iOS, Android, React Native, Flutter)\n"
                "• **DevOps & Cloud** (Docker, K8s, AWS, CI/CD)\n"
                "• **AI / Machine Learning** (LLMs, PyTorch, Data Science)\n"
                "• **Python** • **TypeScript / JS** • **Rust**\n\n"
                "*Clicking a button adds or removes the role immediately.*"
            ),
            color=discord.Color.blurple(),
        )
        embed.set_footer(text="Horizon Devs Self-Assignable Roles")

        view = TechRolesView()
        await ctx.send(embed=embed, view=view)

    # =========================================================================
    # PERSISTENT COMPONENT LISTENER
    # =========================================================================

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction) -> None:
        """Handle persistent component interactions like showcase upvotes across bot restarts."""
        if interaction.type != discord.InteractionType.component:
            return

        custom_id = interaction.data.get("custom_id", "")
        if not custom_id.startswith("showcase:vote:"):
            return

        try:
            showcase_id = int(custom_id.split(":")[-1])
        except (ValueError, IndexError):
            return

        success, message, new_votes = await vote_showcase(
            showcase_id=showcase_id,
            user_id=interaction.user.id,
        )

        if not success:
            await interaction.response.send_message(f"❌ {message}", ephemeral=True)
            return

        if interaction.message and interaction.message.embeds:
            embed = interaction.message.embeds[0]
            embed.set_footer(
                text=f"⭐ {new_votes} upvotes • Horizon Devs Showcase",
                icon_url=embed.footer.icon_url if embed.footer else None,
            )
            view = ShowcaseView(showcase_id=showcase_id, upvotes=new_votes)
            try:
                await interaction.message.edit(embed=embed, view=view)
            except discord.HTTPException:
                pass

        await interaction.response.send_message(f"✅ {message} (Total: {new_votes})", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    """Load the Community cog."""
    await bot.add_cog(Community(bot))
