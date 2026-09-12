from __future__ import annotations

import re
from typing import Any, Dict, Optional

import discord
from discord.ext import commands

from bot.config import JUDGE0_URL, RAPIDAPI_KEY
from bot.utils.http import get_session


# Judge0 CE Language IDs (Official CE specification)
JUDGE0_LANGUAGES: Dict[str, int] = {
    "python": 71,       # Python (3.8.1)
    "py": 71,
    "python3": 71,
    "javascript": 63,   # JavaScript (Node.js 12.14.0)
    "js": 63,
    "node": 63,
    "nodejs": 63,
    "typescript": 74,   # TypeScript (3.7.4)
    "ts": 74,
    "c": 50,            # C (GCC 9.2.0)
    "c++": 54,          # C++ (GCC 9.2.0)
    "cpp": 54,
    "csharp": 51,       # C# (Mono 6.6.0.161)
    "cs": 51,
    "c#": 51,
    "java": 62,         # Java (OpenJDK 13.0.1)
    "rust": 73,         # Rust (1.40.0)
    "rs": 73,
    "go": 60,           # Go (1.13.5)
    "golang": 60,
    "bash": 46,         # Bash (5.0.0)
    "sh": 46,
    "shell": 46,
    "ruby": 72,         # Ruby (2.7.0)
    "rb": 72,
    "php": 68,          # PHP (7.4.1)
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
    # CODE EXECUTION (/run via Judge0 CE)
    # =========================================================================

    @commands.hybrid_command(
        name="run",
        description="Execute a code snippet in an isolated sandbox via Judge0 CE (Python, JS, C++, Rust, etc.).",
    )
    async def run_code(
        self,
        ctx: commands.Context,
        language: str,
        *,
        code: str,
    ) -> None:
        """Execute code using Judge0 CE."""
        if ctx.interaction and not ctx.interaction.response.is_done():
            await ctx.interaction.response.defer()

        clean_lang = language.lower().strip()
        lang_id = JUDGE0_LANGUAGES.get(clean_lang)
        source_code = clean_code_block(code)

        if not source_code:
            await ctx.send("❌ Please provide valid code to execute.")
            return

        if lang_id is None:
            supported = ", ".join(sorted(set(JUDGE0_LANGUAGES.keys())))
            await ctx.send(f"❌ Unsupported language `{language}`.\nSupported:\n`{supported}`")
            return

        is_rapidapi = "rapidapi.com" in JUDGE0_URL
        if is_rapidapi and not RAPIDAPI_KEY:
            embed = discord.Embed(
                title="⚙️ Judge0 CE Configuration Needed",
                description=(
                    "To execute code, please configure your free **RapidAPI Key**:\n\n"
                    "1. Get a key at [RapidAPI Judge0 CE](https://rapidapi.com/judge0-official/api/judge0-ce) (50 free requests/day).\n"
                    "2. Add `RAPIDAPI_KEY=\"your_key_here\"` to your `.env` file.\n\n"
                    "*Alternatively, if self-hosting Judge0 via Docker, set `JUDGE0_URL=http://localhost:2358`.*"
                ),
                color=discord.Color.orange(),
            )
            await ctx.send(embed=embed)
            return

        payload = {
            "language_id": lang_id,
            "source_code": source_code,
            "stdin": "",
        }

        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if is_rapidapi and RAPIDAPI_KEY:
            headers["X-RapidAPI-Key"] = RAPIDAPI_KEY
            headers["X-RapidAPI-Host"] = "judge0-ce.p.rapidapi.com"

        execute_url = f"{JUDGE0_URL.rstrip('/')}/submissions?base64_encoded=false&wait=true"
        session = await get_session()

        try:
            async with session.post(execute_url, json=payload, headers=headers) as resp:
                if resp.status in (401, 403):
                    await ctx.send("❌ Judge0 API authorization failed. Please check `RAPIDAPI_KEY` in `.env`.")
                    return

                if resp.status not in (200, 201):
                    err_text = await resp.text()
                    await ctx.send(f"❌ Judge0 execution error (HTTP {resp.status}): {err_text[:200]}")
                    return

                result = await resp.json()

        except Exception as err:
            await ctx.send(f"❌ Error connecting to Judge0 execution engine: {err}")
            return

        status = result.get("status", {})
        status_desc = status.get("description", "Unknown")
        status_id = status.get("id", 0)

        stdout = result.get("stdout") or ""
        stderr = result.get("stderr") or ""
        compile_output = result.get("compile_output") or ""
        exec_time = result.get("time") or "0.00"
        memory = result.get("memory") or 0

        # Judge0 Status ID 3 is "Accepted"
        is_success = (status_id == 3)
        embed_color = discord.Color.green() if is_success else discord.Color.red()

        embed = discord.Embed(
            title=f"Code Execution: {clean_lang.capitalize()} • {status_desc}",
            color=embed_color,
        )

        output_text = stdout or "(No stdout produced)"
        if len(output_text) > 1000:
            output_text = output_text[:1000] + "\n... [Output truncated]"

        embed.add_field(
            name="Output",
            value=f"```{clean_lang}\n{output_text}\n```",
            inline=False,
        )

        error_details = compile_output or stderr
        if error_details:
            if len(error_details) > 800:
                error_details = error_details[:800] + "\n... [Error truncated]"
            embed.add_field(
                name="Error / Compiler Output",
                value=f"```\n{error_details}\n```",
                inline=False,
            )

        embed.set_footer(
            text=f"Status: {status_desc} • Time: {exec_time}s • Memory: {memory:,} KB • Requested by {ctx.author}",
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
    # NPM PACKAGE LOOKUP (/npm)
    # =========================================================================

    @commands.hybrid_command(
        name="npm",
        description="Search for a Node.js / JavaScript package on npm.",
    )
    async def npm_lookup(
        self,
        ctx: commands.Context,
        package: str,
    ) -> None:
        """Fetch details for a Node.js package from the npm registry."""
        if ctx.interaction and not ctx.interaction.response.is_done():
            await ctx.interaction.response.defer()

        clean_pkg = package.strip().lower()
        api_url = f"https://registry.npmjs.org/{clean_pkg}"
        downloads_url = f"https://api.npmjs.org/downloads/point/last-week/{clean_pkg}"
        session = await get_session()

        try:
            async with session.get(api_url) as resp:
                if resp.status == 404:
                    await ctx.send(f"❌ Package `{package}` was not found on npm.")
                    return
                if resp.status != 200:
                    await ctx.send(f"❌ npm registry error (HTTP {resp.status}).")
                    return
                data = await resp.json()
        except Exception as err:
            await ctx.send(f"❌ Failed to reach npm registry: {err}")
            return

        # Attempt to fetch weekly downloads
        weekly_downloads: Optional[int] = None
        try:
            async with session.get(downloads_url) as dl_resp:
                if dl_resp.status == 200:
                    dl_data = await dl_resp.json()
                    weekly_downloads = dl_data.get("downloads")
        except Exception:
            pass

        dist_tags = data.get("dist-tags", {})
        latest_ver = dist_tags.get("latest", "unknown")
        version_data = data.get("versions", {}).get(latest_ver, {}) if latest_ver != "unknown" else {}

        description = data.get("description") or version_data.get("description") or "No description provided."
        license_name = version_data.get("license") or data.get("license") or "Not specified"
        if isinstance(license_name, dict):
            license_name = license_name.get("type", "Custom")

        embed = discord.Embed(
            title=f"📦 {clean_pkg} v{latest_ver}",
            url=f"https://www.npmjs.com/package/{clean_pkg}",
            description=description,
            color=discord.Color.red(),
        )

        embed.add_field(
            name="Install",
            value=f"```bash\nnpm i {clean_pkg}\n```",
            inline=False,
        )

        if weekly_downloads is not None:
            embed.add_field(name="📈 Weekly Downloads", value=f"{weekly_downloads:,}", inline=True)

        embed.add_field(name="📜 License", value=str(license_name)[:30], inline=True)

        deps_count = len(version_data.get("dependencies", {}))
        dev_deps_count = len(version_data.get("devDependencies", {}))
        embed.add_field(
            name="🔗 Dependencies",
            value=f"{deps_count} direct • {dev_deps_count} dev",
            inline=True,
        )

        homepage = version_data.get("homepage") or data.get("homepage")
        repo = version_data.get("repository") or data.get("repository")
        links: List[str] = []
        if homepage:
            links.append(f"[Homepage]({homepage})")
        if isinstance(repo, dict) and repo.get("url"):
            clean_repo = repo["url"].replace("git+", "").replace(".git", "")
            links.append(f"[Repository]({clean_repo})")
        elif isinstance(repo, str):
            clean_repo = repo.replace("git+", "").replace(".git", "")
            links.append(f"[Repository]({clean_repo})")

        if links:
            embed.add_field(name="🌐 Links", value=" • ".join(links), inline=False)

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
