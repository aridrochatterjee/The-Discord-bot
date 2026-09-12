from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

# Discord Bot Token
TOKEN = os.getenv("DISCORD_TOKEN")

# Supabase Credentials (Optional on boot, required for persistent features)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_ANON_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

# Piston Code Execution API (Default or Self-Hosted)
PISTON_URL = os.getenv("PISTON_URL", "https://emkc.org/api/v2/piston")
PISTON_API_KEY = os.getenv("PISTON_API_KEY")