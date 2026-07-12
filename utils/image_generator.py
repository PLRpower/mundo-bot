import os
import tempfile
from jinja2 import Environment, FileSystemLoader
from html2image import Html2Image
from utils.ddragon import ddragon

LOCALES = {
    "fr": {
        "just_now": "À l'instant",
        "h_ago": "h",
        "d_ago": "j",
        "victory": "Victoire",
        "defeat": "Défaite",
        "blue_team": "Équipe Bleue",
        "red_team": "Équipe Rouge",
        "kills": "Kills",
        "dragons": "Dragons",
        "towers": "Tours",
        "damage": "Dégâts",
        "vision": "Vision",
        "match_of": "Match de",
        "game": "Partie",
        "months": ["", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
    },
    "en": {
        "just_now": "Just now",
        "h_ago": "h ago",
        "d_ago": "d ago",
        "victory": "Victory",
        "defeat": "Defeat",
        "blue_team": "Blue Team",
        "red_team": "Red Team",
        "kills": "Kills",
        "dragons": "Dragons",
        "towers": "Towers",
        "damage": "Damage",
        "vision": "Vision",
        "match_of": "Match of",
        "game": "Game",
        "months": ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    }
}

class MatchImageGenerator:
    def __init__(self):
        # Configuration de Jinja2
        template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')
        self.env = Environment(loader=FileSystemLoader(template_dir))
        self.env.cache = None # Désactiver le cache pour recharger le HTML à chaque appel
        
        # Configuration de Html2Image
        self.hti = Html2Image(output_path=tempfile.gettempdir())
        
    async def generate_match_scoreboard(self, match_data: dict, target_name: str, target_puuid: str = None, lang: str = "fr") -> str:
        """
        Génère une image du tableau des scores d'une partie.
        Retourne le chemin absolu vers l'image générée.
        """
        await ddragon.init()
        
        info = match_data.get("info", {})
        game_duration = info.get("gameDuration", 1) # en secondes
        if game_duration < 60: # Sometimes Riot API returns milliseconds if game ended early
            game_duration = game_duration * 1000
        game_duration_min = game_duration / 60
        
        # Préparation des équipes
        teams_data = {}
        for team in info.get("teams", []):
            teams_data[team["teamId"]] = {
                "teamId": team["teamId"],
                "win": team["win"],
                "objectives": team["objectives"],
                "total_kills": 0,
                "participants": []
            }
            
        # Calcul des stats globales par équipe et préparation des participants
        max_damage = 0
        for p in info.get("participants", []):
            team_id = p["teamId"]
            teams_data[team_id]["total_kills"] += p["kills"]
            if "max_damage" not in teams_data[team_id]:
                teams_data[team_id]["max_damage"] = 0
            if p["totalDamageDealtToChampions"] > teams_data[team_id]["max_damage"]:
                teams_data[team_id]["max_damage"] = p["totalDamageDealtToChampions"]
            if p["totalDamageDealtToChampions"] > max_damage:
                max_damage = p["totalDamageDealtToChampions"]
                
        # Formatage des participants
        for p in info.get("participants", []):
            team_id = p["teamId"]
            team_kills = max(1, teams_data[team_id]["total_kills"])
            kp = round(((p["kills"] + p["assists"]) / team_kills) * 100)
            
            cs = p["totalMinionsKilled"] + p["neutralMinionsKilled"]
            cs_min = round(cs / game_duration_min, 1) if game_duration_min > 0 else 0
            
            dmg_percent = round((p["totalDamageDealtToChampions"] / max_damage) * 100) if max_damage > 0 else 0
            is_max_damage = (p["totalDamageDealtToChampions"] == teams_data[team_id]["max_damage"]) and (p["totalDamageDealtToChampions"] > 0)
            
            items = [
                ddragon.get_item_url(p["item0"]),
                ddragon.get_item_url(p["item1"]),
                ddragon.get_item_url(p["item2"]),
                ddragon.get_item_url(p["item3"]),
                ddragon.get_item_url(p["item4"]),
                ddragon.get_item_url(p["item5"]),
                ddragon.get_item_url(p["item6"]) # trinket
            ]
            
            perks = p.get("perks", {}).get("styles", [])
            rune1 = perks[0]["selections"][0]["perk"] if len(perks) > 0 else 0
            rune2 = perks[1]["style"] if len(perks) > 1 else 0
            summoner_name = p["riotIdGameName"] if p.get("riotIdGameName") else p["summonerName"]
            tag_line = p.get("riotIdTagline", "")
            full_riot_id = f"{summoner_name}#{tag_line}" if tag_line else summoner_name
            
            if target_puuid and p.get("puuid"):
                is_target = p.get("puuid") == target_puuid
            else:
                target_lower = target_name.lower()
                is_target = target_lower == summoner_name.lower() or target_lower == full_riot_id.lower()
            
            # Format custom participant data
            participant_data = {
                "summonerName": summoner_name,
                "is_target": is_target,
                "championName": p["championName"],
                "champLevel": p["champLevel"],
                "champ_url": ddragon.get_champion_url(p["championName"]),
                "spell1_url": ddragon.get_spell_url(p["summoner1Id"]),
                "spell2_url": ddragon.get_spell_url(p["summoner2Id"]),
                "rune1_url": ddragon.get_rune_url(rune1),
                "rune2_url": ddragon.get_rune_url(rune2),
                "inventory": items,
                "kills": p["kills"],
                "deaths": p["deaths"],
                "assists": p["assists"],
                "kp": kp,
                "cs": cs,
                "cs_min": cs_min,
                "totalDamageDealtToChampions": f"{p['totalDamageDealtToChampions']:,}",
                "dmg_percent": dmg_percent,
                "is_max_damage": is_max_damage,
                "visionScore": p["visionScore"]
            }
            teams_data[team_id]["participants"].append(participant_data)
            
        teams_list = [teams_data[100], teams_data[200]] if 100 in teams_data and 200 in teams_data else list(teams_data.values())
        
        texts = LOCALES.get(lang, LOCALES["fr"])
        # Rendu HTML
        template = self.env.get_template('match.html')
        html_content = template.render(
            target_name=target_name,
            match_info=info,
            teams=teams_list,
            texts=texts
        )
        
        # Génération de l'image
        output_file = f"match_{info['gameId']}.png"
        self.hti.screenshot(html_str=html_content, save_as=output_file, size=(1065, 765))
        
        return os.path.join(tempfile.gettempdir(), output_file)

    async def generate_last_games_history(self, matches_data: list, target_name: str, target_puuid: str, lang: str = "fr") -> str:
        await ddragon.init()
        
        import datetime
        from collections import OrderedDict
        
        days_data = OrderedDict()
        
        for match_data in matches_data:
            info = match_data.get("info", {})
            
            # Find target player
            player_data = next((p for p in info.get("participants", []) if p.get("puuid") == target_puuid), None)
            if not player_data:
                continue
                
            game_end_ts = info.get("gameEndTimestamp", 0)
            if game_end_ts > 0:
                game_end_ts = game_end_ts / 1000
            else:
                game_end_ts = info.get("gameCreation", 0) / 1000
                
            dt = datetime.datetime.fromtimestamp(game_end_ts)
            texts = LOCALES.get(lang, LOCALES["fr"])
            day_str = f"{dt.day} {texts['months'][dt.month]}"
            
            now = datetime.datetime.now()
            diff = now - dt
            if diff.days > 0:
                time_ago = f"{diff.days}{texts['d_ago']}"
            else:
                hours = diff.seconds // 3600
                time_ago = f"{hours}{texts['h_ago']}" if hours > 0 else texts["just_now"]
                
            game_duration = info.get("gameDuration", 1)
            if game_duration < 60:
                game_duration = game_duration * 1000
            if game_duration > 10000:
                game_duration = game_duration / 1000
            
            m, s = divmod(int(game_duration), 60)
            duration_str = f"{m}:{s:02d}"
            
            win = player_data.get("win", False)
            kills = player_data.get("kills", 0)
            deaths = player_data.get("deaths", 0)
            assists = player_data.get("assists", 0)
            
            kda_ratio = round((kills + assists) / max(1, deaths), 1)
            
            team_id = player_data.get("teamId")
            team_kills = sum(p["kills"] for p in info.get("participants", []) if p.get("teamId") == team_id)
            enemy_kills = sum(p["kills"] for p in info.get("participants", []) if p.get("teamId") != team_id)
            kp = round(((kills + assists) / max(1, team_kills)) * 100)
            
            cs = player_data.get("totalMinionsKilled", 0) + player_data.get("neutralMinionsKilled", 0)
            cs_min = round(cs / (game_duration / 60), 1) if game_duration > 0 else 0
            
            items = [
                ddragon.get_item_url(player_data.get(f"item{i}", 0)) for i in range(7)
            ]
            
            perks = player_data.get("perks", {}).get("styles", [])
            rune1 = perks[0]["selections"][0]["perk"] if len(perks) > 0 else 0
            rune2 = perks[1]["style"] if len(perks) > 1 else 0
                
            opponent_url = None
            team_position = player_data.get("teamPosition")
            if team_position and team_position not in ["", "Invalid", "UTILITY"]:
                for p in info.get("participants", []):
                    if p.get("teamId") != player_data.get("teamId") and p.get("teamPosition") == team_position:
                        opponent_url = ddragon.get_champion_url(p.get("championName"))
                        break
            elif team_position == "UTILITY":
                for p in info.get("participants", []):
                    if p.get("teamId") != player_data.get("teamId") and p.get("teamPosition") == "UTILITY":
                        opponent_url = ddragon.get_champion_url(p.get("championName"))
                        break
            
            LANE_MAP = {
                "TOP": "Top",
                "JUNGLE": "Jungle",
                "MIDDLE": "Mid",
                "BOTTOM": "ADC",
                "UTILITY": "Support"
            }
            lane_str = LANE_MAP.get(team_position, team_position.capitalize() if team_position else "")
            
            LANE_ICON_MAP = {
                "TOP": "https://s-lol-web.op.gg/images/icon/icon-position-top.svg",
                "JUNGLE": "https://s-lol-web.op.gg/images/icon/icon-position-jungle.svg",
                "MIDDLE": "https://s-lol-web.op.gg/images/icon/icon-position-mid.svg",
                "BOTTOM": "https://s-lol-web.op.gg/images/icon/icon-position-adc.svg",
                "UTILITY": "https://s-lol-web.op.gg/images/icon/icon-position-support.svg"
            }
            lane_icon_url = LANE_ICON_MAP.get(team_position, "")
            
            match_dict = {
                "win": win,
                "victory_text": texts["victory"] if win else texts["defeat"],
                "team_kills": team_kills,
                "enemy_kills": enemy_kills,
                "duration": duration_str,
                "time_ago": time_ago,
                "game_mode": info.get("gameMode", texts["game"]).replace("CLASSIC", "Normal Draft").replace("ARAM", "ARAM"),
                "champion": player_data.get("championName"),
                "champ_url": ddragon.get_champion_url(player_data.get("championName")),
                "opponent_url": opponent_url,
                "lane": lane_str,
                "lane_icon_url": lane_icon_url,
                "level": player_data.get("champLevel", 1),
                "kills": kills,
                "deaths": deaths,
                "assists": assists,
                "kda_ratio": kda_ratio,
                "cs_min": cs_min,
                "kp": kp,
                "spell1": ddragon.get_spell_url(player_data.get("summoner1Id")),
                "spell2": ddragon.get_spell_url(player_data.get("summoner2Id")),
                "rune1": ddragon.get_rune_url(rune1),
                "rune2": ddragon.get_rune_url(rune2),
                "inventory": items
            }
            
            if day_str not in days_data:
                days_data[day_str] = {"matches": [], "wins": 0, "losses": 0}
                
            days_data[day_str]["matches"].append(match_dict)
            if win:
                days_data[day_str]["wins"] += 1
            else:
                days_data[day_str]["losses"] += 1
                
        template = self.env.get_template('last_games.html')
        html_content = template.render(
            target_name=target_name,
            days=days_data
        )
        
        # Calcul précis de la hauteur nécessaire
        # Body padding: 40px (20px haut, 20px bas)
        # Chaque jour: ~55px (titre 24px + marges et paddings + margin-bottom du groupe)
        # Chaque match: 98px (height 90px + margin-bottom 8px)
        calculated_height = 40 + (len(days_data) * 55) + (len(matches_data) * 98)
        
        output_file = f"last_games_{target_name}.png"
        self.hti.screenshot(html_str=html_content, save_as=output_file, size=(920, calculated_height))
        
        return os.path.join(tempfile.gettempdir(), output_file)
