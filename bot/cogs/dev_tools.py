"""
Developer Tools Cog
-------------------

Useful developer-focused commands for Horizon Devs.

Commands:
    /github          - Look up a GitHub repository
    /github-user     - Look up a GitHub user
    /github-commits  - Show recent commits from a repository
    /pypi            - Look up a Python package
    /npm             - Look up an npm package
    /cheat           - Search cheat.sh
    /json            - Validate and format JSON
    /diff            - Compare two pieces of text
    /regex           - Test a regular expression

No code execution is performed by this cog.
"""

from __future__ import annotations

import difflib
import json
import logging
import re
from datetime import datetime
from urllib.parse import quote, urlparse

import discord
from discord import app_commands
from discord.ext import commands

from bot.utils.http import get_session

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GITHUB_API = "https://api.github.com"

MAX_JSON_INPUT = 6000
MAX_REGEX_PATTERN = 500
MAX_REGEX_TEXT = 4000
MAX_DIFF_INPUT = 5000

CHEAT_MAX_OUTPUT = 3500
GITHUB_COMMITS_PER_PAGE = 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def clean_code_block(text: str) -> str:
    """
    Remove Markdown code fences from user input.

    Example:
        ```json
        {"hello": "world"}
        ```

    becomes:
        {"hello": "world"}
    """
    text = text.strip()

    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()

        if len(lines) >= 2:
            lines = lines[1:-1]
            return "\n".join(lines).strip()

    return text


def truncate(text: str, limit: int = 3500) -> str:
    """Keep Discord output within a reasonable size."""
    if len(text) <= limit:
        return text

    return text[: limit - 30] + "\n... output truncated"


def format_number(value: int | None) -> str:
    """Format large numbers nicely."""
    if value is None:
        return "Unknown"

    return f"{value:,}"


def format_date(value: str | None) -> str:
    """Convert an ISO timestamp to a Discord timestamp."""
    if not value:
        return "Unknown"

    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return f"<t:{int(dt.timestamp())}:R>"
    except ValueError:
        return value


def github_headers() -> dict[str, str]:
    """Headers shared by GitHub API requests."""
    return {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "Horizon-Devs-Bot",
    }


def parse_github_repo(value: str) -> tuple[str, str] | None:
    """
    Parse common GitHub repository formats.

    Supported:
        owner/repo
        github.com/owner/repo
        https://github.com/owner/repo
        https://github.com/owner/repo.git
    """
    value = value.strip()

    if not value:
        return None

    # Plain owner/repo
    plain_match = re.fullmatch(
        r"([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)",
        value.rstrip("/"),
    )

    if plain_match:
        owner, repo = plain_match.groups()
        return owner, repo.removesuffix(".git")

    # URL format
    if not re.match(r"^https?://", value, re.IGNORECASE):
        value = f"https://{value}"

    try:
        parsed = urlparse(value)
    except ValueError:
        return None

    if parsed.netloc.lower() not in {
        "github.com",
        "www.github.com",
    }:
        return None

    parts = [
        part
        for part in parsed.path.strip("/").split("/")
        if part
    ]

    if len(parts) < 2:
        return None

    owner = parts[0]
    repo = parts[1].removesuffix(".git")

    if not re.fullmatch(r"[A-Za-z0-9_.-]+", owner):
        return None

    if not re.fullmatch(r"[A-Za-z0-9_.-]+", repo):
        return None

    return owner, repo


def parse_github_user(value: str) -> str | None:
    """Extract a GitHub username from a username or profile URL."""
    value = value.strip().rstrip("/")

    if not value:
        return None

    # Plain username
    if "/" not in value and "://" not in value:
        if re.fullmatch(r"[A-Za-z0-9-]+", value):
            return value

        return None

    if not re.match(r"^https?://", value, re.IGNORECASE):
        value = f"https://{value}"

    try:
        parsed = urlparse(value)
    except ValueError:
        return None

    if parsed.netloc.lower() not in {
        "github.com",
        "www.github.com",
    }:
        return None

    parts = [
        part
        for part in parsed.path.strip("/").split("/")
        if part
    ]

    if len(parts) != 1:
        return None

    username = parts[0]

    if not re.fullmatch(r"[A-Za-z0-9-]+", username):
        return None

    return username


async def github_get(
    endpoint: str,
) -> tuple[int, dict | list | None]:
    """Perform a GET request against the GitHub API."""
    session = await get_session()

    url = f"{GITHUB_API}{endpoint}"

    try:
        async with session.get(
            url,
            headers=github_headers(),
            timeout=10,
        ) as response:
            try:
                data = await response.json()
            except Exception:
                data = None

            return response.status, data

    except Exception:
        logger.exception("GitHub API request failed: %s", endpoint)
        return 0, None


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------


class DevTools(commands.Cog):
    """Developer-focused utility commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

        logger.info("DevTools cog initialized successfully.")

    # -----------------------------------------------------------------------
    # /github
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="github",
        description="Look up a GitHub repository.",
    )
    @app_commands.describe(
        repository="GitHub repository, e.g. discord.py or owner/repo",
    )
    async def github(
        self,
        interaction: discord.Interaction,
        repository: str,
    ) -> None:
        """Display GitHub repository information."""
        parsed = parse_github_repo(repository)

        if parsed is None:
            await interaction.response.send_message(
                "Invalid GitHub repository.\n"
                "Use something like `owner/repository`.",
                ephemeral=True,
            )
            return

        owner, repo = parsed

        await interaction.response.defer()

        status, data = await github_get(
            f"/repos/{quote(owner)}/{quote(repo)}"
        )

        if status == 404:
            await interaction.followup.send(
                f"GitHub repository `{owner}/{repo}` was not found."
            )
            return

        if status == 403:
            await interaction.followup.send(
                "GitHub API rate limit reached. Try again later."
            )
            return

        if status != 200 or not isinstance(data, dict):
            await interaction.followup.send(
                "I couldn't retrieve that GitHub repository right now."
            )
            return

        description = data.get("description") or "No description."

        embed = discord.Embed(
            title=data.get("full_name", f"{owner}/{repo}"),
            description=truncate(description, 1000),
            url=data.get("html_url"),
        )

        embed.add_field(
            name="Language",
            value=data.get("language") or "Unknown",
            inline=True,
        )

        embed.add_field(
            name="Stars",
            value=format_number(data.get("stargazers_count")),
            inline=True,
        )

        embed.add_field(
            name="Forks",
            value=format_number(data.get("forks_count")),
            inline=True,
        )

        embed.add_field(
            name="Issues",
            value=format_number(data.get("open_issues_count")),
            inline=True,
        )

        embed.add_field(
            name="License",
            value=(
                data.get("license", {}).get("spdx_id")
                if data.get("license")
                else "None"
            ),
            inline=True,
        )

        embed.add_field(
            name="Updated",
            value=format_date(data.get("updated_at")),
            inline=True,
        )

        await interaction.followup.send(embed=embed)

    # -----------------------------------------------------------------------
    # /github-user
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="github-user",
        description="Look up a GitHub user.",
    )
    @app_commands.describe(
        username="GitHub username or profile URL",
    )
    async def github_user(
        self,
        interaction: discord.Interaction,
        username: str,
    ) -> None:
        """Display GitHub user information."""
        clean_username = parse_github_user(username)

        if clean_username is None:
            await interaction.response.send_message(
                "Invalid GitHub username or profile URL.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        status, data = await github_get(
            f"/users/{quote(clean_username)}"
        )

        if status == 404:
            await interaction.followup.send(
                f"GitHub user `{clean_username}` was not found."
            )
            return

        if status == 403:
            await interaction.followup.send(
                "GitHub API rate limit reached. Try again later."
            )
            return

        if status != 200 or not isinstance(data, dict):
            await interaction.followup.send(
                "I couldn't retrieve that GitHub user right now."
            )
            return

        name = data.get("name") or data.get("login")

        embed = discord.Embed(
            title=f"GitHub User — {name}",
            description=data.get("bio") or "No bio.",
            url=data.get("html_url"),
        )

        avatar = data.get("avatar_url")

        if avatar:
            embed.set_thumbnail(url=avatar)

        embed.add_field(
            name="Username",
            value=f"`@{data.get('login', clean_username)}`",
            inline=True,
        )

        embed.add_field(
            name="Public Repos",
            value=format_number(data.get("public_repos")),
            inline=True,
        )

        embed.add_field(
            name="Followers",
            value=format_number(data.get("followers")),
            inline=True,
        )

        embed.add_field(
            name="Following",
            value=format_number(data.get("following")),
            inline=True,
        )

        embed.add_field(
            name="Location",
            value=data.get("location") or "Unknown",
            inline=True,
        )

        embed.add_field(
            name="Joined",
            value=format_date(data.get("created_at")),
            inline=True,
        )

        await interaction.followup.send(embed=embed)

    # -----------------------------------------------------------------------
    # /github-commits
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="github-commits",
        description="Show recent commits from a GitHub repository.",
    )
    @app_commands.describe(
        repository="GitHub repository, e.g. owner/repository",
    )
    async def github_commits(
        self,
        interaction: discord.Interaction,
        repository: str,
    ) -> None:
        """Display the latest commits."""
        parsed = parse_github_repo(repository)

        if parsed is None:
            await interaction.response.send_message(
                "Invalid GitHub repository.\n"
                "Use something like `owner/repository`.",
                ephemeral=True,
            )
            return

        owner, repo = parsed

        await interaction.response.defer()

        status, data = await github_get(
            f"/repos/{quote(owner)}/{quote(repo)}/commits"
            f"?per_page={GITHUB_COMMITS_PER_PAGE}"
        )

        if status == 404:
            await interaction.followup.send(
                f"GitHub repository `{owner}/{repo}` was not found."
            )
            return

        if status == 403:
            await interaction.followup.send(
                "GitHub API rate limit reached. Try again later."
            )
            return

        if status != 200 or not isinstance(data, list):
            await interaction.followup.send(
                "I couldn't retrieve the commits right now."
            )
            return

        if not data:
            await interaction.followup.send(
                f"`{owner}/{repo}` doesn't have any commits."
            )
            return

        embed = discord.Embed(
            title=f"Recent Commits — {owner}/{repo}",
            url=f"https://github.com/{owner}/{repo}/commits",
        )

        for commit in data:
            commit_data = commit.get("commit", {})
            author_data = commit_data.get("author", {})

            message = (
                commit_data.get("message", "No commit message.")
                .splitlines()[0]
            )

            sha = commit.get("sha", "")[:7]
            author = (
                author_data.get("name")
                or commit.get("author", {}).get("login")
                or "Unknown"
            )

            date = format_date(author_data.get("date"))

            commit_url = commit.get("html_url")

            value = (
                f"**{truncate(message, 180)}**\n"
                f"`{sha}` • {author} • {date}"
            )

            if commit_url:
                value += f"\n[View commit]({commit_url})"

            embed.add_field(
                name="Commit",
                value=value,
                inline=False,
            )

        await interaction.followup.send(embed=embed)

    # -----------------------------------------------------------------------
    # /pypi
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="pypi",
        description="Look up a Python package on PyPI.",
    )
    @app_commands.describe(
        package="Python package name, e.g. discord.py",
    )
    async def pypi(
        self,
        interaction: discord.Interaction,
        package: str,
    ) -> None:
        """Display PyPI package information."""
        clean_pkg = package.strip()

        if not clean_pkg:
            await interaction.response.send_message(
                "Please provide a package name.",
                ephemeral=True,
            )
            return

        if len(clean_pkg) > 200:
            await interaction.response.send_message(
                "That package name is too long.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        session = await get_session()

        url = f"https://pypi.org/pypi/{quote(clean_pkg)}/json"

        try:
            async with session.get(url, timeout=10) as response:
                if response.status == 404:
                    await interaction.followup.send(
                        f"PyPI package `{clean_pkg}` was not found."
                    )
                    return

                if response.status != 200:
                    await interaction.followup.send(
                        "PyPI couldn't be reached right now."
                    )
                    return

                data = await response.json()

        except Exception:
            logger.exception("PyPI request failed for %s", clean_pkg)

            await interaction.followup.send(
                "I couldn't retrieve that package right now."
            )
            return

        info = data.get("info", {})

        project_url = info.get("project_url")
        homepage = info.get("home_page")

        embed = discord.Embed(
            title=info.get("name", clean_pkg),
            description=truncate(
                info.get("summary") or "No description.",
                1000,
            ),
            url=project_url or f"https://pypi.org/project/{clean_pkg}/",
        )

        embed.add_field(
            name="Version",
            value=info.get("version") or "Unknown",
            inline=True,
        )

        embed.add_field(
            name="Python",
            value=info.get("requires_python") or "Not specified",
            inline=True,
        )

        embed.add_field(
            name="License",
            value=info.get("license") or "Unknown",
            inline=True,
        )

        embed.add_field(
            name="Author",
            value=truncate(info.get("author") or "Unknown", 100),
            inline=True,
        )

        dependencies = info.get("requires_dist") or []

        embed.add_field(
            name="Dependencies",
            value=format_number(len(dependencies)),
            inline=True,
        )

        if homepage:
            embed.add_field(
                name="Homepage",
                value=f"[Open project]({homepage})",
                inline=True,
            )

        await interaction.followup.send(embed=embed)

    # -----------------------------------------------------------------------
    # /npm
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="npm",
        description="Look up an npm package.",
    )
    @app_commands.describe(
        package="npm package name, e.g. discord.js",
    )
    async def npm(
        self,
        interaction: discord.Interaction,
        package: str,
    ) -> None:
        """Display npm package information."""
        clean_pkg = package.strip()

        if not clean_pkg:
            await interaction.response.send_message(
                "Please provide a package name.",
                ephemeral=True,
            )
            return

        if len(clean_pkg) > 200:
            await interaction.response.send_message(
                "That package name is too long.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        session = await get_session()

        encoded_pkg = quote(clean_pkg, safe="@/")

        registry_url = (
            f"https://registry.npmjs.org/{encoded_pkg}"
        )

        downloads_url = (
            "https://api.npmjs.org/downloads/point/"
            f"last-week/{encoded_pkg}"
        )

        try:
            async with session.get(
                registry_url,
                timeout=10,
            ) as response:
                if response.status == 404:
                    await interaction.followup.send(
                        f"npm package `{clean_pkg}` was not found."
                    )
                    return

                if response.status != 200:
                    await interaction.followup.send(
                        "The npm registry couldn't be reached right now."
                    )
                    return

                data = await response.json()

            weekly_downloads = None

            try:
                async with session.get(
                    downloads_url,
                    timeout=10,
                ) as response:
                    if response.status == 200:
                        downloads_data = await response.json()
                        weekly_downloads = downloads_data.get("downloads")

            except Exception:
                logger.warning(
                    "npm download count request failed for %s",
                    clean_pkg,
                )

        except Exception:
            logger.exception("npm request failed for %s", clean_pkg)

            await interaction.followup.send(
                "I couldn't retrieve that package right now."
            )
            return

        latest_version = (
            data.get("dist-tags", {}).get("latest")
            or "Unknown"
        )

        repository = data.get("repository") or {}

        if isinstance(repository, dict):
            repository_url = repository.get("url")
        else:
            repository_url = None

        homepage = data.get("homepage")

        dependencies = (
            data.get("versions", {})
            .get(latest_version, {})
            .get("dependencies", {})
        )

        embed = discord.Embed(
            title=data.get("name", clean_pkg),
            description=truncate(
                data.get("description") or "No description.",
                1000,
            ),
            url=f"https://www.npmjs.com/package/{encoded_pkg}",
        )

        embed.add_field(
            name="Version",
            value=latest_version,
            inline=True,
        )

        embed.add_field(
            name="Weekly Downloads",
            value=format_number(weekly_downloads),
            inline=True,
        )

        embed.add_field(
            name="License",
            value=data.get("license") or "Unknown",
            inline=True,
        )

        embed.add_field(
            name="Dependencies",
            value=format_number(len(dependencies)),
            inline=True,
        )

        if repository_url:
            repository_url = repository_url.removeprefix("git+")
            repository_url = repository_url.removesuffix(".git")

            embed.add_field(
                name="Repository",
                value=f"[Open repository]({repository_url})",
                inline=True,
            )

        if homepage:
            embed.add_field(
                name="Homepage",
                value=f"[Open homepage]({homepage})",
                inline=True,
            )

        await interaction.followup.send(embed=embed)

    # -----------------------------------------------------------------------
    # /cheat
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="cheat",
        description="Search cheat.sh for a programming reference.",
    )
    @app_commands.describe(
        query="What you need help with, e.g. python list",
    )
    async def cheat(
        self,
        interaction: discord.Interaction,
        query: str,
    ) -> None:
        """Search cheat.sh."""
        clean_query = query.strip()

        if not clean_query:
            await interaction.response.send_message(
                "Please provide something to search for.",
                ephemeral=True,
            )
            return

        if len(clean_query) > 200:
            await interaction.response.send_message(
                "That search query is too long.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        session = await get_session()

        encoded_query = quote(
            clean_query,
            safe="/+",
        )

        url = f"https://cheat.sh/{encoded_query}?T"

        try:
            async with session.get(
                url,
                timeout=10,
                headers={
                    "User-Agent": "Horizon-Devs-Bot",
                },
            ) as response:
                if response.status != 200:
                    await interaction.followup.send(
                        "cheat.sh couldn't find a result for that query."
                    )
                    return

                result = await response.text()

        except Exception:
            logger.exception(
                "cheat.sh request failed for %s",
                clean_query,
            )

            await interaction.followup.send(
                "I couldn't reach cheat.sh right now."
            )
            return

        # Remove common ANSI escape sequences.
        result = re.sub(
            r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])",
            "",
            result,
        ).strip()

        if not result:
            await interaction.followup.send(
                "cheat.sh returned an empty result."
            )
            return

        result = truncate(result, CHEAT_MAX_OUTPUT)

        if len(result) > 1900:
            result = result[:1850] + "\n... output truncated"

        await interaction.followup.send(
            f"```text\n{result}\n```"
        )

    # -----------------------------------------------------------------------
    # /json
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="json",
        description="Validate and pretty-print JSON.",
    )
    @app_commands.describe(
        data="JSON data. Code blocks are supported.",
    )
    async def json_command(
        self,
        interaction: discord.Interaction,
        data: str,
    ) -> None:
        """Validate and format JSON."""
        data = clean_code_block(data)

        if not data:
            await interaction.response.send_message(
                "Please provide JSON.",
                ephemeral=True,
            )
            return

        if len(data) > MAX_JSON_INPUT:
            await interaction.response.send_message(
                f"JSON input is limited to {MAX_JSON_INPUT} characters.",
                ephemeral=True,
            )
            return

        try:
            parsed = json.loads(data)

        except json.JSONDecodeError as exc:
            line = exc.lineno
            column = exc.colno

            await interaction.response.send_message(
                "Invalid JSON.\n"
                f"Error: `{exc.msg}`\n"
                f"Location: line `{line}`, column `{column}`",
                ephemeral=True,
            )
            return

        formatted = json.dumps(
            parsed,
            indent=2,
            ensure_ascii=False,
        )

        if len(formatted) > 1900:
            formatted = formatted[:1850] + "\n... output truncated"

        await interaction.response.send_message(
            "Valid JSON.\n"
            f"```json\n{formatted}\n```"
        )

    # -----------------------------------------------------------------------
    # /diff
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="diff",
        description="Compare two pieces of text.",
    )
    @app_commands.describe(
        before="Original text",
        after="New text",
    )
    async def diff(
        self,
        interaction: discord.Interaction,
        before: str,
        after: str,
    ) -> None:
        """Generate a unified diff."""
        before = clean_code_block(before)
        after = clean_code_block(after)

        if len(before) > MAX_DIFF_INPUT:
            await interaction.response.send_message(
                f"Original text is limited to {MAX_DIFF_INPUT} characters.",
                ephemeral=True,
            )
            return

        if len(after) > MAX_DIFF_INPUT:
            await interaction.response.send_message(
                f"New text is limited to {MAX_DIFF_INPUT} characters.",
                ephemeral=True,
            )
            return

        if before == after:
            await interaction.response.send_message(
                "No changes detected."
            )
            return

        before_lines = before.splitlines()
        after_lines = after.splitlines()

        diff_lines = difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile="before",
            tofile="after",
            lineterm="",
        )

        diff_text = "\n".join(diff_lines)

        if not diff_text:
            await interaction.response.send_message(
                "No changes detected."
            )
            return

        diff_text = truncate(diff_text, 1800)

        await interaction.response.send_message(
            f"```diff\n{diff_text}\n```"
        )

    # -----------------------------------------------------------------------
    # /regex
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="regex",
        description="Test a regular expression against text.",
    )
    @app_commands.describe(
        pattern="Regular expression pattern",
        text="Text to test",
    )
    async def regex(
        self,
        interaction: discord.Interaction,
        pattern: str,
        text: str,
    ) -> None:
        """Test a Python regular expression."""
        if len(pattern) > MAX_REGEX_PATTERN:
            await interaction.response.send_message(
                f"Regex pattern is limited to {MAX_REGEX_PATTERN} characters.",
                ephemeral=True,
            )
            return

        if len(text) > MAX_REGEX_TEXT:
            await interaction.response.send_message(
                f"Test text is limited to {MAX_REGEX_TEXT} characters.",
                ephemeral=True,
            )
            return

        try:
            compiled = re.compile(pattern)

        except re.error as exc:
            await interaction.response.send_message(
                "Invalid regex pattern.\n"
                f"Error: `{exc}`",
                ephemeral=True,
            )
            return

        match = compiled.search(text)

        if match is None:
            embed = discord.Embed(
                title="Regex Test",
                description="No match found.",
            )

            embed.add_field(
                name="Pattern",
                value=f"`{truncate(pattern, 900)}`",
                inline=False,
            )

            await interaction.response.send_message(
                embed=embed
            )
            return

        matched_text = match.group(0)

        groups = match.groups()

        embed = discord.Embed(
            title="Regex Test",
            description="Match found.",
        )

        embed.add_field(
            name="Pattern",
            value=f"`{truncate(pattern, 900)}`",
            inline=False,
        )

        embed.add_field(
            name="Matched",
            value=f"`{truncate(matched_text, 900)}`",
            inline=False,
        )

        embed.add_field(
            name="Position",
            value=f"`{match.start()} → {match.end()}`",
            inline=True,
        )

        embed.add_field(
            name="Groups",
            value=str(len(groups)),
            inline=True,
        )

        if groups:
            formatted_groups = "\n".join(
                f"`{index}` → `{truncate(str(value), 300)}`"
                for index, value in enumerate(groups, start=1)
            )

            embed.add_field(
                name="Captured Groups",
                value=truncate(formatted_groups, 1000),
                inline=False,
            )

        await interaction.response.send_message(
            embed=embed
        )


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------


async def setup(bot: commands.Bot) -> None:
    """Load the DevTools cog."""
    await bot.add_cog(DevTools(bot))

    logger.info("DevTools cog loaded successfully.")
