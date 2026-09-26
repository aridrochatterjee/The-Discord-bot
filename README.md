# Horizon Devs Discord Bot

A modular Discord bot for the **Horizon Devs** programming community. It brings together community moderation, member support, coding challenges, reputation, and an optional AI coding helper.

> **Project status:** Under active development. Some features require Supabase configuration and the corresponding database schema. Check the setup sections before enabling them in your server.

---

## Contents

- [Features](#features)
- [Requirements](#requirements)
- [Getting Started](#getting-started)
- [Environment Configuration](#environment-configuration)
- [Discord Developer Portal Setup](#discord-developer-portal-setup)
- [Supabase Setup](#supabase-setup)
- [Running the Bot](#running-the-bot)
- [Commands](#commands)
- [AI Coding Helper](#ai-coding-helper)
- [Staff Member Profiles](#staff-member-profiles)
- [Project Structure](#project-structure)
- [Configuration Notes](#configuration-notes)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)

---

## Features

### Community moderation

- Ban, unban, kick, and softban members.
- Timeout and remove timeouts.
- Bulk-delete recent messages.
- Filter configured invite links and other disallowed links.
- Send moderation feedback through Discord interactions.
- Record bot-performed moderation actions in the database when the moderation-case schema and query helper are configured.

### Community tools

- Slash commands and hybrid commands, depending on the command.
- Coding challenges with difficulty-based points.
- Challenge submission interface using Discord interactions.
- Reputation and community contribution tracking.
- Optional AI coding helper restricted to a configured channel.

### Staff member profiles

The planned staff lookup tools provide a private overview of a member, including their Discord account and server details, staff-entered notes, and bot-recorded moderation cases.

This feature requires the matching member-profile cog, database helpers, and SQL schema to be installed. See [Staff Member Profiles](#staff-member-profiles).

---

## Requirements

- Python **3.13** (recommended for this project)
- A Discord application and bot token
- A Discord server where you have permission to add and configure bots
- Supabase project credentials for database-backed features
- A Groq API key if you want to use the AI coding helper

The project uses `discord.py` and environment variables loaded from a `.env` file. Database-backed functionality uses Supabase.

---

## Getting Started

### 1. Clone the repository

```powershell
git clone https://github.com/aridrochatterjee/The-Discord-bot.git
cd The-Discord-bot
```

### 2. Create a virtual environment

On Windows, using Python 3.13:

```powershell
py -3.13 -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, you can run the environment's Python directly instead:

```powershell
.\.venv\Scripts\python.exe --version
```

Or, for the current PowerShell session only, allow local activation scripts:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If `python` does not point to the virtual environment's interpreter, use:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root. Add the environment variables expected by your local `bot/config.py`.

Example:

```dotenv
TOKEN=your_discord_bot_token

SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_api_key

GROQ_API_KEY=your_groq_api_key
```

Replace the example values with your own credentials. Do not include quotation marks unless your value requires them.

**Important:**
- Never commit `.env` or share your bot token or API keys.
- Do not use a Supabase service-role key in a public repository or expose it in client-side code.
- The AI helper is optional. If you do not use it, leave its API key unset and disable or avoid loading that feature as appropriate for your codebase.
- Variable names must match the names read by `bot/config.py`. If you changed the configuration file, update this example to match.

### 5. Invite the bot to your server

In the Discord Developer Portal, open your application and use **OAuth2 → URL Generator** to create an invite link.

Select the scopes required by the bot:

- `bot`
- `applications.commands`

Choose the bot permissions needed for the commands you intend to use. Typical permissions may include:

- View Channels
- Send Messages
- Embed Links
- Read Message History
- Manage Messages
- Kick Members
- Ban Members
- Moderate Members
- View Audit Log, if you use any audit-log-based tooling

Only grant permissions that the bot actually needs. Discord role hierarchy also applies: the bot's highest role must be above members and roles it needs to moderate.

---

## Environment Configuration

| Variable | Purpose |
|---|---|
| `TOKEN` | Discord bot token |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_KEY` | Supabase API key used by the bot |
| `GROQ_API_KEY` | API key for the optional Groq-powered AI helper |

The exact variable names are determined by your `bot/config.py`. If your local configuration uses different names, use those names in `.env`.

---

## Discord Developer Portal Setup

### Enable privileged intents

Open your application in the [Discord Developer Portal](https://discord.com/developers/applications).

Go to **Bot → Privileged Gateway Intents** and enable the intents needed by the bot:

- **Server Members Intent** — needed for member-related events and reliable member information.
- **Message Content Intent** — needed if the bot reads message content for prefix commands or link filtering.

The corresponding intents must also be enabled in the bot's code. Enabling them in the portal alone is not enough.

If you change the intents, restart the bot after saving the portal settings.

### Configure permissions and role order

1. Invite the bot with the permissions it needs.
2. In your server's role settings, move the bot role above roles it must manage.
3. Avoid giving the bot Administrator unless it is genuinely necessary.
4. For staff-only commands, configure command checks and staff permissions in the bot code.

---

## Supabase Setup

Database-backed features need a Supabase project and the matching SQL schema.

### 1. Create a project

1. Open [Supabase](https://supabase.com/).
2. Create a project.
3. Copy the project URL and API key from the project's API settings.
4. Put the values into your local `.env` file.

Use the key type and access policy intended for your bot's server-side use. Never expose privileged keys in a public client application.

### 2. Apply the schema

Open the Supabase project and go to **SQL Editor**.

Run the SQL schema file included with your local project, if present. If you are setting up member profiles and moderation history, also apply the SQL statements for those tables.

The member-profile feature expects tables for:

- Staff-maintained member profile information
- First-seen records, if enabled
- Bot-recorded moderation cases

Use the exact table and column names expected by your `bot/database/queries.py` implementation. The SQL and query code must match.

### 3. Verify the connection

Start the bot and inspect the console logs. A successful initialization message from the database client indicates that the Supabase client was created. It does not, by itself, prove that every table or query is configured correctly.

If the database client is unavailable, database-backed features may not work until the connection settings are corrected.

---

## Running the Bot

From the project root, with the virtual environment activated:

```powershell
python main.py
```

If your project entry point is located under `bot/`, use the actual entry-point file in your checkout. For example:

```powershell
python -m bot.main
```

Use the entry point that exists in your local repository. Do not run both commands at once.

When the bot starts, check the console for:
- Successful Discord login
- Database initialization status
- Cog loading messages
- Slash-command synchronization messages
- Any missing environment variables or failed extensions

After changing commands or cogs, restart the bot and confirm that the updated commands have synchronized.

---

## Commands

The commands below describe the command set developed for this bot. Commands may be unavailable if their cog is not loaded, the relevant database setup is missing, or the bot lacks Discord permissions.

### Moderation

| Command | Description |
|---|---|
| `/ban` | Ban a member from the server |
| `/unban` | Remove a ban |
| `/kick` | Kick a member |
| `/softban` | Ban and then unban a member to remove recent messages, subject to Discord API success |
| `/timeout` | Apply a timeout to a member |
| `/remove_timeout` | Remove a member's timeout |
| `/purge` | Bulk-delete a limited number of recent messages |

Moderation commands require the relevant Discord permissions and must respect role hierarchy.

The bot may store successful moderation actions in its own case history when database logging is configured. This is a bot-maintained record, not a complete record of every action ever taken by all moderators.

### Coding challenges

| Command | Description |
|---|---|
| `/challenge post` | Create or publish a coding challenge |

Challenge submissions use a Discord interaction interface. The exact challenge workflow and any additional commands depend on the currently installed challenge cog.

The project's configured point values are:

| Difficulty | Points |
|---|---:|
| Easy | 5 |
| Medium | 10 |
| Hard | 15 |

### Reputation

The bot includes reputation and contribution tracking backed by Supabase. The exact command names and available management actions depend on the loaded reputation cog and the database schema installed in your project.

### AI coding helper

See [AI Coding Helper](#ai-coding-helper) for setup and usage details.

### Staff member profiles

See [Staff Member Profiles](#staff-member-profiles) for the staff lookup and profile tools.

---

## AI Coding Helper

The optional AI helper uses the Groq API through an OpenAI-compatible endpoint. It is intended to support community members with programming questions and short explanations.

### Intended scope

The helper is designed for topics such as:

- Programming and software development
- Debugging small code snippets
- Programming concepts
- Math and physics questions
- History questions

It should keep answers beginner-friendly and concise, use code blocks when useful, and avoid Markdown tables.

The helper is not intended to generate or manage entire projects on demand. It may ignore messages outside its configured topic scope.

### Configure the AI channel

The `/ai_channel` command configures the channel where the helper listens. It requires the appropriate server-management permission.

The helper is designed to respond only when mentioned in the configured channel. It ignores messages from bots and webhooks, direct messages, and messages outside the configured channel.

Channel configuration and short conversation history may be stored in memory, depending on the implementation. If they are not persisted to a database, they reset when the bot restarts.

### API configuration

Set the Groq API key in `.env` using the variable name read by your `bot/config.py`, commonly:

```dotenv
GROQ_API_KEY=your_groq_api_key
```

The current implementation may specify the model and API endpoint directly in the AI cog. Check the settings in that file before changing providers or models.

### Rate limits

The AI cog uses application-level rate limits to reduce spam and API usage. These limits are separate from any provider-side rate limits. If the API provider rejects requests or the configured key is invalid, check the bot logs and provider dashboard.

---

## Staff Member Profiles

The staff member lookup feature is intended to give authorized staff a private, organized view of a member's information.

### Planned command layout

| Command | Description |
|---|---|
| `/member lookup <member>` | Show a private staff overview of a member |
| `/member profile set <member> <bio> [notes]` | Add or update staff-maintained profile information |
| `/member profile remove <member>` | Remove the staff-maintained profile |
| `/member history <member>` | Show bot-recorded moderation cases for a member |

These commands require the corresponding member-profile cog and database helpers to be installed and loaded. They may not be available in older versions of the repository.

### Information shown

The overview may include Discord-provided details such as:

- Username and display name
- Discord user ID
- Account creation date
- Current server join date
- Current nickname and roles, where available
- Avatar

Staff-entered information is kept separate from Discord account information. Staff notes should be factual and relevant to moderation or community administration.

### Moderation history limitations

The history view can show only cases that the bot has actually recorded. It cannot reliably reconstruct every past action taken by other bots or moderators.

If there are no stored cases, the interface should say that there are **no bot-recorded cases**. This does not prove that the member has never received a warning, timeout, kick, or ban.

First-seen records can only be collected while the bot is running and configured to observe members. The bot cannot recover an earlier first-seen date if it was not previously recording it.

### Privacy and access

Member profiles and moderation history should be restricted to authorized staff and returned privately. Do not use the feature to infer a member's personality, trustworthiness, or intent from limited account or moderation data.

---

## Project Structure

The repository is organized around a main bot entry point, cogs for individual feature areas, and database helpers.

A typical layout may look like this:

```text
The-Discord-bot/
├── bot/
│   ├── cogs/
│   │   ├── general.py
│   │   ├── moderation.py
│   │   ├── gpt.py
│   │   ├── challenge.py
│   │   └── ...
│   ├── database/
│   │   ├── client.py
│   │   └── queries.py
│   └── config.py
├── .env
├── .gitignore
├── requirements.txt
└── main.py
```

The exact filenames can differ between branches and versions. Refer to your checked-out repository for the authoritative structure.

### Main areas

- `bot/cogs/` — Discord commands, listeners, and feature-specific logic.
- `bot/database/` — Supabase initialization and query helpers.
- `bot/config.py` — environment variable loading and configuration.
- `main.py` — application entry point, if present in your checkout.
- `.env` — local secrets and environment configuration; do not commit this file.

---

## Configuration Notes

### Keep secrets out of Git

Your `.gitignore` should exclude at least:

```gitignore
.env
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
.ruff_cache/
```

If a token or API key is accidentally committed, revoke or rotate it. Removing it from the latest commit does not guarantee it has been removed from Git history.

### Configure command permissions

Discord application commands and bot-side checks are separate layers. For sensitive actions:

- Check permissions in the command implementation.
- Use Discord's command permission settings where appropriate.
- Keep the bot role below trusted staff roles only if the bot does not need to manage them; place it above roles it must moderate.
- Use private interaction responses for staff-only information.

### Database schema changes

When adding or changing a database-backed feature:

1. Update the SQL schema.
2. Update the matching query helper.
3. Update the cog that calls the helper.
4. Test the query against your development Supabase project.
5. Document any new environment variables or permissions.

Keep the schema and application code in sync.

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'discord'`

Install dependencies using the Python interpreter from your virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Then run the bot with that same interpreter:

```powershell
.\.venv\Scripts\python.exe main.py
```

### PowerShell will not activate `.venv`

For the current terminal session, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Alternatively, call `.venv\Scripts\python.exe` directly without activating the environment.

### The bot starts, but commands do not appear

Check the following:

1. Confirm the bot has been invited with the `applications.commands` scope.
2. Check the console for cog-loading or command-sync errors.
3. Confirm that the cog containing the command is loaded.
4. Restart the bot after command changes.
5. Confirm the command is available in the server where you are testing.
6. Check whether the command has permission restrictions.

### The bot cannot read message content

If the bot needs message content for prefix commands or link filtering:

1. Enable **Message Content Intent** in the Discord Developer Portal.
2. Confirm the intent is enabled in the bot's code.
3. Restart the bot.

### Member information or member events are missing

Enable **Server Members Intent** in the Discord Developer Portal and in the bot's code. Also verify that the bot is in the server and has the permissions needed for the relevant operation.

### Supabase initialization fails

Check:

- `SUPABASE_URL` is the project URL, not a dashboard URL.
- `SUPABASE_KEY` is set and copied correctly.
- The `.env` file is in the expected project directory.
- The environment variable names match `bot/config.py`.
- Your network can reach Supabase.

A successful client initialization does not guarantee that all expected tables exist. If a query fails, verify that the SQL schema has been applied and matches the query helper's table and column names.

### AI requests fail

Check:

- The API key is present and valid.
- The key is loaded under the variable name expected by the cog.
- The configured model and endpoint are valid for your provider.
- Your provider account has available quota.
- The bot logs for API errors and rate-limit responses.

### Moderation commands fail

Check:

- The bot has the required Discord permission.
- The bot role is above the target member's highest role.
- The target is in the server, if the command requires a current member.
- The requested action meets Discord's API limits and requirements.

---

## Development

### Working on a feature

1. Create a branch for the change.
2. Keep feature logic inside the relevant cog or module.
3. Keep database access in the database layer rather than duplicating query code across cogs.
4. Add or update the required SQL schema when introducing database-backed functionality.
5. Test commands in a development server before using them in a live community.
6. Update this README if the command interface, configuration, or setup steps change.

### Suggested local checks

If the repository includes these tools, run them before opening a pull request:

```powershell
python -m compileall .
```

If Ruff is installed:

```powershell
ruff check .
```

If pytest tests are present:

```powershell
pytest
```

Only report checks as passing if you have actually run them in your current environment.

---

## Contributing

Contributions, bug reports, and improvements are welcome.

Before submitting a change:

- Keep pull requests focused on a clear feature or fix.
- Explain what changed and why.
- Include steps to reproduce bugs and describe the expected behavior.
- Do not include tokens, API keys, private server data, or member information in issues or pull requests.
- Test changes in a development server when they affect Discord commands or permissions.
- Update documentation when setup instructions or command behavior changes.

For larger changes, open an issue or discussion first so the implementation can be coordinated.

---

## License

Add the project's chosen open-source license here before publishing or redistributing the repository. Until a license file is present, do not assume that the project is licensed for unrestricted reuse.
