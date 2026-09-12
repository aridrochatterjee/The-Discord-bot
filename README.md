The Discord Bot

A simple Discord bot built with Python and `discord.py`.

This project uses a modular structure with **Cogs**, making it easier to organize commands and add new features.

---

## 📁 Project Structure

```text
The-Discord-bot/
│
├── bot/
│   ├── cogs/
│   │   ├── __init__.py
│   │   ├── general.py
│   │   └── moderation.py
│   │
│   ├── database/
│   │   └── __init__.py
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   └── checks.py
│   │
│   ├── __init__.py
│   ├── __main__.py
│   ├── config.py
│   └── main.py
│
├── tests/
│   └── __init__.py
│
├── .env
├── .gitignore
├── requirements.txt
└── README.md
````

---

# 🚀 Features

* Discord bot built with Python
* Modular Cog-based architecture
* General commands
* Moderation commands
* Environment variable configuration
* Easy to expand with new features

---

# 🛠️ Requirements

* Python 3.10+
* A Discord Bot Token

---

# 📦 Installation

## 1. Clone the repository

```bash
git clone https://github.com/aridrochatterjee/The-Discord-bot.git
```

Move into the project:

```bash
cd The-Discord-bot
```

---

## 2. Create a virtual environment

### Windows

```bash
python -m venv .venv
```

Activate it:

```powershell
.venv\Scripts\Activate.ps1
```

---

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

# 🔐 Environment Variables

Create a `.env` file in the root directory.

```env
DISCORD_TOKEN=your_bot_token_here
```

⚠️ Never upload your `.env` file or Discord token to GitHub.

The `.env` file should be included in `.gitignore`.

---

# ▶️ Running the Bot

Run the bot from the project root:

```bash
python -m bot
```

Do **not** run:

```bash
python bot/main.py
```

Running `python -m bot` ensures Python correctly recognizes the `bot` package.

---

# 📂 Cogs

Commands are organized using Discord.py Cogs.

Example structure:

```text
bot/cogs/
├── general.py
└── moderation.py
```

This makes the project easier to maintain and allows new features to be added without putting everything inside one file.

---

# 🌐 Hosting

The bot can be hosted using a Python hosting service or a server panel that supports:

* Git repositories
* Python
* Environment variables
* Automatic updates

The hosting service should run:

```bash
python -m bot
```

Make sure the correct startup file or startup command is configured.

---

# 🔄 Updating the Bot

When changes are made locally:

```bash
git add .
git commit -m "your commit message"
git push origin main
```

If your hosting provider supports Git auto-update, restarting the server should pull the latest changes.

---

# 🤝 Contributing

Contributions are welcome!

1. Fork the repository
2. Create a new branch

```bash
git checkout -b feature/your-feature
```

3. Make your changes
4. Commit them

```bash
git commit -m "feat: add new feature"
```

5. Push your branch
6. Open a Pull Request

---

# 📜 License

This project is licensed under the Apache License 2.0.

---

# 👨‍💻 Author

Created by **Aridro Chatterjee**

---

⭐ If you like this project, consider giving it a star!

```

### Important before we continue

For your new server, **we will not use "Reinstall Server" again**.

The correct approach is:

**GitHub → server clones repository → server runs bot**

And before touching anything, we'll verify each step carefully so nothing gets deleted again.
```
