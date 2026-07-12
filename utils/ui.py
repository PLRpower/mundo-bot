import discord
import datetime

def generate_match_select_options(matches: list, target_puuid: str, limit: int = 20) -> list[discord.SelectOption]:
    """
    Generate a list of discord.SelectOption for a list of matches.
    """
    options = []
    for match in matches[:limit]:
        info = match.get("info", {})
        game_id = str(info.get("gameId"))
        queue_id = info.get("queueId")
        queue_map = {
            400: "Draft",
            420: "Classée Solo",
            430: "Blind",
            440: "Classée Flex",
            450: "ARAM",
            490: "Quickplay",
            1700: "Arena"
        }
        game_mode = queue_map.get(queue_id, info.get("gameMode", "Custom"))
        
        player = next((p for p in info.get("participants", []) if p.get("puuid") == target_puuid), None)
        if not player:
            continue
            
        champion = player.get("championName", "Inconnu")
        win_str = "Victoire" if player.get("win") else "Défaite"
        kills = player.get("kills", 0)
        deaths = player.get("deaths", 0)
        assists = player.get("assists", 0)
        
        game_creation = info.get("gameCreation", 0)
        if game_creation > 1000000000000:
            game_creation = game_creation / 1000
        dt = datetime.datetime.fromtimestamp(game_creation).strftime("%d/%m/%y %H:%M")
        
        label = f"{champion} - {game_mode}"
        description = f"{win_str} | {kills}/{deaths}/{assists} | {dt}"
        emoji = "🟢" if player.get("win") else "🔴"
        
        options.append(discord.SelectOption(
            label=label[:100],
            description=description[:100],
            value=game_id,
            emoji=emoji
        ))
    return options
