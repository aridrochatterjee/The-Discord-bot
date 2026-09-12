from __future__ import annotations

import re
from typing import Any, Dict, Optional

import discord
from discord.ext import commands

from bot.config import PISTON_API_KEY, PISTON_URL
from bot.utils.http import get_session


# Common programming language aliases mapped to Piston runtime names
LANGUAGE_ALIASES: Dict[str, str] = {
    "py": "python",
    "python3": "python",
    "js": "javascript",
    "node": "javascript",
    "nodejs": "javascript",
    "ts": "typescript",
    "c++": "c++",
    "cpp": "c++",
    "c#": "csharp",
    "cs": "csharp",
    "rs": "rust",
    "golang": "go",
    "sh": "bash",
    "shell": "bash",
    "rb": "ruby",
}

GITHUB_URL_RE = re.compile(
    r"(?:https?://github\.com/)?([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)"
)

# Strips ANSI escape sequences from terminal outputs
ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def clean_code_block(code: str) -> str:
    """Strip markdown code fence syntax if user wrapped their snippet in ```."""
    stripped = code.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        # Remove opening ```lang and closing ```
        if len(lines) >= 2:
            return "\n".join(lines[1:-1]).strip()
    return stripped


def parse_github_repo(input_str: str) -> Optional[tuple[str, str]]:
    """Parse owner and repo name from string, stripping URLs, spaces, and .git suffix."""
    match = GITHUB_URL_RE.search(input_str.strip())
    if not match:
        return None
    owner = match.group(1)
    repo = match.group(2)
    if repo.endswith(".git"):
        repo = repo[:-4]
    return owner, repo


class DevTools(commands.Cog, name="Developer Tools"):
    """Developer utilities and coding tools for the Horizon Devs community."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # =========================================================================
    # CODE EXECUTION (/run)
    # =========================================================================

    @commands.hybrid_command(
        name="run",
        description="Execute a code snippet in an isolated sandbox (Python, JS, C++, Rust, Go, etc.).",
    )
    async def run_code(
        self,
        ctx: commands.Context,
        language: str,
        *,
        code: str,
    ) -> None:
        """Execute code using the Piston sandbox API."""
        if ctx.interaction and not ctx.interaction.response.is_done():
            await ctx.interaction.response.defer()

        clean_lang = language.lower().strip()
        runtime_lang = LANGUAGE_ALIASES.get(clean_lang, clean_lang)
        source_code = clean_code_block(code)

        if not source_code:
            await ctx.send("❌ Please provide valid code to execute.")
            return

        payload = {
            "language": runtime_lang,
            "version": "*",
            "files": [{"content": source_code}],
        }

        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if PISTON_API_KEY:
            headers["Authorization"] = PISTON_API_KEY

        execute_url = f"{PISTON_URL.rstrip('/')}/execute"
        session = await get_session()

        try:
            async with session.post(execute_url, json=payload, headers=headers) as resp:
                if resp.status == 401:
                    embed = discord.Embed(
                        title="🔒 Code Execution Authorization Required",
                        description=(
                            "The public Piston API requires an authorized key or a self-hosted instance.\n\n"
                            "**How to configure:**\n"
                            "• Set `PISTON_API_KEY` in your `.env` file, or\n"
                            "• Host your own Piston instance and set `PISTON_URL=http://localhost:2000/api/v2/piston`."
                        ),
                        color=discord.Color.red(),
                    )
                    await ctx.send(embed=embed)
                    return

                if resp.status not in (200, 201):
                    try:
                        err_json = await resp.json()
                        err_msg = err_json.get("message", "Execution failed.")
                    except Exception:
                        err_msg = (await resp.text())[:200]
                    await ctx.send(f"❌ Execution error: {err_msg}")
                    return

                result = await resp.json()

        except Exception as err:
            await ctx.send(f"❌ Error connecting to execution engine: {err}")
            return

        run_data = result.get("run", {})
        stdout = run_data.get("stdout", "")
        stderr = run_data.get("stderr", "")
        exit_code = run_data.get("code", 0)
        version = result.get("version", "unknown")

        is_success = (exit_code == 0) and not stderr
        embed_color = discord.Color.green() if is_success else discord.Color.red()

        embed = discord.Embed(
            title=f"Code Execution: {runtime_lang.capitalize()} ({version})",
            color=embed_color,
        )

        output_text = stdout or "(No output)"
        if len(output_text) > 1000:
            output_text = output_text[:1000] + "\n... [Output truncated]"

        embed.add_field(
            name="Output",
            value=f"```{runtime_lang}\n{output_text}\n```",
            inline=False,
        )

        if stderr:
            err_text = stderr
            if len(err_text) > 800:
                err_text = err_text[:800] + "\n... [Error truncated]"
            embed.add_field(
                name="Standard Error",
                value=f"```\n{err_text}\n```",
                inline=False,
            )

        embed.set_footer(
            text=f"Exit Code: {exit_code} • Requested by {ctx.author}",
            icon_url=ctx.author.display_avatar.url,
        )

        await ctx.send(embed=embed)

    # =========================================================================
    # GITHUB REPO LOOKUP (/github)
    # =========================================================================

    @commands.hybrid_command(
        name="github",
        description="Lookup repository stats, stars, issues, and license on GitHub.",
    )
    async def github_lookup(
        self,
        ctx: commands.Context,
        *,
        repo: str,
    ) -> None:
        """Fetch statistics for a GitHub repository."""
        if ctx.interaction and not ctx.interaction.response.is_done():
            await ctx.interaction.response.defer()

        parsed = parse_github_repo(repo)
        if not parsed:
            await ctx.send("❌ Please provide a valid repository in `owner/repo` format.")
            return

        owner, repo_name = parsed
        api_url = f"https://api.github.com/repos/{owner}/{repo_name}"
        session = await get_session()

        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "HorizonDevs-Bot",
        }

        try:
            async with session.get(api_url, headers=headers) as resp:
                if resp.status == 404:
                    await ctx.send(f"❌ Repository `{owner}/{repo_name}` was not found.")
                    return
                if resp.status != 200:
                    await ctx.send(f"❌ GitHub API error (HTTP {resp.status}).")
                    return
                data = await resp.json()
        except Exception as err:
            await ctx.send(f"❌ Failed to reach GitHub: {err}")
            return

        embed = discord.Embed(
            title=data.get("full_name", f"{owner}/{repo_name}"),
            url=data.get("html_url"),
            description=data.get("description") or "No description provided.",
            color=discord.Color.blurple(),
        )

        owner_info = data.get("owner", {})
        if owner_info.get("avatar_url"):
            embed.set_thumbnail(url=owner_info["avatar_url"])

        embed.add_field(name="⭐ Stars", value=f"{data.get('stargazers_count', 0):,}", inline=True)
        embed.add_field(name="🍴 Forks", value=f"{data.get('forks_count', 0):,}", inline=True)
        embed.add_field(name="🐛 Issues", value=f"{data.get('open_issues_count', 0):,}", inline=True)

        lang = data.get("language") or "None"
        license_info = data.get("license") or {}
        license_name = license_info.get("spdx_id") or license_info.get("name") or "None"

        embed.add_field(name="💻 Language", value=lang, inline=True)
        embed.add_field(name="📜 License", value=license_name, inline=True)
        embed.add_field(name="🌿 Default Branch", value=f"`{data.get('default_branch', 'main')}`", inline=True)

        embed.set_footer(
            text=f"Requested by {ctx.author}",
            icon_url=ctx.author.display_avatar.url,
        )

        await ctx.send(embed=embed)

    # =========================================================================
    # PYPI PACKAGE LOOKUP (/pypi)
    # =========================================================================

    @commands.hybrid_command(
        name="pypi",
        description="Search for a Python package on PyPI.",
    )
    async def pypi_lookup(
        self,
        ctx: commands.Context,
        package: str,
    ) -> None:
        """Fetch details for a Python package from PyPI."""
        if ctx.interaction and not ctx.interaction.response.is_done():
            await ctx.interaction.response.defer()

        clean_pkg = package.strip().lower()
        api_url = f"https://pypi.org/pypi/{clean_pkg}/json"
        session = await get_session()

        try:
            async with session.get(api_url) as resp:
                if resp.status == 404:
                    await ctx.send(f"❌ Package `{package}` was not found on PyPI.")
                    return
                if resp.status != 200:
                    await ctx.send(f"❌ PyPI API error (HTTP {resp.status}).")
                    return
                data = await resp.json()
        except Exception as err:
            await ctx.send(f"❌ Failed to reach PyPI: {err}")
            return

        info = data.get("info", {})
        embed = discord.Embed(
            title=f"📦 {info.get('name', clean_pkg)} v{info.get('version', '')}",
            url=info.get("project_url") or f"https://pypi.org/project/{clean_pkg}/",
            description=info.get("summary") or "No description provided.",
            color=discord.Color.blue(),
        )

        embed.add_field(
            name="Install",
            value=f"`pip install {info.get('name', clean_pkg)}`",
            inline=False,
        )

        author = info.get("author") or info.get("maintainer") or "Unknown"
        license_name = info.get("license") or "Not specified"
        if len(license_name) > 30:
            license_name = license_name[:27] + "..."

        embed.add_field(name="Author", value=author, inline=True)
        embed.add_field(name="License", value=license_name, inline=True)

        home_page = info.get("home_page") or info.get("project_urls", {}).get("Homepage")
        if home_page:
            embed.add_field(name="Homepage", value=f"[Link]({home_page})", inline=True)

        embed.set_footer(
            text=f"Requested by {ctx.author}",
            icon_url=ctx.author.display_avatar.url,
        )

        await ctx.send(embed=embed)

    # =========================================================================
    # CHEAT SHEET LOOKUP (/cheat)
    # =========================================================================

    @commands.hybrid_command(
        name="cheat",
        description="Quick programming/CLI cheat sheet reference (e.g. /cheat git rebase or /cheat tar).",
    )
    async def cheat_lookup(
        self,
        ctx: commands.Context,
        *,
        query: str,
    ) -> None:
        """Fetch cheat sheet notes from cheat.sh."""
        if ctx.interaction and not ctx.interaction.response.is_done():
            await ctx.interaction.response.defer()

        clean_query = query.strip().replace(" ", "+")
        url = f"https://cheat.sh/{clean_query}?T"
        session = await get_session()

        headers = {"User-Agent": "curl/7.68.0"}

        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    await ctx.send(f"❌ Could not retrieve cheat sheet for `{query}`.")
                    return
                text = await resp.text()
        except Exception as err:
            await ctx.send(f"❌ Failed to reach cheat.sh: {err}")
            return

        # Strip terminal ANSI codes
        cleaned = ANSI_ESCAPE_RE.sub("", text).strip()
        if not cleaned or "ERROR: " in cleaned[:20]:
            await ctx.send(f"❌ No cheat sheet found for `{query}`.")
            return

        if len(cleaned) > 1500:
            cleaned = cleaned[:1500] + "\n... [Truncated. Run in terminal: curl cheat.sh/" + clean_query + "]"

        embed = discord.Embed(
            title=f"📖 Cheat Sheet: {query}",
            description=f"```bash\n{cleaned}\n```",
            color=discord.Color.dark_teal(),
        )
        embed.set_footer(
            text=f"Source: cheat.sh • Requested by {ctx.author}",
            icon_url=ctx.author.display_avatar.url,
        )

        await ctx.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    """Load the Developer Tools cog."""
    await bot.add_cog(DevTools(bot))
