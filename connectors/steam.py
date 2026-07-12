import aiohttp
from typing import Optional
from config import STEAM_API_TOKEN
from .base import GameConnector

class SteamConnector(GameConnector):
    def __init__(self):
        self.api_key = STEAM_API_TOKEN
        self.base_url = "https://api.steampowered.com"

    @property
    def game_name(self) -> str:
        return "Steam"

    async def verify_steam_id(self, steam_id64: str) -> Optional[dict]:
        """Vérifie si le SteamID64 est valide et retourne les infos du profil"""
        if not self.api_key:
            return None
            
        url = f"{self.base_url}/ISteamUser/GetPlayerSummaries/v0002/"
        params = {
            "key": self.api_key,
            "steamids": steam_id64
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    players = data.get("response", {}).get("players", [])
                    if players:
                        return players[0]
                return None

    async def resolve_vanity_url(self, vanity_name: str) -> Optional[str]:
        """Convertit un pseudo personnalisé (Vanity URL) en SteamID64"""
        if not self.api_key:
            return None
            
        url = f"{self.base_url}/ISteamUser/ResolveVanityURL/v0001/"
        params = {
            "key": self.api_key,
            "vanityurl": vanity_name
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    response_data = data.get("response", {})
                    if response_data.get("success") == 1:
                        return response_data.get("steamid")
                return None

    async def get_recently_played_games(self, steam_id64: str, count: int = 3) -> list[dict]:
        """Récupère les jeux récemment joués par l'utilisateur"""
        if not self.api_key:
            return []
            
        url = f"{self.base_url}/IPlayerService/GetRecentlyPlayedGames/v0001/"
        params = {
            "key": self.api_key,
            "steamid": steam_id64,
            "count": count
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    games = data.get("response", {}).get("games", [])
                    return games
                return []

    async def fetch_user_stats(self, account_id: str) -> dict:
        """Implémentation obligatoire de l'interface GameConnector"""
        return {}
