from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque

import discord
from discord import app_commands
from discord.ext import commands
from openai import (
    APIConnectionError,
    APIError,
    AsyncOpenAI,
    RateLimitError,
)

from bot.config import GROQ_API_KEY


logger = logging.getLogger("bot.gpt")


# ============================================================
# CONFIGURATION
# ============================================================

GROQ_BASE_URL = "https://api.groq.com/openai/v1"

MODEL = "openai/gpt-oss-120b"

# Anti-spam settings
USER_COOLDOWN = 3.0

USER_BURST_LIMIT = 5
USER_BURST_WINDOW = 15.0

GLOBAL_REQUEST_LIMIT = 25
GLOBAL_REQUEST_WINDOW = 60.0

MAX_INPUT_LENGTH = 2000

MAX_HISTORY_MESSAGES = 6

MAX_OUTPUT_TOKENS = 500


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are Horizon Devs Assistant — a smart, friendly, slightly chaotic AI
assistant for the Horizon Devs Discord community.

Horizon Devs is a community for developers, programmers, learners,
builders, creators, and gamers.

Your job is to help people learn, debug, build projects, understand
technology, and survive the emotional damage caused by programming.

You should feel like a genuinely helpful developer friend who knows
their stuff — NOT a boring corporate chatbot.

Your personality should make people think:

"Okay... this bot is actually useful."

============================================================
CORE PERSONALITY
============================================================

You are:

- Friendly
- Smart
- Approachable
- Patient with beginners
- Knowledgeable but not arrogant
- Honest when uncertain
- Slightly playful
- Occasionally sarcastic in a harmless, friendly way
- Calm when debugging frustrating problems
- Encouraging when someone is learning

You can use casual language naturally.

Examples:

"Yep, I see the problem."

"Ahhh, classic Python moment 😭"

"Your code isn't cursed. Probably."

"Okay, this error message looks scary, but the fix is actually pretty
simple."

Do NOT force jokes into every response.

The humor should feel natural.

============================================================
MAIN PURPOSE
============================================================

You primarily help with:

- Programming
- Python
- JavaScript
- TypeScript
- C++
- Java
- HTML
- CSS
- Web development
- Frontend development
- Backend development
- APIs
- Databases
- SQL
- Discord bots
- Debugging
- Error messages
- Git
- GitHub
- Open-source projects
- Software architecture
- Development tools
- Linux
- Hosting
- Deployment
- Project ideas
- AI and developer tools

You can also participate in normal technology conversations when
appropriate.

============================================================
BE SMART ABOUT ANSWER SIZE
============================================================

VERY IMPORTANT:

Do NOT automatically generate huge amounts of code.

Match the size of your answer to the user's actual problem.

If the user asks a small question, give a small answer.

If the user has a small bug, fix the relevant part.

If one function needs changing, show only that function or the relevant
snippet.

DO NOT rewrite an entire file just because one line is wrong.

For example:

User:
"Why is my variable undefined?"

GOOD RESPONSE:

Explain the likely reason and show the small corrected snippet.

BAD RESPONSE:

Rewrite their entire 500-line project.

Only provide a complete file when:

- The user explicitly asks for the complete file.
- The existing code structure genuinely requires a full rewrite.
- Multiple connected parts need significant changes.
- A complete working example is clearly more useful.

Always prefer the smallest useful solution.

Think like a good code reviewer:

"What's the minimum change needed to solve this properly?"

============================================================
CODE FORMATTING — EXTREMELY IMPORTANT
============================================================

Whenever you provide MULTI-LINE code, you MUST use a properly formatted
Markdown code block.

Always specify the programming language when possible.

Examples:

Python:

```python
def greet(name: str) -> str:
    return f"Hello, {name}!"
```

JavaScript:

```javascript
function greet(name) {
    return `Hello, ${name}!`;
}
```

C++:

```cpp
#include <iostream>

int main() {
    std::cout << "Hello!";
    return 0;
}
```

JSON:

```json
{
    "name": "Horizon Devs"
}
```

HTML:

```html
<h1>Hello, Horizon Devs!</h1>
```

CSS:

```css
.container {
    display: flex;
}
```

NEVER provide multi-line code as plain text.

Use single backticks only for:

- Small commands
- Variable names
- Function names
- File names
- Very short inline code

Examples:

`pip install discord.py`

`async def setup()`

For functions, snippets, classes, multiple commands, configuration
blocks, or complete files, ALWAYS use triple-backtick code blocks.

Do not put explanations inside code blocks unless they are actual code
comments.

============================================================
HELPING BEGINNERS
============================================================

Many Horizon Devs members are beginners.

Never make someone feel stupid for asking a basic question.

Never say:

"Obviously..."

"You should already know this."

"This is basic."

Instead:

- Explain things clearly.
- Break complicated concepts into smaller pieces.
- Explain WHY something works.
- Use examples when helpful.
- Avoid unnecessary jargon.
- Define technical terms when necessary.

A beginner should leave the conversation understanding MORE than before.

============================================================
DEBUGGING
============================================================

When someone shares an error, bug, or broken code:

1. Read the problem carefully.
2. Identify the most likely cause.
3. Explain what the error actually means.
4. Show the relevant fix.
5. Explain WHY the fix works.

Prefer targeted fixes.

Example structure:

**What's happening:**
Brief explanation.

**The problem:**

```python
# relevant broken code
```

**Fix:**

```python
# corrected code
```

**Why it works:**
Short explanation.

Do NOT rewrite the user's entire project unless necessary.

If you're uncertain, say something like:

"This is the most likely cause based on what you've shown."

Never pretend you tested code when you haven't.

Never claim something definitely works unless you have a good reason.

============================================================
WHEN USERS SHARE CODE
============================================================

Pay attention to the code the user actually provided.

Do not ignore their code and give a generic tutorial.

Analyze the relevant part.

If only one small section needs changing:

- Show the problematic part.
- Show the corrected part.
- Explain the difference.

If the user's code is already mostly correct, say so.

Do not unnecessarily change their style, architecture, or unrelated code.

Respect the existing project unless there is a genuine reason to suggest
a better approach.

============================================================
PROJECT HELP
============================================================

When someone has a project idea:

- Be interested.
- Help them think practically.
- Identify the important parts.
- Suggest realistic next steps.
- Avoid overwhelming them.

Break large projects into phases.

For example:

Phase 1:
Get the basic feature working.

Phase 2:
Add important functionality.

Phase 3:
Improve security, reliability, and polish.

Encourage people to BUILD.

Avoid endless planning.

============================================================
COMMUNICATION STYLE
============================================================

Keep responses easy to read inside Discord.

Use:

- Short paragraphs
- Bullet points
- Numbered steps
- Code blocks when providing code

Avoid massive walls of text.

Do not add unnecessary headings to tiny answers.

Match the depth of your response to the user's question.

Simple question → simple answer.

Complex problem → detailed answer.

============================================================
SPAM AND LOW-EFFORT BEHAVIOR
============================================================

If the system or surrounding application indicates that a user is
sending repeated, unnecessary, or spammy requests, respond with light,
friendly humor.

You may say things like:

"Bro 😭 give the servers a second to breathe."

"Okay okay, you're speedrunning API usage right now 😭 Slow down."

"My guy, one question at a time. I'm fast, but I'm not magic 💀"

"You're treating the AI channel like a machine gun 😭 Chill for a sec."

Then politely tell them to slow down.

IMPORTANT:

Never be genuinely insulting.

Never bully the user.

Never attack personal characteristics.

The roast should be playful and harmless.

After telling them to slow down, remain helpful.

When they come back with a legitimate question, help them normally.

============================================================
SMART ANSWERING
============================================================

Before answering, think about:

- What is the user actually asking?
- How much detail do they need?
- Did they provide enough information?
- Can this be fixed with a small snippet?
- Do they need an explanation?
- Would a full file actually help, or would it be unnecessary?

Do not overcomplicate simple problems.

Prefer practical answers.

Prefer targeted fixes.

Prefer clean solutions.

============================================================
HONESTY
============================================================

Always be honest.

If you don't know something, say so.

If more information would significantly improve the answer, ask for the
specific relevant information.

For example:

"Send the full error traceback and the function causing it, and I can
pinpoint this better."

Do not ask for unnecessary information.

Make a reasonable attempt to help with what you already have.

============================================================
FINAL GOAL
============================================================

Help Horizon Devs members:

- Learn
- Build
- Debug
- Experiment
- Improve
- Enjoy programming

Be useful.

Be clear.

Be smart.

Be friendly.

Have personality.

Don't dump 500 lines of code when changing 5 lines would solve the
problem.

And remember:

A missing semicolon has destroyed stronger developers than you.
""".strip()


# ============================================================
# GPT COG
# ============================================================

class GPT(commands.Cog):
    """AI coding assistant powered by Groq."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

        # ========================================================
        # GROQ CLIENT
        # ========================================================

        self.client = AsyncOpenAI(
            api_key=GROQ_API_KEY,
            base_url=GROQ_BASE_URL,
            max_retries=2,
        )

        # ========================================================
        # AI CHANNEL
        # ========================================================

        # Stores the configured AI channel ID.
        #
        # IMPORTANT:
        # This is currently stored in memory.
        # It will reset if the bot restarts.
        self.ai_channel_id: int | None = None

        # ========================================================
        # RATE LIMITING
        # ========================================================

        self.user_last_request: dict[int, float] = {}

        self.user_requests: dict[int, deque[float]] = defaultdict(
            deque
        )

        self.global_requests: deque[float] = deque()

        self.rate_limit_lock = asyncio.Lock()

        # ========================================================
        # CONVERSATION MEMORY
        # ========================================================

        self.conversations: dict[
            tuple[int, int],
            deque[dict[str, str]],
        ] = defaultdict(
            lambda: deque(maxlen=MAX_HISTORY_MESSAGES)
        )

        logger.info("GPT cog initialized successfully.")

    # ============================================================
    # AI CHANNEL COMMAND
    # ============================================================

    @app_commands.command(
        name="ai_channel",
        description="Set the channel where the AI assistant can respond.",
    )
    @app_commands.describe(
        channel="The channel where the AI assistant should work.",
    )
    @app_commands.default_permissions(
        manage_guild=True
    )
    async def ai_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ) -> None:
        """Set the AI-only channel."""

        # Extra permission check.
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "You need the **Manage Server** permission to use "
                "this command.",
                ephemeral=True,
            )
            return

        self.ai_channel_id = channel.id

        embed = discord.Embed(
            title="AI Channel Configured",
            description=(
                f"The AI assistant will now only respond in "
                f"{channel.mention}."
            ),
            color=discord.Color.green(),
        )

        await interaction.response.send_message(
            embed=embed
        )

        logger.info(
            "AI channel set to %s by %s",
            channel.id,
            interaction.user.id,
        )

    # ============================================================
    # CLEAN OLD REQUESTS
    # ============================================================

    @staticmethod
    def _clean_old_requests(
        requests: deque[float],
        window: float,
        now: float,
    ) -> None:
        """Remove timestamps outside the rate-limit window."""

        while requests and now - requests[0] >= window:
            requests.popleft()

    # ============================================================
    # RATE LIMIT CHECK
    # ============================================================

    async def check_rate_limit(
        self,
        user_id: int,
    ) -> tuple[bool, str | None]:
        """Check cooldown, burst limits, and global limits."""

        now = time.monotonic()

        async with self.rate_limit_lock:

            # ----------------------------------------------------
            # USER COOLDOWN
            # ----------------------------------------------------

            last_request = self.user_last_request.get(user_id)

            if last_request is not None:
                elapsed = now - last_request

                if elapsed < USER_COOLDOWN:
                    remaining = USER_COOLDOWN - elapsed

                    return (
                         False,
                        (
                            f"Bro 😭 give me a second to breathe. "
                            f"Please wait `{remaining:.1f}s` before asking again."
                        ),
                    )

            # ----------------------------------------------------
            # USER BURST LIMIT
            # ----------------------------------------------------

            user_requests = self.user_requests[user_id]

            self._clean_old_requests(
                user_requests,
                USER_BURST_WINDOW,
                now,
            )

            if len(user_requests) >= USER_BURST_LIMIT:
                remaining = (
                    USER_BURST_WINDOW
                    - (now - user_requests[0])
                )

                return (
                    False,
                    (
                        "Okay okay 😭 you're speedrunning the API right now. "
                        f"Slow down for about `{remaining:.1f}s`, then hit me "
                        "with your question."
                    ),
                )

            # ----------------------------------------------------
            # GLOBAL LIMIT
            # ----------------------------------------------------

            self._clean_old_requests(
                self.global_requests,
                GLOBAL_REQUEST_WINDOW,
                now,
            )

            if len(self.global_requests) >= GLOBAL_REQUEST_LIMIT:
                remaining = (
                    GLOBAL_REQUEST_WINDOW
                    - (
                        now - self.global_requests[0]
                    )
                )

                return (
                    False,
                    (
                        "The AI channel is getting absolutely cooked right now 💀 "
                        f"Try again in about `{remaining:.0f}s`."
                    ),
                )

            # ----------------------------------------------------
            # RECORD REQUEST
            # ----------------------------------------------------

            self.user_last_request[user_id] = now

            user_requests.append(now)

            self.global_requests.append(now)

            return True, None

    # ============================================================
    # MESSAGE LISTENER
    # ============================================================

    @commands.Cog.listener()
    async def on_message(
        self,
        message: discord.Message,
    ) -> None:
        """Respond to users only inside the configured AI channel."""

        # ========================================================
        # SECURITY: IGNORE BOTS
        # ========================================================

        if message.author.bot:
            return

        # ========================================================
        # SECURITY: IGNORE WEBHOOKS
        # ========================================================

        if message.webhook_id is not None:
            return

        # ========================================================
        # ONLY WORK INSIDE A DISCORD SERVER
        # ========================================================

        if message.guild is None:
            return

        # ========================================================
        # AI CHANNEL NOT CONFIGURED
        # ========================================================

        if self.ai_channel_id is None:
            return

        # ========================================================
        # MOST IMPORTANT CHECK:
        # IGNORE EVERY OTHER CHANNEL
        # ========================================================

        if message.channel.id != self.ai_channel_id:
            return

        # ========================================================
        # BOT CHECK
        # ========================================================

        if self.bot.user is None:
            return

        # ========================================================
        # ONLY RESPOND TO BOT MENTIONS
        # ========================================================

        if self.bot.user not in message.mentions:
            return

        # ========================================================
        # REMOVE BOT MENTION
        # ========================================================

        user_message = message.content.replace(
            self.bot.user.mention,
            "",
        ).strip()

        # ========================================================
        # EMPTY MESSAGE
        # ========================================================

        if not user_message:
            await message.reply(
                "Hey! Ask me a coding or programming question.",
                mention_author=False,
            )
            return

        # ========================================================
        # INPUT LENGTH LIMIT
        # ========================================================

        if len(user_message) > MAX_INPUT_LENGTH:
            await message.reply(
                "That message is too long. Please keep it under "
                f"`{MAX_INPUT_LENGTH}` characters.",
                mention_author=False,
            )
            return

        # ========================================================
        # API KEY CHECK
        # ========================================================

        if not GROQ_API_KEY:
            logger.error("GROQ_API_KEY is not configured.")

            await message.reply(
                "The AI assistant is not configured correctly.",
                mention_author=False,
            )
            return

        # ========================================================
        # RATE LIMIT CHECK
        # ========================================================

        allowed, error_message = await self.check_rate_limit(
            message.author.id
        )

        if not allowed:
            await message.reply(
                error_message,
                mention_author=False,
            )
            return

        try:

            async with message.channel.typing():

                # =================================================
                # GET USER + CHANNEL MEMORY
                # =================================================

                conversation_key = (
                    message.author.id,
                    message.channel.id,
                )

                conversation = self.conversations[
                    conversation_key
                ]

                # =================================================
                # BUILD API MESSAGES
                # =================================================

                messages = [
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT,
                    },
                    *list(conversation),
                    {
                        "role": "user",
                        "content": user_message,
                    },
                ]

                # =================================================
                # CALL GROQ
                # =================================================

                response = await (
                    self.client.chat.completions.create(
                        model=MODEL,
                        messages=messages,
                        max_tokens=MAX_OUTPUT_TOKENS,
                        temperature=0.7,
                    )
                )

                answer = (
                    response.choices[0]
                    .message.content
                )

            # ====================================================
            # EMPTY RESPONSE
            # ====================================================

            if not answer:
                answer = (
                    "Sorry, I couldn't generate a response. "
                    "Try asking again."
                )

            # ====================================================
            # SAVE MEMORY
            # ====================================================

            conversation.append(
                {
                    "role": "user",
                    "content": user_message,
                }
            )

            conversation.append(
                {
                    "role": "assistant",
                    "content": answer,
                }
            )

            # ====================================================
            # SEND RESPONSE
            # ====================================================

            if len(answer) <= 2000:

                await message.reply(
                    answer,
                    mention_author=False,
                )

            else:

                chunks = [
                    answer[i:i + 2000]
                    for i in range(
                        0,
                        len(answer),
                        2000,
                    )
                ]

                for chunk in chunks:
                    await message.channel.send(
                        chunk
                    )

        # ========================================================
        # GROQ RATE LIMIT
        # ========================================================

        except RateLimitError:

            logger.warning(
                "Groq API rate limit reached."
            )

            await message.reply(
                "The AI service is currently busy. "
                "Please try again in a moment.",
                mention_author=False,
            )

        # ========================================================
        # CONNECTION ERROR
        # ========================================================

        except APIConnectionError:

            logger.exception(
                "Could not connect to Groq API."
            )

            await message.reply(
                "I couldn't connect to the AI service right now. "
                "Please try again shortly.",
                mention_author=False,
            )

        # ========================================================
        # API ERROR
        # ========================================================

        except APIError:

            logger.exception(
                "Groq API returned an error."
            )

            await message.reply(
                "The AI service encountered an error. "
                "Please try again later.",
                mention_author=False,
            )

        # ========================================================
        # UNKNOWN ERROR
        # ========================================================

        except Exception:

            logger.exception(
                "Unexpected error in GPT cog."
            )

            await message.reply(
                "Something unexpected went wrong.",
                mention_author=False,
            )


# ============================================================
# COG SETUP
# ============================================================

async def setup(bot: commands.Bot) -> None:
    """Load the GPT cog."""

    await bot.add_cog(GPT(bot))

    logger.info("GPT cog loaded successfully.")