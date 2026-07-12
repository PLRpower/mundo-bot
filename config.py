import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
RIOT_API_KEY = os.getenv("RIOT_API_KEY")
STEAM_API_TOKEN = os.getenv("STEAM_API_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_KEY")
# Utilisation de aiosqlite pour SQLite asynchrone
DATABASE_URL = "sqlite+aiosqlite:///mundo_stats.db"
