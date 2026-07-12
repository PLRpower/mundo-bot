import aiohttp
from typing import Optional
from config import RIOT_API_KEY
from .base import GameConnector

class RiotConnector(GameConnector):
    def __init__(self):
        self.api_key = RIOT_API_KEY
        # Endpoint Account V1 (valable pour toute l'Europe et gère les Riot ID globaux)
        self.account_url = "https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id"
        self.match_url = "https://europe.api.riotgames.com/lol/match/v5/matches"

    @property
    def game_name(self) -> str:
        return "Riot Games"

    async def get_puuid(self, game_name: str, tag_line: str) -> Optional[str]:
        """Récupère le PUUID à partir d'un Riot ID (Pseudo#Tag)"""
        if not self.api_key:
            return None
            
        headers = {"X-Riot-Token": self.api_key}
        url = f"{self.account_url}/{game_name}/{tag_line}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("puuid")
                return None

    async def get_match_ids(self, puuid: str, count: int = 20) -> list[str]:
        """Récupère les IDs des dernières parties"""
        if not self.api_key:
            return []
            
        headers = {"X-Riot-Token": self.api_key}
        ids_url = f"{self.match_url}/by-puuid/{puuid}/ids?start=0&count={count}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(ids_url, headers=headers) as response:
                if response.status != 200:
                    return []
                return await response.json()

    async def get_match_details(self, match_id: str) -> Optional[dict]:
        """Récupère les détails d'un match spécifique"""
        if not self.api_key:
            return None
            
        headers = {"X-Riot-Token": self.api_key}
        detail_url = f"{self.match_url}/{match_id}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(detail_url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                return None

    async def get_last_matches(self, puuid: str, count: int = 3) -> list[dict]:
        """Récupère les détails des dernières parties de League of Legends en direct"""
        match_ids = await self.get_match_ids(puuid, count)
        matches_data = []
        for match_id in match_ids:
            detail = await self.get_match_details(match_id)
            if detail:
                matches_data.append(detail)
        return matches_data

    async def get_match_timeline(self, match_id: str) -> dict:
        """Récupère la timeline détaillée d'une partie de League of Legends"""
        if not self.api_key:
            return {}
            
        headers = {"X-Riot-Token": self.api_key}
        url = f"{self.match_url}/{match_id}/timeline"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                return {}

    async def fetch_user_stats(self, account_id: str) -> dict:
        """Implémentation obligatoire de l'interface GameConnector"""
        return {}

    async def get_active_game(self, puuid: str) -> Optional[dict]:
        """Vérifie si le joueur est actuellement dans une partie et renvoie les détails"""
        if not self.api_key:
            return None
            
        headers = {"X-Riot-Token": self.api_key}
        url = f"https://euw1.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{puuid}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                return None

    async def _fetch_league_entries(self, session, summoner_id: str, headers: dict) -> str:
        url_league = f"https://euw1.api.riotgames.com/lol/league/v4/entries/by-summoner/{summoner_id}"
        
        for _ in range(3):
            async with session.get(url_league, headers=headers) as resp:
                if resp.status == 429:
                    retry_after = int(resp.headers.get("Retry-After", 1))
                    import asyncio
                    await asyncio.sleep(retry_after)
                    continue
                if resp.status != 200:
                    return "Unranked"
                entries = await resp.json()
                
                best_entry = None
                for entry in entries:
                    if entry.get("queueType") == "RANKED_SOLO_5x5":
                        best_entry = entry
                        break
                    elif entry.get("queueType") == "RANKED_FLEX_SR":
                        best_entry = entry
                        
                if best_entry:
                    tier = best_entry.get("tier", "").capitalize()
                    rank = best_entry.get("rank", "")
                    lp = best_entry.get("leaguePoints", 0)
                    wins = best_entry.get("wins", 0)
                    losses = best_entry.get("losses", 0)
                    total_games = wins + losses
                    winrate = int((wins / total_games) * 100) if total_games > 0 else 0
                    q_type = "Solo/Duo" if best_entry.get("queueType") == "RANKED_SOLO_5x5" else "Flex"
                    return f"{tier} {rank} ({lp} LP) - {winrate}% WR ({q_type})"
                    
                return "Unranked"
        return "Unranked"

    async def get_summoner_rank_by_id(self, summoner_id: str) -> str:
        if not self.api_key:
            return "Unranked"
            
        headers = {"X-Riot-Token": self.api_key}
        async with aiohttp.ClientSession() as session:
            return await self._fetch_league_entries(session, summoner_id, headers)

    async def get_summoner_rank(self, puuid: str) -> str:
        if not self.api_key:
            return "Unranked"
            
        headers = {"X-Riot-Token": self.api_key}
        
        async with aiohttp.ClientSession() as session:
            # Get summoner id
            url_summoner = f"https://euw1.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
            for _ in range(3):
                async with session.get(url_summoner, headers=headers) as resp:
                    if resp.status == 429:
                        retry_after = int(resp.headers.get("Retry-After", 1))
                        import asyncio
                        await asyncio.sleep(retry_after)
                        continue
                    if resp.status != 200:
                        return "Unranked"
                    summoner = await resp.json()
                    summoner_id = summoner.get("id")
                    return await self._fetch_league_entries(session, summoner_id, headers)
            return "Unranked"
