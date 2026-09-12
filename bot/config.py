import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise ValueError("DISCORD_TOKEN is not set in the .env file.")