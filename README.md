# ⚡ Horizon Devs — Discord Bot

A feature-rich Discord bot built for the **Horizon Devs** developer community.

The bot focuses on developer productivity, community participation, reputation, coding challenges, bounties, moderation, and useful developer utilities.

Built with **Python 3.11+**, **discord.py 2.x**, and **Supabase PostgreSQL**.

---

## 🚀 Features

### 🛠️ Developer Tools

Developer-focused utilities for working with GitHub, Python packages, JavaScript packages, JSON, regex, diffs, and command-line references.

| Command | Description |
|---|---|
| `/github <owner/repo>` | View GitHub repository information such as stars, forks, issues, language, license, and links. |
| `/github-user <username>` | View a GitHub user's public profile, repositories, followers, and account information. |
| `/github-commits <owner/repo>` | View recent commits from a GitHub repository. |
| `/pypi <package>` | Look up Python package metadata from PyPI. |
| `/npm <package>` | Look up Node.js / JavaScript package information from npm. |
| `/cheat <query>` | Search quick programming and CLI cheat sheets through cheat.sh. |
| `/json <data>` | Validate and pretty-print JSON. |
| `/diff` | Compare two pieces of text and display their differences. |
| `/regex` | Test a regular expression against text and inspect matches. |

> Developer tools are designed to be lightweight utilities that can be used directly from Discord.

---

## 🏆 Developer Challenges

The challenge system gives the community structured coding problems with difficulty tiers and submissions.

### Commands

| Command | Description |
|---|---|
| `/challenge post` | Create a new developer challenge. |
| `/challenge list` | Browse active and previous challenges. |
| `/challenge award` | Award Dev Karma to a successful solver. |
| `/challenge end` | End an active challenge. |

### Challenge Features

- 🟢 Easy / 🟡 Medium / 🔴 Hard difficulty tiers
- Custom point values
- Challenge deadlines
- Automatic discussion/submission threads
- Interactive solution submission modal
- GitHub repository submissions
- Live demo links
- Implementation and architecture notes
- Dev Karma rewards
- Admin/owner controls

Challenge submissions can be made through the interactive submission interface attached to the challenge.

---

## 💰 Dev Karma Bounties

The bounty system allows developers to post coding tasks with a Dev Karma reward.

### Commands

| Command | Description |
|---|---|
| `/bounty create` | Create a coding bounty with a Karma reward. |
| `/bounty list` | View currently open bounties. |
| `/bounty accept` | Accept a submitted solution and award the bounty reward. |
| `/bounty cancel` | Cancel an open bounty and return the escrowed reward. |

### Bounty Features

- Karma-based rewards
- Reward escrow
- Dedicated bounty discussion threads
- Interactive solution submission
- Creator-controlled solution acceptance
- Automatic bounty state management
- Protection against invalid reward transfers

---

## 🌟 Community Showcase

The showcase system lets developers share projects with the Horizon Devs community.

### `/showcase`

Opens an interactive submission modal for:

- Project title
- Tech stack
- Project description
- GitHub repository
- Live demo

After submission, the bot creates a showcase card with:

- ⭐ Upvote button
- Project information
- GitHub / demo links
- Dedicated feedback discussion thread

Showcase voting is persisted in the database to prevent duplicate votes.

---

## 🏅 Dev Karma & Reputation

The reputation system rewards members who actively help other developers.

### `/thank <member> [reason]`

Give another developer **1 Dev Karma** for helping with:

- Debugging
- Programming
- Code reviews
- Technical questions
- Project assistance

The system includes protection against:

- Self-awards
- Bot awards
- Repeated awards within the cooldown period

### `/karma [member]`

View a developer's:

- Current Dev Karma
- Rank
- Progress toward the next rank
- Reputation progress bar

### Developer Ranks

| Rank | Title |
|---|---|
| 🌱 | Junior Helper |
| 🛠️ | Code Contributor |
| 🏆 | Community Mentor |
| ⚡ | Lead Architect |
| 🧙 | Horizon Tech Sage |

### `/leaderboard`

Displays the top contributors in the server.

---

## 🛡️ Moderation

The moderation system provides server-management commands and automatic protection.

### Commands

| Command | Description |
|---|---|
| `/ban` | Ban a member. |
| `/kick` | Kick a member. |
| `/softban` | Ban and immediately unban a member to remove recent messages. |
| `/timeout` | Temporarily restrict a member. |
| `/remove_timeout` | Remove an active timeout. |
| `/unban` | Unban a user by Discord ID. |
| `/purge` | Bulk-delete messages. |

### Automatic Protection

The bot can automatically detect and remove configured:

- Discord invite links
- Blocked/adult domains

Temporary warning messages are used when automated filtering triggers.

### Moderation Notifications

Moderation actions can also provide users with clear notices containing the action and reason.

---

## ℹ️ General Utilities

### `/ping`

Check the bot's WebSocket latency.

### `/server_info`

View information about the current server, including:

- Member count
- Channel statistics
- Server owner
- Server information

### `/user_info [member]`

View information about a Discord member, including:

- Account creation date
- Server join date
- Roles
- Discord profile information

---

## 🤖 GPT Developer Assistant

The bot also includes an AI-powered developer assistant through:

`bot/cogs/gpt.py`

The assistant is designed around developer questions and can help with topics such as:

- Python
- JavaScript
- C++
- Web development
- Debugging
- Git
- GitHub
- Programming concepts
- Code explanations

The AI assistant is intended to operate inside the configured Discord AI channel and uses the project's configured AI provider.

---

## 📖 Interactive Help

### `/help`

The bot includes an interactive help interface with category selection.

Available categories:

- 🛠️ Developer Tools
- 🛡️ Moderation
- ℹ️ General Utilities
- 🌟 Community

The help menu uses a Discord select menu so users can switch between command categories without sending additional commands.

---

# 🗄️ Database

The bot uses **Supabase PostgreSQL** for persistent community data.

The database layer is located inside:

```text
bot/database/
├── client.py
├── queries.py
└── schema.sql
```

### Stored Data

The database schema contains systems for:

- Reputation / Dev Karma
- Reputation audit logs
- Showcase projects
- Showcase votes
- Developer challenges
- Challenge submissions
- Coding bounties
- Bounty rewards
- Developer leaderboard

The schema uses Discord snowflake IDs as `BIGINT` values and includes indexes for commonly queried data.

---

# 📁 Project Structure

```text
The-Discord-bot/
│
├── app.py
├── requirements.txt
├── pytest.ini
├── .env
├── .env.example
├── .gitignore
├── LICENSE
├── README.md
│
├── bot/
│   ├── __init__.py
│   ├── __main__.py
│   ├── config.py
│   ├── main.py
│   │
│   ├── cogs/
│   │   ├── __init__.py
│   │   ├── bounty.py
│   │   ├── challenge.py
│   │   ├── community.py
│   │   ├── dev_tools.py
│   │   ├── general.py
│   │   ├── gpt.py
│   │   ├── help.py
│   │   ├── moderation.py
│   │   └── reputation.py
│   │
│   ├── database/
│   │   ├── __init__.py
│   │   ├── client.py
│   │   ├── queries.py
│   │   └── schema.sql
│   │
│   └── utils/
│       ├── __init__.py
│       ├── checks.py
│       ├── http.py
│       └── status.py
│
└── tests/
```

---

# ⚙️ Requirements

- Python **3.11+**
- Discord bot application
- Supabase project
- Required API credentials for enabled external services

Python dependencies are listed in:

```text
requirements.txt
```

---

# 🔧 Installation

## 1. Clone the repository

```bash
git clone https://github.com/aridrochatterjee/The-Discord-bot.git
cd The-Discord-bot
```

---

## 2. Create a virtual environment

### Windows

```bash
py -3.13 -m venv .venv
.venv\Scripts\activate
```

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

# 🔐 Environment Configuration

Create your local `.env` file from `.env.example`.

```env
DISCORD_TOKEN="your_discord_bot_token"

SUPABASE_URL="https://your-project.supabase.co"
SUPABASE_KEY="your_supabase_key"
```

Add any additional API credentials required by the enabled bot features to your `.env` file.

### Important

Never commit your `.env` file.

The repository should contain:

```text
.env.example
```

but **not** your real:

```text
.env
```

---

# 🗃️ Database Setup

1. Create a project in Supabase.
2. Open the Supabase dashboard.
3. Go to **SQL Editor**.
4. Create a new SQL query.
5. Copy the contents of:

```text
bot/database/schema.sql
```

6. Run the SQL script.
7. Add the resulting Supabase URL and key to `.env`.

The bot uses the database for persistent reputation, challenges, showcases, bounties, and related community data.

---

# ▶️ Running the Bot

Start the application with:

```bash
python app.py
```

If your environment uses the Python launcher:

```bash
py app.py
```

Once connected successfully, the bot will load its configured cogs and synchronize its hybrid commands.

---

# 🧪 Testing

The project uses **pytest**.

Run:

```bash
pytest -v
```

Tests are organized under:

```text
tests/
```

The test suite covers important bot components such as:

- Permission checks
- Database operations
- Developer tools
- Help interface
- Reputation
- Challenges
- Bounties
- Community features

> Test counts may change as the project evolves, so the README intentionally does not hard-code a specific number of passing tests.

---

# 🔒 Security

This project handles Discord and database credentials, so keep secrets outside the repository.

Never commit:

```text
.env
```

API keys, bot tokens, and Supabase credentials should always be stored in environment variables.

If a secret is accidentally committed, rotate the credential immediately.

---

# 🧩 Architecture

The bot is organized around Discord.py cogs.

```text
Discord
   │
   ▼
app.py
   │
   ▼
bot/main.py
   │
   ├── General
   ├── Moderation
   ├── Developer Tools
   ├── GPT Assistant
   ├── Community
   ├── Reputation
   ├── Challenges
   ├── Bounties
   └── Help
          │
          ▼
     Database Layer
          │
          ▼
     Supabase PostgreSQL
```

Shared HTTP functionality is handled through:

```text
bot/utils/http.py
```

Permission helpers are located in:

```text
bot/utils/checks.py
```

Bot presence/status functionality is handled through:

```text
bot/utils/status.py
```

---

# 🛠️ Development

When adding a new feature:

1. Create or update the appropriate cog.
2. Keep database operations inside `bot/database/queries.py`.
3. Keep reusable permission logic inside `bot/utils/checks.py`.
4. Keep external HTTP session handling inside `bot/utils/http.py`.
5. Add tests for important behavior.
6. Update the README when public commands change.

### Example

A new moderation command belongs in:

```text
bot/cogs/moderation.py
```

A new database operation belongs in:

```text
bot/database/queries.py
```

A new developer utility belongs in:

```text
bot/cogs/dev_tools.py
```

---

# 🤝 Contributing

Contributions are welcome.

A typical contribution workflow is:

```text
Create branch
    ↓
Make changes
    ↓
Run tests
    ↓
Commit changes
    ↓
Push branch
    ↓
Open Pull Request
    ↓
Review
    ↓
Merge
```

Keep pull requests focused on one feature, bug fix, or improvement whenever possible.

---

# 📜 License

This project is licensed under the terms specified in:

```text
LICENSE
```

---

# ⚡ Horizon Devs

Built for developers, by developers.

**Code. Build. Learn. Help each other.**
```
