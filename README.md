# Horizon Devs — Discord Bot

An advanced Discord bot tailored for the **Horizon Devs** developer community, built with Python, `discord.py`, and Supabase PostgreSQL.

---

## 🚀 Features & Commands

All commands are **hybrid commands** supporting both slash (`/command`) and prefix (`.command`) usage.

### 🛠️ Developer Tools (`bot/cogs/dev_tools.py`)
* **`/run <language> <code>`** — Execute code in an isolated sandbox (Python, JavaScript, TypeScript, C++, Rust, Go, Java, Bash, etc.).
* **`/github <owner/repo>`** — Fetch repository stats (stars ⭐, forks 🍴, open issues 🐛, license, default branch, primary language).
* **`/pypi <package>`** — Inspect Python package metadata, latest version, author, license, and install snippet.
* **`/cheat <query>`** — Instant command-line cheat sheet search via `cheat.sh` (e.g., `/cheat git rebase`, `/cheat tar`).

### 🌟 Community Showcase & Tech Roles (`bot/cogs/community.py`)
* **`/showcase`** — Opens an interactive popup modal to submit developer projects (Title, Tech Stack, Description, GitHub, Live Demo). Automatically creates a showcase card, adds an interactive `⭐ Upvote` button, and opens a feedback discussion thread.
* **`/techroles`** — Posts a self-assignable developer roles board (Frontend, Backend, Mobile, DevOps, AI/ML, Python, TypeScript, Rust) with auto-creation of missing server roles.

### 🏆 Dev Karma & Reputation (`bot/cogs/reputation.py`)
* **`/thank <@member> [reason]`** — Award 1 Dev Karma point to a member who helped you with code or debugging (with cooldown and anti-cheat guards).
* **`/karma [@member]`** — Check karma points, developer rank tier (*🌱 Junior Helper*, *🛠️ Code Contributor*, *🏆 Community Mentor*, *⚡ Lead Architect*, *🧙‍♂️ Horizon Tech Sage*), and tier progress bar.
* **`/leaderboard`** — View the top 10 most helpful developers and contributors in the server with medal badges (`🥇`, `🥈`, `🥉`).

### 🛡️ Moderation & Auto-Defense (`bot/cogs/moderation.py`)
* **Commands:** `/ban`, `/kick`, `/softban`, `/timeout`, `/remove_timeout`, `/unban`, `/purge`.
* **Automated Filtering:** Auto-deletes Discord invite links and adult domains with self-deleting warnings.
* **Audit & DM Notifications:** Sends clear moderation notices to users and logs timestamps in `Asia/Kolkata` timezone.

### ℹ️ General Utilities & Presence (`bot/cogs/general.py`, `/bot/utils/status.py`)
* **`/ping`** — Check bot latency.
* **`/server_info`** & **`/user_info`** — View server stats and detailed user profiles.
* **Rotating Dev Status:** Background task rotating live member counts and funny developer quotes every 10 seconds.

### 📖 Interactive Help (`bot/cogs/help.py`)
* **`/help`** — Dynamic interactive menu featuring dropdown category selectors for Developer Tools, Community & Karma, Moderation, and General Utilities.

---

## 🗄️ Database & Persistence (`Supabase`)

The bot integrates with **Supabase PostgreSQL**:
* **[schema.sql](bot/database/schema.sql)**: Complete database schema with `BIGINT` snowflakes and RLS policies:
  - `reputation`: User karma and points.
  - `reputation_logs`: Audit log of all karma awards.
  - `showcases`: Submitted community projects.
  - `showcase_votes`: Upvote records per user to prevent duplicate voting.
  - `top_developers`: Database view for ranking contributors.

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
Fill in your credentials:
```env
# [REQUIRED] Discord Bot Token
DISCORD_TOKEN="your-discord-bot-token"

# [DATABASE] Supabase Configuration
SUPABASE_URL="https://your-project.supabase.co"
SUPABASE_KEY="your-supabase-service-role-or-anon-key"

# [CODE EXECUTION] Piston Sandbox (Optional)
PISTON_URL="https://emkc.org/api/v2/piston"
PISTON_API_KEY=""
```

### 3. Run Database Schema
1. Open your project dashboard at [supabase.com](https://app.supabase.com).
2. Navigate to **SQL Editor** -> **New query**.
3. Paste the contents of `bot/database/schema.sql` and click **Run**.

### 4. Run the Bot
```bash
python app.py
```

### 5. Running Tests
```bash
pytest -v
```
All 18 automated tests will run with 0 errors and 0 warnings.
