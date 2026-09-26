from __future__ import annotations

import asyncio
import logging
import re
import time
from collections import defaultdict, deque
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands
from openai import APIConnectionError, APIError, AsyncOpenAI, RateLimitError

from bot.config import GROQ_API_KEY

logger = logging.getLogger("bot.gpt")

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
MODEL = "openai/gpt-oss-120b"

USER_COOLDOWN = 3.0
USER_BURST_LIMIT = 5
USER_BURST_WINDOW = 15.0
GLOBAL_REQUEST_LIMIT = 25
GLOBAL_REQUEST_WINDOW = 60.0

MAX_INPUT_LENGTH = 2000
MAX_HISTORY_MESSAGES = 6
MAX_OUTPUT_TOKENS = 1200
DISCORD_MESSAGE_LIMIT = 2000
IGNORE_SENTINEL = "[IGNORE]"

PROMPT_PATH = Path(__file__).with_name("gpt_system.txt")


def load_system_prompt() -> str:
    """Load the system prompt stored beside this cog."""
    try:
        prompt = PROMPT_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        logger.exception("Could not load system prompt from %s", PROMPT_PATH)
        raise RuntimeError(
            f"Missing or unreadable system prompt file: {PROMPT_PATH}"
        )

    if not prompt:
        raise RuntimeError(f"System prompt file is empty: {PROMPT_PATH}")

    return prompt


SYSTEM_PROMPT = load_system_prompt()


def convert_markdown_tables(text: str) -> str:
    """Convert simple Markdown tables into readable Discord bullets."""
    lines = text.splitlines()
    output: list[str] = []
    i = 0

    def is_table_line(line: str) -> bool:
        stripped = line.strip()
        return stripped.startswith("|") and stripped.endswith("|")

    def cells(line: str) -> list[str]:
        return [cell.strip() for cell in line.strip().strip("|").split("|")]

    while i < len(lines):
        if not is_table_line(lines[i]):
            output.append(lines[i])
            i += 1
            continue

        table_lines: list[str] = []
        while i < len(lines) and is_table_line(lines[i]):
            table_lines.append(lines[i])
            i += 1

        if len(table_lines) < 2:
            output.extend(table_lines)
            continue

        headers = cells(table_lines[0])
        data_start = 1

        # Skip the Markdown separator row, if present.
        if data_start < len(table_lines):
            separator = cells(table_lines[data_start])
            if separator and all(
                re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) is not None
                for cell in separator
            ):
                data_start += 1

        converted: list[str] = []
        for row in table_lines[data_start:]:
            values = cells(row)
            if not any(values):
                continue

            fields = []
            for column, value in enumerate(values):
                if not value:
                    continue
                label = headers[column] if column < len(headers) else f"Item {column + 1}"
                fields.append(f"**{label}:** {value}")

            if fields:
                converted.append("- " + " · ".join(fields))

        output.extend(converted or table_lines)

    return "\n".join(output).strip()


def split_discord_message(text: str, limit: int = DISCORD_MESSAGE_LIMIT) -> list[str]:
    """Split text under Discord's limit and keep fenced code blocks balanced."""
    chunks: list[str] = []
    current = ""
    inside_fence = False
    fence_marker = "```"
    language = ""

    for line in text.splitlines(keepends=True):
        line_content = line.rstrip("\r\n")

        if line_content.lstrip().startswith(fence_marker):
            if not inside_fence:
                inside_fence = True
                language = line_content.lstrip()[3:].strip()
            else:
                inside_fence = False
                language = ""

        candidate = current + line
        closing = "\n```" if inside_fence else ""

        if len(candidate) + len(closing) <= limit:
            current = candidate
            continue

        if current:
            if inside_fence:
                current = current.rstrip() + "\n```"
            chunks.append(current)
            current = ("```" + language + "\n") if inside_fence else ""

        # Handle an unusually long single line without exceeding the limit.
        while len(line) > limit - (len(current) + 8):
            available = max(1, limit - len(current) - 8)
            piece, line = line[:available], line[available:]
            current += piece
            if inside_fence:
                chunks.append(current.rstrip() + "\n```")
                current = "```" + language + "\n"
            else:
                chunks.append(current)
                current = ""

        current += line

    if current.strip():
        if inside_fence and len(current) + 4 <= limit:
            current = current.rstrip() + "\n```"
        chunks.append(current)

    return [chunk for chunk in chunks if chunk.strip()]


class GPT(commands.Cog):
    """Mention-triggered Horizon Devs assistant powered by Groq."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.client = AsyncOpenAI(
            api_key=GROQ_API_KEY or "missing-api-key",
            base_url=GROQ_BASE_URL,
            max_retries=2,
        )

        # This setting is in memory and resets when the bot restarts.
        self.ai_channel_id: int | None = None

        self.user_last_request: dict[int, float] = {}
        self.user_requests: dict[int, deque[float]] = defaultdict(deque)
        self.global_requests: deque[float] = deque()
        self.rate_limit_lock = asyncio.Lock()

        self.conversations: dict[
            tuple[int, int], deque[dict[str, str]]
        ] = defaultdict(lambda: deque(maxlen=MAX_HISTORY_MESSAGES))

        logger.info("GPT cog initialized.")

    async def cog_unload(self) -> None:
        await self.client.close()

    @app_commands.command(
        name="ai_channel",
        description="Set the channel where the AI assistant responds.",
    )
    @app_commands.describe(channel="The AI assistant's channel.")
    @app_commands.default_permissions(manage_guild=True)
    async def ai_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ) -> None:
        if interaction.guild is None or not isinstance(
            interaction.user, discord.Member
        ):
            await interaction.response.send_message(
                "Use this command inside a server.", ephemeral=True
            )
            return

        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "You need **Manage Server** permission.", ephemeral=True
            )
            return

        self.ai_channel_id = channel.id

        embed = discord.Embed(
            title="AI Channel Configured",
            description=f"I'll respond to mentions in {channel.mention}.",
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

        logger.info(
            "AI channel set to %s by user %s",
            channel.id,
            interaction.user.id,
        )

    @staticmethod
    def _clean_old_requests(
        requests: deque[float], window: float, now: float
    ) -> None:
        while requests and now - requests[0] >= window:
            requests.popleft()

    async def check_rate_limit(self, user_id: int) -> tuple[bool, str | None]:
        now = time.monotonic()

        async with self.rate_limit_lock:
            last_request = self.user_last_request.get(user_id)
            if last_request is not None:
                remaining = USER_COOLDOWN - (now - last_request)
                if remaining > 0:
                    return False, f"Give me a second to breathe. Try again in `{remaining:.1f}s`."

            user_requests = self.user_requests[user_id]
            self._clean_old_requests(user_requests, USER_BURST_WINDOW, now)

            if len(user_requests) >= USER_BURST_LIMIT:
                remaining = USER_BURST_WINDOW - (now - user_requests[0])
                return False, f"Slow down a little and try again in `{remaining:.1f}s`."

            self._clean_old_requests(
                self.global_requests, GLOBAL_REQUEST_WINDOW, now
            )
            if len(self.global_requests) >= GLOBAL_REQUEST_LIMIT:
                remaining = GLOBAL_REQUEST_WINDOW - (
                    now - self.global_requests[0]
                )
                return False, f"The AI channel is busy. Try again in `{remaining:.0f}s`."

            self.user_last_request[user_id] = now
            user_requests.append(now)
            self.global_requests.append(now)
            return True, None

    async def ask_groq(
        self,
        messages: list[dict[str, str]],
    ) -> tuple[str, str | None]:
        """Return response text and finish reason."""
        response = await self.client.chat.completions.create(
            model=MODEL,
            messages=messages,
            max_tokens=MAX_OUTPUT_TOKENS,
            temperature=0.5,
        )

        choice = response.choices[0]
        return choice.message.content or "", choice.finish_reason

    async def send_answer(self, message: discord.Message, answer: str) -> None:
        answer = convert_markdown_tables(answer)
        chunks = split_discord_message(answer)

        if not chunks:
            await message.reply(
                "I couldn't produce a readable answer. Please try again.",
                mention_author=False,
            )
            return

        await message.reply(chunks[0], mention_author=False)
        for chunk in chunks[1:]:
            await message.channel.send(chunk)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.webhook_id is not None:
            return
        if message.guild is None or self.ai_channel_id is None:
            return
        if message.channel.id != self.ai_channel_id:
            return
        if self.bot.user is None or self.bot.user not in message.mentions:
            return

        user_message = message.content.replace(
            self.bot.user.mention, ""
        ).strip()

        if not user_message:
            await message.reply(
                "Mention me with a tech, math, physics, or history question.",
                mention_author=False,
            )
            return

        if len(user_message) > MAX_INPUT_LENGTH:
            await message.reply(
                f"Please keep your message under `{MAX_INPUT_LENGTH}` characters.",
                mention_author=False,
            )
            return

        if not GROQ_API_KEY:
            logger.error("GROQ_API_KEY is not configured.")
            await message.reply(
                "The AI assistant isn't configured right now.",
                mention_author=False,
            )
            return

        allowed, rate_message = await self.check_rate_limit(message.author.id)
        if not allowed:
            await message.reply(rate_message, mention_author=False)
            return

        conversation_key = (message.author.id, message.channel.id)
        conversation = self.conversations[conversation_key]

        api_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *list(conversation),
            {"role": "user", "content": user_message},
        ]

        try:
            async with message.channel.typing():
                answer, finish_reason = await self.ask_groq(api_messages)

                # If the model hits its token limit, request one continuation.
                if finish_reason == "length" and answer.strip():
                    continuation_messages = [
                        *api_messages,
                        {"role": "assistant", "content": answer},
                        {
                            "role": "user",
                            "content": (
                                "Continue from exactly where you stopped. "
                                "Do not repeat the previous text. Keep it concise."
                            ),
                        },
                    ]
                    extra, _ = await self.ask_groq(continuation_messages)
                    if extra.strip():
                        answer = answer.rstrip() + "\n" + extra.lstrip()

            if not answer.strip():
                return

            if answer.strip() == IGNORE_SENTINEL:
                return

            # Save only actual, in-scope replies to short-term memory.
            conversation.append({"role": "user", "content": user_message})
            conversation.append({"role": "assistant", "content": answer})

            await self.send_answer(message, answer)

        except RateLimitError:
            logger.warning("Groq API rate limit reached.")
            await message.reply(
                "The AI service is busy right now. Please try again shortly.",
                mention_author=False,
            )
        except APIConnectionError:
            logger.exception("Could not connect to Groq API.")
            await message.reply(
                "I couldn't connect to the AI service. Try again shortly.",
                mention_author=False,
            )
        except APIError:
            logger.exception("Groq API returned an error.")
            await message.reply(
                "The AI service encountered an error. Please try again later.",
                mention_author=False,
            )
        except Exception:
            logger.exception("Unexpected error in GPT cog.")
            await message.reply(
                "Something unexpected went wrong while answering.",
                mention_author=False,
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GPT(bot))
    logger.info("GPT cog loaded successfully.")