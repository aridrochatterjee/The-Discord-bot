# ⚡ Horizon Devs — Discord Bot

An advanced, feature-packed Discord bot tailored for the **Horizon Devs** developer community. Built with Python 3.11+, `discord.py` 2.0+ (hybrid slash & prefix commands), and Supabase PostgreSQL.

---

## 🚀 Features & Commands Overview

All commands are **hybrid commands** supporting both slash (`/command`) and prefix (`.command`) interactions with full ephemeral error reporting, interactive modals, and persistent buttons.

### 🛠️ Developer Tools (`bot/cogs/dev_tools.py`)
* **`/run <language> <code>`** — Execute code in an isolated sandbox via Judge0 CE (Python, JavaScript, TypeScript, C++, Rust, Go, Java, Bash, and 15+ others). Supports fenced markdown codeblocks (` ```python ... ``` `).
* **`/github <owner/repo>`** — Fetch GitHub repository statistics (stars ⭐, forks 🍴, open issues 🐛, license, default branch, primary language, and repository links).
* **`/pypi <package>`** — Inspect Python package metadata on PyPI (latest version, summary, author, license, and `pip install` snippets).
* **`/npm <package>`** — Inspect Node.js/JavaScript package metadata on npm (latest version, description, formatted weekly downloads, license, direct & dev dependencies count, and `npm i` install snippets).
* **`/cheat <query>`** — Instant command-line and programming cheat sheet search powered by `cheat.sh` (e.g. `/cheat git rebase`, `/cheat tar`, `/cheat docker`).

---

### 🤖 Daily Developer Challenges (`bot/cogs/challenge.py`)
Engage the developer community with daily coding challenges, difficulty points, and automated threads:
* **`/challenge post <title> <description> [day_number] [rules] [easy_pts] [med_pts] [hard_pts] [duration_days] [ping_role]`** — *(Owner/Admin only)* Post daily coding challenges with customizable difficulty tiers (🟢 Easy, 🟡 Medium, 🔴 Hard), points, countdown timer, auto-created submission thread, and an interactive `🚀 Submit Solution` modal button.
* **`/challenge award <id> <member> <points> [reason]`** — *(Owner/Admin only)* Award Dev Karma points directly to solvers and mark submissions as accepted.
* **`/challenge end <id>`** — *(Owner/Admin only)* Close active challenges to lock new submissions.
* **`/challenge list`** — Browse active and past challenges with deadlines and point structures.
* **Interactive Submission Modal (`ChallengeSubmissionModal`)** — Prompts solvers for GitHub repository URL, live demo link, difficulty tier attempted, and architecture/implementation notes.

---

### 💰 Dev Karma Bounties (`bot/cogs/bounty.py`)
Peer-to-peer coding bounty economy backed by Dev Karma points:
* **`/bounty create <title> <reward_karma> <description>`** — Post a challenging bug or feature request, staking Dev Karma points held in escrow. Automatically creates an announcement card with a `💡 Submit Solution` button and a dedicated discussion thread.
* **`/bounty accept <bounty_id> <@solver>`** — The creator (or administrator) confirms a winning solution, instantly transferring the escrowed Dev Karma reward to `@solver` and marking the bounty `RESOLVED`.
* **`/bounty cancel <bounty_id>`** — Cancel an unsolved bounty to refund the escrowed karma points back to the creator.
* **`/bounty list`** — Browse currently open coding bounties in the server.

---

### 🌟 Community Showcase (`bot/cogs/community.py`)
* **`/showcase`** — Opens an interactive popup modal to submit developer projects (Title, Tech Stack, Description, GitHub, Live Demo). Automatically creates a showcase card, attaches an interactive `⭐ Upvote` button (persistent across restarts), and opens a dedicated feedback discussion thread.

---

### 🏆 Dev Karma & Reputation (`bot/cogs/reputation.py`)
* **`/thank <@member> [reason]`** — Award 1 Dev Karma point to a member who helped you with code or debugging.
  - **Daily Limiter:** Strictly limited to **once per day per recipient** (rolling 24-hour window per user pair). Duplicate attempts reject the karma and show remaining hours/minutes.
  - **Anti-Cheat:** Prevents self-thanking and bot-thanking.
* **`/karma [@member]`** — Check karma points, developer rank tier (*🌱 Junior Helper*, *🛠️ Code Contributor*, *🏆 Community Mentor*, *⚡ Lead Architect*, *🧙‍♂️ Horizon Tech Sage*), and ASCII progress bar toward the next rank.
* **`/leaderboard`** — View the top 10 most helpful developers and contributors in the server with medal badges (`🥇`, `🥈`, `🥉`).

---

### 🛡️ Moderation & Auto-Defense (`bot/cogs/moderation.py`)
* **Commands:** `/ban`, `/kick`, `/softban`, `/timeout`, `/remove_timeout`, `/unban`, `/purge`.
* **Automated Filtering:** Auto-deletes Discord invite links and adult domains with self-deleting warnings.
* **Audit & DM Notifications:** Sends clear moderation notices to users with reasons and logs timestamps in `Asia/Kolkata` timezone.

---

### ℹ️ General Utilities & Presence (`bot/cogs/general.py`, `/bot/utils/status.py`)
* **`/ping`** — Check bot websocket latency.
* **`/server_info`** & **`/user_info`** — View server stats, channel counts, and detailed user profiles.
* **Rotating Dev Status:** Background task rotating live member counts and funny developer quotes every 10 seconds.

---

### 📖 Interactive Help (`bot/cogs/help.py`)
* **`/help`** — Dynamic interactive select menu with categorized command embeds for Developer Tools, Community & Challenges, Moderation, and General Utilities.

---

## 🗄️ Database & Schema (`Supabase PostgreSQL`)

The bot integrates with **Supabase PostgreSQL** via REST and async postgrest client:
* **[`bot/database/schema.sql`](bot/database/schema.sql)** — Complete database schema with `BIGINT` snowflakes, performance indexes, and Row-Level Security (RLS) policies:
  - `reputation` — User karma points and timestamps.
  - `reputation_logs` — Audit log of all karma awards and bounty transfers.
  - `showcases` — Submitted community developer projects.
  - `showcase_votes` — Upvote records per user to prevent duplicate voting.
  - `challenges` — Daily developer challenges with difficulty tiers and deadlines.
  - `challenge_submissions` — Member challenge submissions with GitHub repos and demo links.
  - `bounties` — Coding bounties with escrowed Dev Karma rewards and solver records.
  - `top_developers` — Database view for server-wide leaderboard rankings.

---

## ⚙️ Setup & Installation

### 1. Clone & Install Dependencies
```bash
git clone https://github.com/aridrochatterjee/The-Discord-bot.git
cd The-Discord-bot
pip install -r requirements.txt
```

### 2. Configure Environment Variables (`.env`)
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Fill in your configuration:
```env
# [REQUIRED] Discord Bot Token
# https://discord.com/developers/applications
DISCORD_TOKEN="your_discord_bot_token_here"

# [DATABASE] Supabase Configuration
SUPABASE_URL="https://your-project-ref.supabase.co"
SUPABASE_KEY="your_supabase_anon_or_service_role_key_here"

# [CODE EXECUTION] Judge0 CE Configuration
# Option A: RapidAPI Free Tier (50 free runs/day)
# https://rapidapi.com/judge0-official/api/judge0-ce
JUDGE0_URL="https://judge0-ce.p.rapidapi.com"
RAPIDAPI_KEY="your_rapidapi_key_here"

# Option B: Self-Hosted Judge0 via Docker (Free & Unlimited)
# docker run -d -p 2358:2358 judge0/judge0
# JUDGE0_URL="http://localhost:2358"
# RAPIDAPI_KEY=""
```

### 3. Run Database Schema
1. Open your project dashboard at [supabase.com](https://app.supabase.com).
2. Navigate to **SQL Editor** -> **New query**.
3. Paste the contents of [`bot/database/schema.sql`](bot/database/schema.sql) and click **Run**.

### 4. Run the Bot
```bash
python app.py
```

### 5. Running Automated Tests
```bash
pytest -v
```
All **28 automated tests** will execute with 0 errors and 0 warnings:
```text
============================= 28 passed in 0.50s ==============================
```

---

## 📁 Project Structure

```text
The-Discord-bot/
├── app.py                      # Application entry point
├── requirements.txt            # Dependencies (discord.py, supabase, aiohttp, etc.)
├── pytest.ini                  # Pytest configuration (filters audioop deprecation)
├── .env.example                # Environment variable configuration template
├── README.md                   # Project documentation
├── bot/
│   ├── config.py               # Central environment variable parser
│   ├── main.py                 # Bot client setup, view registration, error handlers
│   ├── cogs/
│   │   ├── general.py          # /ping, /server_info, /user_info
│   │   ├── moderation.py       # /ban, /kick, /timeout, auto-defense filters
│   │   ├── dev_tools.py        # /run (Judge0), /github, /pypi, /npm, /cheat
│   │   ├── community.py        # /showcase, modal submissions, upvotes, threads
│   │   ├── reputation.py       # /thank, /karma, /leaderboard (24h cooldown)
│   │   ├── challenge.py        # /challenge post, submit, award, end, list
│   │   ├── bounty.py           # /bounty create, list, accept, cancel
│   │   └── help.py             # /help interactive category dropdown
│   ├── database/
│   │   ├── client.py           # Supabase async client initialization
│   │   ├── queries.py          # Reputation, showcase, challenge & bounty queries
│   │   └── schema.sql          # PostgreSQL DDL, tables, views, RLS policies
│   └── utils/
│       ├── checks.py           # is_admin_or_owner(), is_admin(), is_guild_owner()
│       ├── http.py             # Shared aiohttp ClientSession manager
│       └── status.py           # Rotating member count and developer quotes
└── tests/
    ├── test_checks.py          # Unit tests for permission decorators
    ├── test_community.py       # Unit tests for showcase modal and upvotes
    ├── test_database.py        # Unit tests for karma, thank cooldown, fallbacks
    ├── test_dev_tools.py       # Unit tests for Judge0, github parsing, npm parsing
    ├── test_help.py            # Unit tests for interactive help select options
    ├── test_reputation.py      # Unit tests for karma tiers and progress bar
    ├── test_challenge.py       # Unit tests for challenge modals, views, checks
    └── test_bounty.py          # Unit tests for bounty modals, views, escrow guards
```
