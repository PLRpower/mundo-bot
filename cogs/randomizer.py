import discord
from discord.ext import commands
from discord import app_commands
import random
from utils.ddragon import ddragon

ROLES_CHAMPS = {
    "Top": ["Aatrox", "Camille", "ChoGath", "Darius", "DrMundo", "Fiora", "Garen", "Gnar", "Gragas", "Gwen", "Illaoi", "Irelia", "Jax", "Jayce", "KSante", "Kayle", "Kennen", "Kled", "Malphite", "Maokai", "Mordekaiser", "Nasus", "Olaf", "Ornn", "Pantheon", "Poppy", "Quinn", "Renekton", "Riven", "Rumble", "Sejuani", "Sett", "Shen", "Shyvana", "Singed", "Sion", "TahmKench", "Teemo", "Trundle", "Tryndamere", "Urgot", "Vayne", "Volibear", "Wukong", "Yasuo", "Yone", "Yorick"],
    "Jungle": ["Amumu", "Belveth", "Briar", "Diana", "Ekko", "Elise", "Evelynn", "Fiddlesticks", "Gragas", "Graves", "Hecarim", "Ivern", "JarvanIV", "Karthus", "Kayn", "KhaZix", "Kindred", "LeeSin", "Lillia", "MasterYi", "Nidalee", "Nocturne", "Nunu", "Rammus", "RekSai", "Rengar", "Sejuani", "Shaco", "Shyvana", "Skarner", "Taliyah", "Talon", "Udyr", "Vi", "Viego", "Volibear", "Warwick", "XinZhao", "Zac"],
    "Mid": ["Ahri", "Akali", "Akshan", "Anivia", "Annie", "AurelionSol", "Azir", "Cassiopeia", "Corki", "Diana", "Ekko", "Fizz", "Galio", "Hwei", "Irelia", "Kassadin", "Katarina", "LeBlanc", "Lissandra", "Lux", "Malzahar", "Naafiri", "Neeko", "Orianna", "Qiyana", "Ryze", "Smolder", "Sylas", "Syndra", "Talon", "TwistedFate", "Veigar", "Velkoz", "Vex", "Viktor", "Vladimir", "Xerath", "Yasuo", "Yone", "Zed", "Ziggs", "Zoe"],
    "ADC": ["Aphelios", "Ashe", "Caitlyn", "Draven", "Ezreal", "Jhin", "Jinx", "Kaisa", "Kalista", "KogMaw", "Lucian", "MissFortune", "Nilah", "Samira", "Sivir", "Smolder", "Tristana", "Twitch", "Varus", "Vayne", "Xayah", "Zeri"],
    "Support": ["Alistar", "Braum", "Bard", "Blitzcrank", "Karma", "Janna", "Leona", "Lulu", "Milio", "Morgana", "Nami", "Nautilus", "Pyke", "Rakan", "Rell", "Renata", "Senna", "Seraphine", "Sona", "Soraka", "Swain", "Taric", "Thresh", "Yuumi", "Zilean", "Zyra", "Brand", "Lux", "Velkoz", "Xerath", "Maokai", "Pantheon"]
}

class Randomizer(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.app_emojis_cache = {}

    async def get_emoji(self, safe_name: str) -> str:
        if not self.app_emojis_cache:
            try:
                emojis = await self.bot.fetch_application_emojis()
                self.app_emojis_cache = {e.name.lower(): f"<:{e.name}:{e.id}>" for e in emojis}
            except:
                pass
        return self.app_emojis_cache.get(safe_name.lower(), "")

    random_group = app_commands.Group(name="random", description="Générateur aléatoire (Compos, Champions, Builds)")

    @random_group.command(name="team", description="Génère une équipe complète aléatoire (5 champions)")
    async def random_team(self, interaction: discord.Interaction):
        await ddragon.init()
        team = {}
        used_champs = set()

        for r, champs in ROLES_CHAMPS.items():
            available = [c for c in champs if c not in used_champs]
            if not available:
                available = champs
            champ = random.choice(available)
            used_champs.add(champ)
            team[r] = champ

        embed = discord.Embed(title="🎲 Équipe Aléatoire", color=0x16161a)
        role_emojis = {"Top": "🛡️", "Jungle": "🌳", "Mid": "🧙‍♂️", "ADC": "🏹", "Support": "🏥"}
        
        for r, champ in team.items():
            safe_name = champ.replace(" ", "").replace("'", "").replace(".", "")
            champ_emoji = await self.get_emoji(safe_name)
            
            role_emoji = await self.get_emoji(f"role_{r.lower()}")
            if not role_emoji:
                role_emoji = role_emojis.get(r, "")
                
            embed.add_field(name=f"{role_emoji} {r}", value=f"{champ_emoji} **{champ}**", inline=False)
        
        await interaction.response.send_message(embed=embed)

    @random_group.command(name="champion", description="Génère un champion aléatoire pour un rôle donné")
    @app_commands.describe(role="Le rôle pour lequel générer un champion")
    @app_commands.choices(role=[
        app_commands.Choice(name="Top", value="Top"),
        app_commands.Choice(name="Jungle", value="Jungle"),
        app_commands.Choice(name="Mid", value="Mid"),
        app_commands.Choice(name="ADC", value="ADC"),
        app_commands.Choice(name="Support", value="Support")
    ])
    async def random_champion(self, interaction: discord.Interaction, role: app_commands.Choice[str]):
        await ddragon.init()
        champs = ROLES_CHAMPS.get(role.value, [])
        if not champs:
            await interaction.response.send_message("❌ Rôle invalide.")
            return

        champ = random.choice(champs)
        safe_name = champ.replace(" ", "").replace("'", "").replace(".", "")
        champ_emoji = await self.get_emoji(safe_name)
        
        role_emoji = await self.get_emoji(f"role_{role.name.lower()}")
        if not role_emoji:
            role_emojis = {"Top": "🛡️", "Jungle": "🌳", "Mid": "🧙‍♂️", "ADC": "🏹", "Support": "🏥"}
            role_emoji = role_emojis.get(role.name, "")
            
        embed = discord.Embed(title=f"🎲 Champion Aléatoire - {role_emoji} {role.name}", description=f"Ton champion est {champ_emoji} **{champ}** !", color=0x16161a)
        embed.set_thumbnail(url=ddragon.get_champion_url(champ))
        await interaction.response.send_message(embed=embed)

    @random_group.command(name="build", description="Génère un build complet et des runes aléatoires")
    @app_commands.describe(champion="Nom du champion (laisser vide pour un champion 100% aléatoire)")
    async def random_build(self, interaction: discord.Interaction, champion: str = None):
        await ddragon.init()
        if not champion:
            all_champs = list(ddragon.champions.values())
            champion = random.choice(all_champs)
            
        boots = []
        legendaries = []
        
        for item_id, item_data in ddragon.items.items():
            if not item_data.get("maps", {}).get("11", False): continue
            if not item_data.get("gold", {}).get("purchasable", False): continue
            if "into" in item_data and len(item_data["into"]) > 0: continue
            if "Consumable" in item_data.get("tags", []): continue
            if "Trinket" in item_data.get("tags", []): continue
            if "Jungle" in item_data.get("tags", []): continue
            
            if "Boots" in item_data.get("tags", []):
                boots.append(item_data["name"])
            else:
                if item_data.get("gold", {}).get("total", 0) < 1500: continue
                legendaries.append(item_data["name"])

        selected_boot = random.choice(boots) if boots else "Bottes"
        selected_items = random.sample(legendaries, min(5, len(legendaries)))
        full_build = [selected_boot] + selected_items
        
        build_str_parts = []
        for item in full_build:
            safe_item = "item_" + "".join(c for c in item if c.isalnum())
            item_emoji = await self.get_emoji(safe_item)
            build_str_parts.append(f"• {item_emoji} {item}")
        
        trees = ddragon.rune_trees
        if len(trees) >= 2:
            primary_tree, secondary_tree = random.sample(trees, 2)
            
            primary_runes = []
            for slot in primary_tree["slots"]:
                if slot["runes"]:
                    r_name = random.choice(slot["runes"])["name"]
                    safe_r = "rune_" + "".join(c for c in r_name if c.isalnum())
                    r_emoji = await self.get_emoji(safe_r)
                    primary_runes.append(f"{r_emoji} {r_name}")
                    
            secondary_slots = secondary_tree["slots"][1:]
            selected_secondary_slots = random.sample(secondary_slots, 2)
            secondary_runes = []
            for slot in selected_secondary_slots:
                if slot["runes"]:
                    r_name = random.choice(slot["runes"])["name"]
                    safe_r = "rune_" + "".join(c for c in r_name if c.isalnum())
                    r_emoji = await self.get_emoji(safe_r)
                    secondary_runes.append(f"{r_emoji} {r_name}")
        else:
            primary_tree = {"name": "Inconnu"}
            secondary_tree = {"name": "Inconnu"}
            primary_runes = ["?"] * 4
            secondary_runes = ["?"] * 2

        safe_champ = champion.replace(" ", "").replace("'", "").replace(".", "")
        champ_emoji = await self.get_emoji(safe_champ)
        embed = discord.Embed(title=f"🎲 Build Aléatoire pour {champ_emoji} {champion}", color=0x16161a)
        
        build_str = "\n".join(build_str_parts)
        embed.add_field(name="🎒 Objets", value=build_str, inline=False)
        
        safe_ptree = "rune_" + "".join(c for c in primary_tree["name"] if c.isalnum())
        ptree_emoji = await self.get_emoji(safe_ptree)
        
        safe_stree = "rune_" + "".join(c for c in secondary_tree["name"] if c.isalnum())
        stree_emoji = await self.get_emoji(safe_stree)
        
        primary_str = "\n".join([f"• {r}" for r in primary_runes])
        embed.add_field(name=f"{ptree_emoji} Principal : {primary_tree['name']}", value=primary_str, inline=True)
        
        secondary_str = "\n".join([f"• {r}" for r in secondary_runes])
        embed.add_field(name=f"{stree_emoji} Secondaire : {secondary_tree['name']}", value=secondary_str, inline=True)
        
        try:
            embed.set_thumbnail(url=ddragon.get_champion_url(champion))
        except:
            pass

        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Randomizer(bot))
