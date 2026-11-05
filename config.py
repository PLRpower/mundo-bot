import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
RIOT_API_KEY = os.getenv("RIOT_API_KEY")
STEAM_API_TOKEN = os.getenv("STEAM_API_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_KEY")
DESKBIRD_REFRESH_TOKEN = os.getenv("DESKBIRD_REFRESH_TOKEN")
DESKBIRD_API_KEY = os.getenv("DESKBIRD_API_KEY")
# Utilisation de aiosqlite pour SQLite asynchrone
DATABASE_URL = "sqlite+aiosqlite:///mundo_stats.db"
