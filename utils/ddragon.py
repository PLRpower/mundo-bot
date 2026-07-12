import aiohttp
import json
import os

class DataDragon:
    def __init__(self):
        self.version = "14.6.1"  # Default fallback
        self.champions = {}
        self.summoner_spells = {}
        self.runes = {}
        self.rune_trees = []
        self.items = {}
        self.initialized = False

    async def init(self):
        if self.initialized:
            return
            
        async with aiohttp.ClientSession() as session:
            # Get latest version
            async with session.get("https://ddragon.leagueoflegends.com/api/versions.json") as resp:
                if resp.status == 200:
                    versions = await resp.json()
                    self.version = versions[0]

            # Fetch Summoner Spells
            async with session.get(f"https://ddragon.leagueoflegends.com/cdn/{self.version}/data/en_US/summoner.json") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for key, spell in data["data"].items():
                        self.summoner_spells[str(spell["key"])] = spell["id"]
                        
            # Fetch Champions mapping
            async with session.get(f"https://ddragon.leagueoflegends.com/cdn/{self.version}/data/en_US/champion.json") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for key, champ in data["data"].items():
                        self.champions[str(champ["key"])] = champ["id"]
                        
            # Fetch Runes (perks)
            async with session.get(f"https://ddragon.leagueoflegends.com/cdn/{self.version}/data/en_US/runesReforged.json") as resp:
                if resp.status == 200:
                    self.rune_trees = await resp.json()
                    for tree in self.rune_trees:
                        # Add tree itself
                        self.runes[tree["id"]] = tree["icon"]
                        for slot in tree["slots"]:
                            for rune in slot["runes"]:
                                self.runes[rune["id"]] = rune["icon"]
                                
            # Fetch Items
            async with session.get(f"https://ddragon.leagueoflegends.com/cdn/{self.version}/data/en_US/item.json") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.items = data["data"]
                                
        self.initialized = True

    def get_champion_name(self, champion_id: int) -> str:
        return self.champions.get(str(champion_id), f"Champion {champion_id}")

    def get_champion_url(self, champion_name: str) -> str:
        # Some champion names from API differ slightly from ddragon (e.g. FiddleSticks -> Fiddlesticks, MonkeyKing -> Wukong)
        # We assume the name provided by Riot API is mostly correct for DDragon
        if champion_name == "FiddleSticks": champion_name = "Fiddlesticks"
        return f"https://ddragon.leagueoflegends.com/cdn/{self.version}/img/champion/{champion_name}.png"

    def get_item_url(self, item_id: int) -> str:
        if item_id == 0:
            return "" # empty slot
        return f"https://ddragon.leagueoflegends.com/cdn/{self.version}/img/item/{item_id}.png"

    def get_spell_url(self, spell_id: int) -> str:
        spell_key = self.summoner_spells.get(str(spell_id))
        if spell_key:
            return f"https://ddragon.leagueoflegends.com/cdn/{self.version}/img/spell/{spell_key}.png"
        return ""

    def get_rune_url(self, rune_id: int) -> str:
        rune_path = self.runes.get(rune_id)
        if rune_path:
            return f"https://ddragon.leagueoflegends.com/cdn/img/{rune_path}"
        return ""

ddragon = DataDragon()
